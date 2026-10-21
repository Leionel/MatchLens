"""Track C: Event Attribution Specialist & Computational Tools.

Provides:
1. TemporalWindowDecomposition: Objective event contribution weighting in time windows.
2. CausalChainQuery: Backward temporal and spatial chain extraction along possession sequences.
3. AlternativeHypothesisAssessment: Evaluation of rival explanations with dispute annotations.
4. EventAttributionSpecialist: Dedicated Level 1–2 agent with computational tools.
"""
from __future__ import annotations

import math
from typing import Any, Literal, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field, computed_field

from .models.xt import ExpectedThreatModel
from .schema import NormalizedEvent


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class AttributionEventItem(BaseModel):
    """An event's objective contribution breakdown within an attribution window."""
    model_config = ConfigDict(extra="ignore")

    event_id: str
    t: float
    team: str
    actor: str
    action_type: str
    x: Optional[float] = None
    y: Optional[float] = None
    metric_contributions: dict[str, float] = Field(default_factory=dict)
    weight: float
    contribution_share: float

    # Backward compatibility properties for dictionaries or older tests
    @computed_field
    @property
    def second(self) -> float:
        return round(self.t, 1)

    @computed_field
    @property
    def action(self) -> str:
        return self.action_type

    @computed_field
    @property
    def player(self) -> str:
        return self.actor

    @computed_field
    @property
    def xt_delta(self) -> float:
        return self.metric_contributions.get("delta_xt", 0.0)

    @computed_field
    @property
    def xg(self) -> float:
        return self.metric_contributions.get("xg", 0.0)

    @computed_field
    @property
    def progressive_distance(self) -> float:
        return self.metric_contributions.get("progression_meters", 0.0)

    @computed_field
    @property
    def contribution_score(self) -> float:
        return self.weight


class TemporalWindowDecompositionResult(BaseModel):
    """Objective Level 2 decomposition of metric contributions within a time window."""
    model_config = ConfigDict(extra="ignore")

    match_id: str = "syn_default"
    team: str
    window_start: float
    window_end: float
    total_events: int
    top_events: list[AttributionEventItem]
    metric_summary: dict[str, float] = Field(default_factory=dict)
    decomposition_formula: str = "W(e) = BaseMetric(e) * exp(-decay * (t_end - t_e))"
    disclaimer: str = "Level 2 指标归因分解结果，非主观战术定性。"

    # Aliases and properties for compatibility
    @computed_field
    @property
    def window_start_s(self) -> float:
        return self.window_start

    @computed_field
    @property
    def window_end_s(self) -> float:
        return self.window_end

    @computed_field
    @property
    def top_contributing_events(self) -> list[dict[str, Any]]:
        return [ev.model_dump() for ev in self.top_events]

    @computed_field
    @property
    def total_xt_delta(self) -> float:
        return self.metric_summary.get("total_xt_delta", 0.0)

    @computed_field
    @property
    def total_xg(self) -> float:
        return self.metric_summary.get("total_xg", 0.0)

    @computed_field
    @property
    def total_progressive_distance(self) -> float:
        return self.metric_summary.get("total_progressive_distance", 0.0)

    @computed_field
    @property
    def summary(self) -> str:
        return (
            f"Window {self.window_start:.0f}s–{self.window_end:.0f}s: Team {self.team} recorded {self.total_events} actions. "
            f"Cumulative delta_xT: {self.total_xt_delta:+.3f}, xG: {self.total_xg:.2f}, "
            f"progressive advance: {self.total_progressive_distance:.1f}m."
        )


class CausalChainStep(BaseModel):
    """A single sequential step along a causal possession sequence."""
    model_config = ConfigDict(extra="ignore")

    step_index: int
    event_id: str
    t: float
    team: str
    actor: str
    action_type: str
    x: Optional[float] = None
    y: Optional[float] = None
    zone_index: Optional[int] = None
    delta_xt: Optional[float] = None
    is_turnover: bool = False
    is_shot: bool = False
    is_key_pass: bool = False

    @computed_field
    @property
    def second(self) -> float:
        return round(self.t, 1)

    @computed_field
    @property
    def action(self) -> str:
        return self.action_type


class CausalChainQueryResult(BaseModel):
    """Sequence of events leading up to a target action, traced backward."""
    model_config = ConfigDict(extra="ignore")

    target_event_id: str
    sequence_id: Optional[str] = None
    steps: list[CausalChainStep]
    chain_length: int
    total_duration_s: float
    territorial_gain_m: float
    cumulative_xt: float
    initiating_event: Optional[CausalChainStep] = None

    @computed_field
    @property
    def chain_events(self) -> list[dict[str, Any]]:
        return [s.model_dump() for s in self.steps]

    @computed_field
    @property
    def chain_duration_s(self) -> float:
        return self.total_duration_s

    @computed_field
    @property
    def directness(self) -> float:
        if not self.steps or self.chain_length <= 1:
            return 1.0
        return min(1.0, max(0.0, self.territorial_gain_m / max(1.0, self.chain_length * 12.0)))

    @computed_field
    @property
    def terminal_outcome(self) -> str:
        return self.steps[-1].action_type if self.steps else "unknown"


class AlternativeHypothesis(BaseModel):
    """A competing explanation with quantitative plausibility and dispute notes."""
    model_config = ConfigDict(extra="ignore")

    hypothesis_id: str
    claim_type: str = "alternative"
    description: str
    supporting_events: list[str] = Field(default_factory=list)
    supporting_metrics: dict[str, float] = Field(default_factory=dict)
    counterevidence: list[str] = Field(default_factory=list)
    plausibility_score: float
    status: Literal["supported", "disputed", "rejected"]

    # Backward compatibility properties
    @computed_field
    @property
    def category(self) -> str:
        return self.hypothesis_id

    @computed_field
    @property
    def evidence_events(self) -> list[str]:
        return self.supporting_events

    @computed_field
    @property
    def confidence(self) -> float:
        return self.plausibility_score

    @computed_field
    @property
    def competing_with_primary(self) -> bool:
        return self.status != "rejected"


class AlternativeHypothesisAssessmentResult(BaseModel):
    """Evaluation result comparing a primary claim against rival hypotheses."""
    model_config = ConfigDict(extra="ignore")

    primary_hypothesis_id: str
    competing_hypotheses: list[AlternativeHypothesis]
    dispute_points: list[str] = Field(default_factory=list)
    confidence_penalty: float = 0.0
    recommended_level: int = 1

    # Backward compatibility properties
    @computed_field
    @property
    def target_window_or_sequence(self) -> str:
        return self.primary_hypothesis_id

    @computed_field
    @property
    def primary_hypothesis(self) -> str:
        return self.primary_hypothesis_id

    @computed_field
    @property
    def alternatives(self) -> list[AlternativeHypothesis]:
        return self.competing_hypotheses

    @computed_field
    @property
    def is_contested(self) -> bool:
        return len(self.dispute_points) > 0 or any(h.status == "supported" for h in self.competing_hypotheses)

    @computed_field
    @property
    def controversy_score(self) -> float:
        scores = [h.plausibility_score for h in self.competing_hypotheses]
        return max(scores) if scores else 0.0

    @computed_field
    @property
    def recommendation(self) -> Literal["accept_primary", "flag_contested", "require_conservative_variant"]:
        if self.controversy_score >= 0.75:
            return "require_conservative_variant"
        elif self.is_contested:
            return "flag_contested"
        return "accept_primary"


# ---------------------------------------------------------------------------
# Helper Extraction Functions
# ---------------------------------------------------------------------------

def _extract_event_info(ev: Any, index: int) -> dict[str, Any]:
    """Uniformly extracts fields from dict, NormalizedEvent, or Event object."""
    if isinstance(ev, dict):
        eid = str(ev.get("event_id", ev.get("id", f"ev-{index}")))
        t = float(ev.get("timestamp_seconds", ev.get("second", ev.get("clock_seconds", 0.0))))
        team = str(ev.get("team_id", ev.get("team", "H")))
        action = str(ev.get("action_type", ev.get("type", "pass"))).lower()
        actor = str(ev.get("player_name", ev.get("player", f"Player_{index}")))
        x = float(ev.get("x", 50.0)) if ev.get("x") is not None else 50.0
        y = float(ev.get("y", 34.0)) if ev.get("y") is not None else 34.0
        end_x = float(ev.get("end_x", x)) if ev.get("end_x") is not None else x
        end_y = float(ev.get("end_y", y)) if ev.get("end_y") is not None else y
        xg = float(ev.get("xg", 0.0))
    else:
        eid = str(getattr(ev, "event_id", getattr(ev, "id", f"ev-{index}")))
        t = float(getattr(ev, "timestamp_seconds", getattr(ev, "clock_seconds", getattr(ev, "second", 0.0))))
        team = str(getattr(ev, "team_id", getattr(ev, "team", "H")))
        action_val = getattr(ev, "action_type", getattr(ev, "type", "pass"))
        action = str(action_val.value if hasattr(action_val, "value") else action_val).lower()
        actor = str(getattr(ev, "player_name", getattr(ev, "player", f"Player_{index}")))
        x = float(getattr(ev, "x", 50.0) if getattr(ev, "x", None) is not None else 50.0)
        y = float(getattr(ev, "y", 34.0) if getattr(ev, "y", None) is not None else 34.0)
        end_x = float(getattr(ev, "end_x", x) if getattr(ev, "end_x", None) is not None else x)
        end_y = float(getattr(ev, "end_y", y) if getattr(ev, "end_y", None) is not None else y)
        xg = float(getattr(ev, "xg", 0.0) if getattr(ev, "xg", None) is not None else 0.0)

    return {
        "event_id": eid,
        "t": t,
        "team": team,
        "action": action,
        "actor": actor,
        "x": x,
        "y": y,
        "end_x": end_x,
        "end_y": end_y,
        "xg": xg,
    }


def _calc_zone_index(x: float, y: float) -> int:
    """Computes standard 9-zone pitch partition index (0-8).
    3 columns (defensive, middle, attacking) x 3 rows (left, center, right).
    """
    col = min(2, max(0, int(x / (105.0 / 3.0))))
    row = min(2, max(0, int(y / (68.0 / 3.0))))
    return row * 3 + col


# ---------------------------------------------------------------------------
# Dedicated Computational Tools
# ---------------------------------------------------------------------------

def temporal_window_decomposition(
    events: Sequence[Any],
    window_start: float = 0.0,
    window_end: float = 300.0,
    team: str = "H",
    metric_weights: Optional[dict[str, float]] = None,
    decay_lambda: float = 0.005,
    top_k: int = 5,
    match_id: str = "syn_default",
    window_start_s: Optional[float] = None,
    window_end_s: Optional[float] = None,
) -> TemporalWindowDecompositionResult:
    """Decomposes all actions inside [window_start, window_end] into objective metric contributions.
    
    Formula:
    W(e) = BaseMetric(e) * exp(-decay_lambda * (window_end - t_e))
    ContributionShare(e) = max(0, W(e)) / sum(max(0, W(k)))
    """
    w_start = window_start_s if window_start_s is not None else window_start
    w_end = window_end_s if window_end_s is not None else window_end

    xt_model = ExpectedThreatModel.load_default("16x12")
    weights = metric_weights or {"xt": 4.0, "xg": 2.5, "prog": 0.02, "shot": 0.5, "defensive": 0.3}

    scored_items: list[AttributionEventItem] = []
    total_xt = 0.0
    total_xg = 0.0
    total_prog = 0.0

    raw_items = []
    for idx, raw_ev in enumerate(events):
        info = _extract_event_info(raw_ev, idx)
        t = info["t"]
        if not (w_start <= t <= w_end):
            continue
        if info["team"] != team:
            continue

        action = info["action"]
        x, y = info["x"], info["y"]
        end_x, end_y = info["end_x"], info["end_y"]

        # Delta xT calculation
        if action in ("pass", "carry", "actiontype.pass", "actiontype.carry"):
            delta_xt = xt_model.value_at(end_x, end_y) - xt_model.value_at(x, y)
        else:
            delta_xt = 0.0

        xg_val = info["xg"]
        prog_meters = max(0.0, end_x - x)

        total_xt += delta_xt
        total_xg += xg_val
        total_prog += prog_meters

        # Exponential decay factor
        dt = max(0.0, w_end - t)
        decay_factor = math.exp(-decay_lambda * dt)

        # Base contribution calculation
        base_metric = (
            delta_xt * weights["xt"]
            + xg_val * weights["xg"]
            + prog_meters * weights["prog"]
        )
        if action in ("shot", "goal"):
            base_metric += weights["shot"]
        if action in ("ball recovery", "recovery", "interception", "tackle"):
            base_metric += weights["defensive"]

        final_weight = max(0.0, base_metric * decay_factor)
        raw_items.append((info, delta_xt, xg_val, prog_meters, final_weight))

    sum_weights = sum(item[4] for item in raw_items)
    for info, d_xt, xg, prog, weight in raw_items:
        share = (weight / sum_weights) if sum_weights > 0 else (1.0 / len(raw_items) if raw_items else 0.0)
        scored_items.append(
            AttributionEventItem(
                event_id=info["event_id"],
                t=info["t"],
                team=info["team"],
                actor=info["actor"],
                action_type=info["action"],
                x=info["x"],
                y=info["y"],
                metric_contributions={
                    "delta_xt": round(d_xt, 4),
                    "xg": round(xg, 4),
                    "progression_meters": round(prog, 1),
                },
                weight=round(weight, 4),
                contribution_share=round(share, 4),
            )
        )

    # Sort descending by weight
    scored_items.sort(key=lambda item: item.weight, reverse=True)
    top_items = scored_items[:top_k]

    return TemporalWindowDecompositionResult(
        match_id=match_id,
        team=team,
        window_start=w_start,
        window_end=w_end,
        total_events=len(scored_items),
        top_events=top_items,
        metric_summary={
            "total_xt_delta": round(total_xt, 4),
            "total_xg": round(total_xg, 4),
            "total_progressive_distance": round(total_prog, 1),
        },
    )


def causal_chain_query(
    events: Sequence[Any],
    target_event_id: str,
    lookback_seconds: float = 30.0,
) -> CausalChainQueryResult:
    """Traces backward from a target event along the unbroken possession chain."""
    xt_model = ExpectedThreatModel.load_default("16x12")

    # Locate target event
    target_idx = -1
    for idx, ev in enumerate(events):
        info = _extract_event_info(ev, idx)
        if info["event_id"] == str(target_event_id):
            target_idx = idx
            break

    if target_idx == -1:
        # Fallback to last event if target ID not found
        target_idx = max(0, len(events) - 1)

    target_info = _extract_event_info(events[target_idx], target_idx) if events else None
    if not target_info:
        return CausalChainQueryResult(
            target_event_id=str(target_event_id),
            steps=[],
            chain_length=0,
            total_duration_s=0.0,
            territorial_gain_m=0.0,
            cumulative_xt=0.0,
        )

    target_team = target_info["team"]
    target_t = target_info["t"]

    collected_steps_raw: list[dict[str, Any]] = []
    for i in range(target_idx, -1, -1):
        info = _extract_event_info(events[i], i)
        dt = target_t - info["t"]
        if dt > lookback_seconds:
            break
        if info["team"] != target_team:
            # Turnover point reached
            break
        collected_steps_raw.append(info)

    collected_steps_raw.reverse()

    steps: list[CausalChainStep] = []
    cumulative_xt = 0.0
    for s_idx, info in enumerate(collected_steps_raw):
        act = info["action"]
        x, y = info["x"], info["y"]
        end_x, end_y = info["end_x"], info["end_y"]

        d_xt = (
            xt_model.value_at(end_x, end_y) - xt_model.value_at(x, y)
            if act in ("pass", "carry", "actiontype.pass", "actiontype.carry")
            else 0.0
        )
        cumulative_xt += d_xt

        is_turnover = (s_idx == 0 and act in ("ball recovery", "recovery", "interception", "tackle"))
        is_shot = act in ("shot", "goal")
        is_key_pass = (s_idx == len(collected_steps_raw) - 2 and collected_steps_raw[-1]["action"] in ("shot", "goal"))

        steps.append(
            CausalChainStep(
                step_index=s_idx,
                event_id=info["event_id"],
                t=info["t"],
                team=info["team"],
                actor=info["actor"],
                action_type=act,
                x=x,
                y=y,
                zone_index=_calc_zone_index(x, y),
                delta_xt=round(d_xt, 4),
                is_turnover=is_turnover,
                is_shot=is_shot,
                is_key_pass=is_key_pass,
            )
        )

    duration = (steps[-1].t - steps[0].t) if len(steps) > 1 else 0.0
    start_x = steps[0].x if steps and steps[0].x is not None else 0.0
    end_x = steps[-1].x if steps and steps[-1].x is not None else 0.0
    territorial_gain = end_x - start_x

    return CausalChainQueryResult(
        target_event_id=str(target_event_id),
        steps=steps,
        chain_length=len(steps),
        total_duration_s=round(duration, 1),
        territorial_gain_m=round(territorial_gain, 1),
        cumulative_xt=round(cumulative_xt, 4),
        initiating_event=steps[0] if steps else None,
    )


def alternative_hypothesis_assessment(
    events: Sequence[Any],
    primary_hypothesis: str = "High pressing forced turnover and chance",
    window_start: float = 0.0,
    window_end: float = 300.0,
    team: str = "H",
    primary_team: Optional[str] = None,
    window_start_s: Optional[float] = None,
    window_end_s: Optional[float] = None,
) -> AlternativeHypothesisAssessmentResult:
    """Evaluates canonical rival explanations (unforced error, deflection, solo run)
    against actual match events in the window.
    """
    target_team = primary_team or team
    opponent = "N" if target_team == "H" else "H"
    w_start = window_start_s if window_start_s is not None else window_start
    w_end = window_end_s if window_end_s is not None else window_end

    unforced_errors: list[str] = []
    deflections: list[str] = []
    solo_carries: list[str] = []
    opp_misplaced_passes: list[str] = []
    team_tackles: list[str] = []

    for idx, raw_ev in enumerate(events):
        info = _extract_event_info(raw_ev, idx)
        if not (w_start <= info["t"] <= w_end):
            continue

        act = info["action"]
        ev_team = info["team"]
        eid = info["event_id"]

        if ev_team == opponent:
            if act in ("miscontrol", "dispossessed", "turnover", "bad_pass", "error"):
                unforced_errors.append(eid)
            elif act == "pass" and info.get("outcome") in ("incomplete", "out"):
                opp_misplaced_passes.append(eid)
        else:
            if act in ("tackle", "interception", "ball recovery", "recovery"):
                team_tackles.append(eid)
            if act == "carry" and (info["end_x"] - info["x"]) > 25.0:
                solo_carries.append(eid)

        if act in ("block", "deflection", "saved"):
            deflections.append(eid)

    rivals: list[AlternativeHypothesis] = []
    dispute_points: list[str] = []

    # 1. Rival H1: Opponent unforced error
    all_opp_errors = unforced_errors + opp_misplaced_passes
    if all_opp_errors:
        plausibility = min(0.85, 0.45 + 0.12 * len(all_opp_errors))
        status = "supported" if plausibility >= 0.60 else "disputed"
        rivals.append(
            AlternativeHypothesis(
                hypothesis_id="opponent_unforced_error",
                claim_type="alternative",
                description=(
                    f"Turnover stemmed from opponent unforced miscontrol/misplaced pass "
                    f"({len(all_opp_errors)} incidents) rather than coordinated pressing action."
                ),
                supporting_events=all_opp_errors,
                supporting_metrics={"opponent_error_count": float(len(all_opp_errors))},
                counterevidence=team_tackles[:2],
                plausibility_score=round(plausibility, 2),
                status=status,
            )
        )
        if len(all_opp_errors) > len(team_tackles):
            dispute_points.append(
                f"Opponent committed {len(all_opp_errors)} unforced errors vs {len(team_tackles)} active tackles."
            )

    # 2. Rival H2: Individual solo dribble / fast break vs collective structure
    if solo_carries:
        plausibility = min(0.80, 0.50 + 0.15 * len(solo_carries))
        rivals.append(
            AlternativeHypothesis(
                hypothesis_id="individual_dribble_break",
                claim_type="alternative",
                description=(
                    f"Chance progression was driven by isolated individual ball-carrying "
                    f"({len(solo_carries)} carries >25m) rather than collective positional combinations."
                ),
                supporting_events=solo_carries,
                supporting_metrics={"long_carries_count": float(len(solo_carries))},
                counterevidence=[],
                plausibility_score=round(plausibility, 2),
                status="supported" if plausibility >= 0.65 else "disputed",
            )
        )
        dispute_points.append(
            f"Observed {len(solo_carries)} direct progressive ball carries exceeding 25 meters."
        )

    # 3. Rival H3: Deflection / rebound luck
    if deflections:
        plausibility = min(0.75, 0.40 + 0.15 * len(deflections))
        rivals.append(
            AlternativeHypothesis(
                hypothesis_id="deflection_luck",
                claim_type="alternative",
                description="Chance creation was influenced by defensive deflections or fortunate rebounds.",
                supporting_events=deflections,
                supporting_metrics={"deflection_count": float(len(deflections))},
                counterevidence=[],
                plausibility_score=round(plausibility, 2),
                status="disputed",
            )
        )

    penalty = 0.25 if len(dispute_points) > 0 else 0.0
    recommended_lvl = 1 if len(dispute_points) > 0 else 2

    return AlternativeHypothesisAssessmentResult(
        primary_hypothesis_id=primary_hypothesis,
        competing_hypotheses=rivals,
        dispute_points=dispute_points,
        confidence_penalty=penalty,
        recommended_level=recommended_lvl,
    )


# ---------------------------------------------------------------------------
# Event Attribution Specialist Agent
# ---------------------------------------------------------------------------

class EventAttributionSpecialist:
    """Dedicated Level 1–2 agent specializing in metric breakdown,
    causal sequence query, and rival hypothesis assessment.
    """

    def __init__(self, match_id: str, events: Sequence[Any]):
        self.match_id = match_id
        self.events = events

    def decompose_window(
        self,
        start: float,
        end: float,
        team: str,
        top_k: int = 5,
    ) -> TemporalWindowDecompositionResult:
        return temporal_window_decomposition(
            self.events,
            window_start=start,
            window_end=end,
            team=team,
            top_k=top_k,
            match_id=self.match_id,
        )

    def query_causal_chain(
        self,
        target_event_id: str,
        lookback_seconds: float = 30.0,
    ) -> CausalChainQueryResult:
        return causal_chain_query(
            self.events,
            target_event_id=target_event_id,
            lookback_seconds=lookback_seconds,
        )

    def assess_alternatives(
        self,
        start: float,
        end: float,
        team: str,
        primary_hypothesis: str = "",
    ) -> AlternativeHypothesisAssessmentResult:
        return alternative_hypothesis_assessment(
            self.events,
            primary_hypothesis=primary_hypothesis,
            window_start=start,
            window_end=end,
            team=team,
        )

    # Expose tools as static methods for convenience
    temporal_window_decomposition = staticmethod(temporal_window_decomposition)
    causal_chain_query = staticmethod(causal_chain_query)
    alternative_hypothesis_assessment = staticmethod(alternative_hypothesis_assessment)


# Re-exports for clean API and backward compatibility
from .sufficiency import DataSufficiencyAdvisor, DataSufficiencyNotice
from .gate import publication_gate_2, publication_gate_2_0
from .benchmark import run_agent_benchmark_harness
