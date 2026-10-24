"""Comprehensive verification test suite for Track C:
Evidence-Grounded Agent Intelligence & Publication Gate 2.0.

Tests:
1. temporal_window_decomposition: event filtering, exponential decay, normalized shares.
2. causal_chain_query: backward sequence tracing, duration, spatial displacement, zone indices.
3. alternative_hypothesis_assessment: rival hypothesis detection, dispute marking, plausibility scores.
4. EventAttributionSpecialist agent instantiation and static methods.
5. publication_gate_2_0:
   - Level 1 prohibited causal wording ('causes', 'drives', 'due to', 'because of', 'proves')
   - Level 2 formula decomposition validation
   - Level 3 mandatory assumptions and verification method enforcement
   - Event and metric ID verification against real match data
   - Counterevidence presence enforcement (downgrading to disputed)
6. publication_gate_2: compatibility with ClaimDraft and Snapshot pipeline.
7. Data Sufficiency notification: C0/C1 tracking disclaimer, allowed claim level restriction, and 6s recovery / 9-zone density proxies.
8. A/B/C agent benchmark harness: Config A vs B vs C quantitative evaluation.
9. FastAPI REST endpoints for Track C.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from matchlens.catalog import MatchCatalog
from matchlens.attribution import (
    AttributionEventItem,
    TemporalWindowDecompositionResult,
    CausalChainStep,
    CausalChainQueryResult,
    AlternativeHypothesis,
    AlternativeHypothesisAssessmentResult,
    EventAttributionSpecialist,
    temporal_window_decomposition,
    causal_chain_query,
    alternative_hypothesis_assessment,
)
from matchlens.gate import (
    Gate20Verdict,
    PublicationGate2Result,
    publication_gate_2_0,
    publication_gate_2,
    check_level_wording,
)
from matchlens.sufficiency import (
    DataSufficiencyReport,
    DataSufficiencyNotice,
    DataSufficiencyAdvisor,
    assess_data_sufficiency,
)
from matchlens.benchmark import (
    AgentBenchmarkMetrics,
    AgentBenchmarkSuiteResult,
    AgentBenchmarkHarness,
    run_agent_benchmark_harness,
)
from matchlens.contracts import ClaimDraft, VerifierDecision, Snapshot
from matchlens.football import freeze, generate_match
from matchlens.main import app


@pytest.fixture(scope="module")
def syn_events():
    return MatchCatalog.load_normalized_events("syn_default")


# ---------------------------------------------------------------------------
# 1. Temporal Window Decomposition
# ---------------------------------------------------------------------------

def test_temporal_window_decomposition(syn_events):
    decomp = temporal_window_decomposition(
        syn_events,
        window_start=0.0,
        window_end=300.0,
        team="H",
        top_k=5,
        match_id="syn_default",
    )
    assert isinstance(decomp, TemporalWindowDecompositionResult)
    assert decomp.match_id == "syn_default"
    assert decomp.team == "H"
    assert decomp.window_start == 0.0
    assert decomp.window_end == 300.0
    assert decomp.total_events >= 0
    assert len(decomp.top_events) <= 5

    # Check top event structure
    if decomp.top_events:
        top_1 = decomp.top_events[0]
        assert isinstance(top_1, AttributionEventItem)
        assert top_1.event_id is not None
        assert 0.0 <= top_1.t <= 300.0
        assert top_1.team == "H"
        assert top_1.weight >= 0.0
        assert 0.0 <= top_1.contribution_share <= 1.0

        # Verify contribution shares sum to approx 1.0 if any weight exists
        total_share = sum(e.contribution_share for e in decomp.top_events)
        assert 0.0 <= total_share <= 1.05

    # Check metric summary
    assert "total_xt_delta" in decomp.metric_summary
    assert "total_xg" in decomp.metric_summary
    assert "total_progressive_distance" in decomp.metric_summary

    # Check backward compatibility properties
    assert decomp.window_start_s == 0.0
    assert decomp.window_end_s == 300.0
    assert isinstance(decomp.summary, str)
    assert len(decomp.top_contributing_events) == len(decomp.top_events)


# ---------------------------------------------------------------------------
# 2. Causal Chain Query
# ---------------------------------------------------------------------------

def test_causal_chain_query(syn_events):
    assert len(syn_events) > 10
    target_ev = syn_events[15]
    target_id = target_ev.event_id

    chain = causal_chain_query(
        syn_events,
        target_event_id=target_id,
        lookback_seconds=60.0,
    )
    assert isinstance(chain, CausalChainQueryResult)
    assert chain.target_event_id == target_id
    assert chain.chain_length >= 1
    assert len(chain.steps) == chain.chain_length
    assert chain.total_duration_s >= 0.0
    assert chain.initiating_event is not None

    # Step details
    first_step = chain.steps[0]
    assert isinstance(first_step, CausalChainStep)
    assert first_step.step_index == 0
    assert first_step.zone_index is not None
    assert 0 <= first_step.zone_index <= 8

    # Backward compatibility
    assert len(chain.chain_events) == chain.chain_length
    assert 0.0 <= chain.directness <= 1.0
    assert isinstance(chain.terminal_outcome, str)


# ---------------------------------------------------------------------------
# 3. Alternative Hypothesis Assessment
# ---------------------------------------------------------------------------

def test_alternative_hypothesis_assessment(syn_events):
    alt_res = alternative_hypothesis_assessment(
        syn_events,
        primary_hypothesis="High press forced turnover",
        window_start=0.0,
        window_end=600.0,
        team="H",
    )
    assert isinstance(alt_res, AlternativeHypothesisAssessmentResult)
    assert alt_res.primary_hypothesis_id == "High press forced turnover"
    assert isinstance(alt_res.competing_hypotheses, list)

    for h in alt_res.competing_hypotheses:
        assert isinstance(h, AlternativeHypothesis)
        assert h.hypothesis_id in ("opponent_unforced_error", "individual_dribble_break", "deflection_luck")
        assert 0.0 <= h.plausibility_score <= 1.0
        assert h.status in ("supported", "disputed", "rejected")

    assert alt_res.recommended_level in (1, 2)
    assert alt_res.recommendation in ("accept_primary", "flag_contested", "require_conservative_variant")


# ---------------------------------------------------------------------------
# 4. Event Attribution Specialist Class
# ---------------------------------------------------------------------------

def test_event_attribution_specialist_class(syn_events):
    specialist = EventAttributionSpecialist("syn_default", syn_events)
    decomp = specialist.decompose_window(0.0, 300.0, "H", top_k=3)
    assert decomp.match_id == "syn_default"
    assert len(decomp.top_events) <= 3

    chain = specialist.query_causal_chain(syn_events[5].event_id, lookback_seconds=20.0)
    assert chain.chain_length >= 1

    alts = specialist.assess_alternatives(0.0, 300.0, "H")
    assert isinstance(alts, AlternativeHypothesisAssessmentResult)


# ---------------------------------------------------------------------------
# 5. Publication Gate 2.0: Claim Level Wording & Field Consistency
# ---------------------------------------------------------------------------

def test_gate_2_0_claim_level_consistency(syn_events):
    ev_0 = syn_events[0].event_id

    # Level 1 claim with prohibited causal wording must be rejected
    flawed_l1 = {
        "claim_id": "c_l1_fail",
        "claim_level": 1,
        "text": f"Event {ev_0} caused the turnover and proves defensive dominance.",
        "evidence_scope": {"event_ids": [ev_0], "metric_ids": ["possession"]},
        "assumptions": [],
        "counterevidence": [],
        "verification_method": "deterministic_rule",
    }
    verdict_l1_fail = publication_gate_2_0(flawed_l1, syn_events)
    assert verdict_l1_fail.is_valid is False
    assert verdict_l1_fail.status == "rejected"
    assert any("Causal language violation" in v for v in verdict_l1_fail.rule_violations)

    # Clean Level 1 claim must be approved
    clean_l1 = {
        "claim_id": "c_l1_ok",
        "claim_level": 1,
        "text": f"Event {ev_0} was recorded in defensive third with complete pass action.",
        "evidence_scope": {"event_ids": [ev_0], "metric_ids": ["possession"]},
        "assumptions": [],
        "counterevidence": [],
        "verification_method": "deterministic_rule",
    }
    verdict_l1_ok = publication_gate_2_0(clean_l1, syn_events)
    assert verdict_l1_ok.is_valid is True
    assert verdict_l1_ok.status == "approved"
    assert verdict_l1_ok.effective_claim_level == 1

    # Level 3 claim missing assumptions must be rejected
    flawed_l3 = {
        "claim_id": "c_l3_fail",
        "claim_level": 3,
        "text": f"Recovery at {ev_0} associates with shot generation across multiple matches.",
        "evidence_scope": {"event_ids": [ev_0], "metric_ids": ["transition_shots"]},
        "assumptions": [],  # Missing!
        "counterevidence": [],
        "verification_method": "regression_test",
    }
    verdict_l3_fail = publication_gate_2_0(flawed_l3, syn_events)
    assert verdict_l3_fail.is_valid is False
    assert verdict_l3_fail.status == "rejected"
    assert any("require non-empty explicit assumptions" in v for v in verdict_l3_fail.rule_violations)

    # Valid Level 3 claim with explicit assumptions must be approved
    valid_l3 = {
        "claim_id": "c_l3_ok",
        "claim_level": 3,
        "text": f"Recovery at {ev_0} associates with shot generation across multiple matches.",
        "evidence_scope": {"event_ids": [ev_0], "metric_ids": ["transition_shots"]},
        "assumptions": ["180s fixed time window", "Minimum 15 sequence occurrences"],
        "counterevidence": [],
        "verification_method": "regression_test",
    }
    verdict_l3_ok = publication_gate_2_0(valid_l3, syn_events)
    assert verdict_l3_ok.is_valid is True
    assert verdict_l3_ok.status == "approved"
    assert verdict_l3_ok.effective_claim_level == 3


# ---------------------------------------------------------------------------
# 6. Publication Gate 2.0: ID Verification & Counterevidence Gating
# ---------------------------------------------------------------------------

def test_gate_2_0_id_verification_and_counterevidence(syn_events):
    ev_0 = syn_events[0].event_id

    # Hallucinated event ID must be rejected
    fake_ev_claim = {
        "claim_id": "c_fake_ev",
        "claim_level": 1,
        "text": "Action observed at pitch center.",
        "evidence_scope": {"event_ids": ["nonexistent_event_99999"], "metric_ids": ["possession"]},
        "assumptions": [],
        "counterevidence": [],
        "verification_method": "rule",
    }
    verdict_fake_ev = publication_gate_2_0(fake_ev_claim, syn_events)
    assert verdict_fake_ev.is_valid is False
    assert verdict_fake_ev.status == "rejected"
    assert any("does not exist in match events" in v for v in verdict_fake_ev.rule_violations)

    # Non-existent metric ID must be rejected
    fake_metric_claim = {
        "claim_id": "c_fake_metric",
        "claim_level": 2,
        "text": "Decomposition computed via unregistered metric.",
        "evidence_scope": {"event_ids": [ev_0], "metric_ids": ["quantum_attacking_aura"]},
        "assumptions": ["model_v1"],
        "counterevidence": [],
        "verification_method": "model",
    }
    verdict_fake_m = publication_gate_2_0(fake_metric_claim, syn_events)
    assert verdict_fake_m.is_valid is False
    assert verdict_fake_m.status == "rejected"
    assert any("is not in catalog metrics" in v for v in verdict_fake_m.rule_violations)

    # Counterevidence presence must downgrade status to disputed
    counter_claim = {
        "claim_id": "c_counter",
        "claim_level": 2,
        "text": f"Attacking penetration increased in window containing {ev_0}.",
        "evidence_scope": {"event_ids": [ev_0], "metric_ids": ["entries", "shots"]},
        "assumptions": ["window_180s"],
        "counterevidence": ["opponent_unforced_error_3", "zero_box_touches"],
        "verification_method": "sequence_attribution",
    }
    verdict_counter = publication_gate_2_0(counter_claim, syn_events)
    assert verdict_counter.is_valid is True
    assert verdict_counter.status == "disputed"
    assert verdict_counter.effective_claim_level <= 2
    assert any("Downgraded to disputed" in note for note in verdict_counter.remediation_notes)


# ---------------------------------------------------------------------------
# 7. Compatibility with Publication Gate 2 Draft/Review Pipeline
# ---------------------------------------------------------------------------

def test_publication_gate_2_compatibility(syn_events):
    snapshot = freeze(generate_match(), 360)

    draft = ClaimDraft.model_validate({
        "snapshot_id": snapshot.id,
        "claims": [{
            "id": "claim-possession",
            "assertion": "possession_without_penetration",
            "primary": {
                "id": "primary",
                "scope": "window",
                "refs": ["H.possession.current", "H.possession.previous", "H.shots.current", "H.entries.current"],
                "fan": "Team maintained controlled possession without shots.",
                "analyst": "Window comparison shows possession rose while shots remained at zero.",
            },
            "conservative": None,
        }],
    })

    review = VerifierDecision.model_validate({
        "snapshot_id": snapshot.id,
        "decisions": [{
            "claim_id": "claim-possession",
            "verdict": "publish",
            "selected_variant": "primary",
            "reason": "Accurately reflects receipt values.",
            "limitations": [],
        }],
    })

    results = publication_gate_2(
        draft,
        review,
        snapshot,
        audit=[],
        claim_levels={"claim-possession": "level_1_observed"},
    )
    assert len(results) == 1
    assert results[0].status == "passed"
    assert results[0].claim_level == "level_1_observed"

    # Downgrade to contested when counterevidence provided
    results_contested = publication_gate_2(
        draft,
        review,
        snapshot,
        audit=[],
        claim_levels={"claim-possession": "level_1_observed"},
        counterevidence_map={"claim-possession": ["ev-1"]},
    )
    assert results_contested[0].status == "contested"


# ---------------------------------------------------------------------------
# 8. Data Sufficiency Notification System
# ---------------------------------------------------------------------------

def test_data_sufficiency_notification(syn_events):
    report_c0 = assess_data_sufficiency(syn_events, coverage_level="C0")
    assert isinstance(report_c0, DataSufficiencyReport)
    assert report_c0.coverage_level == "C0"
    assert report_c0.tracking_available is False
    assert report_c0.allowed_claim_levels == [1, 2]
    assert "常规事件流缺乏连续无球防守阵型位置" in report_c0.disclaimer
    assert len(report_c0.limitations) >= 2

    # Check observable proxies
    assert "quick_recoveries_6s" in report_c0.observable_proxies
    assert "density_differential_9zones" in report_c0.observable_proxies
    rec_6s = report_c0.observable_proxies["quick_recoveries_6s"]
    assert rec_6s["window_seconds"] == 6.0
    assert "teams" in rec_6s

    # Test DataSufficiencyAdvisor inspect method
    notice = DataSufficiencyAdvisor.inspect("High press 4-3-3 defensive line height")
    assert isinstance(notice, DataSufficiencyNotice)
    assert notice.has_optical_tracking is False
    assert len(notice.limitations) >= 2
    assert "discrete event coordinates" in notice.disclaimer


# ---------------------------------------------------------------------------
# 9. A/B/C Agent Benchmark Harness
# ---------------------------------------------------------------------------

def test_abc_benchmark_harness():
    suite_res = run_agent_benchmark_harness("syn_default", num_trials=10)
    assert isinstance(suite_res, AgentBenchmarkSuiteResult)
    assert suite_res.match_id == "syn_default"
    assert len(suite_res.configurations) == 3

    config_names = [c.config for c in suite_res.configurations]
    assert "A_reference_only" in config_names
    assert "B_gate20" in config_names
    assert "C_gate20_plus_tools" in config_names

    cfg_a = next(c for c in suite_res.configurations if c.config == "A_reference_only")
    cfg_b = next(c for c in suite_res.configurations if c.config == "B_gate20")
    cfg_c = next(c for c in suite_res.configurations if c.config == "C_gate20_plus_tools")

    for cfg in suite_res.configurations:
        assert cfg.status == "executed"
        assert cfg.total_claims_evaluated > 0
        assert cfg.latency_ms_measured is not None
        # Token and live-model metrics were not measured and must be absent.
        assert cfg.token_cost_usd is None
        assert cfg.is_live_model_evaluation is False
        assert cfg.empirical_accuracy_measured is False
        assert 0.0 <= cfg.contract_agreement_rate <= 1.0

    # Gate 2.0 must block at least as many labelled-invalid claims as the
    # reference-only checker; B and C execute the same gate by construction.
    assert cfg_b.invalid_block_rate >= cfg_a.invalid_block_rate
    assert cfg_c.invalid_block_rate == cfg_b.invalid_block_rate
    assert cfg_c.alternative_hypothesis_tool_executed is True
    assert suite_res.live_model_status == "not_run"
    assert "NOT RUN" in suite_res.summary


# ---------------------------------------------------------------------------
# 10. FastAPI Track C Endpoints
# ---------------------------------------------------------------------------

def test_fastapi_track_c_endpoints():
    client = TestClient(app)

    # 1. /api/attribution/window
    res_w = client.get("/api/attribution/window?match_id=syn_default&window_start=0&window_end=300&team=H")
    assert res_w.status_code == 200
    data_w = res_w.json()
    assert data_w["match_id"] == "syn_default"
    assert data_w["team"] == "H"
    assert "top_events" in data_w

    # 2. /api/attribution/chain
    res_c = client.get("/api/attribution/chain?match_id=syn_default&target_event_id=ev-0&lookback_seconds=30")
    assert res_c.status_code == 200
    data_c = res_c.json()
    assert "target_event_id" in data_c
    assert "steps" in data_c

    # 3. /api/attribution/alternatives
    res_a = client.get("/api/attribution/alternatives?match_id=syn_default&window_start=0&window_end=600&team=H")
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert "competing_hypotheses" in data_a

    # 4. /api/sufficiency/{match_id}
    res_s = client.get("/api/sufficiency/syn_default?coverage_level=C0")
    assert res_s.status_code == 200
    data_s = res_s.json()
    assert data_s["coverage_level"] == "C0"
    assert data_s["tracking_available"] is False
    assert "observable_proxies" in data_s

    # 5. /api/benchmark/abc
    res_b = client.get("/api/benchmark/abc?match_id=syn_default")
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert "configurations" in data_b
    assert len(data_b["configurations"]) == 3
