"""
Track E: Research & Validation Scientific Suite Tests.

Comprehensive verification of:
1. BL-09 Scientific evaluation benchmark & reproducibility protocol
   - Fixed-seed deterministic bootstrap resampling for xG and xT
   - SHA-256 dataset fingerprinting with tamper evidence
   - Monotonicity verification
   - Cross-match generalization across synthetic and World Cup Final 2022 datasets
2. Quantitative A/B/C Multi-Agent Benchmark Evaluator
   - Gate pass/block rates, accuracy, alternative hypothesis coverage
   - Token cost and latency trade-offs
3. Level 3 Research / Exploratory What-If Counterfactual Sandbox
   - Three modes: Descriptive, Scenario-based, Exploratory research
   - Strict Level 3 disclaimer enforcement
   - Perturbations: turnover removal, lateral channel redirection, shot prevention
4. Backwards compatibility with legacy engines and endpoints
"""
import pytest

from matchlens.catalog import MatchCatalog
from matchlens.models.xt import ExpectedThreatModel
from matchlens.validation import (
    AgentBenchmarkEvaluator,
    AgentBenchmarkMetrics,
    CrossMatchGeneralizationReport,
    DatasetFingerprint,
    MetricConfidenceInterval,
    ScientificEvaluationBenchmark,
    ScientificValidationEngine,
    ScientificValidationReport,
    run_agent_benchmark_evaluation,
)
from matchlens.whatif import (
    WhatIfMode,
    WhatIfSandbox,
    WhatIfScenarioRequest,
    WhatIfSimulationEngine,
    WhatIfSimulationResult,
    WHATIF_DISCLAIMER_TEXT,
)


@pytest.fixture
def synthetic_events():
    return MatchCatalog.load_normalized_events("syn_default")


@pytest.fixture
def transitions_events():
    return MatchCatalog.load_normalized_events("syn_transitions")


@pytest.fixture
def wc2022_final_events():
    return MatchCatalog.load_normalized_events("sb_wc2022_final")


# ===========================================================================
# 1. BL-09 Scientific Evaluation Benchmark & Protocol Tests
# ===========================================================================

def test_bootstrap_resampling_deterministic_reproducibility(synthetic_events):
    """Verify fixed seed produces bit-identical point estimates, CIs, and std devs."""
    report_run1 = ScientificEvaluationBenchmark.run_bootstrap_resampling(
        match_id="syn_default",
        events=synthetic_events,
        iterations=40,
        seed=101,
        eval_cross_match=False,
    )
    report_run2 = ScientificEvaluationBenchmark.run_bootstrap_resampling(
        match_id="syn_default",
        events=synthetic_events,
        iterations=40,
        seed=101,
        eval_cross_match=False,
    )

    # Determinism check
    assert report_run1.match_id == "syn_default"
    assert report_run1.bootstrap_iterations == 40
    assert report_run1.dataset_fingerprint.sha256_hash == report_run2.dataset_fingerprint.sha256_hash
    assert report_run1.dataset_fingerprint.seed_used == 101

    assert len(report_run1.confidence_intervals) == 3
    for ci1, ci2 in zip(report_run1.confidence_intervals, report_run2.confidence_intervals):
        assert ci1.metric_name == ci2.metric_name
        assert ci1.point_estimate == ci2.point_estimate
        assert ci1.ci_lower_95 == ci2.ci_lower_95
        assert ci1.ci_upper_95 == ci2.ci_upper_95
        assert ci1.std_dev == ci2.std_dev
        assert ci1.ci_lower_95 <= ci1.point_estimate <= ci1.ci_upper_95

    assert report_run1.monotonicity_preserved is True
    assert "BL-09 Scientific Validation Benchmark" in report_run1.summary


def test_bootstrap_resampling_empty_events_raises_error():
    """Verify empty event stream raises descriptive ValueError."""
    with pytest.raises(ValueError, match="empty_event_stream"):
        ScientificEvaluationBenchmark.run_bootstrap_resampling("syn_empty", [], iterations=10)


def test_dataset_fingerprint_sha256_tamper_evidence(synthetic_events):
    """Verify SHA-256 fingerprint generation is deterministic and tamper-evident."""
    fp1 = ScientificEvaluationBenchmark.generate_fingerprint("syn_default", synthetic_events, seed=42)
    fp2 = ScientificEvaluationBenchmark.generate_fingerprint("syn_default", synthetic_events, seed=42)

    assert fp1.sha256_hash == fp2.sha256_hash
    assert len(fp1.sha256_hash) == 64  # SHA-256 hex string length
    assert fp1.total_events == len(synthetic_events)
    assert fp1.first_timestamp_s <= fp1.last_timestamp_s

    # Tamper with an event in a modified copy
    tampered_events = [ev.model_copy(deep=True) for ev in synthetic_events]
    tampered_events[0].clock_seconds += 5.0
    fp_tampered = ScientificEvaluationBenchmark.generate_fingerprint("syn_default", tampered_events, seed=42)

    assert fp1.sha256_hash != fp_tampered.sha256_hash


def test_cross_match_generalization_synthetic(synthetic_events, transitions_events):
    """Verify generalization evaluation between two distinct synthetic scenarios."""
    report = ScientificEvaluationBenchmark.evaluate_cross_match_generalization(
        train_match_id="syn_default",
        test_match_id="syn_transitions",
        train_events=synthetic_events,
        test_events=transitions_events,
    )

    assert isinstance(report, CrossMatchGeneralizationReport)
    assert report.train_match_id == "syn_default"
    assert report.test_match_id == "syn_transitions"
    assert report.cross_match_mae >= 0.0
    assert report.cross_match_rmse >= 0.0
    assert report.cross_match_pearson_r > 0.70  # Spatial correlation between pitch zones

    # Check zone-wise error breakdown
    assert "defensive_third" in report.zone_mae
    assert "middle_third" in report.zone_mae
    assert "attacking_third" in report.zone_mae
    assert "penalty_box" in report.zone_mae
    assert isinstance(report.is_generalizable, bool)


def test_cross_match_generalization_world_cup_final(synthetic_events, wc2022_final_events):
    """Verify generalization against real StatsBomb 2022 World Cup Final dataset."""
    assert len(wc2022_final_events) >= 10

    report = ScientificEvaluationBenchmark.evaluate_cross_match_generalization(
        train_match_id="syn_default",
        test_match_id="sb_wc2022_final",
        train_events=synthetic_events,
        test_events=wc2022_final_events,
    )

    assert report.test_match_id == "sb_wc2022_final"
    assert report.cross_match_mae >= 0.0
    assert report.cross_match_pearson_r > 0.60
    assert "Cross-match Generalization" in report.summary


# ===========================================================================
# 2. Automated A/B/C Multi-Agent Benchmark Evaluator Tests
# ===========================================================================

def test_agent_benchmark_evaluator_abc_synthetic(synthetic_events):
    """Verify quantitative evaluation of A/B/C multi-agent configurations."""
    result = AgentBenchmarkEvaluator.evaluate_match(
        match_id="syn_default",
        events=synthetic_events,
        num_windows=5,
        seed=42,
    )

    assert result.match_id == "syn_default"
    assert len(result.configurations) == 3

    config_a = next(c for c in result.configurations if c.config == "A_dual_agent")
    config_b = next(c for c in result.configurations if c.config == "B_dual_agent_plus_tools")
    config_c = next(c for c in result.configurations if c.config == "C_triple_agent_specialist")

    # Gate block rate: Config A > Config B > Config C (Triple agent resolves disputes)
    assert config_a.gate_block_rate > config_b.gate_block_rate > config_c.gate_block_rate

    # Accuracy rate: Config C > Config B > Config A
    assert config_c.accuracy_rate > config_b.accuracy_rate > config_a.accuracy_rate

    # Alternative hypothesis coverage: Config C has dedicated specialist
    assert config_c.alternative_hypothesis_coverage > config_b.alternative_hypothesis_coverage > config_a.alternative_hypothesis_coverage

    # Token cost & latency trade-offs: Config C > Config B > Config A
    assert config_c.token_cost_usd_est > config_b.token_cost_usd_est > config_a.token_cost_usd_est
    assert config_c.latency_ms_est > config_b.latency_ms_est > config_a.latency_ms_est

    assert "Configuration C" in result.recommendation
    assert "A/B/C Multi-Agent Benchmark" in result.summary


def test_agent_benchmark_evaluator_world_cup_final(wc2022_final_events):
    """Verify quantitative evaluation executes on real Qatar World Cup Final data."""
    result = AgentBenchmarkEvaluator.evaluate_match(
        match_id="sb_wc2022_final",
        events=wc2022_final_events,
        num_windows=4,
        seed=99,
    )

    assert result.match_id == "sb_wc2022_final"
    assert len(result.configurations) == 3
    for cfg in result.configurations:
        assert cfg.total_claims_evaluated > 0
        assert 0.0 <= cfg.gate_block_rate <= 1.0
        assert 0.0 <= cfg.gate_pass_rate <= 1.0
        assert 0.0 <= cfg.accuracy_rate <= 1.0


def test_run_agent_benchmark_evaluation_helper():
    """Verify convenience runner function."""
    res = run_agent_benchmark_evaluation("syn_default")
    assert res.match_id == "syn_default"
    assert len(res.configurations) == 3


# ===========================================================================
# 3. Level 3 Research What-If Counterfactual Sandbox Tests
# ===========================================================================

def test_whatif_sandbox_modes_and_strict_disclaimers(synthetic_events):
    """Verify Level 3 Research labeling and mandatory exploratory disclaimers."""
    # 1. Descriptive mode (factual baseline re-evaluation)
    req_desc = WhatIfScenarioRequest(
        scenario_type="custom",
        mode="descriptive",
    )
    res_desc = WhatIfSandbox.simulate(synthetic_events, req_desc)
    assert res_desc.mode == "descriptive"
    assert res_desc.claim_level == "level_3_hypothesis"
    assert res_desc.claim_level_int == 3
    assert res_desc.is_exploratory is True
    assert res_desc.is_exploratory_only is True
    assert "Level 3 Research / Exploratory — Not validated for production causal claims" in res_desc.disclaimer
    assert "RESEARCH SANDBOX NOTICE" in res_desc.disclaimer

    # 2. Scenario-based mode
    req_scen = WhatIfScenarioRequest(
        scenario_type="invert_corridor",
        mode="scenario_based",
        target_time_range=(0.0, 300.0),
    )
    res_scen = WhatIfSandbox.simulate(synthetic_events, req_scen)
    assert res_scen.mode == "scenario_based"
    assert res_scen.claim_level_int == 3
    assert res_scen.is_exploratory is True
    assert res_scen.disclaimer == WHATIF_DISCLAIMER_TEXT


def test_whatif_turnover_removal(synthetic_events):
    """Verify removing turnover increases OAAI / threat or calculates counterfactual impact."""
    res = WhatIfSandbox.remove_turnover(
        synthetic_events,
        target_time_range=(0.0, 900.0),
    )

    assert isinstance(res, WhatIfSimulationResult)
    assert res.scenario_type == "remove_turnover"
    assert res.affected_events_count >= 0
    assert len(res.confidence_band) == 2
    assert res.confidence_band[0] <= res.confidence_band[1]
    assert res.is_exploratory is True


def test_whatif_channel_redirection(synthetic_events):
    """Verify channel redirection shifts attack laterally and computes delta threat."""
    res_left = WhatIfSandbox.channel_redirection(
        synthetic_events,
        target_time_range=(0.0, 600.0),
        to_channel="left",
    )

    assert res_left.scenario_type == "channel_redirection"
    assert res_left.claim_level == "level_3_hypothesis"
    assert isinstance(res_left.delta_threat, float)
    assert isinstance(res_left.delta_oaai_amplitude, float)
    assert res_left.confidence_band[0] <= res_left.confidence_band[1]


def test_whatif_prevent_shot(synthetic_events):
    """Verify shot prevention removes shot event and impacts expected goals."""
    res = WhatIfSandbox.prevent_shot(
        synthetic_events,
        target_time_range=(0.0, 5400.0),
    )

    assert res.scenario_type == "prevent_shot"
    assert res.delta_xg <= 0.0001  # Shot removal should not increase xG
    assert res.claim_level_int == 3


def test_whatif_alternate_pass_target(synthetic_events):
    """Verify targeting pass to new coordinates recalculates threat."""
    # Find first pass event
    first_pass = next(
        ev for ev in synthetic_events
        if ev.action_type.value.lower() == "pass" and ev.end_x is not None
    )

    req = WhatIfScenarioRequest(
        scenario_type="alternate_pass_target",
        mode="scenario_based",
        target_event_id=first_pass.event_id,
        alternate_coordinates=(100.0, 34.0),  # Centered inside 6-yard box
    )
    res = WhatIfSandbox.simulate(synthetic_events, req)

    assert res.scenario_type == "alternate_pass_target"
    assert res.affected_events_count == 1
    assert first_pass.event_id in res.affected_event_ids
    assert res.is_exploratory is True


# ===========================================================================
# 4. Backwards Compatibility & Aliasing Tests
# ===========================================================================

def test_backwards_compatibility_aliases(synthetic_events):
    """Verify ScientificValidationEngine and WhatIfSimulationEngine legacy calls."""
    # ScientificValidationEngine alias
    report = ScientificValidationEngine.run_bootstrap_validation(
        match_id="syn_default",
        events=synthetic_events,
        iterations=25,
        seed=77,
    )
    assert report.match_id == "syn_default"
    assert report.bootstrap_iterations == 25
    assert len(report.confidence_intervals) == 3
    assert report.monotonicity_preserved is True

    # WhatIfSimulationEngine alias
    req = WhatIfScenarioRequest(scenario_type="remove_turnover", target_time_range=(0.0, 300.0))
    res = WhatIfSimulationEngine.simulate(synthetic_events, req)
    assert res.claim_level == "level_3_hypothesis"
    assert res.is_exploratory_only is True
    assert "Level 3 Research / Exploratory — Not validated for production causal claims" in res.disclaimer
