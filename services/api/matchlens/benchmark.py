"""Deterministic publication-pipeline benchmark (no synthetic LLM metrics).

The three configurations are *pipeline configurations*, not three agents:

- A_reference_only: checks that cited event IDs exist.
- B_gate20: runs the real Gate 2.0 rule engine (wording, assumptions,
  verification method, metric namespace, model version).
- C_gate20_plus_tools: B plus the real deterministic attribution tools.

No configuration dispatches a language model. Live-model accuracy, token cost
and model latency are therefore reported as Not Run, never estimated. The
claim labels used here are a small hand-authored contract fixture; agreement
with those labels is *contract agreement*, not empirical model accuracy.
"""
from __future__ import annotations

import time
from typing import Any, Literal, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field, computed_field

from .catalog import MatchCatalog
from .gate import publication_gate_2_0
from .schema import NormalizedEvent


ConfigId = Literal["A_reference_only", "B_gate20", "C_gate20_plus_tools"]


class AgentBenchmarkMetrics(BaseModel):
    """Auditable metrics for one deterministic pipeline configuration."""
    model_config = ConfigDict(extra="ignore")

    config: ConfigId
    benchmark_type: Literal["deterministic_contract", "live_agent_empirical"] = "deterministic_contract"
    status: Literal["executed", "not_run"] = "executed"
    total_claims_evaluated: int
    valid_count: int
    invalid_count: int
    accepted_count: int
    blocked_count: int
    invalid_block_rate: Optional[float] = None
    valid_acceptance_rate: Optional[float] = None
    false_accept_rate: Optional[float] = None
    contract_agreement_rate: Optional[float] = None
    latency_ms_measured: Optional[float] = None
    token_cost_usd: Optional[float] = None
    token_source: Literal["not_run", "live_usage"] = "not_run"
    alternative_hypothesis_tool_executed: bool = False
    is_live_model_evaluation: bool = False
    empirical_accuracy_measured: bool = False
    data_provenance: str = "Deterministic Contract Benchmark (executed rule engine)"
    notes: Optional[str] = None

    # Compatibility aliases: all computed from executed results, never constants.
    @computed_field
    @property
    def gate_interception_rate(self) -> Optional[float]:
        return self.invalid_block_rate

    @computed_field
    @property
    def gate_block_rate(self) -> Optional[float]:
        return self.invalid_block_rate

    @computed_field
    @property
    def accuracy_rate(self) -> Optional[float]:
        return self.contract_agreement_rate

    @computed_field
    @property
    def gate_pass_rate(self) -> Optional[float]:
        return round(self.accepted_count / self.total_claims_evaluated, 4) if self.total_claims_evaluated else None

    @computed_field
    @property
    def alternative_hypothesis_coverage(self) -> Optional[float]:
        # No per-claim alternative assessment is executed; the ratio is not measured.
        return None

    @computed_field
    @property
    def avg_latency_ms(self) -> Optional[float]:
        return self.latency_ms_measured

    @computed_field
    @property
    def latency_ms_est(self) -> Optional[float]:
        return self.latency_ms_measured

    @computed_field
    @property
    def token_cost_usd_est(self) -> Optional[float]:
        return self.token_cost_usd

    @computed_field
    @property
    def avg_token_consumption(self) -> Optional[int]:
        return None


class AgentBenchmarkSuiteResult(BaseModel):
    """Complete deterministic pipeline report plus explicit live-model status."""
    model_config = ConfigDict(extra="ignore")

    benchmark_id: str
    match_id: str
    benchmark_type: Literal["deterministic_contract", "live_agent_empirical"] = "deterministic_contract"
    configurations: list[AgentBenchmarkMetrics]
    dataset: dict[str, Any] = Field(default_factory=dict)
    live_model_status: Literal["not_run", "run"] = "not_run"
    recommendation: str
    summary: str


def _build_candidate_claims(events: list[NormalizedEvent]) -> list[dict[str, Any]]:
    """Hand-authored contract fixtures with declared expected labels.

    These labels are test-fixture ground truth, not model outputs and not an
    empirical validation set.
    """
    if not events:
        return []

    ev_0 = events[0].event_id
    ev_1 = events[min(2, len(events) - 1)].event_id
    ev_mid = events[len(events) // 2].event_id

    ev_x = events[0].x if events[0].x is not None else 0.0
    ev_y = events[0].y if events[0].y is not None else 0.0
    location_note = "location recorded" if events[0].x is not None else "location not recorded"

    candidates = [
        {
            "claim_id": "c1_valid_obs",
            "claim_level": 1,
            "text": f"Event {ev_0} is a recorded on-ball action ({location_note}).",
            "evidence_scope": {"event_ids": [ev_0], "metric_ids": ["possession"]},
            "assumptions": [],
            "counterevidence": [],
            "verification_method": "direct_event_check",
            "metric_versions": {"oaai": "1.0.0"},
            "ground_truth_valid": True,
        },
        {
            "claim_id": "c2_causal_overreach_l1",
            "claim_level": 1,
            "text": f"Event {ev_0} directly caused the opponent turnover and drives team attacking momentum.",
            "evidence_scope": {"event_ids": [ev_0], "metric_ids": ["oaai"]},
            "assumptions": [],
            "counterevidence": [],
            "verification_method": "direct_event_check",
            "metric_versions": {"oaai": "1.0.0"},
            "ground_truth_valid": False,
        },
        {
            "claim_id": "c3_valid_l2_decomp",
            "claim_level": 2,
            "text": f"Window cumulative delta_xT was evaluated across the sequences containing {ev_0} and {ev_1}.",
            "evidence_scope": {"event_ids": [ev_0, ev_1], "metric_ids": ["delta_xt", "xG"]},
            "assumptions": ["Bilinear interpolation on a 16x12 grid"],
            "counterevidence": [],
            "verification_method": "xt_bilinear_model",
            "metric_versions": {"delta_xt": "1.0.0"},
            "ground_truth_valid": True,
        },
        {
            "claim_id": "c4_missing_assumptions_l3",
            "claim_level": 3,
            "text": f"High recoveries observed near {ev_mid} indicate a deliberate tactical pressing plan by the coach.",
            "evidence_scope": {"event_ids": [ev_mid], "metric_ids": ["high_recoveries"]},
            "assumptions": [],
            "counterevidence": [],
            "verification_method": "",
            "metric_versions": {"oaai": "1.0.0"},
            "ground_truth_valid": False,
        },
        {
            "claim_id": "c5_hallucinated_ref",
            "claim_level": 1,
            "text": "Recorded clearance at event ev-fake-99999 stopped a dangerous counter-attack.",
            "evidence_scope": {"event_ids": ["ev-fake-99999"], "metric_ids": ["possession"]},
            "assumptions": [],
            "counterevidence": [],
            "verification_method": "direct_event_check",
            "metric_versions": {"oaai": "1.0.0"},
            "ground_truth_valid": False,
        },
        {
            "claim_id": "c6_contested_counterevidence",
            "claim_level": 2,
            "text": f"Sustained attacking pressure in the final third near {ev_1} preceded consecutive chances.",
            "evidence_scope": {"event_ids": [ev_1], "metric_ids": ["entries", "shots"]},
            "assumptions": ["Continuous possession sequence"],
            "counterevidence": [f"{ev_0}_unforced_error", "misplaced_pass_3"],
            "verification_method": "sequence_attribution",
            "metric_versions": {"oaai": "1.0.0"},
            "ground_truth_valid": False,
        },
        {
            "claim_id": "c7_valid_l3_hypothesis",
            "claim_level": 3,
            "text": f"Transition shots following recoveries near {ev_0} reflect positive spatial progression tendency.",
            "evidence_scope": {"event_ids": [ev_0, ev_1], "metric_ids": ["transition_shots"]},
            "assumptions": ["Observed within a 180s window baseline", "Sample size N>=10 sequences"],
            "counterevidence": [],
            "verification_method": "bootstrap_significance_test",
            "metric_versions": {"oaai": "1.0.0"},
            "ground_truth_valid": True,
        },
        {
            "claim_id": "c8_invalid_version",
            "claim_level": 2,
            "text": f"Decomposition using a legacy metric model at {ev_0}.",
            "evidence_scope": {"event_ids": [ev_0], "metric_ids": ["oaai"]},
            "assumptions": ["Legacy weights"],
            "counterevidence": [],
            "verification_method": "model_v0_run",
            "metric_versions": {"oaai": "0.1.0-deprecated"},
            "ground_truth_valid": False,
        },
    ]
    return candidates


def _coverage_or_unknown(match_id: str) -> str:
    try:
        return MatchCatalog.get_match_context(match_id).data_coverage
    except Exception:
        return "unknown"


def _reference_only_verdict(claim: dict[str, Any], known_event_ids: set[str]) -> str:
    refs = [str(ref) for ref in claim.get("evidence_scope", {}).get("event_ids", [])]
    if not refs:
        return "rejected"
    return "approved" if all(ref in known_event_ids for ref in refs) else "rejected"


class AgentBenchmarkHarness:
    """Runs deterministic publication-pipeline configurations on real events."""

    def __init__(self, match_id: str = "syn_default"):
        self.match_id = match_id
        self.events = MatchCatalog.load_normalized_events(match_id)

    def run(self, num_trials: int = 15) -> AgentBenchmarkSuiteResult:
        candidates = _build_candidate_claims(self.events)
        if not candidates:
            return AgentBenchmarkSuiteResult(
                benchmark_id=f"bm-{self.match_id}-empty",
                match_id=self.match_id,
                configurations=[],
                dataset={"event_count": 0, "fixture_claims": 0},
                live_model_status="not_run",
                recommendation="No claims could be constructed from an empty event stream.",
                summary="Deterministic pipeline benchmark not run: empty event stream.",
            )

        known_event_ids = {event.event_id for event in self.events}
        total = len(candidates)
        valid_count = sum(1 for c in candidates if c["ground_truth_valid"])
        invalid_count = total - valid_count

        def metrics(
            config: ConfigId,
            verdicts: dict[str, str],
            latency_ms: float,
            *,
            alt_executed: bool = False,
            notes: str = "",
        ) -> AgentBenchmarkMetrics:
            accepted = [c for c in candidates if verdicts[c["claim_id"]] == "approved"]
            blocked = [c for c in candidates if verdicts[c["claim_id"]] != "approved"]
            accepted_valid = sum(1 for c in accepted if c["ground_truth_valid"])
            accepted_invalid = len(accepted) - accepted_valid
            blocked_invalid = sum(1 for c in blocked if not c["ground_truth_valid"])
            agreement = (accepted_valid + blocked_invalid) / total
            return AgentBenchmarkMetrics(
                config=config,
                total_claims_evaluated=total,
                valid_count=valid_count,
                invalid_count=invalid_count,
                accepted_count=len(accepted),
                blocked_count=len(blocked),
                invalid_block_rate=round(blocked_invalid / invalid_count, 4) if invalid_count else None,
                valid_acceptance_rate=round(accepted_valid / valid_count, 4) if valid_count else None,
                false_accept_rate=round(accepted_invalid / invalid_count, 4) if invalid_count else None,
                contract_agreement_rate=round(agreement, 4),
                latency_ms_measured=round(latency_ms, 3),
                token_cost_usd=None,
                token_source="not_run",
                alternative_hypothesis_tool_executed=alt_executed,
                is_live_model_evaluation=False,
                empirical_accuracy_measured=False,
                notes=notes,
            )

        # --- A: reference existence only -------------------------------------
        t0 = time.perf_counter()
        verdicts_a = {c["claim_id"]: _reference_only_verdict(c, known_event_ids) for c in candidates}
        time_a = (time.perf_counter() - t0) * 1000.0

        # --- B: real Gate 2.0 -------------------------------------------------
        t0 = time.perf_counter()
        verdicts_b = {}
        for c in candidates:
            verdict = publication_gate_2_0(c, self.events, active_model_version="1.0.0")
            verdicts_b[c["claim_id"]] = "approved" if verdict.status == "approved" else "rejected"
        time_b = (time.perf_counter() - t0) * 1000.0

        # --- C: Gate 2.0 plus real attribution tools --------------------------
        from .attribution import EventAttributionSpecialist

        t0 = time.perf_counter()
        specialist = EventAttributionSpecialist(self.match_id, self.events)
        specialist.decompose_window(0.0, 300.0, "H")
        specialist.assess_alternatives(0.0, 300.0, "H")
        verdicts_c = {}
        for c in candidates:
            verdict = publication_gate_2_0(c, self.events, active_model_version="1.0.0")
            verdicts_c[c["claim_id"]] = "approved" if verdict.status == "approved" else "rejected"
        time_c = (time.perf_counter() - t0) * 1000.0

        configurations = [
            metrics(
                "A_reference_only",
                verdicts_a,
                time_a,
                notes="Only event-ID existence is checked; causal wording and assumptions are not evaluated.",
            ),
            metrics(
                "B_gate20",
                verdicts_b,
                time_b,
                notes="Real Gate 2.0 rules: wording, Level 3 assumptions, metric namespace, model version.",
            ),
            metrics(
                "C_gate20_plus_tools",
                verdicts_c,
                time_c,
                alt_executed=True,
                notes="Gate 2.0 plus real decomposition and alternative-hypothesis tool execution. Not an additional agent.",
            ),
        ]

        by_id = {m.config: m for m in configurations}
        summary = (
            f"Deterministic contract benchmark on {self.match_id} "
            f"({total} hand-authored fixture claims: {valid_count} labelled valid, {invalid_count} labelled invalid). "
            f"A blocked {by_id['A_reference_only'].invalid_block_rate:.0%} of labelled-invalid claims; "
            f"B blocked {by_id['B_gate20'].invalid_block_rate:.0%}; "
            f"C blocked {by_id['C_gate20_plus_tools'].invalid_block_rate:.0%}. "
            "These are rule-execution agreement rates, not LLM accuracy. "
            "Live-model A/B/C evaluation: NOT RUN."
            if invalid_count else
            "Deterministic contract benchmark executed; fixture contains no labelled-invalid claims."
        )
        return AgentBenchmarkSuiteResult(
            benchmark_id=f"bm-{self.match_id}-deterministic",
            match_id=self.match_id,
            configurations=configurations,
            dataset={
                "event_count": len(self.events),
                "fixture_claims": total,
                "label_source": "hand-authored contract fixtures (not empirical ground truth)",
                "coverage": _coverage_or_unknown(self.match_id),
                "live_model_metrics": "not_run",
            },
            live_model_status="not_run",
            recommendation=(
                "Use Gate 2.0 (B/C) as the deterministic publication contract. "
                "No claim of live-agent superiority is supported by this run."
            ),
            summary=summary,
        )


def run_agent_benchmark_harness(match_id: str = "syn_default", num_trials: int = 15) -> AgentBenchmarkSuiteResult:
    """Executes the deterministic publication-pipeline benchmark (no model dispatch)."""
    harness = AgentBenchmarkHarness(match_id=match_id)
    return harness.run(num_trials=num_trials)
