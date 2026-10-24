"""Interactive Football Exploration Engine (Track B).

Implements Backlog items defined in Section 7.1 of docs/FOOTBALL_INTELLIGENCE_PLATFORMS_2026.md:
- BL-03: Quick ball recovery within 6 seconds (parameterized window, observable fact, no counter-press claim)
- BL-04: Team Action Density Differential (Delta D(z) = n_home(z)/N_home - n_away(z)/N_away, high-overlap identification)
- BL-08: Attacking Channel Analysis (Left, Center, Right progression penetration & box conversion)
- S2 x S3 Spatial-Sequence Dual Drilldown (bidirectional linking between 9-zone cells and possession sequences)
- BL-12: Highlight Locator (combining OAAI turning points and S2 sequence indexing to locate key attacking waves)
"""
from __future__ import annotations

import math
from typing import Any, Optional, Sequence

from .football import PLAYERS, TEAMS, attack_x, channel_name
from .oaai import OAAIConfig, compute_oaai, _normalize_event_view


def _atk_x(ev: dict, team: str, point: str = "start") -> Optional[float]:
    coords = ev.get(point)
    if not coords or coords[0] is None:
        return None
    return float(coords[0]) if ev.get("frame") == "team_relative" else attack_x(team, float(coords[0]))


def _chan(ev: dict, team: str, point: str = "start") -> Optional[str]:
    coords = ev.get(point)
    if not coords or coords[1] is None:
        return None
    y = float(coords[1])
    if 22.67 <= y <= 45.33:
        return "center"
    if ev.get("frame") == "team_relative":
        return "left" if y > 45.33 else "right"
    return channel_name(team, y)


# Pitch dimensions & 9-zone definition (3 thirds x 3 channels)
PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0

DEFAULT_ZONE_SPECS = [
    # (x_idx, (x_min, x_max), y_idx, (y_min, y_max))
    (0, (0.0, 35.0), 0, (0.0, 22.67)),
    (0, (0.0, 35.0), 1, (22.67, 45.33)),
    (0, (0.0, 35.0), 2, (45.33, 68.0)),
    (1, (35.0, 70.0), 0, (0.0, 22.67)),
    (1, (35.0, 70.0), 1, (22.67, 45.33)),
    (1, (35.0, 70.0), 2, (45.33, 68.0)),
    (2, (70.0, 105.0), 0, (0.0, 22.67)),
    (2, (70.0, 105.0), 1, (22.67, 45.33)),
    (2, (70.0, 105.0), 2, (45.33, 68.0)),
]


def _point_in_zone(x: float, y: float, cell: dict) -> bool:
    """Checks whether (x, y) coordinates fall within a zone cell boundary."""
    return cell["x_min"] <= x <= cell["x_max"] and cell["y_min"] <= y <= cell["y_max"]


def _segment_intersects_zone(p1: tuple[float, float], p2: tuple[float, float], cell: dict) -> bool:
    """Checks whether a pass or movement line segment p1 -> p2 intersects or starts/ends in a zone."""
    x1, y1 = p1
    x2, y2 = p2
    # Check endpoints
    if _point_in_zone(x1, y1, cell) or _point_in_zone(x2, y2, cell):
        return True

    # Sample intermediate points along the segment
    for alpha in (0.25, 0.5, 0.75):
        xm = x1 + alpha * (x2 - x1)
        ym = y1 + alpha * (y2 - y1)
        if _point_in_zone(xm, ym, cell):
            return True

    return False


# ==============================================================================
# BL-03: Quick Ball Recovery within 6s
# ==============================================================================

def analyze_quick_recoveries(
    events: Sequence[Any],
    window_seconds: float = 6.0,
    target_team: Optional[str] = None,
) -> dict:
    """Analyzes quick ball recoveries occurring within a parameterized window (default 6s) after possession loss.

    Conforms to BL-03:
    - Parameterized window (default 6s, configurable)
    - Observable event frequency without subjective claims
    - Strictly forbidden from asserting "organized counter-pressing"
    """
    norm_events = [_normalize_event_view(e) for e in events if _normalize_event_view(e)["kind"] != "end"]
    norm_events.sort(key=lambda e: (e["t"], e["id"]))

    teams = [target_team] if target_team in ("H", "N") else ["H", "N"]
    results_by_team: dict[str, dict] = {}

    for team in teams:
        losses: list[dict] = []
        recoveries_found: list[dict] = []
        n = len(norm_events)

        for i in range(n - 1):
            curr_ev = norm_events[i]
            next_ev = norm_events[i + 1]

            # Detect possession turnover from team to opponent
            is_turnover = False
            if curr_ev["team"] == team:
                if next_ev["team"] != team:
                    is_turnover = True
                elif curr_ev["kind"] == "turnover":
                    is_turnover = True

            if is_turnover:
                loss_t = curr_ev["t"]
                loss_loc = curr_ev["end"]
                loss_record = {
                    "loss_event_id": curr_ev["id"],
                    "loss_t": loss_t,
                    "loss_location": loss_loc,
                    "recovered": False,
                    "recovery_event": None,
                }
                losses.append(loss_record)

                # Look forward within [loss_t, loss_t + window_seconds]
                for j in range(i + 1, n):
                    cand = norm_events[j]
                    dt = cand["t"] - loss_t
                    if dt > window_seconds:
                        break
                    if dt < 0:
                        continue

                    # Check if team re-gains possession
                    if cand["team"] == team and cand["kind"] in ("recovery", "pass", "shot"):
                        ax = _atk_x(cand, team)
                        ch = _chan(cand, team)
                        third = (
                            "unknown" if ax is None
                            else "attacking" if ax >= 70.0
                            else "middle" if ax >= 35.0
                            else "defensive"
                        )

                        recovery_item = {
                            "recovery_event_id": cand["id"],
                            "loss_event_id": curr_ev["id"],
                            "loss_t": loss_t,
                            "recovery_t": cand["t"],
                            "elapsed_seconds": round(dt, 2),
                            "actor": cand["actor"],
                            "actor_name": PLAYERS.get(team, {}).get(cand["actor"], cand["actor"]),
                            "location": cand["start"],
                            "attack_x": round(ax, 1) if ax is not None else None,
                            "channel": ch,
                            "third": third,
                            "is_high_recovery": ax is not None and ax >= 70.0,
                        }
                        recoveries_found.append(recovery_item)
                        loss_record["recovered"] = True
                        loss_record["recovery_event"] = recovery_item
                        break

        total_losses = len(losses)
        rec_count = len(recoveries_found)
        rate = round((rec_count / total_losses * 100.0), 1) if total_losses > 0 else 0.0

        third_counts = {"attacking": 0, "middle": 0, "defensive": 0, "unknown": 0}
        channel_counts = {"left": 0, "center": 0, "right": 0, "unknown": 0}
        for r in recoveries_found:
            third_counts[r["third"]] += 1
            if r["channel"]:
                channel_counts[r["channel"]] += 1
            else:
                channel_counts["unknown"] += 1

        results_by_team[team] = {
            "team": team,
            "team_name": TEAMS.get(team, team),
            "window_seconds": window_seconds,
            "total_possession_losses": total_losses,
            "quick_recoveries_count": rec_count,
            "quick_recovery_rate": rate,
            "spatial_distribution_thirds": third_counts,
            "spatial_distribution_channels": channel_counts,
            "recoveries": recoveries_found,
            "high_recoveries_count": sum(1 for r in recoveries_found if r["is_high_recovery"]),
        }

    return {
        "window_seconds": window_seconds,
        "teams": results_by_team,
        "disclaimer": "严格作为失去球权后的可观察统计，严禁宣称'有组织反抢'或主观战术意图 (Level 1 观察事实)。",
    }


# ==============================================================================
# BL-04: Team Action Density Differential
# ==============================================================================

def analyze_action_density_differential(
    events: Sequence[Any],
    overlap_threshold: float = 0.08,
) -> dict:
    """Calculates action density differential between home and away teams across 9 pitch zones:

    Delta D(z) = n_home(z) / N_home - n_away(z) / N_away

    Conforms to BL-04:
    - Proportion-based spatial differential
    - Identifies high-density overlap zones
    - Strictly disclaims physical duels or pitch control.
    """
    norm_events = [
        e for e in (_normalize_event_view(e) for e in events)
        if e["kind"] != "end" and e.get("start") is not None
    ]
    home_events = [e for e in norm_events if e["team"] == "H"]
    away_events = [e for e in norm_events if e["team"] == "N"]

    n_home_total = max(1, len(home_events))
    n_away_total = max(1, len(away_events))

    differential_cells: list[dict] = []
    overlap_count = 0

    for x_idx, (x_min, x_max), y_idx, (y_min, y_max) in DEFAULT_ZONE_SPECS:
        cell_id = f"zone-{x_idx}-{y_idx}"
        y_mid = (y_min + y_max) / 2.0
        x_mid = (x_min + x_max) / 2.0

        # Actions inside this zone
        h_in_cell = [e for e in home_events if x_min <= e["start"][0] <= x_max and y_min <= e["start"][1] <= y_max]
        a_in_cell = [e for e in away_events if x_min <= e["start"][0] <= x_max and y_min <= e["start"][1] <= y_max]

        h_count = len(h_in_cell)
        a_count = len(a_in_cell)

        h_share = h_count / n_home_total
        a_share = a_count / n_away_total
        delta_d = round(h_share - a_share, 4)

        # High-density overlap: both teams conduct a significant fraction of their actions in this zone
        is_overlap = (h_share >= overlap_threshold and a_share >= overlap_threshold)
        if is_overlap:
            overlap_count += 1

        th_name = "Defensive" if x_idx == 0 else ("Middle" if x_idx == 1 else "Attacking")
        ch_name = "Right" if y_idx == 0 else ("Center" if y_idx == 1 else "Left")

        advantage = "home" if delta_d > 0.015 else ("away" if delta_d < -0.015 else "neutral")

        differential_cells.append({
            "cell_id": cell_id,
            "name": f"{th_name} {ch_name}",
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "home_actions_count": h_count,
            "away_actions_count": a_count,
            "home_action_share": round(h_share * 100.0, 1),
            "away_action_share": round(a_share * 100.0, 1),
            "delta_density": delta_d,
            "delta_density_pct": round(delta_d * 100.0, 1),
            "advantage": advantage,
            "is_high_density_overlap": is_overlap,
        })

    return {
        "home_total_actions": n_home_total,
        "away_total_actions": n_away_total,
        "overlap_threshold_pct": round(overlap_threshold * 100.0, 1),
        "overlap_zones_count": overlap_count,
        "zones": differential_cells,
        "disclaimer": "两队在球场各区域的行动占比差分；不标记真实争夺或物理对抗强度 (Level 1 可观察统计)。",
    }


# ==============================================================================
# BL-08: Attacking Channels Analysis
# ==============================================================================

def analyze_attacking_channels(
    events: Sequence[Any],
    sequences: Optional[list[dict]] = None,
    team: str = "H",
    *,
    team_name: Optional[str] = None,
    coordinate_frame: str = "fixed",
) -> dict:
    """Analyzes left, center, and right attacking channels for progression penetration and penalty box conversion.

    Conforms to BL-08:
    - Distinguishes Left, Center, Right channels based on attack direction
    - Measures forward progressive penetration
    - Measures penalty box touch / shot conversion rate.
    """
    team = "N" if team == "N" else "H"
    norm_events = [_normalize_event_view(e) for e in events if _normalize_event_view(e)["team"] == team]

    channels_data: dict[str, dict] = {
        "left": {"attacks_count": 0, "progression_meters": 0.0, "final_third_entries": 0, "box_touches": 0, "shots": 0},
        "center": {"attacks_count": 0, "progression_meters": 0.0, "final_third_entries": 0, "box_touches": 0, "shots": 0},
        "right": {"attacks_count": 0, "progression_meters": 0.0, "final_third_entries": 0, "box_touches": 0, "shots": 0},
    }

    # Evaluate sequence-level progression if sequences are provided
    if sequences:
        for seq in sequences:
            if seq.get("team") != team:
                continue
            start_coords = seq.get("start_coords")
            if not start_coords or start_coords[1] is None:
                continue
            start_y = start_coords[1]
            frame = "team_relative" if seq.get("coordinate_frame") == "team_relative" else "fixed"
            ch = (
                "center" if 22.67 <= start_y <= 45.33
                else ("left" if start_y > 45.33 else "right") if frame == "team_relative"
                else channel_name(team, start_y)
            )
            channels_data[ch]["attacks_count"] += 1
            channels_data[ch]["progression_meters"] += float(seq.get("progressive_distance", 0.0))
            if seq.get("entered_final_third", False):
                channels_data[ch]["final_third_entries"] += 1

            # Check if any event in sequence entered penalty box or shot
            details = seq.get("events_detail", [])
            has_box = False
            has_shot = False
            for step in details:
                if not step.get("end"):
                    continue
                ex, ey = step["end"]
                ax_end = ex if step.get("coordinate_frame") == "team_relative" else attack_x(team, ex)
                if ax_end >= 88.5 and 13.84 <= ey <= 54.16:
                    has_box = True
                if step.get("kind") == "shot":
                    has_shot = True
            if has_box:
                channels_data[ch]["box_touches"] += 1
            if has_shot:
                channels_data[ch]["shots"] += 1
    else:
        # Fallback to discrete event stream aggregation
        for ev in norm_events:
            ch = _chan(ev, team)
            if ch is None:
                continue
            channels_data[ch]["attacks_count"] += 1
            ax_s = _atk_x(ev, team, "start")
            ax_e = _atk_x(ev, team, "end")
            if ax_s is None or ax_e is None:
                continue
            channels_data[ch]["progression_meters"] += max(0.0, ax_e - ax_s)
            if ax_s <= 70.0 < ax_e:
                channels_data[ch]["final_third_entries"] += 1
            end = ev.get("end")
            if ax_e >= 88.5 and end and end[1] is not None and 13.84 <= end[1] <= 54.16:
                channels_data[ch]["box_touches"] += 1
            if ev["kind"] == "shot":
                channels_data[ch]["shots"] += 1

    formatted_channels: dict[str, dict] = {}
    for ch_key, data in channels_data.items():
        n_att = max(1, data["attacks_count"])
        final_third_pct = round((data["final_third_entries"] / n_att) * 100.0, 1)
        box_conv_rate = round((data["box_touches"] / n_att) * 100.0, 1)
        formatted_channels[ch_key] = {
            "channel": ch_key,
            "attacks_count": data["attacks_count"],
            "total_progression_meters": round(data["progression_meters"], 1),
            "final_third_entries_count": data["final_third_entries"],
            "final_third_penetration_rate": final_third_pct,
            "penalty_box_entries_count": data["box_touches"],
            "box_conversion_rate": box_conv_rate,
            "shots_count": data["shots"],
        }

    return {
        "team": team,
        "team_name": team_name or TEAMS.get(team, team),
        "attack_direction": "team_relative" if coordinate_frame == "team_relative" else ("right" if team == "H" else "left"),
        "channels": formatted_channels,
        "disclaimer": "进攻通道渗透与禁区触球转化率；通道以进攻方向划分 (Level 1 观察统计)。",
    }


# ==============================================================================
# S2 x S3 Spatial-Sequence Dual Drilldown Helper
# ==============================================================================

def build_spatial_sequence_drilldown(
    sequences: list[dict],
    zone_cells: Optional[list[dict]] = None,
) -> dict:
    """Precomputes bidirectional drilldown indices between S2 sequences and S3 9-zone cells.

    - zone_to_sequences[cell_id]: list of sequence IDs that intersect or pass through the zone
    - sequence_to_zones[sequence_id]: list of zone cell IDs traversed by that sequence.
    """
    cells = zone_cells or [
        {
            "cell_id": f"zone-{x_idx}-{y_idx}",
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
        }
        for x_idx, (x_min, x_max), y_idx, (y_min, y_max) in DEFAULT_ZONE_SPECS
    ]

    zone_to_sequences: dict[str, list[str]] = {c["cell_id"]: [] for c in cells}
    sequence_to_zones: dict[str, list[str]] = {}

    for seq in sequences:
        seq_id = seq["sequence_id"]
        traversed_zones: set[str] = set()

        details = seq.get("events_detail", [])
        if details:
            for step in details:
                if not step.get("start") or not step.get("end"):
                    continue
                p1 = tuple(step["start"])
                p2 = tuple(step["end"])
                for c in cells:
                    if _segment_intersects_zone(p1, p2, c):
                        traversed_zones.add(c["cell_id"])
        else:
            if not seq.get("start_coords") or not seq.get("end_coords"):
                sequence_to_zones[seq_id] = []
                continue
            p1 = tuple(seq["start_coords"])
            p2 = tuple(seq["end_coords"])
            for c in cells:
                if _segment_intersects_zone(p1, p2, c):
                    traversed_zones.add(c["cell_id"])

        traversed_list = sorted(list(traversed_zones))
        sequence_to_zones[seq_id] = traversed_list

        for zid in traversed_list:
            if zid in zone_to_sequences:
                zone_to_sequences[zid].append(seq_id)

    return {
        "zone_to_sequences": zone_to_sequences,
        "sequence_to_zones": sequence_to_zones,
        "total_indexed_sequences": len(sequences),
        "total_indexed_zones": len(cells),
    }


# ==============================================================================
# BL-12: Highlight Locator
# ==============================================================================

def locate_highlights(
    events: Sequence[Any],
    sequences: list[dict],
    oaai_data: Optional[dict] = None,
    max_highlights: int = 6,
    *,
    team_names: Optional[dict[str, str]] = None,
) -> list[dict]:
    """Automatically locates core match attacking waves and candidate highlights.

    Combines:
    - OAAI momentum surges and turning points (BL-02)
    - High-progression / transition sequences (S2)
    - Goals and high-xG shot attempts.
    """
    candidates: list[dict] = []
    norm_events = [_normalize_event_view(e) for e in events]
    norm_events.sort(key=lambda e: (e["t"], e["id"]))

    seq_map = {sq["sequence_id"]: sq for sq in sequences}
    names = team_names or TEAMS

    # 1. Goal Sequences (Highest priority)
    for sq in sequences:
        if sq.get("outcome") == "goal":
            candidates.append({
                "highlight_id": f"HL-{len(candidates)+1:02d}",
                "title": f"Goal Wave: {names.get(sq["team"], sq["team"])} Goal Execution",
                "team": sq["team"],
                "start_t": sq["start_t"],
                "end_t": sq["end_t"],
                "peak_t": sq["end_t"],
                "impact_score": 10.0,
                "category": "goal",
                "associated_sequence_ids": [sq["sequence_id"]],
                "key_event_ids": sq.get("event_ids", []),
                "claim_level": 1,  # Level 1 Observable Fact
                "description": f"{names.get(sq["team"], sq["team"])} completed a scoring sequence with {sq.get('pass_count', 0)} passes gaining {sq.get('territory_gained', 0)}m.",
            })

    # 2. Key Shot Attempts
    for sq in sequences:
        if sq.get("outcome") == "shot_saved" and sq.get("sequence_id") not in [c["associated_sequence_ids"][0] for c in candidates if c.get("associated_sequence_ids")]:
            candidates.append({
                "highlight_id": f"HL-{len(candidates)+1:02d}",
                "title": f"Shot Chance: {names.get(sq["team"], sq["team"])} Target Effort",
                "team": sq["team"],
                "start_t": sq["start_t"],
                "end_t": sq["end_t"],
                "peak_t": sq["end_t"],
                "impact_score": 7.5,
                "category": "shot",
                "associated_sequence_ids": [sq["sequence_id"]],
                "key_event_ids": sq.get("event_ids", []),
                "claim_level": 1,
                "description": f"Dangerous transition ending in a saved effort ({sq.get('progressive_distance', 0)}m progressive distance).",
            })

    # 3. OAAI Turning Point Waves
    if oaai_data and "change_points" in oaai_data:
        for cp in oaai_data["change_points"]:
            cp_t = cp["at"]
            # Find closest sequence in time
            surrounding_seqs = [
                sq for sq in sequences
                if sq["start_t"] <= cp_t <= sq["end_t"] or abs(sq["end_t"] - cp_t) <= 12.0
            ]
            assoc_ids = [sq["sequence_id"] for sq in surrounding_seqs[:2]]
            amp = abs(cp.get("oaai_amplitude", 0.0))
            team = cp.get("leading_team", "H")
            candidates.append({
                "highlight_id": f"HL-{len(candidates)+1:02d}",
                "title": f"Activity Surge ({names.get(team, team)} Momentum Shift)",
                "team": team,
                "start_t": max(0.0, cp_t - 25.0),
                "end_t": cp_t + 5.0,
                "peak_t": cp_t,
                "impact_score": round(5.0 + amp * 3.0, 1),
                "category": "oaai_surge",
                "associated_sequence_ids": assoc_ids,
                "key_event_ids": [tc["event_id"] for tc in cp.get("top_contributors", [])],
                "claim_level": 2,  # Level 2 Metric Attribution
                "description": f"OAAI reached peak shift of {amp:.2f} driven by {len(cp.get('top_contributors', []))} high-contribution events.",
            })

    # Sort candidates by impact score descending
    candidates.sort(key=lambda h: h["impact_score"], reverse=True)

    # De-duplicate time-overlapping highlights within 15 seconds
    deduped: list[dict] = []
    for c in candidates:
        if not any(abs(c["peak_t"] - d["peak_t"]) < 18.0 for d in deduped):
            c["highlight_id"] = f"HL-{len(deduped)+1:02d}"
            deduped.append(c)
        if len(deduped) >= max_highlights:
            break

    return deduped
