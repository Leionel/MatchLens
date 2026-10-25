"""Independent score verification from recorded events.

The provider index score is a declaration; the event stream is the evidence.
This module derives the score from the events and reports both sides instead of
merging them. A shoot-out is reported separately and never added to the
regulation/extra-time score.
"""
from __future__ import annotations

from typing import Any, Sequence

from .completeness import PENALTY_SHOOTOUT_PERIOD


def _period(event: Any) -> int:
    value = getattr(event, "period", None)
    if value is None and isinstance(event, dict):
        value = event.get("period", 1)
    return int(value or 1)


def _team(event: Any) -> str:
    value = getattr(event, "team_id", None)
    if value is None and isinstance(event, dict):
        value = event.get("team", "")
    return str(value or "")


def _outcome(event: Any) -> str:
    value = getattr(event, "outcome", None)
    if value is None and isinstance(event, dict):
        value = event.get("outcome")
    return str(value or "").lower()


def _event_id(event: Any) -> str:
    value = getattr(event, "event_id", None)
    if value is None and isinstance(event, dict):
        value = event.get("id") or event.get("event_id")
    return str(value or "")


def verify_score(events: Sequence[Any], meta: Any) -> dict[str, Any]:
    recorded = {"H": 0, "N": 0}
    shootout = {"H": 0, "N": 0}
    evidence: list[str] = []
    seen_own_goals: set[tuple[int, float, str]] = set()

    for event in events:
        period = _period(event)
        team = _team(event)
        outcome = _outcome(event)
        if team not in ("H", "N"):
            continue
        t = float(getattr(event, "clock_seconds", 0.0) or 0.0)
        if outcome in ("own_goal", "own_goal_for"):
            credited = team if outcome == "own_goal_for" else ("N" if team == "H" else "H")
            key = (period, round(t, 3), credited)
            if key in seen_own_goals:
                continue
            seen_own_goals.add(key)
            if period >= PENALTY_SHOOTOUT_PERIOD:
                shootout[credited] += 1
            else:
                recorded[credited] += 1
                evidence.append(_event_id(event))
        elif outcome == "goal":
            if period >= PENALTY_SHOOTOUT_PERIOD:
                shootout[team] += 1
            else:
                recorded[team] += 1
                evidence.append(_event_id(event))

    provider_home = getattr(meta, "home_score", None)
    provider_away = getattr(meta, "away_score", None)
    has_provider = provider_home is not None and provider_away is not None
    consistent = has_provider and recorded["H"] == int(provider_home) and recorded["N"] == int(provider_away)
    if not has_provider:
        status = "not_available"
    elif consistent:
        status = "verified"
    else:
        status = "mismatch"

    return {
        "match_id": getattr(meta, "match_id", None),
        "status": status,
        "recorded": recorded,
        "provider_declared": (
            {"H": int(provider_home), "N": int(provider_away)} if has_provider else None
        ),
        "shootout": shootout,
        "consistent": bool(consistent),
        "basis": "recorded_events",
        "score_basis": "regulation_and_extra_time; shootout_excluded",
        "goal_event_ids": sorted(set(evidence)),
        "note": (
            "The provider index score and the score derived from the event stream agree."
            if consistent
            else "The provider index score and the event-recorded goals disagree; both are reported."
            if has_provider
            else "No provider index score is declared for this match."
        ),
    }
