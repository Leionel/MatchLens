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

import bisect
import math
from typing import Any, Literal, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

from .schema import ActionType, DerivedMetric, NormalizedEvent


class _DeadTimeIndex:
    """Merged, prefix-summed dead-ball intervals.

    The decay of an event has to subtract the dead time between the event and
    the sample. Scanning the interval list for every event of every sample is
    quadratic in the number of dead balls, which is what made a full provider
    match take minutes to chart. The intervals are merged once and
    prefix-summed, so a query costs a bisect instead of a scan.
    """

    __slots__ = ("_starts", "_ends", "_prefix")

    def __init__(self, intervals: Optional[Sequence[dict]] = None) -> None:
        merged: list[list[float]] = []
        for interval in sorted(
            intervals or [],
            key=lambda iv: (float(iv.get("start", 0.0) or 0.0), float(iv.get("end", 0.0) or 0.0)),
        ):
            start = float(interval.get("start", 0.0) or 0.0)
            end = float(interval.get("end", 0.0) or 0.0)
            if end <= start:
                continue
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
                continue
            merged.append([start, end])
        self._starts = [interval[0] for interval in merged]
        self._ends = [interval[1] for interval in merged]
        prefix = [0.0]
        for start, end in merged:
            prefix.append(prefix[-1] + (end - start))
        self._prefix = prefix

    def __bool__(self) -> bool:
        return bool(self._starts)

    def seconds_between(self, start: float, end: float) -> float:
        """Dead seconds inside (start, end]."""
        if end <= start or not self._starts:
            return 0.0
        first = bisect.bisect_right(self._ends, start)
        last = bisect.bisect_left(self._starts, end)
        if first >= last:
            return 0.0
        if last - first == 1:
            return max(0.0, min(self._ends[first], end) - max(self._starts[first], start))
        total = max(0.0, min(self._ends[first], end) - max(self._starts[first], start))
        total += max(0.0, min(self._ends[last - 1], end) - max(self._starts[last - 1], start))
        if last - first > 2:
            total += self._prefix[last - 1] - self._prefix[first + 1]
        return total


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

        located = ev.x is not None and ev.y is not None
        start_x = ev.x if located else None
        start_y = ev.y if located else None
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
            "start": (start_x, start_y) if located else None,
            "end": (end_x, end_y) if end_x is not None and end_y is not None else None,
            "located": located,
            "frame": "team_relative",
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
    raw_start = d.get("start")
    if raw_start is None and d.get("x") is not None and d.get("y") is not None:
        raw_start = [d.get("x"), d.get("y")]
    raw_end = d.get("end")
    if raw_end is None and d.get("end_x") is not None and d.get("end_y") is not None:
        raw_end = [d.get("end_x"), d.get("end_y")]
    located = bool(
        raw_start and len(raw_start) >= 2
        and raw_start[0] is not None and raw_start[1] is not None
    )

    return {
        "id": d.get("id", d.get("event_id", "EV")),
        "t": t_val,
        "team": team,
        "team_id": str(d.get("team_id", team)),
        "kind": d.get("kind", d.get("action_type", "pass")),
        "actor": d.get("actor", d.get("player_name", "Player")),
        "start": (float(raw_start[0]), float(raw_start[1])) if located else None,
        "end": (
            (float(raw_end[0]), float(raw_end[1]))
            if raw_end and len(raw_end) >= 2 and raw_end[0] is not None and raw_end[1] is not None
            else None
        ),
        "located": located,
        "frame": d.get("coordinate_frame", "fixed"),
        "outcome": d.get("outcome", "complete"),
        "raw": ev,
    }


def _attack_x(team: str, x: float, frame: str = "fixed") -> float:
    """Longitudinal coordinate relative to attacking direction (0 to 105m)."""
    if frame == "team_relative":
        return x
    return x if team in ("H", "home") else 105.0 - x


def _is_in_penalty_box(ax: float, y: float) -> bool:
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
    frame = ev.get("frame", "fixed")
    located = bool(ev.get("located", ev.get("start") is not None))
    start = ev.get("start")
    end = ev.get("end")
    if located and start is not None:
        start_x, start_y = start
        end_x, end_y = end if end is not None else start
        ax_start = _attack_x(team, start_x, frame)
        ax_end = _attack_x(team, end_x, frame)
        progression_m = max(0.0, ax_end - ax_start)
    else:
        start_x = start_y = end_x = end_y = None
        ax_start = ax_end = None
        progression_m = 0.0

    magnitude = 0.0
    explanation = f"{kind.capitalize()}"

    if kind == "shot":
        # Base shot weight + goal outcome bonus
        is_goal = outcome == "goal"
        base = cfg.shot_base_weight
        if located and ax_start is not None:
            # Pre-shot xG uses goal visible angle & distance without outcome leakage.
            from .models.xg import compute_pre_shot_xg
            shot_eval = compute_pre_shot_xg(x=ax_start, y=start_y, event_id=str(ev.get("id", "")), outcome=outcome)
            approx_xg = shot_eval.pre_shot_xg
            magnitude = base + (approx_xg * cfg.xg_factor) + (cfg.goal_bonus_weight if is_goal else 0.0)
            explanation = f"Goal ({magnitude:.2f})" if is_goal else f"Shot attempt ({magnitude:.2f})"
        else:
            magnitude = base + (cfg.goal_bonus_weight if is_goal else 0.0)
            explanation = "Goal (location unknown; xG not applicable)" if is_goal else "Shot (location unknown; xG not applicable)"

    elif kind == "pass":
        if not located:
            explanation = "Pass (location unknown; no spatial contribution)"
        else:
            # Check if xT model can be evaluated
            if xt_model is not None:
                try:
                    # If event is NormalizedEvent or can be evaluated by xt_model
                    norm_ev = ev["raw"] if isinstance(ev["raw"], NormalizedEvent) else None
                    if norm_ev is not None:
                        eval_fn = getattr(xt_model, "evaluate_action", None) or getattr(xt_model, "evaluate_progression", None)
                        xt_metric = eval_fn(norm_ev) if eval_fn else None
                        if xt_metric is not None and xt_metric.value is not None:
                            magnitude += max(0.0, float(xt_metric.value)) * cfg.xt_factor
                        else:
                            v_start = xt_model.value_at(ax_start, start_y)
                            v_end = xt_model.value_at(ax_end, end_y)
                            delta_xt = max(0.0, v_end - v_start)
                            magnitude += delta_xt * cfg.xt_factor
                    else:
                        v_start = xt_model.value_at(ax_start, start_y)
                        v_end = xt_model.value_at(ax_end, end_y)
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
            elif _is_in_penalty_box(ax_end, end_y):
                magnitude += cfg.penalty_box_entry_bonus
                explanation = f"Penalty box pass (+{progression_m:.1f}m)"
            else:
                explanation = f"Progression pass (+{progression_m:.1f}m)"

    elif kind == "recovery":
        is_high = ax_start is not None and ax_start >= 70.0
        magnitude = cfg.recovery_base_weight + (cfg.high_recovery_bonus if is_high else 0.0)
        explanation = (
            "High attacking recovery" if is_high
            else "Ball recovery" if located
            else "Ball recovery (location unknown)"
        )

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

    if not (cfg.freeze_dead_time and dead_intervals):
        # No frozen intervals: every contribution decays by the same factor
        # between samples, so the timeline is computed in O(events + steps)
        # instead of rescanning the causal prefix at every step.
        home_intensity = 0.0
        away_intensity = 0.0
        net_differential = 0.0
        previous_t = 0.0
        for step_idx in range(total_steps):
            t = round(step_idx * step, 2)
            factor = math.exp(-decay_lambda * (t - previous_t))
            home_intensity *= factor
            away_intensity *= factor
            net_differential *= factor
            while event_ptr < n_events and contributions[event_ptr]["t"] <= t:
                item = contributions[event_ptr]
                weight = math.exp(-decay_lambda * max(0.0, t - item["t"]))
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
                event_ptr += 1
            previous_t = t
            timeline.append({
                "t": t,
                "home_intensity": round(home_intensity, 4),
                "away_intensity": round(away_intensity, 4),
                "oaai_raw": round(net_differential, 4),
                "causal_event_count": event_ptr,
            })
        return timeline

    dead_index = _DeadTimeIndex(dead_intervals)

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
            dead_seconds = dead_index.seconds_between(item["t"], t)
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
# Registry window selection (shared by the metric registry and the chart)
# ==============================================================================

def oaai_window_peak(
    timeline: list[dict],
    team: str,
    start: float,
    end: float,
) -> Optional[dict]:
    """Peak smoothed team intensity of an OAAI timeline inside (start, end].

    This is the single selection rule behind the registry's ``oaai`` metric and
    behind the chart-side registry comparison, so both surfaces publish the
    same number for the same window. Returns ``None`` when the window holds no
    sample; the metric then stays unobserved and never collapses to zero.
    """
    key = "home_smoothed" if team == "H" else "away_smoothed"
    points = [
        p for p in (timeline or [])
        if start < float(p.get("t", 0.0)) <= end
    ]
    if not points:
        return None
    peak = max(points, key=lambda p: abs(float(p.get(key, 0.0))))
    return {
        "value": float(peak.get(key, 0.0)),
        "peak_at": float(peak.get("t", 0.0)),
        "team": team,
        "value_basis": "smoothed_team_intensity",
    }


# ==============================================================================
# Layer A/B ledger: recomputable event contributions at one point
# ==============================================================================

def compute_oaai_contribution_ledger(
    events: Sequence[Any],
    *,
    at: float,
    team: str,
    dead_intervals: Optional[list[dict]] = None,
    config: Optional[OAAIConfig] = None,
    xt_model: Any = None,
    smoothing_mode: Literal["causal", "bilateral"] = "causal",
    limit: Optional[int] = None,
    timeline: Optional[list[dict]] = None,
) -> dict:
    """Recompute every event contribution to OAAI at a selected time.

    The ledger separates the signed net contribution from the selected team's
    intensity contribution. The chart value is the smoothed team intensity at
    the nearest sample; the raw ledger sums are reported separately so the two
    are never conflated.
    """
    cfg = config or OAAIConfig()
    selected_team = "N" if team == "N" else "H"
    initial = [_normalize_event_view(e) for e in events]
    home_team = _infer_home_team(initial)
    norm_events = [_normalize_event_view(e, home_team=home_team) for e in events]
    norm_events.sort(key=lambda e: (e["t"], e["id"]))
    dead = dead_intervals or []
    decay_lambda = math.log(2) / cfg.half_life_seconds

    dead_index = _DeadTimeIndex(dead)

    rows: list[dict] = []
    for event in norm_events:
        if event["t"] > at:
            continue
        signed, magnitude, explanation = compute_event_contribution(
            event, cfg, xt_model=xt_model, home_team=home_team
        )
        effective_dt = max(
            0.0,
            float(at) - event["t"] - dead_index.seconds_between(event["t"], float(at)),
        )
        weight = math.exp(-decay_lambda * effective_dt)
        net = signed * weight
        team_contribution = 0.0
        is_selected = event["team"] == selected_team or str(event.get("team_id")) == selected_team
        if is_selected:
            team_contribution = magnitude * weight if signed > 0 else -magnitude * weight
        start = event.get("start")
        attack_x = None
        if start is not None:
            attack_x = round(_attack_x(event["team"], float(start[0]), event.get("frame", "fixed")), 2)
        rows.append({
            "event_id": event["id"],
            "t": round(event["t"], 2),
            "team": event["team"],
            "actor": event.get("actor") or "Unknown",
            "kind": event.get("kind") or "other",
            "outcome": event.get("outcome") or "",
            "attack_x": attack_x,
            "weight": round(weight, 6),
            "effective_dt": round(effective_dt, 3),
            "signed_contribution": round(signed, 6),
            "magnitude": round(magnitude, 6),
            "net_contribution": round(net, 6),
            "team_contribution": round(team_contribution, 6),
            "decay": round(weight, 6),
            "explanation": explanation,
        })

    rows.sort(key=lambda row: abs(row["team_contribution"] or row["net_contribution"]), reverse=True)
    top = rows if limit is None else rows[:limit]
    raw_team = round(sum(row["team_contribution"] for row in rows), 6)
    raw_net = round(sum(row["net_contribution"] for row in rows), 6)
    top_team = round(sum(row["team_contribution"] for row in top), 6)
    top_net = round(sum(row["net_contribution"] for row in top), 6)

    if timeline is None:
        oaai = compute_oaai(
            events,
            config=cfg,
            smoothing_mode=smoothing_mode,
            t_end=at,
            dead_intervals=dead,
            xt_model=xt_model,
        )
        timeline = oaai.get("timeline", [])
    nearest = min(timeline, key=lambda p: abs(float(p.get("t", 0.0)) - float(at))) if timeline else None
    smoothed_value = None
    if nearest is not None:
        key = "home_smoothed" if selected_team == "H" else "away_smoothed"
        smoothed_value = nearest.get(key)

    return {
        "model_version": cfg.version,
        "smoothing_mode": smoothing_mode,
        "at": round(float(at), 2),
        "team": selected_team,
        "half_life_seconds": cfg.half_life_seconds,
        "sample_step_seconds": cfg.sample_step_seconds,
        "value_basis": "team_intensity_raw_at_selected_time",
        "smoothed_value_at_nearest_sample": smoothed_value,
        "raw_team_intensity": raw_team,
        "raw_net_contribution": raw_net,
        "top_team_intensity": top_team,
        "top_net_contribution": top_net,
        "unlisted_team_intensity": round(raw_team - top_team, 6),
        "contribution_count": len(rows),
        "listed_contribution_count": len(top),
        "contributions": top,
        "disclaimer": (
            "OAAI contribution is a formula decomposition of recorded on-ball activity; "
            "it is not psychological momentum or causal proof."
        ),
    }


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
    *,
    include_raw: bool = False,
) -> dict:
    """Full end-to-end OAAI pipeline generating Layer A, Layer B, Layer C and change points.

    `include_raw` additionally returns the unsmoothed Layer B timeline. The raw
    timeline is the expensive part of the pipeline; returning it lets a caller
    derive the registry's canonical (causal) smoothing from the very same
    computation instead of running the pipeline a second time.
    """
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

    result = {
        "model_version": cfg.version,
        "smoothing_mode": smoothing_mode,
        "sample_step_seconds": cfg.sample_step_seconds,
        "half_life_seconds": cfg.half_life_seconds,
        "timeline": timeline_smoothed,
        "change_points": change_points,
        "disclaimer": "Observed Attacking Activity Index (OAAI) 度量已记录事件反映的进攻活动强度，非心理势头或胜率因果预测。",
    }
    if include_raw:
        result["timeline_raw"] = timeline_raw
    return result


def _plotted_value(point: dict) -> float:
    """The value the momentum chart draws for a timeline sample."""
    value = point.get("oaai_value")
    if value is None:
        value = point.get("oaai_raw")
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def downsample_oaai_timeline(timeline: Sequence[dict], max_points: int = 600) -> list[dict]:
    """Reduce a chart timeline to a renderable size without hiding peaks.

    A full match samples the activity index every two seconds, which is far
    more detail than the chart's pixel width can resolve - and every sample
    travels to the browser on each state push. Each bucket keeps its extreme
    sample, so a spike is never averaged into invisibility, and the first and
    the last sample of the match are always preserved. The samples themselves
    are returned unchanged: this is a rendering budget, not a new metric.
    """
    points = list(timeline)
    if max_points < 4 or len(points) <= max_points:
        return points

    buckets = max(2, max_points // 2)
    size = len(points)
    kept: list[dict] = []
    for index in range(buckets):
        lo = (index * size) // buckets
        hi = ((index + 1) * size) // buckets
        chunk = points[lo:hi]
        if not chunk:
            continue
        low = min(chunk, key=_plotted_value)
        high = max(chunk, key=_plotted_value)
        extremes = [low] if low is high else [low, high]
        for point in sorted(extremes, key=lambda p: p["t"]):
            if not kept or kept[-1] is not point:
                kept.append(point)

    first, last = points[0], points[-1]
    if not kept or kept[0] is not first:
        kept.insert(0, first)
    if kept[-1] is not last:
        kept.append(last)
    return kept


def trim_change_point_contributors(
    change_points: Sequence[dict], max_contributors: int = 2
) -> list[dict]:
    """Keep every change point but shorten its contributor list.

    The number of change points is evidence and stays untouched; only the
    number of supporting events carried with each of them is reduced, because
    the inspector shows the strongest contributors anyway.
    """
    if max_contributors < 1:
        raise ValueError("max_contributors must be positive")
    trimmed: list[dict] = []
    for point in change_points:
        contributors = point.get("top_contributors") or []
        if len(contributors) <= max_contributors:
            trimmed.append(point)
            continue
        copy = dict(point)
        copy["top_contributors"] = list(contributors[:max_contributors])
        copy["top_contributors_truncated"] = len(contributors) - max_contributors
        trimmed.append(copy)
    return trimmed


def chart_oaai_payload(
    oaai_data: dict,
    max_points: int = 600,
    max_contributors: int = 2,
) -> dict:
    """A chart-sized copy of an OAAI result.

    The registry comparison inside the payload was computed on the full
    resolution timeline and is carried over unchanged, so trimming the chart
    copy never changes what the registry publishes.
    """
    payload = dict(oaai_data)
    payload["timeline"] = downsample_oaai_timeline(oaai_data.get("timeline") or [], max_points)
    payload["change_points"] = trim_change_point_contributors(
        oaai_data.get("change_points") or [], max_contributors
    )
    payload["chart_sampling"] = {
        "timeline_points_full": len(oaai_data.get("timeline") or []),
        "timeline_points_chart": len(payload["timeline"]),
        "max_points": max_points,
    }
    return payload
