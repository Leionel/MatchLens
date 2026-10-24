"""
Track E: Research & Validation Scientific Suite.

Implements requirements from:
- docs/FOOTBALL_INTELLIGENCE_PLATFORMS_2026.md (BL-09 Scientific Validation Benchmark, Section 6.4, Section 7.1)
- docs/XT_MODELING_SPEC.md (Empirical Bayes / Dirichlet fitting, spatial threat grid validation)
- Section 6.4.2 (Quantitative A/B/C agent comparative evaluation)

Modules:
1. ScientificEvaluationBenchmark:
   - Deterministic dataset fingerprinting (SHA-256) and audit provenance
   - Automated bootstrap resampling with 95% confidence intervals on xG and empirical xT
   - Empirical xT grid fitting and spatial monotonicity verification
   - Cross-match generalization evaluation (MAE, RMSE, Pearson r, zonal errors) across synthetic scenarios and World Cup Final 2022
2. AgentBenchmarkEvaluator:
   - Quantitative evaluation runner for A/B/C configurations on match datasets
   - Computes distribution statistics, Gate pass/block rates, and cost/latency tradeoffs
3. What-if counterfactual re-exports for seamless architectural integration
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any, Literal, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

from .models.xg import compute_pre_shot_xg
from .models.xt import (
    ExpectedThreatFitter,
    ExpectedThreatModel,
    compare_xt_grids,
    fit_xt_model,
)
from .oaai import compute_oaai
from .schema import ActionType, NormalizedEvent
from .whatif import (
    WhatIfMode,
    WhatIfSandbox,
    WhatIfScenarioRequest,
    WhatIfSimulationEngine,
    WhatIfSimulationResult,
    WHATIF_DISCLAIMER_TEXT,
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


def _extract_team(ev: Any) -> str:
    tid = _get_field(ev, "team_id")
    if tid is None:
        tid = _get_field(ev, "team", "H")
    return str(tid)


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
        x = _get_field(ev, "x")
        y = _get_field(ev, "y")
        eid = _extract_id(ev)
        outcome = _get_field(ev, "outcome")
        shot_eval = compute_pre_shot_xg(x=x, y=y, event_id=eid, outcome=outcome)
        return shot_eval.pre_shot_xg
    return 0.0


# ---------------------------------------------------------------------------
# Data Models for BL-09 Scientific Suite
# ---------------------------------------------------------------------------

class MetricConfidenceInterval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric_name: str
    point_estimate: float
    ci_lower_95: float
    ci_upper_95: float
    std_dev: float
    unit: str


class DatasetFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_id: str
    sha256_hash: str
    total_events: int
    first_timestamp_s: float
    last_timestamp_s: float
    provenance_license: str
    seed_used: int


class CrossMatchGeneralizationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    train_match_id: str
    test_match_id: str
    cross_match_mae: float
    cross_match_rmse: float
    cross_match_pearson_r: float
    zone_mae: dict[str, float]
    is_generalizable: bool
    summary: str


class ScientificValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_id: str
    match_id: str
    dataset_fingerprint: DatasetFingerprint
    bootstrap_iterations: int
    confidence_intervals: list[MetricConfidenceInterval]
    cross_match_mae: Optional[float] = None
    cross_match_rmse: Optional[float] = None
    cross_match_pearson_r: Optional[float] = None
    monotonicity_preserved: bool
    generalization_report: Optional[CrossMatchGeneralizationReport] = None
    summary: str


# ---------------------------------------------------------------------------
# BL-09 Scientific Evaluation Benchmark
# ---------------------------------------------------------------------------

class ScientificEvaluationBenchmark:
    """Automated statistical evaluation benchmark and reproducibility suite.
    
    Provides:
    - SHA-256 dataset fingerprinting with provenance audit tracking
    - Deterministic bootstrap resampling for xG and empirical xT
    - Spatial surface fitting, monotonicity checks, and confidence intervals
    - Cross-match generalization evaluation
    """

    @staticmethod
    def generate_fingerprint(
        match_id: str,
        events: Sequence[dict[str, Any] | NormalizedEvent],
        seed: int = 42,
    ) -> DatasetFingerprint:
        """Computes deterministic SHA-256 fingerprint from canonical event stream."""
        canonical_parts: list[str] = [f"match:{match_id};seed:{seed};"]
        first_t = 0.0
        last_t = 0.0

        for i, ev in enumerate(events):
            t = _extract_time(ev)
            if i == 0:
                first_t = t
            last_t = t

            eid = _extract_id(ev, fallback=f"e{i}")
            act = _extract_action(ev)
            team = _extract_team(ev)
            x = _get_field(ev, "x")
            y = _get_field(ev, "y")
            x_str = f"{float(x):.2f}" if x is not None else "na"
            y_str = f"{float(y):.2f}" if y is not None else "na"

            canonical_parts.append(f"{eid}|{t:.2f}|{team}|{act}|{x_str},{y_str};")

        raw_digest = hashlib.sha256("".join(canonical_parts).encode("utf-8")).hexdigest()

        return DatasetFingerprint(
            match_id=match_id,
            sha256_hash=raw_digest,
            total_events=len(events),
            first_timestamp_s=round(first_t, 2),
            last_timestamp_s=round(last_t, 2),
            provenance_license="StatsBomb Open Data (CC BY-NC 4.0) / MatchLens Synthetic Ground Truth",
            seed_used=seed,
        )

    @classmethod
    def evaluate_cross_match_generalization(
        cls,
        train_match_id: str,
        test_match_id: str,
        train_events: Optional[Sequence[dict[str, Any] | NormalizedEvent]] = None,
        test_events: Optional[Sequence[dict[str, Any] | NormalizedEvent]] = None,
    ) -> CrossMatchGeneralizationReport:
        """Evaluates empirical threat surface generalization between two distinct matches."""
        from .catalog import MatchCatalog

        if train_events is None:
            train_events = MatchCatalog.load_normalized_events(train_match_id)
        if test_events is None:
            test_events = MatchCatalog.load_normalized_events(test_match_id)

        # Ensure events are NormalizedEvent instances
        norm_train: list[NormalizedEvent] = []
        for ev in train_events:
            if isinstance(ev, NormalizedEvent):
                norm_train.append(ev)
            elif isinstance(ev, dict):
                norm_train.append(NormalizedEvent(**ev))

        norm_test: list[NormalizedEvent] = []
        for ev in test_events:
            if isinstance(ev, NormalizedEvent):
                norm_test.append(ev)
            elif isinstance(ev, dict):
                norm_test.append(NormalizedEvent(**ev))

        fitter = ExpectedThreatFitter(nx=16, ny=12, horizon_steps=5)
        model_train = fitter.fit(norm_train, match_ids=[train_match_id])
        model_test = fitter.fit(norm_test, match_ids=[test_match_id])

        # Grid comparison between train-fitted and test-fitted threat matrices
        cmp = compare_xt_grids(model_train, model_test)

        summary = (
            f"Cross-match Generalization ({train_match_id} -> {test_match_id}): "
            f"MAE={cmp['mae']:.4f}, RMSE={cmp['rmse']:.4f}, Pearson r={cmp['correlation']:.4f}. "
            f"Spatial alignment verdict: {'Pass' if cmp['is_consistent'] else 'Review needed'}."
        )

        return CrossMatchGeneralizationReport(
            train_match_id=train_match_id,
            test_match_id=test_match_id,
            cross_match_mae=cmp["mae"],
            cross_match_rmse=cmp["rmse"],
            cross_match_pearson_r=cmp["correlation"],
            zone_mae=cmp["zone_mae"],
            is_generalizable=cmp["is_consistent"],
            summary=summary,
        )

    @classmethod
    def run_bootstrap_resampling(
        cls,
        match_id: str,
        events: Sequence[dict[str, Any] | NormalizedEvent],
        iterations: int = 100,
        seed: int = 42,
        eval_cross_match: bool = True,
        test_match_id: Optional[str] = None,
    ) -> ScientificValidationReport:
        """Executes full reproducible bootstrap protocol with confidence intervals."""
        n = len(events)
        if n == 0:
            raise ValueError("empty_event_stream")

        fingerprint = cls.generate_fingerprint(match_id, events, seed=seed)
        rnd = random.Random(seed)

        # 1. Base point estimates
        xt_model = ExpectedThreatModel.load_default("16x12")

        # 2. Resampling loop
        boot_xg_h: list[float] = []
        boot_xg_n: list[float] = []
        boot_xt_deltas: list[float] = []

        for _ in range(iterations):
            sampled_indices = [rnd.randint(0, n - 1) for _ in range(n)]
            sample_xg_h = 0.0
            sample_xg_n = 0.0
            sample_xt = 0.0

            for idx in sampled_indices:
                ev = events[idx]
                team = _extract_team(ev)
                xg = _extract_xg(ev)

                if team in ("H", "home", "Home"):
                    sample_xg_h += xg
                else:
                    sample_xg_n += xg

                act = _extract_action(ev)
                if "pass" in act or "carry" in act:
                    x = float(_get_field(ev, "x", 50.0) or 50.0)
                    y = float(_get_field(ev, "y", 34.0) or 34.0)
                    end_x = float(_get_field(ev, "end_x", x) or x)
                    end_y = float(_get_field(ev, "end_y", y) or y)
                    sample_xt += (xt_model.value_at(end_x, end_y) - xt_model.value_at(x, y))

            boot_xg_h.append(sample_xg_h)
            boot_xg_n.append(sample_xg_n)
            boot_xt_deltas.append(sample_xt)

        def _calc_ci(values: list[float], name: str, unit: str) -> MetricConfidenceInterval:
            vals = sorted(values)
            m = sum(vals) / len(vals)
            low_idx = int(len(vals) * 0.025)
            high_idx = int(len(vals) * 0.975)
            variance = sum((v - m) ** 2 for v in vals) / max(1, len(vals) - 1)
            std_v = math.sqrt(variance)

            return MetricConfidenceInterval(
                metric_name=name,
                point_estimate=round(m, 3),
                ci_lower_95=round(vals[low_idx], 3),
                ci_upper_95=round(vals[high_idx], 3),
                std_dev=round(std_v, 3),
                unit=unit,
            )

        ci_list = [
            _calc_ci(boot_xg_h, "Home Expected Goals (xG)", "goals"),
            _calc_ci(boot_xg_n, "Away Expected Goals (xG)", "goals"),
            _calc_ci(boot_xt_deltas, "Expected Threat Added (xT)", "threat_units"),
        ]

        # 3. Monotonicity verification on baseline grid
        grid_vals = xt_model.values
        ny, nx = len(grid_vals), len(grid_vals[0])
        grad_pos = 0
        grad_tot = 0
        for iy in range(ny):
            for ix in range(nx - 1):
                grad_tot += 1
                if grid_vals[iy][ix + 1] >= grid_vals[iy][ix]:
                    grad_pos += 1
        mono_score = grad_pos / grad_tot if grad_tot > 0 else 1.0
        monotonicity_preserved = bool(mono_score >= 0.85)

        # 4. Cross-match evaluation
        gen_report: Optional[CrossMatchGeneralizationReport] = None
        target_eval_match = test_match_id or ("syn_transitions" if match_id != "syn_transitions" else "syn_default")
        try:
            if eval_cross_match:
                gen_report = cls.evaluate_cross_match_generalization(
                    train_match_id=match_id,
                    test_match_id=target_eval_match,
                    train_events=events,
                )
        except Exception:
            gen_report = None

        cross_mae = gen_report.cross_match_mae if gen_report else None
        cross_rmse = gen_report.cross_match_rmse if gen_report else None
        cross_r = gen_report.cross_match_pearson_r if gen_report else None

        cross_info = (
            f"Cross-match Pearson r: {cross_r:.3f}."
            if cross_r is not None
            else "Cross-match generalization: not evaluated or insufficient data."
        )
        summary = (
            f"BL-09 Scientific Validation Benchmark: {iterations} bootstrap resamples completed (seed={seed}). "
            f"Home xG 95% CI: [{ci_list[0].ci_lower_95}, {ci_list[0].ci_upper_95}], "
            f"Away xG 95% CI: [{ci_list[1].ci_lower_95}, {ci_list[1].ci_upper_95}], "
            f"xT added 95% CI: [{ci_list[2].ci_lower_95}, {ci_list[2].ci_upper_95}]. "
            f"Monotonicity score: {mono_score:.2%}. {cross_info}"
        )

        return ScientificValidationReport(
            report_id=f"rep-val-{match_id}-{seed}",
            match_id=match_id,
            dataset_fingerprint=fingerprint,
            bootstrap_iterations=iterations,
            confidence_intervals=ci_list,
            cross_match_mae=round(cross_mae, 4) if cross_mae is not None else None,
            cross_match_rmse=round(cross_rmse, 4) if cross_rmse is not None else None,
            cross_match_pearson_r=round(cross_r, 4) if cross_r is not None else None,
            monotonicity_preserved=monotonicity_preserved,
            generalization_report=gen_report,
            summary=summary,
        )

    # Backwards compatibility alias method
    @classmethod
    def run_bootstrap_validation(
        cls,
        match_id: str,
        events: Sequence[dict[str, Any] | NormalizedEvent],
        iterations: int = 100,
        seed: int = 42,
    ) -> ScientificValidationReport:
        """Backwards compatible wrapper for run_bootstrap_resampling."""
        return cls.run_bootstrap_resampling(
            match_id=match_id,
            events=events,
            iterations=iterations,
            seed=seed,
            eval_cross_match=False,
        )


# Backward compatibility alias
ScientificValidationEngine = ScientificEvaluationBenchmark


# ---------------------------------------------------------------------------
# Quantitative Agent Benchmark Evaluator (A/B/C Configurations)
# ---------------------------------------------------------------------------

# The former "agent benchmark" constants (0.375/0.625 accuracy, fixed token
# and latency numbers) were removed in the third-pass audit. The evaluator now
# delegates to the executed deterministic pipeline benchmark.
from .benchmark import (  # noqa: E402
    AgentBenchmarkMetrics,
    AgentBenchmarkSuiteResult,
    AgentBenchmarkHarness,
)


class AgentBenchmarkEvaluator:
    """Runs deterministic publication-pipeline configurations (no model calls)."""

    @classmethod
    def evaluate_match(
        cls,
        match_id: str = "syn_default",
        events: Optional[Sequence[dict[str, Any] | NormalizedEvent]] = None,
        num_windows: int = 5,
        seed: int = 42,
    ) -> AgentBenchmarkSuiteResult:
        from .catalog import MatchCatalog

        if events is None:
            harness = AgentBenchmarkHarness(match_id=match_id)
        else:
            normalized: list[NormalizedEvent] = []
            for ev in events:
                if isinstance(ev, NormalizedEvent):
                    normalized.append(ev)
                else:
                    from .schema import ActionType, RawSourceRecord
                    act = str(_extract_action(ev))
                    action = (
                        ActionType.SHOT if "shot" in act
                        else ActionType.RECOVERY if "recovery" in act
                        else ActionType.CARRY if "carry" in act
                        else ActionType.PASS
                    )
                    normalized.append(NormalizedEvent(
                        event_id=_extract_id(ev, f"ev_{len(normalized)}"),
                        match_id=match_id,
                        source=RawSourceRecord(
                            provider="caller_supplied",
                            provider_event_id=_extract_id(ev, f"raw_{len(normalized)}"),
                            schema_version="1.0.0",
                            license_ref="caller_supplied",
                        ),
                        period=int(_get_field(ev, "period", 1) or 1),
                        clock_seconds=_extract_time(ev),
                        team_id=_extract_team(ev),
                        action_type=action,
                        x=_get_field(ev, "x"),
                        y=_get_field(ev, "y"),
                        end_x=_get_field(ev, "end_x"),
                        end_y=_get_field(ev, "end_y"),
                    ))
            harness = AgentBenchmarkHarness.__new__(AgentBenchmarkHarness)
            harness.match_id = match_id
            harness.events = normalized

        result = harness.run(num_trials=num_windows)
        result.dataset["seed_argument"] = seed
        result.dataset["num_windows_argument"] = num_windows
        return result


def run_agent_benchmark_evaluation(match_id: str = "syn_default") -> AgentBenchmarkSuiteResult:
    """Convenience helper for the deterministic pipeline benchmark."""
    return AgentBenchmarkEvaluator.evaluate_match(match_id=match_id)
