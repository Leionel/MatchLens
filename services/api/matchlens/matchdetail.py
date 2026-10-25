"""Complete Match Detail assembly (Slice C-4).

One read-only payload that gives the Match Hub detail view its sections:
overview, lineups, shots, per-team registry stats, tactics summary and an
events summary. Everything re-uses existing builders and the registry metric
formulas — this module only composes; it defines no new metric.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from .contracts import Snapshot
from .exploration import analyze_action_density_differential, analyze_attacking_channels
from .football import build_sequences
from .score import verify_score


def _lineups(
    events: list[Any], home_name: str, away_name: str, observed_end: float
) -> dict[str, Any]:
    """Starter/substitute structure per team from provider lineup records.

    A player whose first record is a Starting XI row (or is flagged starter)
    is a starter; every other player observed in the match is listed as a
    substitute without inventing an entry minute (substitution events carry
    it when the provider recorded them).
    """
    from .profiles import compute_player_minutes

    starters: dict[str, dict[str, list]] = {"H": [], "N": []}
    starter_ids: dict[str, set[str]] = {"H": set(), "N": set()}
    seen: dict[str, dict[str, dict]] = {"H": {}, "N": {}}

    for e in events:
        if not e.player_id:
            continue
        team = e.team_id
        if team not in ("H", "N"):
            continue
        if str(e.player_id) not in seen[team]:
            minutes = compute_player_minutes(events, str(e.player_id), observed_end)
            seen[team][str(e.player_id)] = {
                "player_id": str(e.player_id),
                "player_name": e.player_name,
                "jersey_number": e.jersey_number,
                "position": e.position,
                "position_role": e.position_role,
                "minutes_seconds": minutes["seconds"],
                "minutes_method": minutes["method"],
            }
        if e.lineup_role == "starter":
            starter_ids[team].add(str(e.player_id))

    for team in ("H", "N"):
        rows = [seen[team][pid] for pid in starter_ids[team] if pid in seen[team]]
        rows.sort(key=lambda r: (r.get("position") or "", r.get("player_name") or ""))
        starters[team] = rows

    subs: dict[str, list] = {"H": [], "N": []}
    for team in ("H", "N"):
        for pid, row in seen[team].items():
            if pid in starter_ids[team]:
                continue
            subs[team].append(row)
        subs[team].sort(key=lambda r: r.get("player_name") or "")

    return {
        "home_team": home_name,
        "away_team": away_name,
        "starters": {
            "H": starters["H"],
            "N": starters["N"],
            "home_team_name": home_name,
            "away_team_name": away_name,
        },
        "substitutes": {"H": subs["H"], "N": subs["N"]},
        "note": (
            "Starter/substitute split follows the provider's lineup records. "
            "Players without any record are absent, not unknown."
        ),
    }


def _shots(events: list[Any]) -> dict[str, Any]:
    """Located shot records with the heuristic pre-shot danger figure."""
    from .models.xg import compute_pre_shot_xg

    rows: list[dict[str, Any]] = []
    for e in events:
        if e.action_type != "Shot" and getattr(e.action_type, "value", None) != "Shot":
            continue
        if e.is_shootout:
            continue
        ax = e.x if e.attack_direction == "left_to_right" else (105.0 - e.x if e.x is not None else None)
        evaluation = None
        if ax is not None and e.y is not None:
            evaluation = compute_pre_shot_xg(x=ax, y=e.y)
        rows.append({
            "event_id": e.event_id,
            "team": e.team_id,
            "player_id": e.player_id,
            "player_name": e.player_name,
            "minute": round(float(e.clock_seconds) / 60.0, 1) if e.clock_seconds is not None else None,
            "t": round(float(e.clock_seconds), 1) if e.clock_seconds is not None else None,
            "period": e.period,
            "period_label": e.period_label,
            "outcome": e.outcome,
            "is_own_goal": bool(e.is_own_goal),
            "x": e.x,
            "y": e.y,
            "pre_shot_xg_heuristic": round(evaluation.pre_shot_xg, 4) if evaluation is not None else None,
            "play_pattern": e.play_pattern,
        })
    rows.sort(key=lambda r: (r["minute"] if r["minute"] is not None else 1e9))
    return {
        "shots": rows,
        "count": len(rows),
        "note": (
            "pre_shot_xg_heuristic is the uncalibrated geometric model (distance + visible angle, "
            "outcome-free), not a calibrated xG."
        ),
    }


def _stats(snap: Snapshot, state: dict) -> dict[str, Any]:
    """Both teams' registry observations for the full frozen prefix."""
    from .metrics import MetricsService
    from .profiles import _match_window_metrics

    as_of = float(snap.data.get("as_of", 0))
    out: dict[str, Any] = {"as_of": as_of, "teams": {}}
    for side in ("H", "N"):
        values = _match_window_metrics(snap, state, ("possession", "shots", "entries", "high_recoveries", "goals", "passes", "carries", "box_entries", "progressive_passes"), side, str(snap.data.get("match_id", "")))
        out["teams"][side] = {
            mid: {"value": mv.value, "status": mv.status, "unit": mv.unit}
            for mid, mv in values.items()
        }
    return out


def _tactics(state: dict, coordinate_frame: str) -> dict[str, Any]:
    channels = {
        team: analyze_attacking_channels(state["events"], team=team, coordinate_frame=coordinate_frame)
        for team in ("H", "N")
    }
    density = analyze_action_density_differential(state["events"])
    sequences = build_sequences(state)
    top_zones = sorted(density.get("zones", []), key=lambda z: -abs(z.get("delta_density", 0.0)))[:4]
    return {
        "attacking_channels": channels,
        "density_top_zones": [
            {k: z.get(k) for k in ("cell_id", "name", "home_actions_count", "away_actions_count", "delta_density", "advantage")}
            for z in top_zones
        ],
        "sequence_count": len(sequences),
        "full_sequences_endpoint": "/api/matches/{match_id}/exploration",
    }


def _events_summary(events: list[Any]) -> dict[str, Any]:
    counts = Counter(e.action_type.value if hasattr(e.action_type, "value") else str(e.action_type) for e in events)
    return {
        "total": len(events),
        "by_action_type": dict(counts.most_common()),
        "public_events_endpoint": "/api/matches/{match_id}/events",
        "raw_event_export": "producer_or_internal_data_access_required",
    }


def build_match_detail(
    eng: Any,
    match_id: str,
    resolve_snapshot,
    *,
    owner_session_id: str | None = None,
    include_all_investigations: bool = False,
) -> dict[str, Any]:
    """Assemble the complete Match Detail payload for one match.

    `resolve_snapshot(eng, match_id, ctx)` is the main module's cached freeze
    helper, injected to avoid a circular import.
    """
    from .catalog import MatchCatalog

    meta = MatchCatalog.get_match(match_id)
    if meta is None:
        raise FileNotFoundError(f"Match not found: {match_id}")
    ctx = MatchCatalog.get_match_context(match_id)
    snap, state = resolve_snapshot(eng, match_id, ctx)
    events = MatchCatalog.load_normalized_events(match_id)

    # A match detail page is a public analytics projection; private drafts are
    # only included for their owning session (or an explicit producer role).
    investigations = eng.investigations.list_for(
        owner_session_id=owner_session_id,
        allow_all=include_all_investigations,
        match_id=match_id,
        limit=10,
    )
    return {
        "match_id": match_id,
        "overview": {
            "metadata": meta.model_dump(),
            "context": {
                "competition": ctx.competition,
                "season": ctx.season,
                "label": ctx.label,
                "duration": ctx.duration,
                "nominal_duration": ctx.nominal_duration,
                "observed_end": ctx.observed_end,
                "replayable_end": ctx.replayable_end,
                "stoppage_time": ctx.stoppage_time,
                "as_of": ctx.as_of,
                "periods": ctx.periods,
                "shootout_clock": ctx.shootout_clock,
                "clock_version": ctx.clock_version,
                "period": ctx.period,
                "continuous_coverage": ctx.continuous_coverage,
                "completeness_status": ctx.completeness_status,
                "dataset_revision": ctx.dataset_revision or ctx.data_version,
                "partial_notice": ctx.partial_notice,
                "provenance_kind": meta.provenance_kind,
            },
        },
        "score_verification": verify_score(events, meta),
        "lineups": _lineups(events, ctx.home_team_name, ctx.away_team_name, float(ctx.observed_end)),
        "shots": _shots(events),
        "stats": _stats(snap, state),
        "tactics": _tactics(state, ctx.coordinate_frame),
        "events_summary": _events_summary(events),
        "ai_insights": {
            "saved_investigations": [
                {
                    "investigation_id": p.investigation_id,
                    "state": p.state,
                    "focus_type": p.focus_type,
                    "focus_id": p.focus_id,
                    "question": p.question,
                    "gate_status": p.gate_preview.status,
                }
                for p in investigations
            ],
            "story_endpoint": f"/api/matches/{match_id}/story?mode=recap",
            "note": (
                "AI insights are investigation records and the story engine; "
                "both remain evidence-bound and gate-checked."
            ),
        },
    }
