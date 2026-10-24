"""Track A (Data & Analytics Foundation) comprehensive test suite.

Verifies:
1. Four-tier data architecture isolation (RawSourceRecord -> NormalizedEvent -> DerivedMetric -> VerifiedClaim).
2. StatsBomb Open Data ingestion adapter (BL-01):
   - Affine coordinate transformations (120x80 yd -> 105x68 m).
   - Clock time & period parsing.
   - Action type and outcome normalization.
   - Attribution and licensing records.
3. Expected Threat (xT) baseline model (XT_MODELING_SPEC.md):
   - Metadata header validation.
   - Continuous bilinear interpolation.
   - Forward threat vs backward threat calculation.
4. Match Catalog & Multi-Match Index (BL-10):
   - C0 synthetic and C1 real match metadata indexing.
   - Loading normalized event streams.
5. FastAPI REST API endpoints.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from matchlens.main import app
from matchlens.schema import (
    ActionType,
    DataCoverageLevel,
    DerivedMetric,
    NormalizedEvent,
    RawSourceRecord,
    VerifiedClaim,
)
from matchlens.adapters.statsbomb import StatsBombAdapter
from matchlens.models.xt import (
    ExpectedThreatModel,
    ExpectedThreatFitter,
    compare_xt_grids,
    fit_xt_model,
)
from matchlens.catalog import MatchCatalog, MatchMetadata


client = TestClient(app)


def test_schema_four_objects_isolation():
    # 1. RawSourceRecord
    source = RawSourceRecord(
        provider="statsbomb_open_data",
        provider_event_id="sb_001",
        schema_version="1.1",
        license_ref="CC BY-NC-SA 4.0",
        payload_ref="event_payload_001",
    )
    assert source.provider == "statsbomb_open_data"

    # 2. NormalizedEvent (MUST NOT embed derived_xt or model values)
    event = NormalizedEvent(
        event_id="ev_001",
        match_id="m_001",
        source=source,
        period=1,
        clock_seconds=124.5,
        team_id="ARG",
        action_type=ActionType.PASS,
        outcome="complete",
        x=52.5,
        y=34.0,
        end_x=70.0,
        end_y=40.0,
    )
    assert event.x == 52.5
    assert not hasattr(event, "derived_xt")

    # Extra/forbidden attributes raise ValidationError
    with pytest.raises(Exception):
        NormalizedEvent(
            event_id="ev_err",
            match_id="m_001",
            source=source,
            period=1,
            clock_seconds=10.0,
            team_id="ARG",
            action_type=ActionType.PASS,
            derived_xt=0.5,  # Forbidden!
        )

    # 3. DerivedMetric differentiates missing/not-applicable from numeric 0.0
    metric_ok = DerivedMetric(
        metric_id="met_01",
        event_id="ev_001",
        name="delta_xT",
        value=0.015,
        status="ok",
        model_version="1.0.0",
    )
    assert metric_ok.value == 0.015

    metric_na = DerivedMetric(
        metric_id="met_02",
        event_id="ev_001",
        name="delta_xT",
        value=None,
        status="not_applicable",
        model_version="1.0.0",
    )
    assert metric_na.value is None
    assert metric_na.status == "not_applicable"

    # 4. VerifiedClaim with reasoning tier
    claim = VerifiedClaim(
        claim_id="cl_01",
        claim_level=2,  # Metric attribution
        text="Messi's forward pass contributed +0.024 to regional threat value.",
        evidence_scope={"event_ids": ["ev_001"], "match_id": "m_001"},
        assumptions=["Standard xT open-play Markov transition grid"],
        verification_method="deterministic_xt_delta",
    )
    assert claim.claim_level == 2


def test_statsbomb_coordinate_affine_transform():
    # Corner (0, 0) yd -> (0, 0) m
    x0, y0 = StatsBombAdapter.transform_coordinates(0.0, 0.0)
    assert x0 == 0.0
    assert y0 == 0.0

    # Corner (120, 80) yd -> (105, 68) m
    x1, y1 = StatsBombAdapter.transform_coordinates(120.0, 80.0)
    assert x1 == 105.0
    assert y1 == 68.0

    # Center (60, 40) yd -> (52.5, 34.0) m
    xc, yc = StatsBombAdapter.transform_coordinates(60.0, 40.0)
    assert xc == 52.5
    assert yc == 34.0

    # None handling
    xn, yn = StatsBombAdapter.transform_coordinates(None, None)
    assert xn is None
    assert yn is None


def test_statsbomb_clock_parsing():
    # Period 1, minute 22, second 15 -> 1335.0 seconds
    c1 = StatsBombAdapter.parse_clock_seconds(1, 22, 15)
    assert c1 == 22 * 60 + 15

    # Period 2, minute 34, second 10 -> 45*60 + 34*60 + 10 = 4750.0 seconds
    c2 = StatsBombAdapter.parse_clock_seconds(2, 34, 10)
    assert c2 == 45 * 60 + (34 * 60 + 10)

    # Extra time Period 3 -> 90*60 + elapsed
    c3 = StatsBombAdapter.parse_clock_seconds(3, 5, 0)
    assert c3 == 90 * 60 + 300


def test_statsbomb_adapter_full_ingestion():
    raw_sample = [
        {
            "id": "e_test_1",
            "index": 1,
            "period": 1,
            "minute": 10,
            "second": 20,
            "type": {"id": 30, "name": "Pass"},
            "team": {"id": 1, "name": "Argentina"},
            "player": {"id": 10, "name": "Messi"},
            "location": [60.0, 40.0],
            "pass": {
                "end_location": [90.0, 50.0],
                "outcome": None,  # Complete
            },
        },
        {
            "id": "e_test_2",
            "index": 2,
            "period": 1,
            "minute": 10,
            "second": 25,
            "type": {"id": 16, "name": "Shot"},
            "team": {"id": 1, "name": "Argentina"},
            "player": {"id": 11, "name": "Di Maria"},
            "location": [108.0, 40.0],
            "shot": {
                "end_location": [120.0, 40.0, 1.0],
                "outcome": {"id": 97, "name": "Goal"},
            },
        },
    ]

    adapter = StatsBombAdapter(match_id="test_m")
    events = adapter.load_events(raw_sample)

    assert len(events) == 2
    e1, e2 = events

    # Event 1: Pass
    assert e1.action_type == ActionType.PASS
    assert e1.outcome == "complete"
    assert e1.x == 52.5
    assert e1.y == 34.0
    assert e1.end_x == 78.75
    assert e1.end_y == 42.5
    assert e1.source.provider == "statsbomb_open_data"

    # Event 2: Shot
    assert e2.action_type == ActionType.SHOT
    assert e2.outcome == "goal"
    assert e2.x == 94.5  # 108 * (105 / 120)
    assert e2.y == 34.0  # 40 * (68 / 80)


def test_xt_model_loading_and_evaluation():
    # 1. Load model adhering to XT_MODELING_SPEC.md
    model = ExpectedThreatModel.load_default("16x12")
    assert model.nx == 16
    assert model.ny == 12
    assert model.metadata["model_name"] == "matchlens_xt_grid"
    assert "license_and_attribution" in model.metadata

    # 2. Values monotonicity & boundary checks
    # Threat in defensive third vs central box
    v_defensive = model.value_at(15.0, 34.0)
    v_box = model.value_at(98.0, 34.0)
    assert v_box > v_defensive
    assert 0.0 < v_defensive < 0.05
    assert 0.15 < v_box <= 0.35

    # 3. Bilinear interpolation continuity
    # Near boundary between grid cells, delta should be smooth (< 0.02)
    v_a = model.value_at(52.0, 34.0)
    v_b = model.value_at(53.0, 34.0)
    assert abs(v_b - v_a) < 0.02

    # 4. Action evaluation
    source = RawSourceRecord(
        provider="synthetic",
        provider_event_id="e1",
        schema_version="1.0",
        license_ref="test",
    )

    # Forward pass -> positive threat
    fwd_pass = NormalizedEvent(
        event_id="ev_fwd",
        match_id="m1",
        source=source,
        period=1,
        clock_seconds=100.0,
        team_id="H",
        action_type=ActionType.PASS,
        outcome="complete",
        x=50.0,
        y=34.0,
        end_x=85.0,
        end_y=34.0,
    )
    metric_fwd = model.evaluate_action(fwd_pass)
    assert metric_fwd.status == "ok"
    assert metric_fwd.value is not None
    assert metric_fwd.value > 0.02

    # Backward pass -> negative threat
    bwd_pass = NormalizedEvent(
        event_id="ev_bwd",
        match_id="m1",
        source=source,
        period=1,
        clock_seconds=105.0,
        team_id="H",
        action_type=ActionType.PASS,
        outcome="complete",
        x=85.0,
        y=34.0,
        end_x=50.0,
        end_y=34.0,
    )
    metric_bwd = model.evaluate_action(bwd_pass)
    assert metric_bwd.value is not None
    assert metric_bwd.value < -0.02

    # Inapplicable action (e.g. Tackle) -> status not_applicable
    tackle = NormalizedEvent(
        event_id="ev_tkl",
        match_id="m1",
        source=source,
        period=1,
        clock_seconds=110.0,
        team_id="H",
        action_type=ActionType.TACKLE,
        x=50.0,
        y=34.0,
    )
    metric_tkl = model.evaluate_action(tackle)
    assert metric_tkl.status == "not_applicable"
    assert metric_tkl.value is None


def test_match_catalog_and_loading():
    matches = MatchCatalog.list_matches()
    # At least 6 synthetic + 1 real World Cup final
    assert len(matches) >= 7

    # Check synthetic match
    syn = MatchCatalog.get_match("syn_default")
    assert syn is not None
    assert syn.coverage_level == DataCoverageLevel.C0_SYNTHETIC
    assert syn.home_team == "Harbor FC"

    # Check StatsBomb real match
    sb_match = MatchCatalog.get_match("sb_wc2022_final")
    assert sb_match is not None
    assert sb_match.coverage_level in (DataCoverageLevel.C1_OPEN_EVENTS, DataCoverageLevel.C1_PARTIAL)
    assert sb_match.home_team == "Argentina"
    assert sb_match.away_team == "France"

    # Test loading events
    events = MatchCatalog.load_normalized_events("sb_wc2022_final")
    assert len(events) >= 12
    assert all(isinstance(e, NormalizedEvent) for e in events)


def test_api_track_a_endpoints():
    # 1. GET /api/matches
    res_list = client.get("/api/matches")
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert "matches" in data_list
    assert len(data_list["matches"]) >= 7

    # 2. GET /api/matches/{match_id}
    res_meta = client.get("/api/matches/sb_wc2022_final")
    assert res_meta.status_code == 200
    meta = res_meta.json()["match"]
    assert meta["match_id"] == "sb_wc2022_final"
    assert meta["home_team"] == "Argentina"

    # 3. GET /api/matches/{match_id}/events
    res_events = client.get("/api/matches/sb_wc2022_final/events")
    assert res_events.status_code == 200
    data_events = res_events.json()
    assert data_events["count"] >= 12
    assert len(data_events["events"]) >= 12

    # 4. GET /api/models/xt
    res_xt = client.get("/api/models/xt?resolution=16x12")
    assert res_xt.status_code == 200
    xt_data = res_xt.json()
    assert xt_data["model_name"] == "matchlens_xt_grid"
    assert xt_data["grid_resolution"] == {"nx": 16, "ny": 12}
    assert "license_and_attribution" in xt_data

    # 5. GET /api/models/xt/compare
    res_comp = client.get("/api/models/xt/compare?resolution=16x12&match_id=sb_wc2022_final")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert "comparison" in comp_data
    assert comp_data["comparison"]["is_consistent"] is True


def test_statsbomb_own_goal_handling():
    """Verify BL-01 own goal parsing from type and shot outcomes."""
    adapter = StatsBombAdapter(match_id="test_og")
    raw_events = [
        # 1. Type: Own Goal Against
        {
            "id": "og_1",
            "index": 1,
            "period": 1,
            "minute": 15,
            "second": 0,
            "type": {"id": 25, "name": "Own Goal Against"},
            "team": {"id": 1, "name": "Team A"},
            "player": {"id": 101, "name": "Defender Smith"},
            "location": [10.0, 40.0],
        },
        # 2. Shot with type: Own Goal
        {
            "id": "og_2",
            "index": 2,
            "period": 2,
            "minute": 60,
            "second": 30,
            "type": {"id": 16, "name": "Shot"},
            "team": {"id": 2, "name": "Team B"},
            "player": {"id": 102, "name": "Defender Jones"},
            "location": [15.0, 38.0],
            "shot": {
                "type": {"id": 25, "name": "Own Goal"},
                "outcome": {"id": 97, "name": "Goal"},
            },
        },
    ]

    events = adapter.load_events(raw_events)
    assert len(events) == 2
    assert events[0].outcome == "own_goal"
    assert events[0].is_own_goal is True
    assert events[0].action_type == ActionType.OWN_GOAL

    assert events[1].outcome == "own_goal"
    assert events[1].is_own_goal is True
    assert len(adapter.own_goals) == 2


def test_statsbomb_red_yellow_cards_and_player_deficit():
    """Verify card extraction, player expulsion tracking and team man advantage state."""
    adapter = StatsBombAdapter(match_id="test_cards")
    raw_events = [
        # Normal event initializes team player count to 11
        {
            "id": "c_0",
            "index": 1,
            "period": 1,
            "minute": 5,
            "second": 0,
            "type": {"id": 30, "name": "Pass"},
            "team": {"id": 1, "name": "Team Alpha"},
            "location": [60.0, 40.0],
        },
        {
            "id": "c_1",
            "index": 2,
            "period": 1,
            "minute": 12,
            "second": 0,
            "type": {"id": 30, "name": "Pass"},
            "team": {"id": 2, "name": "Team Beta"},
            "location": [60.0, 40.0],
        },
        # Yellow card on Team Alpha
        {
            "id": "c_2",
            "index": 3,
            "period": 1,
            "minute": 20,
            "second": 0,
            "type": {"id": 22, "name": "Foul Committed"},
            "team": {"id": 1, "name": "Team Alpha"},
            "player": {"id": 4, "name": "Alpha Player 4"},
            "foul_committed": {
                "card": {"id": 7, "name": "Yellow Card"},
            },
        },
        # Direct red card on Team Alpha
        {
            "id": "c_3",
            "index": 4,
            "period": 1,
            "minute": 35,
            "second": 0,
            "type": {"id": 22, "name": "Foul Committed"},
            "team": {"id": 1, "name": "Team Alpha"},
            "player": {"id": 5, "name": "Alpha Player 5"},
            "foul_committed": {
                "card": {"id": 6, "name": "Red Card"},
            },
        },
        # Second yellow card on Team Beta via bad behaviour
        {
            "id": "c_4",
            "index": 5,
            "period": 2,
            "minute": 70,
            "second": 0,
            "type": {"id": 24, "name": "Bad Behaviour"},
            "team": {"id": 2, "name": "Team Beta"},
            "player": {"id": 8, "name": "Beta Player 8"},
            "bad_behaviour": {
                "card": {"id": 8, "name": "Second Yellow"},
            },
        },
    ]

    events = adapter.load_events(raw_events)
    assert events[2].card == "yellow_card"
    assert events[3].card == "red_card"
    assert events[4].card == "second_yellow"

    summary = adapter.get_discipline_summary()
    assert summary["yellow_cards_count"] == 1
    assert summary["red_cards_count"] == 2
    # Canonical identity is the provider team ID, never a display name.
    assert summary["team_player_counts"]["1"] == 10
    assert summary["team_player_counts"]["2"] == 10
    assert len(summary["expulsions"]) == 2


def test_statsbomb_non_standard_penalty_shootout():
    """Verify shootout clock handling, period >= 5 parsing and sudden death detection."""
    adapter = StatsBombAdapter(match_id="test_shootout")
    raw_events = []
    # Generate 12 shootout kicks (regular 10 kicks + 2 sudden death kicks)
    for k in range(1, 13):
        team = "ARG" if k % 2 == 1 else "FRA"
        raw_events.append({
            "id": f"pk_{k}",
            "index": k,
            "period": 5 if k <= 10 else 6,
            "minute": 120 + (k // 2),
            "second": (k % 2) * 30,
            "type": {"id": 16, "name": "Shot"},
            "team": {"id": 1 if team == "ARG" else 2, "name": team},
            "player": {"id": 100 + k, "name": f"Kicker {k}"},
            "location": [108.0, 40.0],
            "shot": {
                "type": {"id": 25, "name": "Penalty Shootout"},
                "outcome": {"id": 97, "name": "Goal" if k % 3 != 0 else "Saved"},
            },
        })

    events = adapter.load_events(raw_events)
    assert len(events) == 12
    for ev in events:
        assert 7200.0 <= ev.clock_seconds <= 7600.0

    shootout_summary = adapter.get_shootout_summary()
    assert shootout_summary["is_shootout"] is True
    assert shootout_summary["total_kicks"] == 12
    assert shootout_summary["sudden_death_reached"] is True
    assert "1" in shootout_summary["team_shootout_goals"]
    assert "2" in shootout_summary["team_shootout_goals"]


def test_statsbomb_missing_and_corrupt_coordinates_resilience():
    """Verify graceful handling of None, empty, out-of-bounds, NaN/Inf, and string coords."""
    import math

    # 1. Transform coordinates edge cases
    assert StatsBombAdapter.transform_coordinates(None, 40.0) == (None, None)
    assert StatsBombAdapter.transform_coordinates(60.0, None) == (None, None)
    assert StatsBombAdapter.transform_coordinates("invalid", 40.0) == (None, None)
    assert StatsBombAdapter.transform_coordinates(float("nan"), 40.0) == (None, None)
    assert StatsBombAdapter.transform_coordinates(float("inf"), 40.0) == (None, None)

    # Clamping extreme values
    x_clamped, y_clamped = StatsBombAdapter.transform_coordinates(-50.0, 200.0)
    assert x_clamped == 0.0
    assert y_clamped == 68.0

    # String numeric input
    xs, ys = StatsBombAdapter.transform_coordinates("60.0", "40.0")
    assert xs == 52.5
    assert ys == 34.0

    # 2. Extract location edge cases
    assert StatsBombAdapter.extract_location(None) == (None, None)
    assert StatsBombAdapter.extract_location([]) == (None, None)
    assert StatsBombAdapter.extract_location([50.0]) == (None, None)
    # 3D location
    x3d, y3d = StatsBombAdapter.extract_location([120.0, 40.0, 1.2])
    assert x3d == 105.0
    assert y3d == 34.0

    # 3. NormalizedEvent with missing coords evaluated by xT model
    adapter = StatsBombAdapter(match_id="test_missing")
    raw = [
        {
            "id": "ev_no_loc",
            "index": 1,
            "period": 1,
            "minute": 1,
            "second": 0,
            "type": {"id": 30, "name": "Pass"},
            "team": {"name": "Team A"},
            "location": None,
            "pass": {"end_location": None},
        }
    ]
    evs = adapter.load_events(raw)
    assert evs[0].x is None
    assert evs[0].y is None
    assert evs[0].end_x is None
    assert evs[0].end_y is None

    xt_model = ExpectedThreatModel.load_default("16x12")
    metric = xt_model.evaluate_action(evs[0])
    assert metric.status == "missing_input"
    assert metric.value is None


def test_statsbomb_and_catalog_multi_match_batch_loading():
    """Verify batch ingestion of multiple matches across synthetic and real catalogs."""
    # 1. StatsBombAdapter.load_multiple_matches
    batch_raw = [
        {
            "metadata": {"match_id": "m_1"},
            "events": [
                {
                    "id": "m1_e1",
                    "index": 1,
                    "period": 1,
                    "minute": 1,
                    "second": 0,
                    "type": {"name": "Pass"},
                    "team": {"name": "T1"},
                    "location": [60.0, 40.0],
                }
            ],
        },
        {
            "metadata": {"match_id": "m_2"},
            "events": [
                {
                    "id": "m2_e1",
                    "index": 1,
                    "period": 1,
                    "minute": 2,
                    "second": 0,
                    "type": {"name": "Shot"},
                    "team": {"name": "T2"},
                    "location": [108.0, 40.0],
                    "shot": {"outcome": {"name": "Goal"}},
                }
            ],
        },
        {"metadata": {"match_id": "m_corrupted"}, "events": "not_a_list"},
    ]

    loaded_batch = StatsBombAdapter.load_multiple_matches(batch_raw)
    assert "m_1" in loaded_batch and len(loaded_batch["m_1"]) == 1
    assert "m_2" in loaded_batch and len(loaded_batch["m_2"]) == 1
    assert "m_corrupted" in loaded_batch or "error_match_2" in loaded_batch

    # 2. MatchCatalog.load_multiple_matches & get_batch_summary
    cat_matches = ["syn_default", "syn_counterattack", "sb_wc2022_final"]
    loaded_cat = MatchCatalog.load_multiple_matches(cat_matches)
    assert len(loaded_cat) == 3
    for mid in cat_matches:
        assert len(loaded_cat[mid]) > 0

    batch_summary = MatchCatalog.get_batch_summary(cat_matches)
    assert batch_summary["total_matches"] == 3
    assert batch_summary["total_events"] > 200
    assert batch_summary["passes_count"] > 100
    assert batch_summary["shots_count"] > 10


def test_xt_model_dirichlet_shrinkage_fitting():
    """Verify ExpectedThreatFitter on multi-match event stream with Dirichlet shrinkage."""
    import math

    # Load multi-match event sequence
    batch_events = MatchCatalog.load_multiple_matches(["syn_default", "syn_transitions", "sb_wc2022_final"])
    all_events = []
    for ev_list in batch_events.values():
        all_events.extend(ev_list)

    assert len(all_events) > 250

    # Fit custom model with Dirichlet shrinkage
    fitter = ExpectedThreatFitter(
        nx=16,
        ny=12,
        horizon_steps=5,
        alpha_g=5.0,
        alpha_T=10.0,
        alpha_s=5.0,
        spatial_smooth=True,
    )
    fitted_model = fitter.fit(
        all_events,
        match_ids=["syn_default", "syn_transitions", "sb_wc2022_final"],
        competitions=["Simulation League", "FIFA World Cup 2022"],
    )

    # 1. Verify metadata adhering to XT_MODELING_SPEC.md Section 5
    meta = fitted_model.metadata
    assert meta["model_name"] == "matchlens_xt_grid_fitted"
    assert meta["model_version"] == "1.1.0"
    assert meta["grid_resolution"] == {"nx": 16, "ny": 12}
    assert meta["horizon_steps"] == 5
    assert "dirichlet_eb_shrinkage" in meta["smoothing_method"]
    assert meta["training_corpus"]["num_matches"] == 3
    assert meta["training_corpus"]["num_move_events"] > 100
    assert meta["training_corpus"]["num_shot_events"] > 10

    # 2. Values sanity checks
    for r in fitted_model.values:
        for val in r:
            assert isinstance(val, float)
            assert not math.isnan(val)
            assert 0.001 <= val <= 0.35

    # Threat in attacking box is significantly higher than defensive third
    v_def = fitted_model.value_at(15.0, 34.0)
    v_box = fitted_model.value_at(96.0, 34.0)
    assert v_box > v_def


def test_xt_grid_comparison_and_validation():
    """Verify compare_xt_grids against precomputed benchmark grid."""
    baseline = ExpectedThreatModel.load_default("16x12")

    events = MatchCatalog.load_normalized_events("syn_default") + MatchCatalog.load_normalized_events("syn_balanced")
    fitted = fit_xt_model(events, nx=16, ny=12, alpha_g=5.0, alpha_T=10.0)

    comp = compare_xt_grids(fitted, baseline)
    assert "mae" in comp
    assert "rmse" in comp
    assert "correlation" in comp
    assert "zone_mae" in comp
    assert "monotonicity_scores" in comp
    assert "is_consistent" in comp

    # Fitted model with empirical Bayes shrinkage strongly correlates with benchmark
    assert comp["correlation"] > 0.80
    assert comp["mae"] < 0.05
    assert comp["rmse"] < 0.06
    assert comp["is_consistent"] is True

    # Check instance method convenience
    direct_comp = fitted.compare_with(baseline)
    assert direct_comp["correlation"] == comp["correlation"]


def test_xt_spatial_smoothing_removes_discontinuities():
    """Verify 2D Gaussian smoothing eliminates step artifacts while preserving trends."""
    events = MatchCatalog.load_normalized_events("syn_comeback")

    fitter_smooth = ExpectedThreatFitter(nx=16, ny=12, spatial_smooth=True, smooth_sigma=0.8)
    fitter_raw = ExpectedThreatFitter(nx=16, ny=12, spatial_smooth=False)

    m_smooth = fitter_smooth.fit(events)
    m_raw = fitter_raw.fit(events)

    def max_adjacent_delta(values):
        max_d = 0.0
        ny, nx = len(values), len(values[0])
        for iy in range(ny):
            for ix in range(nx - 1):
                max_d = max(max_d, abs(values[iy][ix + 1] - values[iy][ix]))
        return max_d

    delta_smooth = max_adjacent_delta(m_smooth.values)
    delta_raw = max_adjacent_delta(m_raw.values)

    assert delta_smooth <= delta_raw + 1e-4
    assert m_smooth.value_at(95.0, 34.0) > m_smooth.value_at(20.0, 34.0)

