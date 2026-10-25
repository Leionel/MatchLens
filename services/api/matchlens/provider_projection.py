"""Provider publication boundary.

StatsBomb Open Data is licensed for published *analysis* with attribution, not
for redistribution of the event payload. The public product therefore exposes:

* aggregate metrics, sequences, charts and evidence references;
* a bounded window of the live replay for visualisation;
* a bounded structural sample for traceability.

The complete machine-readable event stream is internal/protected event access:
it requires the independently verified producer/admin token. Bounded public
windows are not pagination: asking for a different ``limit`` or ``offset`` never
returns a different slice of the match.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

from .provider_terms import STATSBOMB_ATTRIBUTION_TEXT, STATSBOMB_LICENSE_REF

PROTECTED_PROVENANCE = "provider_payload"
PUBLIC_STATE_WINDOW_SECONDS = 180
PUBLIC_STATE_MAX_EVENTS = 160
PUBLIC_EVENT_SAMPLE_LIMIT = 24


def is_protected_provider(provenance_kind: str | None) -> bool:
    return provenance_kind == PROTECTED_PROVENANCE


def publication_notice(*, match_id: str, tier: str) -> dict[str, Any]:
    return {
        "access_tier": tier,
        "match_id": match_id,
        "license_ref": STATSBOMB_LICENSE_REF,
        "attribution_text": STATSBOMB_ATTRIBUTION_TEXT,
        "raw_event_export": "requires_producer_data_access",
        "policy": (
            "Public responses carry aggregate analysis, visualisation windows and bounded "
            "evidence summaries. The complete provider event payload is not downloadable "
            "anonymously and cannot be reassembled through pagination or limit parameters."
        ),
    }


def _event_time(event: dict) -> float:
    try:
        return float(event.get("t", event.get("clock_seconds", 0.0)) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def bounded_state_events(
    events: Sequence[dict],
    *,
    at: float,
    window_seconds: float = PUBLIC_STATE_WINDOW_SECONDS,
    max_events: int = PUBLIC_STATE_MAX_EVENTS,
    total_events: int | None = None,
) -> tuple[list[dict], dict[str, Any]]:
    """The replay window carried in public state.

    Newest events are kept; when a dense window exceeds the cap, structural
    events (shots, goals, recoveries, period ends) are prioritised and the
    truncation is stated, never hidden.
    """
    start = max(0.0, float(at) - max(1.0, window_seconds))
    window = [event for event in events if start <= _event_time(event) <= float(at)]
    structural = [
        event for event in window
        if str(event.get("kind") or event.get("action_type") or "").lower()
        in ("shot", "goal", "recovery", "period_end", "own_goal")
    ]
    if len(window) <= max_events:
        selected = window
        truncated = 0
    else:
        keep = {id(event) for event in structural[-max_events // 2:]}
        remaining = [event for event in window if id(event) not in keep]
        tail = remaining[-(max_events - len(keep)):] if max_events > len(keep) else []
        selected = sorted([*structural[-max_events // 2:], *tail], key=_event_time)
        selected = selected[-max_events:]
        truncated = len(window) - len(selected)
    meta = {
        "start": start,
        "end": float(at),
        "window_seconds": window_seconds,
        "events_in_window": len(window),
        "events_returned": len(selected),
        "events_truncated": truncated,
        "total_events_observed": int(total_events if total_events is not None else len(events)),
    }
    return selected, meta


def public_event_summary(
    events: Sequence[dict],
    *,
    match_id: str,
) -> dict[str, Any]:
    """Aggregate + bounded structural evidence sample, never the full stream."""
    from collections import Counter

    by_period: Counter[str] = Counter()
    by_action: Counter[str] = Counter()
    by_team: Counter[str] = Counter()
    for event in events:
        by_period[str(event.get("period", "?"))] += 1
        by_action[str(event.get("kind") or event.get("action_type") or "other")] += 1
        by_team[str(event.get("team") or "?")] += 1

    structural = [
        event for event in events
        if str(event.get("kind") or event.get("action_type") or "").lower()
        in ("shot", "own_goal", "period_end", "recovery")
    ]
    # One bounded sample, chosen by match structure rather than by an offset a
    # caller can walk through.
    sample = structural[:PUBLIC_EVENT_SAMPLE_LIMIT]
    if not sample:
        sample = list(events[:PUBLIC_EVENT_SAMPLE_LIMIT])
    return {
        "match_id": match_id,
        "count": len(events),
        "by_period": dict(sorted(by_period.items(), key=lambda item: item[0])),
        "by_action_type": dict(by_action.most_common()),
        "by_team": dict(by_team),
        "sample": [
            {
                "event_id": event.get("id") or event.get("event_id"),
                "period": event.get("period"),
                "t": event.get("t", event.get("clock_seconds")),
                "team": event.get("team"),
                "action_type": event.get("kind") or event.get("action_type"),
                "outcome": event.get("outcome"),
                "player_name": event.get("actor_name") or event.get("actor"),
            }
            for event in sample
        ],
        "sample_limit": PUBLIC_EVENT_SAMPLE_LIMIT,
        "sample_rule": "first structural events (shots, own goals, period ends, recoveries)",
        **publication_notice(match_id=match_id, tier="public_analysis_projection"),
    }


def strip_sequence_event_detail(
    sequences: Iterable[dict],
    *,
    at: float,
    window_seconds: float = PUBLIC_STATE_WINDOW_SECONDS,
) -> list[dict]:
    """Remove full per-event coordinates from public sequence projections.

    Sequence aggregates and event references remain available for
    traceability; only a recent sequence may carry compact step labels, and
    those steps never include pitch coordinates.
    """
    out: list[dict] = []
    for sequence in sequences:
        row = dict(sequence)
        detail = row.get("events_detail") or []
        recent = _event_time({"t": row.get("end_t", 0)}) >= max(0.0, float(at) - window_seconds)
        if detail and recent:
            row["events_detail"] = [
                {
                    "seq_step": step.get("seq_step"),
                    "id": step.get("id"),
                    "kind": step.get("kind"),
                    "team": step.get("team"),
                    "actor": step.get("actor"),
                    "actor_name": step.get("actor_name"),
                    "receiver": step.get("receiver"),
                    "receiver_name": step.get("receiver_name"),
                    "outcome": step.get("outcome"),
                    "t": step.get("t"),
                    "gain_m": step.get("gain_m"),
                    "channel": step.get("channel"),
                }
                for step in detail
            ]
        else:
            row.pop("events_detail", None)
        out.append(row)
    return out
