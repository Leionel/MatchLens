"""Observed Attacking Activity Index (OAAI) Engine (BL-02).

Implements the three-layer architecture specified in Section 2.2.2 & 7.1 of
docs/FOOTBALL_INTELLIGENCE_PLATFORMS_2026.md:
- Layer A: Event Contribution Layer (xT, xG, progression, recovery, turnover weights)
- Layer B: Causal Time Aggregation Layer (exponential decay kernel, strictly causal t_k <= t)
- Layer C: Visualization Smoothing Layer (single-sided causal vs bilateral post-match)
- Change-point Detection & Level 2 Metric Attribution (top contributing events in preceding causal window)

Non-causal interpretation boundary:
OAAI measures recorded attacking activity intensity, NOT psychological momentum or true tactical causality.
"""
from __future__ import annotations

import math
from typing import Any, Literal, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

from .schema import ActionType, DerivedMetric, NormalizedEvent


class OAAIConfig(BaseModel):
    """Versioned configuration parameters for OAAI calculations."""
    model_config = ConfigDict(extra="forbid")

    version: str = "1.0.0"
    # Layer A: Event Contribution Weights
    shot_base_weight: float = 0.35
    goal_bonus_weight: float = 0.90
    xg_factor: float = 1.00
    progression_meter_weight: float = 0.015
    final_third_entry_bonus: float = 0.20
    penalty_box_entry_bonus: float = 0.35
    recovery_base_weight: float = 0.18
    high_recovery_bonus: float = 0.28  # Recovery in attacking third (ax >= 70)
    turnover_penalty_weight: float = 0.22  # Negative attribution for losing ball
    xt_factor: float = 1.20  # Multiplier when delta_xT is available

    # Layer B: Time Aggregation
    half_life_seconds: float = 30.0  # Time for event contribution to decay by half
    sample_step_seconds: float = 2.0  # Sampling interval on time grid
    freeze_dead_time: bool = True     # Freeze decay during stoppages/dead time

    # Layer C: Visualization Smoothing
    causal_window_samples: int = 3    # Single-sided moving average window (past only)
    bilateral_window_samples: int = 5  # Two-sided symmetric window for post-match

    # Change-point detection
    inflection_threshold: float = 0.30  # Minimum amplitude to register a change-point
    attribution_window_seconds: float = 45.0  # Lookback window for top-contributor extraction
    top_contributors_limit: int = 4


def _infer_home_team(norm_events: Sequence[dict]) -> str:
    """Infers the reference home team ID from events."""
    for e in norm_events:
        tid = str(e.get("team_id", e.get("team", "")))
        if tid == "H" or tid.lower() == "home":
            return tid
    if norm_events:
        return str(norm_events[0].get("team_id", norm_events[0].get("team", "H")))
    return "H"


def _normalize_event_view(ev: Any, home_team: Optional[str] = None) -> dict:
    """Normalize synthetic Event, dict or NormalizedEvent into uniform record."""
    if isinstance(ev, NormalizedEvent):
        # Determine team code without falsely treating all left_to_right events as Home
        if ev.team_id in ("H", "N"):
            team_code = ev.team_id
        elif home_team:
            team_code = "H" if ev.team_id == home_team else "N"
        elif "home" in ev.team_id.lower():
            team_code = "H"
        elif "away" in ev.team_id.lower():
            team_code = "N"
        else:
            team_code = ev.team_id

        start_x = ev.x if ev.x is not None else 52.5
        start_y = ev.y if ev.y is not None else 34.0
        end_x = ev.end_x if ev.end_x is not None else start_x
        end_y = ev.end_y if ev.end_y is not None else start_y
        kind_str = ev.action_type.value.lower()
        if "pass" in kind_str:
            kind = "pass"
        elif "shot" in kind_str:
            kind = "shot"
        elif "recovery" in kind_str or "interception" in kind_str or "tackle" in kind_str:
            kind = "recovery"
        elif "dispossessed" in kind_str or "clearance" in kind_str or "foul" in kind_str:
            kind = "turnover"
        else:
            kind = "other"

        return {
            "id": ev.event_id,
            "t": float(ev.clock_seconds),
            "team": team_code,
            "team_id": ev.team_id,
            "kind": kind,
            "actor": ev.player_name or ev.player_id or "Unknown",
            "start": (start_x, start_y),
            "end": (end_x, end_y),
            "outcome": ev.outcome or "complete",
            "raw": ev,
        }

    # Dict or synthetic Event
    if isinstance(ev, dict):
        d = ev
    else:
        d = ev.model_dump() if hasattr(ev, "model_dump") else ev.__dict__

    t_val = float(d.get("t", d.get("clock_seconds", 0.0)))
    team = d.get("team", d.get("team_id", "H"))
    start = d.get("start", (d.get("x", 52.5), d.get("y", 34.0)))
    end = d.get("end", (d.get("end_x", start[0]), d.get("end_y", start[1])))

    return {
        "id": d.get("id", d.get("event_id", "EV")),
        "t": t_val,
        "team": team,
        "team_id": str(d.get("team_id", team)),
        "kind": d.get("kind", d.get("action_type", "pass")),
        "actor": d.get("actor", d.get("player_name", "Player")),
        "start": (float(start[0]), float(start[1])),
        "end": (float(end[0]), float(end[1])),
        "outcome": d.get("outcome", "complete"),
        "raw": ev,
    }


def _attack_x(team: str, x: float) -> float:
    """Longitudinal coordinate relative to attacking direction (0 to 105m)."""
    return x if team in ("H", "home") else 105.0 - x


def _is_in_penalty_box(team: str, x: float, y: float) -> bool:
    """Checks whether (x, y) is inside the attacking penalty area."""
    ax = _attack_x(team, x)
    return ax >= 88.5 and 13.84 <= y <= 54.16


# ==============================================================================
# Layer A: Event Contribution Layer
# ==============================================================================

def compute_event_contribution(
    event: Any,
    config: Optional[OAAIConfig] = None,
    xt_model: Any = None,
    home_team: Optional[str] = None,
) -> tuple[float, float, str]:
    """Computes signed and team-specific attacking contribution of a single event.

    Returns:
        (signed_contribution, raw_magnitude, explanation)
        signed_contribution: Positive for Home team, Negative for Away team.
    """
    cfg = config or OAAIConfig()
    ev = _normalize_event_view(event, home_team=home_team)
    team = ev["team"]
    team_id = ev.get("team_id", team)
    kind = ev["kind"]
    outcome = ev["outcome"]
    start_x, start_y = ev["start"]
    end_x, end_y = ev["end"]

    ax_start = _attack_x(team, start_x)
    ax_end = _attack_x(team, end_x)
    progression_m = max(0.0, ax_end - ax_start)

    magnitude = 0.0
    explanation = f"{kind.capitalize()}"

    if kind == "shot":
        # Base shot weight + goal outcome bonus
        is_goal = outcome == "goal"
        base = cfg.shot_base_weight
        # Approximate geometric xG based on goal proximity & angle if no explicit xG
        dist_to_goal = math.sqrt((105.0 - ax_start) ** 2 + (34.0 - start_y) ** 2)
        approx_xg = max(0.04, min(0.85, math.exp(-dist_to_goal / 14.0)))
        magnitude = base + (approx_xg * cfg.xg_factor) + (cfg.goal_bonus_weight if is_goal else 0.0)
        explanation = f"Goal ({magnitude:.2f})" if is_goal else f"Shot attempt ({magnitude:.2f})"

    elif kind == "pass":
        # Check if xT model can be evaluated
        if xt_model is not None:
            try:
                # If event is NormalizedEvent or can be evaluated by xt_model
                norm_ev = ev["raw"] if isinstance(ev["raw"], NormalizedEvent) else None
                if norm_ev is not None:
                    xt_metric = xt_model.evaluate_progression(norm_ev)
                    if xt_metric.value is not None:
                        magnitude += max(0.0, xt_metric.value) * cfg.xt_factor
                else:
                    v_start = xt_model.value_at(start_x, start_y)
                    v_end = xt_model.value_at(end_x, end_y)
                    delta_xt = max(0.0, v_end - v_start)
                    magnitude += delta_xt * cfg.xt_factor
            except Exception:
                magnitude += progression_m * cfg.progression_meter_weight
        else:
            magnitude += progression_m * cfg.progression_meter_weight

        # Tactical territory bonuses
        if ax_start <= 70.0 < ax_end:
            magnitude += cfg.final_third_entry_bonus
            explanation = f"Final third entry pass (+{progression_m:.1f}m)"
        elif _is_in_penalty_box(team, end_x, end_y):
            magnitude += cfg.penalty_box_entry_bonus
            explanation = f"Penalty box pass (+{progression_m:.1f}m)"
        else:
            explanation = f"Progression pass (+{progression_m:.1f}m)"

    elif kind == "recovery":
        is_high = ax_start >= 70.0
        magnitude = cfg.recovery_base_weight + (cfg.high_recovery_bonus if is_high else 0.0)
        explanation = "High attacking recovery" if is_high else "Ball recovery"

    elif kind == "turnover":
        # Turnover penalizes the team that lost possession
        magnitude = -cfg.turnover_penalty_weight
        explanation = "Possession turnover"

    else:
        # Default minor activity
        magnitude = 0.02
        explanation = "In-play sequence action"

    # Signed contribution: Home gets +magnitude, Away gets -magnitude
    is_home = (team == "H" or team == home_team or (home_team and team_id == home_team))
    signed_val = magnitude if is_home else -magnitude
    return round(signed_val, 5), round(abs(magnitude), 5), explanation


# ==============================================================================
# Layer B: Causal Time Aggregation Layer
# ==============================================================================

def aggregate_oaai_timeline(
    events: Sequence[Any],
    config: Optional[OAAIConfig] = None,
    t_end: Optional[float] = None,
    dead_intervals: Optional[list[dict]] = None,
    xt_model: Any = None,
    home_team: Optional[str] = None,
) -> list[dict]:
    """Aggregates event contributions over time using STRICT CAUSAL FILTERING.

    At any sample time t, the value OAAI(t) depends strictly on events where t_k <= t.
    Events with t_k > t are never read or processed.

    Decay kernel: K(delta_t) = exp(-lambda * delta_t), where lambda = ln(2) / half_life.
    """
    cfg = config or OAAIConfig()
    initial_views = [_normalize_event_view(e) for e in events]
    inferred_home = home_team or _infer_home_team(initial_views)
    norm_events = [_normalize_event_view(e, home_team=inferred_home) for e in events]
    # Sort chronologically by timestamp
    norm_events.sort(key=lambda e: (e["t"], e["id"]))

    if not norm_events:
        return []

    max_t = t_end if t_end is not None else max(e["t"] for e in norm_events)
    decay_lambda = math.log(2) / cfg.half_life_seconds

    # Precompute Layer A contributions for all events
    contributions = []
    for e in norm_events:
        signed_c, mag, expl = compute_event_contribution(e, cfg, xt_model=xt_model, home_team=inferred_home)
        contributions.append({
            "event": e,
            "t": e["t"],
            "team": e["team"],
            "team_id": e.get("team_id", e["team"]),
            "is_home": (e["team"] == "H" or e.get("team_id") == inferred_home),
            "signed_c": signed_c,
            "mag": mag,
            "expl": expl,
        })

    # Sample time grid
    step = cfg.sample_step_seconds
    total_steps = int(math.floor(max_t / step)) + 1
    timeline: list[dict] = []

    # Causal index pointer: pointer to the first event with t_k > t
    event_ptr = 0
    n_events = len(contributions)

    for step_idx in range(total_steps):
        t = round(step_idx * step, 2)

        # Advance pointer to include ONLY events with t_k <= t (Causal boundary)
        while event_ptr < n_events and contributions[event_ptr]["t"] <= t:
            event_ptr += 1

        # Causal subset: strictly events up to event_ptr - 1
        causal_events = contributions[:event_ptr]

        home_intensity = 0.0
        away_intensity = 0.0
        net_differential = 0.0

        for item in causal_events:
            dt = t - item["t"]
            if dt < 0:
                continue  # Invariant guard against negative dt

            # Handle dead-time freeze if requested
            if cfg.freeze_dead_time and dead_intervals:
                # Subtract dead time that occurred between item["t"] and t
                dead_seconds = 0.0
                for iv in dead_intervals:
                    iv_s, iv_e = iv.get("start", 0), iv.get("end", 0)
                    overlap_s = max(item["t"], iv_s)
                    overlap_e = min(t, iv_e)
                    if overlap_e > overlap_s:
                        dead_seconds += (overlap_e - overlap_s)
                dt = max(0.0, dt - dead_seconds)

            weight = math.exp(-decay_lambda * dt)
            net_differential += item["signed_c"] * weight
            if item["is_home"]:
                if item["signed_c"] > 0:
                    home_intensity += item["mag"] * weight
                else:
                    home_intensity = max(0.0, home_intensity - item["mag"] * weight)
            else:
                if item["signed_c"] < 0:
                    away_intensity += item["mag"] * weight
                else:
                    away_intensity = max(0.0, away_intensity - item["mag"] * weight)

        timeline.append({
            "t": t,
            "home_intensity": round(home_intensity, 4),
            "away_intensity": round(away_intensity, 4),
            "oaai_raw": round(net_differential, 4),
            "causal_event_count": len(causal_events),
        })

    return timeline


# ==============================================================================
# Layer C: Visualization Smoothing Layer
# ==============================================================================

def smooth_oaai_timeline(
    timeline: list[dict],
    mode: Literal["causal", "bilateral"] = "causal",
    config: Optional[OAAIConfig] = None,
) -> list[dict]:
    """Applies visualization smoothing to aggregated OAAI timeline.

    - "causal": Single-sided moving average using strictly past and current samples.
      Safe for live / real-time streaming.
    - "bilateral": Symmetric two-sided filter for post-match tactical analysis.
      Explicitly labeled in metadata.
    """
    cfg = config or OAAIConfig()
    if not timeline:
        return []

    smoothed: list[dict] = []
    n = len(timeline)

    if mode == "causal":
        window = cfg.causal_window_samples
        for i in range(n):
            start_idx = max(0, i - window + 1)
            subset = timeline[start_idx : i + 1]
            avg_diff = sum(p["oaai_raw"] for p in subset) / len(subset)
            avg_h = sum(p["home_intensity"] for p in subset) / len(subset)
            avg_a = sum(p["away_intensity"] for p in subset) / len(subset)

            pt = dict(timeline[i])
            pt["oaai_value"] = round(avg_diff, 4)
            pt["home_smoothed"] = round(avg_h, 4)
            pt["away_smoothed"] = round(avg_a, 4)
            pt["smoothing_mode"] = "causal"
            smoothed.append(pt)

    elif mode == "bilateral":
        half_w = cfg.bilateral_window_samples // 2
        for i in range(n):
            start_idx = max(0, i - half_w)
            end_idx = min(n, i + half_w + 1)
            subset = timeline[start_idx:end_idx]
            avg_diff = sum(p["oaai_raw"] for p in subset) / len(subset)
            avg_h = sum(p["home_intensity"] for p in subset) / len(subset)
            avg_a = sum(p["away_intensity"] for p in subset) / len(subset)

            pt = dict(timeline[i])
            pt["oaai_value"] = round(avg_diff, 4)
            pt["home_smoothed"] = round(avg_h, 4)
            pt["away_smoothed"] = round(avg_a, 4)
            pt["smoothing_mode"] = "bilateral"
            smoothed.append(pt)

    return smoothed


# ==============================================================================
# Change-point Detection & Level 2 Metric Attribution
# ==============================================================================

def detect_change_points(
    smoothed_timeline: list[dict],
    events: Sequence[Any],
    config: Optional[OAAIConfig] = None,
    xt_model: Any = None,
) -> list[dict]:
    """Detects inflection points/momentum peaks on the smoothed OAAI curve,

    Extracts top contributing events (Level 2 Metric Attribution) in the
    causal lookback window preceding each change-point.
    """
    cfg = config or OAAIConfig()
    if len(smoothed_timeline) < 3:
        return []

    norm_events = [_normalize_event_view(e) for e in events]
    norm_events.sort(key=lambda e: (e["t"], e["id"]))

    change_points: list[dict] = []
    thresh = cfg.inflection_threshold
    window_sec = cfg.attribution_window_seconds

    # Detect local extrema where absolute slope or peak value exceeds threshold
    n = len(smoothed_timeline)
    for i in range(1, n - 1):
        prev_v = smoothed_timeline[i - 1]["oaai_value"]
        curr_v = smoothed_timeline[i]["oaai_value"]
        next_v = smoothed_timeline[i + 1]["oaai_value"]
        t_curr = smoothed_timeline[i]["t"]

        is_peak = (curr_v > prev_v and curr_v >= next_v and curr_v >= thresh)
        is_valley = (curr_v < prev_v and curr_v <= next_v and curr_v <= -thresh)
        is_zero_crossing = (prev_v * curr_v <= 0 and abs(curr_v - prev_v) >= thresh)

        if is_peak or is_valley or is_zero_crossing:
            # Avoid duplicate change points within 15 seconds
            if change_points and abs(t_curr - change_points[-1]["at"]) < 15.0:
                # Keep the one with larger absolute amplitude
                if abs(curr_v) > abs(change_points[-1]["oaai_amplitude"]):
                    change_points.pop()
                else:
                    continue

            leading_team = "H" if curr_v > 0 else ("N" if curr_v < 0 else "neutral")
            change_type = "home_surge" if curr_v >= thresh else ("away_surge" if curr_v <= -thresh else "lead_turn")

            # Extract causal lookback events in [t_curr - window_sec, t_curr]
            window_events = [
                e for e in norm_events
                if (t_curr - window_sec) <= e["t"] <= t_curr
            ]

            # Compute contribution of each event
            attributed_events = []
            for e in window_events:
                signed_c, mag, expl = compute_event_contribution(e, cfg, xt_model=xt_model)
                attributed_events.append({
                    "event_id": e["id"],
                    "t": e["t"],
                    "team": e["team"],
                    "actor": e["actor"],
                    "kind": e["kind"],
                    "outcome": e["outcome"],
                    "contribution": signed_c,
                    "magnitude": mag,
                    "explanation": expl,
                })

            # Sort by relevance to current surge direction
            if leading_team == "H":
                attributed_events.sort(key=lambda x: x["contribution"], reverse=True)
            elif leading_team == "N":
                attributed_events.sort(key=lambda x: x["contribution"])
            else:
                attributed_events.sort(key=lambda x: x["magnitude"], reverse=True)

            top_contributors = attributed_events[: cfg.top_contributors_limit]

            change_points.append({
                "change_point_id": f"CP-{len(change_points)+1:02d}",
                "at": t_curr,
                "oaai_amplitude": curr_v,
                "leading_team": leading_team,
                "change_type": change_type,
                "claim_level": 2,  # Level 2 Metric Attribution
                "disclaimer": "指标归因仅代表公式分解，不代表战术因果。",
                "window_seconds": window_sec,
                "top_contributors": top_contributors,
            })

    return change_points


# ==============================================================================
# Full Pipeline Orchestration
# ==============================================================================

def compute_oaai(
    events: Sequence[Any],
    config: Optional[OAAIConfig] = None,
    smoothing_mode: Literal["causal", "bilateral"] = "causal",
    t_end: Optional[float] = None,
    dead_intervals: Optional[list[dict]] = None,
    xt_model: Any = None,
) -> dict:
    """Full end-to-end OAAI pipeline generating Layer A, Layer B, Layer C and change points."""
    cfg = config or OAAIConfig()
    timeline_raw = aggregate_oaai_timeline(
        events=events,
        config=cfg,
        t_end=t_end,
        dead_intervals=dead_intervals,
        xt_model=xt_model,
    )
    timeline_smoothed = smooth_oaai_timeline(
        timeline=timeline_raw,
        mode=smoothing_mode,
        config=cfg,
    )
    change_points = detect_change_points(
        smoothed_timeline=timeline_smoothed,
        events=events,
        config=cfg,
        xt_model=xt_model,
    )

    return {
        "model_version": cfg.version,
        "smoothing_mode": smoothing_mode,
        "sample_step_seconds": cfg.sample_step_seconds,
        "half_life_seconds": cfg.half_life_seconds,
        "timeline": timeline_smoothed,
        "change_points": change_points,
        "disclaimer": "Observed Attacking Activity Index (OAAI) 度量已记录事件反映的进攻活动强度，非心理势头或胜率因果预测。",
    }
