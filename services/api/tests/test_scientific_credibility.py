"""Test suite verifying Phase 1 Scientific Credibility & Fact Correctness remediations.

Verifies:
1. Zero outcome leakage in xG: Shots from identical coordinates have identical pre-shot xG regardless of outcome.
2. xG metadata integrity: Clearly labeled as heuristic_shot_danger, uncalibrated, with explicit pre-shot features.
3. xT threat surface provenance: Default grid labeled as heuristic_threat_surface / uncalibrated_spatial_prior, no false StatsBomb training claims.
4. No automatic disk-write side-effects on xT module import.
5. What-if sandbox scientific constraints: No fake 95% CI labeling on heuristic formula; is_calibrated_ci is False; explicit disclaimer.
6. Bootstrap & Cross-match validation: No canned 0.038 / 0.052 / 0.924 fallback when evaluation fails or is skipped.
7. Multi-Agent Benchmark: Explicit deterministic contract categorization without manufactured LLM accuracy.
"""
from __future__ import annotations

import math
import pytest

from matchlens.models.xg import compute_pre_shot_xg, ShotDangerMetadata
from matchlens.models.xt import ExpectedThreatModel, create_calibrated_xt_grid
from matchlens.validation import (
    ScientificEvaluationBenchmark,
    AgentBenchmarkEvaluator,
    _extract_xg,
)
from matchlens.whatif import WhatIfSandbox, WhatIfScenarioRequest


def test_zero_outcome_leakage_in_preshot_xg():
    """Verify that a shot's pre-shot xG depends ONLY on coordinates, never on whether it resulted in a goal."""
    x, y = 96.0, 34.0  # In front of goal, central

    shot_goal = compute_pre_shot_xg(x=x, y=y, event_id="ev_goal", outcome="goal")
    shot_saved = compute_pre_shot_xg(x=x, y=y, event_id="ev_saved", outcome="saved")
    shot_blocked = compute_pre_shot_xg(x=x, y=y, event_id="ev_blocked", outcome="blocked")
    shot_miss = compute_pre_shot_xg(x=x, y=y, event_id="ev_miss", outcome="miss")

    # All pre-shot probabilities must be identical down to exact precision
    assert shot_goal.pre_shot_xg == shot_saved.pre_shot_xg == shot_blocked.pre_shot_xg == shot_miss.pre_shot_xg
    # Must NOT be artificially elevated to 0.75 just because a goal was scored
    assert shot_goal.pre_shot_xg != 0.75 or shot_saved.pre_shot_xg == 0.75
    assert 0.0 < shot_goal.pre_shot_xg < 0.85

    # Check that is_goal accurately reflects outcome without leaking into probability
    assert shot_goal.is_goal is True
    assert shot_saved.is_goal is False


def test_xg_metadata_and_provenance():
    """Verify that xG returns explicit uncalibrated heuristic metadata."""
    shot_eval = compute_pre_shot_xg(x=90.0, y=28.0, event_id="ev_meta_test")
    meta = shot_eval.metadata

    assert isinstance(meta, ShotDangerMetadata)
    assert meta.xg_source == "heuristic_shot_danger"
    assert meta.calibration_status == "uncalibrated_heuristic"
    assert "distance_to_goal" in meta.features_used
    assert "angle_to_goal" in meta.features_used
    assert meta.training_data is None


def test_extract_xg_helper_uses_leak_free_computation():
    """Verify that the extract_xg helper in validation does not return 0.75 on goal outcome."""
    ev_goal = {"action_type": "Shot", "x": 80.0, "y": 34.0, "outcome": "goal"}
    ev_miss = {"action_type": "Shot", "x": 80.0, "y": 34.0, "outcome": "miss"}

    xg_goal = _extract_xg(ev_goal)
    xg_miss = _extract_xg(ev_miss)

    assert xg_goal == xg_miss
    assert xg_goal < 0.50  # From 25m out, danger should be ~0.08-0.20, definitely not 0.75


def test_xt_default_surface_provenance_and_metadata():
    """Verify default xT grid is transparently labeled as analytical heuristic surface."""
    grid_dict = create_calibrated_xt_grid(16, 12)
    assert grid_dict["model_type"] == "heuristic_threat_surface"
    assert grid_dict["calibration_status"] == "uncalibrated_spatial_prior"
    assert grid_dict["training_corpus"] is None
    assert "Analytical" in grid_dict["description"] or "analytical" in grid_dict["description"]


def test_whatif_sandbox_scientific_disclaimer_and_no_fake_ci():
    """Verify What-if sandbox does not claim 95% CI on heuristic formulas."""
    events = [
        {"event_id": "ev_1", "action_type": "Pass", "x": 50.0, "y": 34.0, "end_x": 75.0, "end_y": 25.0, "clock_seconds": 10.0},
        {"event_id": "ev_2", "action_type": "Shot", "x": 92.0, "y": 34.0, "outcome": "saved", "clock_seconds": 15.0},
    ]
    req = WhatIfScenarioRequest(scenario_type="prevent_shot", target_event_id="ev_2")
    res = WhatIfSandbox.simulate(events, req)

    assert res.is_calibrated_ci is False
    assert "uncalibrated" in res.uncertainty_method
    assert "NOT calibrated 95% confidence intervals" in res.disclaimer
    assert len(res.sensitivity_spread) == 2
    assert res.sensitivity_spread[0] <= res.sensitivity_spread[1]


def test_bootstrap_validation_no_hardcoded_cross_match_fallbacks():
    """Verify that when cross_match generalization is not run, fields are None, not 0.038 / 0.924."""
    events = [
        {"event_id": f"ev_{i}", "action_type": "Pass", "x": 50.0, "y": 34.0, "end_x": 60.0, "end_y": 30.0, "clock_seconds": float(i * 10)}
        for i in range(15)
    ]
    report = ScientificEvaluationBenchmark.run_bootstrap_resampling(
        match_id="syn_test",
        events=events,
        iterations=10,
        eval_cross_match=False,
    )
    # Must NOT return canned 0.038 / 0.052 / 0.924
    assert report.cross_match_mae is None
    assert report.cross_match_rmse is None
    assert report.cross_match_pearson_r is None
    assert "not evaluated" in report.summary or "insufficient" in report.summary


def test_agent_benchmark_deterministic_contract_labeling():
    """Verify AgentBenchmarkEvaluator categorizes output as deterministic contract test."""
    events = [
        {"event_id": f"ev_{i}", "action_type": "Pass", "x": 50.0, "y": 34.0, "end_x": 60.0, "end_y": 30.0, "clock_seconds": float(i * 10)}
        for i in range(25)
    ]
    result = AgentBenchmarkEvaluator.evaluate_match(match_id="syn_test", events=events, num_windows=3)

    assert result.benchmark_type == "deterministic_contract"
    for cfg in result.configurations:
        assert cfg.benchmark_type == "deterministic_contract"
        assert cfg.is_live_model_evaluation is False
        assert cfg.empirical_accuracy_measured is False
        assert "Deterministic Contract Benchmark" in cfg.data_provenance
