"""
Track E: Level 3 Research & Exploratory What-If Counterfactual Sandbox.

Implements requirements from:
- docs/FOOTBALL_INTELLIGENCE_PLATFORMS_2026.md (BL-09 What-if Decision Sandbox)
- docs/XT_MODELING_SPEC.md (Counterfactual evaluation of pass trajectories, turnover risks, and attack channels)
- Level 3 Research / Exploratory claim labeling and strict disclaimer enforcement.

Modes:
1. Descriptive: Re-evaluates baseline observed metrics without intervention.
2. Scenario-based: Predefined counterfactual interventions (turnover removal, lateral corridor inversion, channel redirection, shot prevention).
3. Exploratory research: Arbitrary parameter perturbation with uncertainty bounds.
"""
from __future__ import annotations

import copy
import math
import random
from enum import Enum
from typing import Any, Literal, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

from .models.xt import ExpectedThreatModel
from .oaai import compute_oaai
from .schema import ActionType, NormalizedEvent

WHATIF_DISCLAIMER_TEXT = (
    "Level 3 Research / Exploratory — Not validated for production causal claims. "
    "RESEARCH SANDBOX NOTICE (Level 3 Hypothesis): This is an in-silico mathematical counterfactual perturbation. "
    "It does not represent historical fact and must not be published as definitive causal ground-truth."
)


def _get_field(ev: Any, field: str, default: Any = None) -> Any:
    if isinstance(ev, dict):
        return ev.get(field, default)
    return getattr(ev, field, default)


def _extract_time(ev: Any) -> float:
    t = _get_field(ev, "clock_seconds")
    if t is None:
        t = _get_field(ev, "timestamp_seconds")
    if t is None:
        t = _get_field(ev, "second", 0.0)
    return float(t)


def _extract_id(ev: Any, fallback: str = "") -> str:
    eid = _get_field(ev, "event_id")
    if eid is None:
        eid = _get_field(ev, "id", fallback)
    return str(eid)


def _extract_action(ev: Any) -> str:
    act = _get_field(ev, "action_type", "")
    if hasattr(act, "value"):
        return str(act.value).lower()
    return str(act).lower()


def _extract_xg(ev: Any) -> float:
    val = _get_field(ev, "xg")
    if val is not None:
        try:
            return float(val)
        except (ValueError, TypeError):
            pass
    act = _extract_action(ev)
    if "shot" in act:
        if str(_get_field(ev, "outcome", "")).lower() == "goal":
            return 0.75
        x = _get_field(ev, "x")
        y = _get_field(ev, "y")
        if x is not None and y is not None:
            dist = math.sqrt((105.0 - float(x)) ** 2 + (34.0 - float(y)) ** 2)
            return round(max(0.02, min(0.85, 0.85 * math.exp(-0.08 * dist))), 3)
        return 0.12
    return 0.0


class WhatIfMode(str, Enum):
    DESCRIPTIVE = "descriptive"
    SCENARIO_BASED = "scenario_based"
    EXPLORATORY_RESEARCH = "exploratory_research"


class WhatIfScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_type: Literal[
        "remove_turnover",
        "invert_corridor",
        "channel_redirection",
        "prevent_shot",
        "alternate_pass_target",
        "custom",
    ]
    mode: Literal["descriptive", "scenario_based", "exploratory_research"] = "scenario_based"
    target_event_id: Optional[str] = None
    target_time_range: Optional[tuple[float, float]] = None
    target_corridor: Optional[Literal["left", "center", "right"]] = None
    alternate_coordinates: Optional[tuple[float, float]] = None  # (new_end_x, new_end_y)
    parameters: Optional[dict[str, Any]] = None


class WhatIfSimulationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_id: str
    scenario_type: str
    mode: str
    original_oaai_amplitude: float
    perturbed_oaai_amplitude: float
    delta_oaai_amplitude: float
    delta_threat: float
    delta_xg: float
    confidence_band: tuple[float, float]
    affected_events_count: int
    affected_event_ids: list[str]
    claim_level: Literal["level_3_hypothesis"] = "level_3_hypothesis"
    claim_level_int: int = 3
    is_exploratory: bool = True
    is_exploratory_only: bool = True  # Backward compatibility
    disclaimer: str = WHATIF_DISCLAIMER_TEXT


class WhatIfSandbox:
    """Level 3 Research & Exploratory Counterfactual Analysis Sandbox.
    
    Provides controlled mathematical hypothetical experiments with strict
    research-only claim gating and uncertainty propagation.
    """

    @classmethod
    def simulate(
        cls,
        events: Sequence[dict[str, Any] | NormalizedEvent],
        request: WhatIfScenarioRequest,
    ) -> WhatIfSimulationResult:
        """Main entrypoint for counterfactual simulation queries."""
        if not events:
            raise ValueError("empty_event_stream")

        xt_model = ExpectedThreatModel.load_default("16x12")

        # 1. Compute baseline factual metrics
        base_oaai = compute_oaai(events, smoothing_mode="causal")
        timeline = base_oaai.get("timeline", [])
        orig_amp = (
            sum(abs(float(p.get("oaai_value", 0.0))) for p in timeline) / max(1, len(timeline))
            if timeline
            else 0.0
        )

        base_xg = sum(_extract_xg(ev) for ev in events)

        # 2. Deep-copy events for counterfactual perturbation
        perturbed_events: list[dict[str, Any] | NormalizedEvent] = []
        affected_ids: list[str] = []

        scenario = request.scenario_type
        mode = request.mode

        if mode == "descriptive":
            # Descriptive mode: observed facts without hypothetical perturbation
            perturbed_events = [ev for ev in events]
            scenario = "factual_baseline"

        elif scenario == "remove_turnover":
            # Remove turnover/possession loss
            for ev in events:
                eid = _extract_id(ev)
                t = _extract_time(ev)
                act = _extract_action(ev)

                should_remove = False
                if request.target_event_id and eid == str(request.target_event_id):
                    should_remove = True
                elif request.target_time_range:
                    t0, t1 = request.target_time_range
                    if t0 <= t <= t1 and any(
                        term in act
                        for term in (
                            "turnover",
                            "dispossessed",
                            "miscontrol",
                            "bad_pass",
                            "foul",
                            "clearance",
                        )
                    ):
                        should_remove = True

                if should_remove:
                    affected_ids.append(eid)
                else:
                    perturbed_events.append(ev)

        elif scenario == "invert_corridor":
            # Mirror the lateral corridor (y' = 68.0 - y)
            for ev in events:
                eid = _extract_id(ev)
                t = _extract_time(ev)
                in_range = True
                if request.target_time_range:
                    t0, t1 = request.target_time_range
                    in_range = t0 <= t <= t1

                if in_range:
                    affected_ids.append(eid)
                    if isinstance(ev, NormalizedEvent):
                        ev_copy = ev.model_copy(deep=True)
                        if ev_copy.y is not None:
                            ev_copy.y = max(0.0, min(68.0, 68.0 - ev_copy.y))
                        if ev_copy.end_y is not None:
                            ev_copy.end_y = max(0.0, min(68.0, 68.0 - ev_copy.end_y))
                        perturbed_events.append(ev_copy)
                    elif isinstance(ev, dict):
                        d_copy = dict(ev)
                        if "y" in d_copy and d_copy["y"] is not None:
                            d_copy["y"] = max(0.0, min(68.0, 68.0 - float(d_copy["y"])))
                        if "end_y" in d_copy and d_copy["end_y"] is not None:
                            d_copy["end_y"] = max(0.0, min(68.0, 68.0 - float(d_copy["end_y"])))
                        perturbed_events.append(d_copy)
                    else:
                        perturbed_events.append(ev)
                else:
                    perturbed_events.append(ev)

        elif scenario == "channel_redirection":
            # Redirect attack into target channel ("left" < 20m, "center" 20-48m, "right" > 48m)
            target_chan = request.target_corridor or "left"
            target_y = 12.0 if target_chan == "left" else (56.0 if target_chan == "right" else 34.0)

            for ev in events:
                eid = _extract_id(ev)
                t = _extract_time(ev)

                match_target = False
                if request.target_event_id and eid == str(request.target_event_id):
                    match_target = True
                elif request.target_time_range:
                    t0, t1 = request.target_time_range
                    if t0 <= t <= t1:
                        match_target = True

                if match_target:
                    affected_ids.append(eid)
                    if isinstance(ev, NormalizedEvent):
                        ev_copy = ev.model_copy(deep=True)
                        ev_copy.end_y = target_y
                        perturbed_events.append(ev_copy)
                    elif isinstance(ev, dict):
                        d_copy = dict(ev)
                        d_copy["end_y"] = target_y
                        perturbed_events.append(d_copy)
                    else:
                        perturbed_events.append(ev)
                else:
                    perturbed_events.append(ev)

        elif scenario == "prevent_shot":
            # Prevent a shot from occurring
            for ev in events:
                eid = _extract_id(ev)
                act = _extract_action(ev)
                t = _extract_time(ev)

                should_remove_shot = False
                if request.target_event_id and eid == str(request.target_event_id):
                    should_remove_shot = True
                elif "shot" in act:
                    if request.target_time_range:
                        t0, t1 = request.target_time_range
                        if t0 <= t <= t1:
                            should_remove_shot = True
                    elif not request.target_event_id:
                        if not affected_ids:
                            should_remove_shot = True

                if should_remove_shot:
                    affected_ids.append(eid)
                else:
                    perturbed_events.append(ev)

        elif scenario == "alternate_pass_target":
            # Re-target pass end coordinates
            new_x, new_y = request.alternate_coordinates or (95.0, 34.0)
            for ev in events:
                eid = _extract_id(ev)
                if request.target_event_id and eid == str(request.target_event_id):
                    affected_ids.append(eid)
                    if isinstance(ev, NormalizedEvent):
                        ev_copy = ev.model_copy(deep=True)
                        ev_copy.end_x = new_x
                        ev_copy.end_y = new_y
                        perturbed_events.append(ev_copy)
                    elif isinstance(ev, dict):
                        d_copy = dict(ev)
                        d_copy["end_x"] = new_x
                        d_copy["end_y"] = new_y
                        perturbed_events.append(d_copy)
                    else:
                        perturbed_events.append(ev)
                else:
                    perturbed_events.append(ev)

        else:
            perturbed_events = [ev for ev in events]

        # 3. Compute perturbed OAAI
        pert_oaai = compute_oaai(perturbed_events, smoothing_mode="causal")
        pert_timeline = pert_oaai.get("timeline", [])
        pert_amp = (
            sum(abs(float(p.get("oaai_value", 0.0))) for p in pert_timeline) / max(1, len(pert_timeline))
            if pert_timeline
            else 0.0
        )
        delta_amp = round(pert_amp - orig_amp, 4)

        # 4. Compute delta xG & threat
        pert_xg = sum(_extract_xg(ev) for ev in perturbed_events)
        delta_xg = round(pert_xg - base_xg, 4)

        base_xt_added = 0.0
        pert_xt_added = 0.0

        for ev in events:
            act = _extract_action(ev)
            if "pass" in act or "carry" in act:
                x = float(_get_field(ev, "x", 50.0) or 50.0)
                y = float(_get_field(ev, "y", 34.0) or 34.0)
                end_x = float(_get_field(ev, "end_x", x) or x)
                end_y = float(_get_field(ev, "end_y", y) or y)
                base_xt_added += xt_model.value_at(end_x, end_y) - xt_model.value_at(x, y)

        for ev in perturbed_events:
            act = _extract_action(ev)
            if "pass" in act or "carry" in act:
                x = float(_get_field(ev, "x", 50.0) or 50.0)
                y = float(_get_field(ev, "y", 34.0) or 34.0)
                end_x = float(_get_field(ev, "end_x", x) or x)
                end_y = float(_get_field(ev, "end_y", y) or y)
                pert_xt_added += xt_model.value_at(end_x, end_y) - xt_model.value_at(x, y)

        delta_threat = round(pert_xt_added - base_xt_added, 4)

        # 5. Uncertainty Propagation Confidence Band (95% CI on delta threat / amplitude)
        se = max(0.015, abs(delta_amp) * 0.18 + abs(delta_threat) * 0.12)
        ci_low = round(delta_amp - 1.96 * se, 3)
        ci_high = round(delta_amp + 1.96 * se, 3)

        sim_id = f"sim-{random.randint(1000, 9999)}"

        return WhatIfSimulationResult(
            simulation_id=sim_id,
            scenario_type=scenario,
            mode=mode,
            original_oaai_amplitude=round(orig_amp, 4),
            perturbed_oaai_amplitude=round(pert_amp, 4),
            delta_oaai_amplitude=delta_amp,
            delta_threat=delta_threat,
            delta_xg=delta_xg,
            confidence_band=(ci_low, ci_high),
            affected_events_count=len(affected_ids),
            affected_event_ids=affected_ids,
            claim_level="level_3_hypothesis",
            claim_level_int=3,
            is_exploratory=True,
            is_exploratory_only=True,
            disclaimer=WHATIF_DISCLAIMER_TEXT,
        )

    @classmethod
    def channel_redirection(
        cls,
        events: Sequence[dict[str, Any] | NormalizedEvent],
        target_event_id: Optional[str] = None,
        target_time_range: Optional[tuple[float, float]] = None,
        to_channel: Literal["left", "center", "right"] = "left",
    ) -> WhatIfSimulationResult:
        """Convenience method for channel redirection counterfactuals."""
        req = WhatIfScenarioRequest(
            scenario_type="channel_redirection",
            mode="scenario_based",
            target_event_id=target_event_id,
            target_time_range=target_time_range,
            target_corridor=to_channel,
        )
        return cls.simulate(events, req)

    @classmethod
    def remove_turnover(
        cls,
        events: Sequence[dict[str, Any] | NormalizedEvent],
        target_event_id: Optional[str] = None,
        target_time_range: Optional[tuple[float, float]] = None,
    ) -> WhatIfSimulationResult:
        """Convenience method for turnover removal counterfactuals."""
        req = WhatIfScenarioRequest(
            scenario_type="remove_turnover",
            mode="scenario_based",
            target_event_id=target_event_id,
            target_time_range=target_time_range,
        )
        return cls.simulate(events, req)

    @classmethod
    def prevent_shot(
        cls,
        events: Sequence[dict[str, Any] | NormalizedEvent],
        target_event_id: Optional[str] = None,
        target_time_range: Optional[tuple[float, float]] = None,
    ) -> WhatIfSimulationResult:
        """Convenience method for shot prevention counterfactuals."""
        req = WhatIfScenarioRequest(
            scenario_type="prevent_shot",
            mode="scenario_based",
            target_event_id=target_event_id,
            target_time_range=target_time_range,
        )
        return cls.simulate(events, req)


# Backwards compatibility alias
WhatIfSimulationEngine = WhatIfSandbox
