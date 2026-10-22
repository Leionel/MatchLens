"""Pre-shot heuristic shot danger and uncalibrated opportunity quality estimation.

Strictly enforces pre-shot feature observation:
- Features used: distance to goal center (105, 34), visible goal angle.
- Outcome leakage strictly prohibited: a goal outcome MUST NOT elevate pre-shot probability.
- Clearly distinguishes:
  1. Actual Goals
  2. Recorded Shots
  3. Heuristic Shot Danger
  4. Model-estimated xG (Calibrated)
"""
from __future__ import annotations

import math
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ShotDangerMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    xg_model_version: str = "heuristic-pre-shot-v1.0"
    xg_source: Literal["heuristic_shot_danger", "fitted_logistic_model"] = "heuristic_shot_danger"
    features_used: list[str] = Field(default_factory=lambda: ["distance_to_goal", "angle_to_goal"])
    calibration_status: Literal["uncalibrated_heuristic", "calibrated"] = "uncalibrated_heuristic"
    training_data: Optional[str] = None
    evaluation_metrics: Optional[dict[str, float]] = None
    missingness_status: Literal["observed_coordinates", "default_fallback", "missing_coordinates"] = "observed_coordinates"


class ShotEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    pre_shot_xg: float
    distance_meters: Optional[float] = None
    angle_degrees: Optional[float] = None
    is_goal: bool
    metadata: ShotDangerMetadata


def compute_pre_shot_xg(
    x: Optional[float],
    y: Optional[float],
    event_id: str = "",
    outcome: Optional[str] = None,
    attack_direction: str = "left_to_right",
) -> ShotEvaluation:
    """Computes pre-shot danger probability using ONLY pre-shot observable features.

    Outcome leakage is strictly forbidden: whether the shot ended as a 'goal',
    'saved', 'blocked', or 'off_target' has ZERO effect on pre_shot_xg.
    """
    is_goal = str(outcome or "").lower() == "goal"

    if x is None or y is None:
        meta = ShotDangerMetadata(
            missingness_status="missing_coordinates",
            calibration_status="uncalibrated_heuristic",
        )
        return ShotEvaluation(
            event_id=event_id,
            pre_shot_xg=0.08,  # baseline empirical average for unlocalized shots
            distance_meters=None,
            angle_degrees=None,
            is_goal=is_goal,
            metadata=meta,
        )

    # Goal line center is at (105, 34) in standard 105x68 coordinates
    goal_x = 105.0 if attack_direction == "left_to_right" else 0.0
    goal_y = 34.0
    post_y1 = 30.34  # 7.32m goal mouth -> 34 - 3.66
    post_y2 = 37.66  # 34 + 3.66

    dx = abs(goal_x - float(x))
    dy = abs(goal_y - float(y))
    dist = math.sqrt(dx * dx + dy * dy)

    # Visible goal angle computation
    d1 = math.sqrt(dx * dx + (float(y) - post_y1) ** 2)
    d2 = math.sqrt(dx * dx + (float(y) - post_y2) ** 2)
    goal_width = 7.32

    if d1 * d2 > 1e-4:
        cos_theta = max(-1.0, min(1.0, (d1 * d1 + d2 * d2 - goal_width * goal_width) / (2.0 * d1 * d2)))
        angle_rad = math.acos(cos_theta)
        angle_deg = math.degrees(angle_rad)
    else:
        angle_deg = 180.0

    # Danger decays exponentially with distance, scales monotonically with visible angle
    # Bound within [0.015, 0.82]
    # NOTE: NO dependency on outcome!
    base_prob = math.exp(-0.095 * dist)
    angle_factor = min(1.0, max(0.12, angle_deg / 45.0))
    val = round(max(0.015, min(0.82, 0.85 * base_prob * angle_factor)), 3)

    meta = ShotDangerMetadata(
        missingness_status="observed_coordinates",
        calibration_status="uncalibrated_heuristic",
    )
    return ShotEvaluation(
        event_id=event_id,
        pre_shot_xg=val,
        distance_meters=round(dist, 2),
        angle_degrees=round(angle_deg, 1),
        is_goal=is_goal,
        metadata=meta,
    )
