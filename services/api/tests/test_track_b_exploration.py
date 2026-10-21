"""Comprehensive Track B Test Suite: Interactive Football Exploration.

Tests:
1. BL-02 OAAI (Layer A, Layer B, Layer C, Causal Filter Leakage Invariance, Change-points & Level 2 Attribution)
2. BL-03 Quick Ball Recovery within 6s (Parameterization, Monotonicity, Observable fact disclaimer)
3. BL-04 Team Action Density Differential (Zone partition, Share sums, Overlap detection, Disclaimer)
4. BL-08 Attacking Channels (Progression penetration, Box conversion rate, Direction handling)
5. S2 x S3 Dual Drilldown (Bidirectional indexing consistency)
6. BL-12 Highlight Locator (Scoring, Priority, Linkage to sequences & events)
7. Cross-Dataset Robustness (Synthetic scenarios + StatsBomb C1 real World Cup match)
"""
from __future__ import annotations

import pytest

from matchlens.football import generate_match, reduce_match, build_sequences, build_tactical_explorer
from matchlens.catalog import MatchCatalog
from matchlens.models.xt import ExpectedThreatModel
from matchlens.oaai import (
    OAAIConfig,
    compute_event_contribution,
    aggregate_oaai_timeline,
    smooth_oaai_timeline,
    detect_change_points,
    compute_oaai,
)
from matchlens.exploration import (
    analyze_quick_recoveries,
    analyze_action_density_differential,
    analyze_attacking_channels,
    build_spatial_sequence_drilldown,
    locate_highlights,
)


@pytest.fixture
def synthetic_events():
    return generate_match(seed=17, scenario="default")


@pytest.fixture
def synthetic_state(synthetic_events):
    return reduce_match(synthetic_events, at=720)


@pytest.fixture
def statsbomb_events():
    return MatchCatalog.load_normalized_events("sb_wc2022_final")


@pytest.fixture
def xt_model():
    return ExpectedThreatModel.load_default("16x12")


# ==============================================================================
# BL-02 OAAI Tests
# ==============================================================================

def test_oaai_layer_a_event_contributions(synthetic_events, xt_model):
    cfg = OAAIConfig()
    shot_ev = next(e for e in synthetic_events if e.kind == "shot")
    pass_ev = next(e for e in synthetic_events if e.kind == "pass")
    rec_ev = next(e for e in synthetic_events if e.kind == "recovery")

    # Shot contribution should be positive and substantial
    signed_c, mag, expl = compute_event_contribution(shot_ev, cfg, xt_model=xt_model)
    assert mag > 0.3
    assert signed_c == mag if shot_ev.team == "H" else -mag
    assert "shot" in expl.lower() or "goal" in expl.lower()

    # Pass contribution
    p_signed, p_mag, p_expl = compute_event_contribution(pass_ev, cfg, xt_model=xt_model)
    assert p_mag >= 0.0

    # High recovery bonus
    high_rec = synthetic_events[0].model_copy(update={"kind": "recovery", "start": (75.0, 34.0), "team": "H"})
    low_rec = synthetic_events[0].model_copy(update={"kind": "recovery", "start": (20.0, 34.0), "team": "H"})
    _, h_mag, _ = compute_event_contribution(high_rec, cfg)
    _, l_mag, _ = compute_event_contribution(low_rec, cfg)
    assert h_mag > l_mag


def test_oaai_layer_b_causal_no_future_leakage(synthetic_events):
    """CRITICAL TEST: At any sample time t, modifying or adding FUTURE events (t_k > t)

    MUST NOT alter OAAI values for time <= t by even a single floating-point bit!
    """
    cfg = OAAIConfig(sample_step_seconds=2.0)
    split_t = 300.0

    # 1. Base timeline
    timeline_base = aggregate_oaai_timeline(synthetic_events, config=cfg, t_end=720.0)

    # 2. Alter only future events occurring after split_t
    mutated_events = []
    for e in synthetic_events:
        if e.t > split_t:
            # Change shot outcomes, coordinates or insert fake events
            mutated_events.append(e.model_copy(update={"outcome": "goal", "start": (100.0, 34.0)}))
        else:
            mutated_events.append(e)

    timeline_mutated = aggregate_oaai_timeline(mutated_events, config=cfg, t_end=720.0)

    # Verify that up to split_t, all points are EXACTLY identical
    base_past = [pt for pt in timeline_base if pt["t"] <= split_t]
    mutated_past = [pt for pt in timeline_mutated if pt["t"] <= split_t]

    assert len(base_past) == len(mutated_past)
    for p1, p2 in zip(base_past, mutated_past):
        assert p1["t"] == p2["t"]
        assert p1["oaai_raw"] == p2["oaai_raw"], f"Leakage detected at t={p1['t']}"
        assert p1["home_intensity"] == p2["home_intensity"]
        assert p1["away_intensity"] == p2["away_intensity"]
        assert p1["causal_event_count"] == p2["causal_event_count"]

    # Verify that future points after split_t DO differ
    future_diffs = [
        abs(p1["oaai_raw"] - p2["oaai_raw"])
        for p1, p2 in zip(timeline_base, timeline_mutated)
        if p1["t"] > split_t + 10.0
    ]
    assert any(d > 0.01 for d in future_diffs)


def test_oaai_layer_c_smoothing_modes(synthetic_events):
    cfg = OAAIConfig()
    raw = aggregate_oaai_timeline(synthetic_events, config=cfg)
    causal = smooth_oaai_timeline(raw, mode="causal", config=cfg)
    bilateral = smooth_oaai_timeline(raw, mode="bilateral", config=cfg)

    assert len(causal) == len(raw)
    assert len(bilateral) == len(raw)
    assert all(p["smoothing_mode"] == "causal" for p in causal)
    assert all(p["smoothing_mode"] == "bilateral" for p in bilateral)


def test_oaai_change_point_detection_and_attribution(synthetic_events):
    cfg = OAAIConfig(inflection_threshold=0.20)
    res = compute_oaai(synthetic_events, config=cfg, smoothing_mode="causal")

    assert "timeline" in res
    assert "change_points" in res
    cps = res["change_points"]
    assert len(cps) >= 1

    for cp in cps:
        assert cp["claim_level"] == 2
        assert "disclaimer" in cp
        assert "top_contributors" in cp
        assert len(cp["top_contributors"]) <= cfg.top_contributors_limit
        for contributor in cp["top_contributors"]:
            assert "event_id" in contributor
            assert "contribution" in contributor
            assert "magnitude" in contributor


# ==============================================================================
# BL-03 Quick Ball Recovery Tests
# ==============================================================================

def test_quick_recoveries_analysis(synthetic_events):
    # Default 6s window
    res_6s = analyze_quick_recoveries(synthetic_events, window_seconds=6.0)
    assert res_6s["window_seconds"] == 6.0
    assert "disclaimer" in res_6s
    assert "严禁宣称'有组织反抢'" in res_6s["disclaimer"]

    teams = res_6s["teams"]
    assert "H" in teams and "N" in teams
    h_rec = teams["H"]
    assert h_rec["total_possession_losses"] > 0
    assert h_rec["quick_recovery_rate"] >= 0.0
    assert h_rec["quick_recoveries_count"] <= h_rec["total_possession_losses"]

    # Parameterization monotonicity test: 10s window should find >= recoveries than 3s window
    res_3s = analyze_quick_recoveries(synthetic_events, window_seconds=3.0)
    res_10s = analyze_quick_recoveries(synthetic_events, window_seconds=10.0)

    assert res_10s["teams"]["H"]["quick_recoveries_count"] >= res_3s["teams"]["H"]["quick_recoveries_count"]


# ==============================================================================
# BL-04 Team Action Density Differential Tests
# ==============================================================================

def test_action_density_differential(synthetic_events):
    res = analyze_action_density_differential(synthetic_events)

    assert res["home_total_actions"] > 0
    assert res["away_total_actions"] > 0
    assert len(res["zones"]) == 9

    # Sum of shares across all 9 zones should equal 100%
    home_sum_pct = sum(z["home_action_share"] for z in res["zones"])
    away_sum_pct = sum(z["away_action_share"] for z in res["zones"])
    assert pytest.approx(100.0, abs=1.5) == home_sum_pct
    assert pytest.approx(100.0, abs=1.5) == away_sum_pct

    # Differential formula verification
    for z in res["zones"]:
        expected_diff = round(z["home_action_share"] - z["away_action_share"], 1)
        assert pytest.approx(z["delta_density_pct"], abs=0.2) == expected_diff
        assert z["advantage"] in ("home", "away", "neutral")
        assert isinstance(z["is_high_density_overlap"], bool)

    assert "disclaimer" in res
    assert "不标记真实争夺或物理对抗强度" in res["disclaimer"]


# ==============================================================================
# BL-08 Attacking Channels Tests
# ==============================================================================

def test_attacking_channels_analysis(synthetic_state):
    events = synthetic_state["events"]
    sequences = build_sequences(synthetic_state)

    h_channels = analyze_attacking_channels(events, sequences=sequences, team="H")
    n_channels = analyze_attacking_channels(events, sequences=sequences, team="N")

    assert h_channels["team"] == "H"
    assert h_channels["attack_direction"] == "right"
    assert n_channels["team"] == "N"
    assert n_channels["attack_direction"] == "left"

    for ch in ("left", "center", "right"):
        data = h_channels["channels"][ch]
        assert data["attacks_count"] >= 0
        assert 0.0 <= data["final_third_penetration_rate"] <= 100.0
        assert 0.0 <= data["box_conversion_rate"] <= 100.0


# ==============================================================================
# S2 x S3 Dual Drilldown Tests
# ==============================================================================

def test_spatial_sequence_drilldown_indexing(synthetic_state):
    sequences = build_sequences(synthetic_state)
    tactical = build_tactical_explorer(synthetic_state, "H")
    zone_cells = tactical["zone_cells"]

    drilldown = build_spatial_sequence_drilldown(sequences, zone_cells)

    assert "zone_to_sequences" in drilldown
    assert "sequence_to_zones" in drilldown
    assert drilldown["total_indexed_sequences"] == len(sequences)

    # Invariance check: If seq is in zone_to_sequences[z], then z MUST be in sequence_to_zones[seq]
    for zid, seq_ids in drilldown["zone_to_sequences"].items():
        for sid in seq_ids:
            assert zid in drilldown["sequence_to_zones"][sid]


# ==============================================================================
# BL-12 Highlight Locator Tests
# ==============================================================================

def test_highlight_locator(synthetic_state, synthetic_events):
    sequences = build_sequences(synthetic_state)
    oaai_res = compute_oaai(synthetic_events)

    highlights = locate_highlights(synthetic_events, sequences, oaai_data=oaai_res)

    assert len(highlights) >= 1
    # Check highlight structure
    for hl in highlights:
        assert hl["highlight_id"].startswith("HL-")
        assert "title" in hl
        assert hl["team"] in ("H", "N", "neutral")
        assert hl["start_t"] <= hl["end_t"]
        assert hl["impact_score"] >= 0.0
        assert len(hl["associated_sequence_ids"]) >= 0
        assert hl["claim_level"] in (1, 2)


# ==============================================================================
# Cross-Dataset Robustness: StatsBomb WC 2022 Final Real Match
# ==============================================================================

def test_track_b_on_statsbomb_real_match(statsbomb_events, xt_model):
    """Verifies that all Track B algorithms run seamlessly on real C1 StatsBomb match data."""
    # 1. OAAI on StatsBomb
    oaai_res = compute_oaai(statsbomb_events, xt_model=xt_model)
    assert len(oaai_res["timeline"]) > 50
    assert "disclaimer" in oaai_res

    # 2. Quick recoveries on StatsBomb
    rec_res = analyze_quick_recoveries(statsbomb_events, window_seconds=6.0)
    assert "H" in rec_res["teams"] or "ARG" in rec_res["teams"] or len(rec_res["teams"]) > 0

    # 3. Density differential on StatsBomb
    diff_res = analyze_action_density_differential(statsbomb_events)
    assert diff_res["home_total_actions"] > 0
    assert len(diff_res["zones"]) == 9

    # 4. Attacking channels on StatsBomb
    ch_res = analyze_attacking_channels(statsbomb_events, team="H")
    assert "channels" in ch_res


# ==============================================================================
# API Endpoints Integration Tests
# ==============================================================================

def test_exploration_api_endpoints():
    from fastapi.testclient import TestClient
    from matchlens.main import app

    with TestClient(app) as client:
        # 1. Session state includes exploration data
        sess_res = client.post("/api/sessions")
        assert sess_res.status_code == 200
        state_res = client.get("/api/state")
        assert state_res.status_code == 200
        data = state_res.json()
        assert "oaai" in data
        assert "quick_recoveries" in data
        assert "density_differential" in data
        assert "attacking_channels" in data
        assert "spatial_drilldown" in data
        assert "highlights" in data

        # 2. Parameterized recovery endpoint
        rec_res = client.get("/api/exploration/recoveries?window_seconds=8.0")
        assert rec_res.status_code == 200
        rec_data = rec_res.json()
        assert rec_data["window_seconds"] == 8.0
        assert "teams" in rec_data

        # 3. Parameterized OAAI endpoint
        oaai_res = client.get("/api/exploration/oaai?smoothing_mode=bilateral")
        assert oaai_res.status_code == 200
        oaai_data = oaai_res.json()
        assert oaai_data["smoothing_mode"] == "bilateral"
        assert len(oaai_data["timeline"]) > 0

        # 4. Multi-match exploration endpoint (synthetic)
        syn_match_res = client.get("/api/matches/syn_default/exploration")
        assert syn_match_res.status_code == 200
        syn_data = syn_match_res.json()
        assert syn_data["match_id"] == "syn_default"
        assert "oaai" in syn_data
        assert "highlights" in syn_data
        assert len(syn_data["sequences"]) > 0

        # 5. Multi-match exploration endpoint (real StatsBomb World Cup Final)
        sb_match_res = client.get("/api/matches/sb_wc2022_final/exploration")
        assert sb_match_res.status_code == 200
        sb_data = sb_match_res.json()
        assert sb_data["match_id"] == "sb_wc2022_final"
        assert "oaai" in sb_data
        assert "highlights" in sb_data


