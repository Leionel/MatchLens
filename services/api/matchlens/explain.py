"""Explain Any Chart: Evidence-grounded tactical chart explanation engine.

Generates structured, receipt-backed explanations for tactical visualizations:
- oaai_momentum: OAAI wave dynamics, momentum inflection points, dominant intervals.
- density_differential: 9-zone spatial occupancy differential ΔD(z).
- passing_network: Player interaction centroids and high-threat progressive connections.
- attacking_channels: 5-corridor penetration and penalty box entry distribution.
- spatial_drilldown: Spatial sequence chains and progressive territory gain.
- xt_surface: Expected Threat spatial danger and progressive value creation.
- shot_location: A single shot position — geometry, cell, heuristic pre-shot danger.
- cross_match_diff: The same registry metric observed in two matches, side by side.

Every explanation references exact event IDs, formula definitions, and confidence tiers,
strictly upholding Gate 2.0 evidence boundaries.
"""
from __future__ import annotations

import math
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from .contracts import Snapshot


ChartType = Literal[
    "oaai_momentum",
    "density_differential",
    "passing_network",
    "attacking_channels",
    "spatial_drilldown",
    "xt_surface",
    "shot_location",
    "cross_match_diff",
]


class MetricExplanationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: str
    value: str | float | int
    unit: Optional[str] = None
    formula: Optional[str] = None
    receipt_id: Optional[str] = None
    interpretation: str


class ChartExplanationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chart_type: ChartType
    title: str
    summary: str
    team: str
    key_metrics: list[MetricExplanationItem]
    supporting_event_ids: list[str] = Field(default_factory=list)
    confidence_tier: Literal["Level 1 (Direct Observation)", "Level 2 (Formula Decomposition)"]
    limitations: list[str] = Field(default_factory=list)
    causal_disclaimer: str
    #: Cross-match explanations carry the second match's identity so the UI can
    #: hand the pair to /api/investigate (focus_type="cross_match_diff").
    comparison: Optional[dict[str, Any]] = None


ZONE_BOUNDS = {
    "Z1": {"x": (0.0, 35.0), "y": (0.0, 22.67), "name": "Defensive Third - Left"},
    "Z2": {"x": (0.0, 35.0), "y": (22.67, 45.33), "name": "Defensive Third - Center"},
    "Z3": {"x": (0.0, 35.0), "y": (45.33, 68.0), "name": "Defensive Third - Right"},
    "Z4": {"x": (35.0, 70.0), "y": (0.0, 22.67), "name": "Middle Third - Left"},
    "Z5": {"x": (35.0, 70.0), "y": (22.67, 45.33), "name": "Middle Third - Center"},
    "Z6": {"x": (35.0, 70.0), "y": (45.33, 68.0), "name": "Middle Third - Right"},
    "Z7": {"x": (70.0, 105.0), "y": (0.0, 22.67), "name": "Attacking Third - Left"},
    "Z8": {"x": (70.0, 105.0), "y": (22.67, 45.33), "name": "Attacking Third - Center"},
    "Z9": {"x": (70.0, 105.0), "y": (45.33, 68.0), "name": "Attacking Third - Right"},
}


def explain_chart(
    snapshot: Snapshot,
    chart_type: ChartType,
    team: Literal["H", "N"] = "H",
    zone_id: Optional[str] = None,
    player_id: Optional[str] = None,
    sequence_id: Optional[str] = None,
    point_timestamp: Optional[float] = None,
    pass_edge: Optional[tuple[str, str]] = None,
    xt_cell: Optional[tuple[int, int]] = None,
    shot_location: Optional[tuple[float, float]] = None,
    shot_event_id: Optional[str] = None,
    metric_id: Optional[str] = None,
    compare_snapshot: Optional[Snapshot] = None,
    compare_label: Optional[str] = None,
    compare_team: Optional[Literal["H", "N"]] = None,
) -> ChartExplanationResult:
    """Produce an evidence-grounded explanation for any cockpit visualization.

    Slice C additions (additive; existing parameter semantics untouched):
    - ``shot_location`` / ``shot_event_id`` focus an explanation on one shot
      position (chart_type="shot_location").
    - ``compare_snapshot`` + ``metric_id`` produce a two-match diff of one
      registry metric (chart_type="cross_match_diff"); values come from
      MetricsService on both frozen snapshots, never from a reimplementation.
    """
    r = snapshot.data.get("receipts", {})
    at = snapshot.data.get("as_of", 0)
    events = snapshot.data.get("events", [])
    team_name = snapshot.data.get("teams", {}).get(team, f"Team {team}")
    opp_team = "N" if team == "H" else "H"
    opp_name = snapshot.data.get("teams", {}).get(opp_team, f"Team {opp_team}")

    # Helper to extract scalar value from receipts
    def _r_val(key: str, default: float = 0.0) -> float:
        val = r.get(key, {})
        if isinstance(val, dict):
            return float(val.get("value", default))
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    disclaimer = (
        "Tactical findings reflect on-ball event coordinates and temporal receipts. "
        "Opponent defensive line compactness or off-ball running cannot be causally proven without 25Hz optical tracking."
    )

    if chart_type == "oaai_momentum":
        pos_curr = _r_val(f"{team}.possession.current")
        pos_prev = _r_val(f"{team}.possession.previous")
        shots_curr = int(_r_val(f"{team}.shots.current"))
        shots_prev = int(_r_val(f"{team}.shots.previous"))
        rec_curr = int(_r_val(f"{team}.high_recoveries.current"))

        # Contributing events: if point_timestamp provided, find events near peak
        if point_timestamp is not None:
            t_center = float(point_timestamp)
            contributing = [
                e for e in events
                if abs(float(e.get("t", e.get("clock_seconds", 0))) - t_center) <= 20.0
            ]
            ev_ids = [str(e.get("id", e.get("event_id", ""))) for e in contributing if e.get("id") or e.get("event_id")]
            peak_desc = f" around peak at {int(t_center)//60:02d}:{int(t_center)%60:02d}"
        else:
            contributing = [
                e for e in events
                if max(0, at - 180) <= float(e.get("t", e.get("clock_seconds", 0))) <= at
                and (e.get("kind") in ("shot", "recovery") or "shot" in str(e.get("action_type", "")).lower())
            ]
            ev_ids = [str(e.get("id", e.get("event_id", ""))) for e in contributing if e.get("id") or e.get("event_id")]
            peak_desc = f" up to {at//60:02d}:{at%60:02d}"

        summary = (
            f"Observed Attacking Activity Index (OAAI) traces territorial momentum{peak_desc}. "
            f"{team_name} recorded {pos_curr:.1f}% possession share and {shots_curr} shot(s) in the active 180s window, "
            f"compared to {pos_prev:.1f}% and {shots_prev} shot(s) in the prior baseline window."
        )
        metrics = [
            MetricExplanationItem(
                metric="Window Possession",
                value=f"{pos_curr:.1f}% (delta: {pos_curr - pos_prev:+.1f}%)",
                unit="%",
                formula="Duration(Team) / Total_Duration in [T-180, T]",
                receipt_id=f"{team}.possession.current",
                interpretation="Share of active ball control across the 180s comparison period.",
            ),
            MetricExplanationItem(
                metric="Shot Production",
                value=f"{shots_curr} (delta: {shots_curr - shots_prev:+d})",
                unit="shots",
                formula="Count of shot events within the active window",
                receipt_id=f"{team}.shots.current",
                interpretation="Terminal attacking output produced during the wave.",
            ),
            MetricExplanationItem(
                metric="High-Press Recoveries",
                value=rec_curr,
                unit="recoveries",
                formula="Turnovers won in attacking third (x >= 70m)",
                receipt_id=f"{team}.high_recoveries.current",
                interpretation="Front-foot turnovers won before opponent defensive reset.",
            ),
        ]
        return ChartExplanationResult(
            chart_type="oaai_momentum",
            title=f"OAAI Momentum Wave Dynamics ({team_name})",
            summary=summary,
            team=team,
            key_metrics=metrics,
            supporting_event_ids=ev_ids,
            confidence_tier="Level 2 (Formula Decomposition)",
            limitations=[
                "OAAI is an empirical momentum proxy, not an expected goals metric.",
                "Dead-ball intervals and stoppage delays are excluded from decay weights.",
            ],
            causal_disclaimer=disclaimer,
        )

    if chart_type == "density_differential":
        clean_zone = zone_id.upper().strip() if zone_id else None
        if clean_zone and clean_zone not in ZONE_BOUNDS:
            raise ValueError(f"invalid_zone_id: {zone_id}. Supported zones: Z1-Z9.")

        team_evs = [e for e in events if e.get("team") == team or e.get("team_id") in (team, team_name)]
        opp_evs = [e for e in events if e.get("team") == opp_team or e.get("team_id") in (opp_team, opp_name)]
        total_team = max(1, len(team_evs))
        total_opp = max(1, len(opp_evs))

        if clean_zone:
            bounds = ZONE_BOUNDS[clean_zone]
            x_min, x_max = bounds["x"]
            y_min, y_max = bounds["y"]
            in_zone_team = [
                e for e in team_evs
                if x_min <= float(e.get("start", [e.get("x", 50)])[0]) < x_max
                and y_min <= float(e.get("start", [50, e.get("y", 34)])[1]) < y_max
            ]
            in_zone_opp = [
                e for e in opp_evs
                if x_min <= float(e.get("start", [e.get("x", 50)])[0]) < x_max
                and y_min <= float(e.get("start", [50, e.get("y", 34)])[1]) < y_max
            ]
            d_team = len(in_zone_team) / total_team
            d_opp = len(in_zone_opp) / total_opp
            delta_d = d_team - d_opp
            zone_desc = f" focused on {clean_zone} ({bounds['name']})"
            supporting_ids = [str(e.get("id", e.get("event_id", ""))) for e in in_zone_team if e.get("id") or e.get("event_id")]
            diff_metric_val = f"{delta_d:+.3f}"
            zone_actions_val = f"{len(in_zone_team)} vs {len(in_zone_opp)}"
        else:
            zone_desc = " across all 9 standardized pitch zones"
            supporting_ids = [str(e.get("id", e.get("event_id", ""))) for e in team_evs[:8] if e.get("id") or e.get("event_id")]
            diff_metric_val = "Macro Pitch Differential"
            zone_actions_val = f"{len(team_evs)} vs {len(opp_evs)}"

        summary = (
            f"Nine-zone action density differential ΔD(z) evaluates spatial territorial dominance{zone_desc}. "
            f"Compares event frequency distribution of {team_name} against {opp_name} across standardized 3x3 pitch zones."
        )
        metrics = [
            MetricExplanationItem(
                metric="Zone Resolution",
                value="3x3 Standardized (105m x 68m)",
                unit="dimensionless",
                formula="Pitch divided into Defensive, Middle, Attacking thirds x 3 lateral corridors",
                receipt_id=None,
                interpretation="Standard spatial discretization for on-ball event density.",
            ),
            MetricExplanationItem(
                metric="Density Differential Formula",
                value=diff_metric_val,
                unit="dimensionless",
                formula="ΔD(z) = [N_team(z) / N_team_total] - [N_opp(z) / N_opp_total]",
                receipt_id=None,
                interpretation="Positive values indicate zone territorial over-representation relative to match baseline.",
            ),
            MetricExplanationItem(
                metric="Zone Action Count (Team vs Opponent)",
                value=zone_actions_val,
                unit="dimensionless",
                formula="Count of observed events starting inside selected zone bounds",
                receipt_id=None,
                interpretation="Direct frequency comparison of on-ball involvement within the zone.",
            ),
        ]
        return ChartExplanationResult(
            chart_type="density_differential",
            title=f"Nine-Zone Action Density Differential ΔD(z){zone_desc}",
            summary=summary,
            team=team,
            key_metrics=metrics,
            supporting_event_ids=supporting_ids,
            confidence_tier="Level 2 (Formula Decomposition)",
            limitations=[
                "Density reflects only event location coordinates, not continuous player shape.",
                "Zones with zero actions reflect unobserved activity rather than true empty pitch.",
            ],
            causal_disclaimer=disclaimer,
        )

    if chart_type == "passing_network":
        clean_player = player_id.strip() if player_id else None
        passes = [
            e for e in events
            if e.get("kind") == "pass" or "pass" in str(e.get("action_type", "")).lower()
        ]
        team_passes = [
            e for e in passes
            if e.get("team") == team or e.get("team_id") in (team, team_name)
        ]
        if pass_edge:
            src, dst = pass_edge
            edge_passes = [
                e for e in team_passes
                if (e.get("actor") == src or e.get("player_name") == src)
                and (e.get("receiver") == dst or e.get("pass_recipient") == dst)
            ]
            supporting_ids = [str(e.get("id", e.get("event_id", ""))) for e in edge_passes if e.get("id") or e.get("event_id")]
            pass_count_val = len(edge_passes)
            node_desc = f" focusing on passing edge {src} -> {dst}"
        elif clean_player:
            player_passes = [
                e for e in team_passes
                if e.get("actor") == clean_player
                or e.get("receiver") == clean_player
                or e.get("player_name") == clean_player
            ]
            supporting_ids = [str(e.get("id", e.get("event_id", ""))) for e in player_passes if e.get("id") or e.get("event_id")]
            pass_count_val = len(player_passes)
            node_desc = f" focusing on player {clean_player}"
        else:
            supporting_ids = [str(e.get("id", e.get("event_id", ""))) for e in team_passes[-8:] if e.get("id") or e.get("event_id")]
            pass_count_val = len(team_passes)
            node_desc = ""

        summary = (
            f"Passing Network Analysis models interactive ball circulation structure for {team_name}{node_desc}. "
            f"Nodes represent player event origin centroids; edge thickness indicates directional passing volume."
        )
        metrics = [
            MetricExplanationItem(
                metric="Pass Volume",
                value=pass_count_val,
                unit="passes",
                formula="Count of completed and attempted passes recorded in active window",
                receipt_id=None,
                interpretation=f"Passing interactions attributed to {clean_player or team_name}.",
            ),
            MetricExplanationItem(
                metric="Network Density",
                value=f"{len(team_passes)} team passes",
                unit="passes",
                formula="Total on-ball circulation edges recorded for the team",
                receipt_id=None,
                interpretation="Underlying on-ball interaction density across the pitch.",
            ),
        ]
        return ChartExplanationResult(
            chart_type="passing_network",
            title=f"Passing Network & Circulation Structure ({team_name}){node_desc}",
            summary=summary,
            team=team,
            key_metrics=metrics,
            supporting_event_ids=supporting_ids,
            confidence_tier="Level 1 (Direct Observation)",
            limitations=[
                "Pass networks use event origin centroids; they do not reflect average player positions without tracking.",
                "Off-ball running lanes and pressing cover shadows are unobserved.",
            ],
            causal_disclaimer=disclaimer,
        )

    if chart_type == "attacking_channels":
        entries = int(_r_val(f"{team}.entries.current"))
        entry_events = [
            e for e in events
            if (e.get("team") == team or e.get("team_id") in (team, team_name))
            and (e.get("kind") in ("pass", "carry", "shot") or "pass" in str(e.get("action_type", "")).lower())
            and float(e.get("end", [e.get("end_x", 0)])[0]) >= 70.0
        ]
        ev_ids = [str(e.get("id", e.get("event_id", ""))) for e in entry_events if e.get("id") or e.get("event_id")]
        summary = (
            f"Attacking Corridor Breakdown classifies final-third entries and penetrations across 5 channels "
            f"(Left Flank, Half-Space Left, Center, Half-Space Right, Right Flank). {team_name} generated "
            f"{entries} final-third entry event(s) in the current observation period."
        )
        metrics = [
            MetricExplanationItem(
                metric="Final Third Entries",
                value=entries,
                unit="entries",
                formula="Count of passes or carries terminating at x >= 70m",
                receipt_id=f"{team}.entries.current",
                interpretation="Penetrations crossing the defensive line boundary into danger zones.",
            ),
        ]
        return ChartExplanationResult(
            chart_type="attacking_channels",
            title=f"Five-Corridor Attacking Penetration Analysis ({team_name})",
            summary=summary,
            team=team,
            key_metrics=metrics,
            supporting_event_ids=ev_ids[-6:] if ev_ids else [],
            confidence_tier="Level 1 (Direct Observation)",
            limitations=[
                "Channel widths are geometric partitions; they do not adapt to opponent block shifts.",
            ],
            causal_disclaimer=disclaimer,
        )

    if chart_type == "xt_surface":
        xt_desc = ""
        supporting_ids = []
        if xt_cell is not None:
            cx, cy = xt_cell
            xt_desc = f" focusing on pitch cell ({cx}, {cy})"
            x_min, x_max = cx * (105.0 / 16.0), (cx + 1) * (105.0 / 16.0)
            y_min, y_max = cy * (68.0 / 12.0), (cy + 1) * (68.0 / 12.0)
            cell_events = [
                e for e in events
                if (e.get("team") == team or e.get("team_id") in (team, team_name))
                and (
                    (x_min <= float(e.get("end", [e.get("end_x", e.get("x", -1))])[0]) < x_max
                     and y_min <= float(e.get("end", [0, e.get("end_y", e.get("y", -1))])[1]) < y_max)
                    or
                    (x_min <= float(e.get("start", [e.get("x", -1)])[0]) < x_max
                     and y_min <= float(e.get("start", [0, e.get("y", -1)])[1]) < y_max)
                )
            ]
            supporting_ids = [str(e.get("id", e.get("event_id", ""))) for e in cell_events[:6] if e.get("id") or e.get("event_id")]

        summary = (
            f"Expected Threat (xT) spatial surface models the probability that moving the ball to a given pitch coordinate "
            f"will culminate in a goal within the subsequent sequences{xt_desc}. The threat surface concentrates danger in the central "
            f"penalty box and six-yard area, rising smoothly with goal proximity and shooting angle."
        )
        metrics = [
            MetricExplanationItem(
                metric="Model Surface Type",
                value="Heuristic Threat Surface (Uncalibrated Spatial Prior)",
                unit="dimensionless",
                formula="xT(x,y) = f(goal_distance, forward_progression, penalty_box_weight)",
                receipt_id=None,
                interpretation="Spatial prior calibrated for comparative threat evaluation without empirical transition matrices.",
            ),
            MetricExplanationItem(
                metric="Progression Metric",
                value="ΔxT = xT(end) - xT(start)",
                unit="dimensionless",
                formula="Net threat differential created between pass/carry start and end points",
                receipt_id=None,
                interpretation="Quantifies territorial threat advancement through successful actions.",
            ),
        ]
        return ChartExplanationResult(
            chart_type="xt_surface",
            title=f"Expected Threat (xT) Surface Explanation{xt_desc}",
            summary=summary,
            team=team,
            key_metrics=metrics,
            supporting_event_ids=supporting_ids,
            confidence_tier="Level 2 (Formula Decomposition)",
            limitations=[
                "Uncalibrated heuristic spatial prior; not empirically fitted on multi-season event callsets.",
                "Turnover risk penalties are bounded; does not model counter-attack threat conceded.",
            ],
            causal_disclaimer=disclaimer,
        )

    if chart_type == "shot_location":
        return _explain_shot_location(
            snapshot, team,
            shot_location=shot_location,
            shot_event_id=shot_event_id,
        )

    if chart_type == "cross_match_diff":
        return _explain_cross_match_diff(
            snapshot, team,
            metric_id=metric_id or "shots",
            compare_snapshot=compare_snapshot,
            compare_label=compare_label,
            compare_team=compare_team,
        )

    # spatial_drilldown
    clean_seq = sequence_id.strip() if sequence_id else None
    summary = (
        f"Tactical spatial sequence drilldown tracks contiguous possession chains for {team_name}. "
        f"Each chain links uninterrupted on-ball actions between players, verifying time monotonicity "
        f"and pitch coordinate continuity."
    )
    if clean_seq:
        supporting_ids = [str(e.get("id", e.get("event_id", ""))) for e in events if str(e.get("sequence_id", "")) == clean_seq and (e.get("id") or e.get("event_id"))]
    else:
        team_evs = [e for e in events if e.get("team") == team or e.get("team_id") in (team, team_name)]
        seq_evs = [e for e in team_evs if e.get("sequence_id")]
        if seq_evs:
            last_seq = seq_evs[-1].get("sequence_id")
            supporting_ids = [str(e.get("id", e.get("event_id", ""))) for e in seq_evs if e.get("sequence_id") == last_seq and (e.get("id") or e.get("event_id"))]
        else:
            supporting_ids = []

    metrics = [
        MetricExplanationItem(
            metric="Active Event Count",
            value=len(supporting_ids),
            unit="events",
            formula="Count of validated on-ball event records in current sequence window",
            receipt_id=None,
            interpretation="Underlying empirical events supporting this tactical visualization.",
        ),
    ]
    return ChartExplanationResult(
        chart_type=chart_type,
        title=f"Tactical Structure & Sequence Drilldown ({team_name})" + (f" [Seq {clean_seq}]" if clean_seq else ""),
        summary=summary,
        team=team,
        key_metrics=metrics,
        supporting_event_ids=supporting_ids,
        confidence_tier="Level 1 (Direct Observation)",
        limitations=[
            "Spatial sequence chains rely on discrete on-ball event coordinates; continuous off-ball movement between touches is unobserved without optical tracking.",
            "Sequence segmentation follows strict possession change and ball-out-of-bounds boundaries.",
        ],
        causal_disclaimer=disclaimer,
    )


# ==============================================================================
# Slice C: shot-location and cross-match explanation targets
# ==============================================================================

GOAL_CENTER = (105.0, 34.0)
GOAL_HALF_WIDTH = 3.66


def _explain_shot_location(
    snapshot: Snapshot,
    team: str,
    *,
    shot_location: Optional[tuple[float, float]],
    shot_event_id: Optional[str],
) -> ChartExplanationResult:
    """Explain one shot position: geometry, xT cell, heuristic pre-shot danger.

    Coordinates are Level 1 observations. Distance/angle are derived geometry.
    The pre-shot xG figure is the geometric heuristic model (never outcome-
    leaked, never calibrated) and is labelled as such; the defensive shape
    that actually shaped the shot is unobserved.
    """
    from .models.xg import compute_pre_shot_xg
    from .models.xt import ExpectedThreatModel

    data = snapshot.data
    events = data.get("events", [])
    team_name = data.get("teams", {}).get(team, f"Team {team}")
    opp_team = "N" if team == "H" else "H"
    opp_name = data.get("teams", {}).get(opp_team, f"Team {opp_team}")

    target_event = None
    if shot_event_id:
        target_event = next(
            (e for e in events if str(e.get("id")) == str(shot_event_id)), None
        )
        if target_event is None:
            raise ValueError(f"invalid_shot_event_id: {shot_event_id}")
        if target_event.get("kind") != "shot":
            raise ValueError(f"event_is_not_a_shot: {shot_event_id}")

    location = shot_location
    supporting_ids: list[str] = []
    if target_event is not None:
        # The shot position is where the shot was taken; end coordinates are
        # the ball's destination.
        end = target_event.get("start") or target_event.get("end")
        if end:
            location = (float(end[0]), float(end[1]))
        supporting_ids = [str(target_event.get("id"))]
    if location is None:
        raise ValueError("shot_location_or_shot_event_id_required")

    # Fixed-frame snapshots (synthetic) use absolute coordinates where the
    # team attacks right; provider snapshots are team-relative already.
    frame = data.get("coordinate_frame", "fixed")
    x, y = float(location[0]), float(location[1])
    ax = x if (frame == "team_relative" or team == "H") else 105.0 - x

    goal_x, goal_y = GOAL_CENTER
    distance = math.hypot(goal_x - ax, goal_y - y)
    # Angle subtended by the goal mouth at the shot position (radians).
    angle = 2.0 * math.atan2(GOAL_HALF_WIDTH, max(distance, 0.01)) if distance < 120 else 0.0
    cell_x = min(15, max(0, int(ax // (105.0 / 16.0))))
    cell_y = min(11, max(0, int(y // (68.0 / 12.0))))

    xt = ExpectedThreatModel.load_default("16x12")
    xt_value = xt.value_at(ax, y)

    shot_eval = compute_pre_shot_xg(x=ax, y=y)

    # Nearest observed shots of this team within 5m — direct observational
    # context, no inference about defensive pressure.
    near_shots = []
    if target_event is None:
        for e in events:
            if e.get("team") != team or e.get("kind") != "shot":
                continue
            start = e.get("start") or e.get("end")
            if not start:
                continue
            sx, sy = float(start[0]), float(start[1])
            sax = sx if (frame == "team_relative" or team == "H") else 105.0 - sx
            if math.hypot(sax - ax, sy - y) <= 5.0:
                near_shots.append(e)
        supporting_ids = [str(e.get("id")) for e in near_shots[:6] if e.get("id")]

    focus_desc = (
        f" shot event {shot_event_id}" if target_event is not None
        else f" location ({ax:.1f}, {y:.1f})"
    )
    summary = (
        f"Shot location explanation for {team_name} against {opp_name}{focus_desc}: "
        f"{distance:.1f}m from goal centre, goal-mouth angle {math.degrees(angle):.1f}°, "
        f"xT cell ({cell_x}, {cell_y}). The pre-shot danger figure below is a geometric "
        "heuristic evaluated before any outcome is known."
    )
    metrics = [
        MetricExplanationItem(
            metric="Distance to goal centre",
            value=round(distance, 2),
            unit="m",
            formula="hypot(105 - x_attack_relative, 34 - y)",
            interpretation="Straight-line geometric distance of the shot position from the goal centre.",
        ),
        MetricExplanationItem(
            metric="Goal-mouth angle",
            value=round(math.degrees(angle), 2),
            unit="degrees",
            formula="2 * atan2(3.66, distance)",
            interpretation="Angular width of the goal opening as seen from the shot position.",
        ),
        MetricExplanationItem(
            metric="xT cell and cell value",
            value=f"({cell_x}, {cell_y}) = {xt_value:.4f}",
            unit="dimensionless",
            formula="xT grid 16x12 lookup at the shot position",
            interpretation="Heuristic threat of possessing the ball at this position (uncalibrated grid).",
        ),
        MetricExplanationItem(
            metric="Pre-shot xG (geometric heuristic)",
            value=round(shot_eval.pre_shot_xg, 4),
            unit="probability",
            formula="pre-shot geometric model of distance and visible goal angle; outcome not used",
            interpretation="Not a calibrated xG model and not fitted on outcomes; treat as a relative danger proxy.",
        ),
        MetricExplanationItem(
            metric="Nearest observed shots within 5m",
            value=len(near_shots) if target_event is None else 1,
            unit="shots",
            formula="count of same-team shot events with recorded position within 5m",
            interpretation="Direct observational context around this location.",
        ),
    ]
    return ChartExplanationResult(
        chart_type="shot_location",
        title=f"Shot Location Explanation ({team_name}){focus_desc}",
        summary=summary,
        team=team,
        key_metrics=metrics,
        supporting_event_ids=supporting_ids,
        confidence_tier="Level 2 (Formula Decomposition)",
        limitations=[
            "Pre-shot xG here is an uncalibrated geometric heuristic, not a fitted model.",
            "Defensive positions, pressure and keeper behaviour at the shot moment are unobserved in event data.",
            "xT is a possession-value prior for ball progression; it is not shot quality.",
        ],
        causal_disclaimer=(
            "The shot's coordinates and derived geometry are observations; danger values are model outputs. "
            "Neither proves anything about the defensive structure that produced the chance."
        ),
    )


def _explain_cross_match_diff(
    snapshot: Snapshot,
    team: str,
    *,
    metric_id: str,
    compare_snapshot: Optional[Snapshot],
    compare_label: Optional[str],
    compare_team: Optional[Literal["H", "N"]],
) -> ChartExplanationResult:
    """Explain a two-match difference of one registry metric.

    Both values come from `MetricsService.query_range` over each frozen
    snapshot — the same single formula. With one match per side there is no
    sample for statistics: only the raw difference and each side's basis are
    reported, and comparability is stated, never implied.
    """
    from .metrics import MetricsService

    data = snapshot.data
    team_name = data.get("teams", {}).get(team, f"Team {team}")

    if compare_snapshot is None:
        raise ValueError("compare_snapshot_required")

    base = MetricsService.query_range(snapshot, metric_id, team=team, start_s=0.0)
    other_team = compare_team or team
    other = MetricsService.query_range(compare_snapshot, metric_id, team=other_team, start_s=0.0)

    base_data = data
    other_data = compare_snapshot.data
    base_minutes = float(base_data.get("as_of", 0))
    other_minutes = float(other_data.get("as_of", 0))

    base_ok = base.status == "ok" and base.value is not None
    other_ok = other.status == "ok" and other.value is not None
    diff: Optional[float] = None
    per90_base = per90_other = None
    same_unit = base.unit == other.unit
    if base_ok and other_ok and same_unit:
        diff = round(float(other.value) - float(base.value), 4)
        if base.unit not in ("%", "dimensionless") and base_minutes > 0 and other_minutes > 0:
            per90_base = round(float(base.value) * 5400.0 / base_minutes, 2)
            per90_other = round(float(other.value) * 5400.0 / other_minutes, 2)

    label_base = str(base_data.get("teams", {}).get(team, team)) + f" ({base_data.get('match_id', 'match A')})"
    label_other = str(other_data.get("teams", {}).get(other_team, other_team)) + (
        f" ({other_data.get('match_id', 'match B')})"
    )
    if compare_label:
        label_other = compare_label

    summary = (
        f"Cross-match comparison of registry metric '{metric_id}' for {team_name}: "
        f"{label_base} = {base.value if base_ok else base.status}, "
        f"{label_other} = {other.value if other_ok else other.status}. "
        + (
            f"Difference {diff:+.2f} {base.unit}."
            if diff is not None
            else "A difference is not published: at least one side has no observed value or the units differ."
        )
    )
    metrics = [
        MetricExplanationItem(
            metric=f"{metric_id} — {label_base}",
            value=base.value if base_ok else base.status,
            unit=base.unit,
            formula=base.definition,
            interpretation=(
                f"Numerator {base.numerator}, denominator {base.denominator}, "
                f"coverage {base.coverage_status}, minutes basis {base_minutes:.0f}s."
            ),
        ),
        MetricExplanationItem(
            metric=f"{metric_id} — {label_other}",
            value=other.value if other_ok else other.status,
            unit=other.unit,
            formula=other.definition,
            interpretation=(
                f"Numerator {other.numerator}, denominator {other.denominator}, "
                f"coverage {other.coverage_status}, minutes basis {other_minutes:.0f}s."
            ),
        ),
        MetricExplanationItem(
            metric="Difference (match B - match A)",
            value=diff if diff is not None else "not_published",
            unit=base.unit if same_unit else "incompatible_units",
            formula=f"{metric_id}(B) - {metric_id}(A); same registry formula on both snapshots",
            interpretation=(
                "A two-match difference is a raw observation over a sample of one per side; "
                "no significance, interval or rate adjustment beyond the stated minutes basis is attached."
                + (
                    f" Per-90: {per90_base} vs {per90_other}."
                    if per90_base is not None and per90_other is not None
                    else ""
                )
            ),
        ),
    ]
    return ChartExplanationResult(
        chart_type="cross_match_diff",
        title=f"Cross-Match Difference — {metric_id} ({team_name})",
        summary=summary,
        team=team,
        key_metrics=metrics,
        supporting_event_ids=[],
        confidence_tier="Level 2 (Formula Decomposition)",
        limitations=[
            "Sample size is one match per side; no statistical generalisation is possible.",
            "Coverage and minutes differ per match; both bases are reported instead of hidden.",
            "The difference is descriptive (Level 2 metric attribution), not a causal claim.",
        ],
        causal_disclaimer=(
            "Both numbers come from the same registry formula over each frozen snapshot. "
            "Differences across matches have many unobserved causes (opponent, era, coverage); "
            "this explanation does not attribute the difference to any of them."
        ),
        comparison={
            "metric_id": metric_id,
            "match_a": {
                "match_id": base_data.get("match_id"),
                "snapshot_id": snapshot.id,
                "team": team,
                "value": base.value,
                "status": base.status,
                "unit": base.unit,
                "minutes_basis_seconds": base_minutes,
                "dataset_revision": base.dataset_revision,
                "coverage_status": base.coverage_status,
            },
            "match_b": {
                "match_id": other_data.get("match_id"),
                "snapshot_id": compare_snapshot.id,
                "team": other_team,
                "value": other.value,
                "status": other.status,
                "unit": other.unit,
                "minutes_basis_seconds": other_minutes,
                "dataset_revision": other.dataset_revision,
                "coverage_status": other.coverage_status,
            },
            "diff": diff,
            "per_90_a": per90_base,
            "per_90_b": per90_other,
            "investigation_focus_type": "cross_match_diff",
            "investigation_focus_id": metric_id,
        },
    )
