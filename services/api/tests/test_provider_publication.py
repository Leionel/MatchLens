"""Provider publication boundary: public analysis vs protected event export."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from matchlens.catalog import MatchCatalog
from matchlens.main import app

MATCH_ID = "sb_3795221"
PRODUCER = {"X-MatchLens-Token": "producer-test"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    meta = MatchCatalog.get_match(MATCH_ID)
    if meta is None or not meta.analysis_ready:
        pytest.skip(f"{MATCH_ID} is not installed in this checkout")
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("MATCHLENS_PRODUCER_TOKEN", "producer-test")
    with TestClient(app) as test_client:
        assert test_client.post("/api/sessions").status_code == 200
        yield test_client


def test_anonymous_event_endpoint_is_a_bounded_projection(client):
    response = client.get(f"/api/matches/{MATCH_ID}/events")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 4691
    assert body["access_tier"] == "public_analysis_projection"
    assert "events" not in body
    assert len(body["sample"]) <= body["sample_limit"] <= 24
    for event in body["sample"]:
        assert "event_id" in event and "t" in event
        assert "start" not in event and "end" not in event and "x" not in event
    assert body["license_ref"] and body["attribution_text"]
    assert body["raw_event_export"] == "requires_producer_data_access"

    # Pagination cannot turn the public projection into the payload.
    for query in ("limit=10000", "offset=0&limit=5000", "page=2&per_page=10000"):
        paged = client.get(f"/api/matches/{MATCH_ID}/events?{query}").json()
        assert "events" not in paged
        assert len(paged["sample"]) <= 24
        assert paged["count"] == 4691


def test_producer_receives_the_complete_event_stream(client):
    response = client.get(f"/api/matches/{MATCH_ID}/events", headers=PRODUCER)
    assert response.status_code == 200
    body = response.json()
    assert body["access_tier"] == "internal_event_access"
    assert len(body["events"]) == 4691
    first = body["events"][0]
    for key in ("event_id", "period", "clock_seconds", "team_id", "action_type"):
        assert key in first
    assert body["attribution_text"]

    invalid = client.get(
        f"/api/matches/{MATCH_ID}/events",
        headers={"X-MatchLens-Token": "wrong-token"},
    )
    assert invalid.status_code == 403


def test_public_state_carries_a_window_not_the_whole_match(client):
    assert client.post(
        "/api/control", json={"action": "set_match", "match_id": MATCH_ID}
    ).status_code == 200
    assert client.post(
        "/api/control", json={"action": "seek", "at": 4000}
    ).status_code == 200
    state = client.get("/api/state").json()

    boundary = state["provider_data_boundary"]
    assert boundary["access_tier"] == "public_analysis_projection"
    assert boundary["state_window"]["total_events_observed"] == 4691
    assert len(state["events"]) <= 160
    # The state coverage count is the observed prefix at this clock; the
    # boundary reports the full recorded stream separately.
    assert 0 < state["coverage"]["event_count"] < 4691
    assert boundary["state_window"]["events_in_window"] > 0
    for step_owner in state["sequences"]:
        for step in step_owner.get("events_detail", []):
            assert "start" not in step and "end" not in step


def test_evidence_endpoint_is_bounded_for_public_sessions(client):
    assert client.post(
        "/api/control", json={"action": "set_match", "match_id": MATCH_ID}
    ).status_code == 200
    assert client.post(
        "/api/control", json={"action": "seek", "at": 4000}
    ).status_code == 200
    snapshot_id = client.get("/api/state").json()["snapshot_id"]
    assert snapshot_id

    public = client.get(f"/api/evidence/{snapshot_id}")
    assert public.status_code == 200
    body = public.json()
    assert body["provider_data_boundary"]["access_tier"] == "public_analysis_projection"
    assert len(body["events"]) <= 160
    assert body["total_event_count"] == body["provider_data_boundary"]["state_window"]["total_events_observed"]

    internal = client.get(f"/api/evidence/{snapshot_id}", headers=PRODUCER)
    assert internal.status_code == 200
    assert len(internal.json()["events"]) == body["total_event_count"]
    assert len(internal.json()["events"]) > len(body["events"])


def test_public_sequence_endpoint_hides_per_event_coordinates(client):
    public = client.get(f"/api/matches/{MATCH_ID}/exploration")
    assert public.status_code == 200
    payload = public.json()
    assert payload["provider_data_boundary"]["access_tier"] == "public_analysis_projection"
    for sequence in payload["sequences"]:
        for step in sequence.get("events_detail", []):
            assert "start" not in step and "end" not in step

    denied = client.get(
        f"/api/matches/{MATCH_ID}/exploration?include_event_detail=true"
    )
    assert denied.status_code == 403
    assert "provider_event_detail_requires_data_access" in denied.text

    full = client.get(
        f"/api/matches/{MATCH_ID}/exploration?include_event_detail=true",
        headers=PRODUCER,
    )
    assert full.status_code == 200
    assert any(
        "start" in step
        for sequence in full.json()["sequences"]
        for step in sequence.get("events_detail", [])
    )


def test_public_evidence_graph_has_references_without_pitch_coordinates(client):
    public = client.get(f"/api/matches/{MATCH_ID}/evidence-graph?at=1800")
    assert public.status_code == 200
    nodes = public.json()["nodes"]
    event_nodes = [node for node in nodes if node["type"] == "event"]
    assert event_nodes
    assert all("start" not in node and "end" not in node for node in event_nodes)

    internal = client.get(
        f"/api/matches/{MATCH_ID}/evidence-graph?at=1800",
        headers=PRODUCER,
    )
    assert internal.status_code == 200
    internal_events = [node for node in internal.json()["nodes"] if node["type"] == "event"]
    assert internal_events
    assert any("start" in node for node in internal_events)


def test_match_detail_points_at_the_public_projection(client):
    detail = client.get(f"/api/matches/{MATCH_ID}/detail")
    assert detail.status_code == 200
    summary = detail.json()["events_summary"]
    assert summary["total"] == 4691
    assert summary["public_events_endpoint"] == "/api/matches/{match_id}/events"
    assert summary["raw_event_export"] == "producer_or_internal_data_access_required"
