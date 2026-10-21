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
from matchlens.models.xt import ExpectedThreatModel
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
    assert sb_match.coverage_level == DataCoverageLevel.C1_OPEN_EVENTS
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
