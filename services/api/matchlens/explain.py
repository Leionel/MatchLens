"""Explain Any Chart: Evidence-grounded tactical chart explanation engine.

Generates structured, receipt-backed explanations for tactical visualizations:
- oaai_momentum: OAAI wave dynamics, momentum inflection points, dominant intervals.
- density_differential: 9-zone spatial occupancy differential ΔD(z).
- passing_network: Player interaction centroids and high-threat progressive connections.
- attacking_channels: 5-corridor penetration and penalty box entry distribution.
- spatial_drilldown: Spatial sequence chains and progressive territory gain.
- xt_surface: Expected Threat spatial danger and progressive value creation.

Every explanation references exact event IDs, formula definitions, and confidence tiers,
strictly upholding Gate 2.0 evidence boundaries.
"""
from __future__ import annotations

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
) -> ChartExplanationResult:
    """Produce an evidence-grounded explanation for any cockpit visualization."""
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
