"""Verification test suite for Phase 2:
Seek Control, Match Selection, Claim Registry, Challenge Hardening, and Gate 2.0.
"""
import pytest
from fastapi.testclient import TestClient

from matchlens.main import app
from matchlens.gate import publication_gate_2_0
from matchlens.football import generate_match, freeze


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.post("/api/sessions")
        yield c


def test_seek_control(client):
    # Test seeking to a valid timestamp
    res = client.post("/api/control", json={"action": "seek", "at": 450})
    assert res.status_code == 200
    state = res.json()
    assert state["at"] == 450
    assert state["paused"] is True
    assert state["snapshot_id"] is not None

    # Test clamping beyond format_seconds
    res_clamped = client.post("/api/control", json={"action": "seek", "at": 9999})
    assert res_clamped.status_code == 200
    assert res_clamped.json()["at"] == 720


def test_set_match_control(client):
    res = client.post("/api/control", json={"action": "set_match", "match_id": "syn_transitions"})
    assert res.status_code == 200
    state = res.json()
    assert state["match_id"] == "syn_transitions"
    assert state["scenario"] == "transitions"
    assert state["at"] == 0
    assert state["paused"] is True


def test_challenge_nonexistent_snapshot_rejected(client):
    # Challenge against a non-existent snapshot must return 404
    payload = {
        "claim_id": "claim-possession-without-penetration-h",
        "snapshot_id": "snap-nonexistent-999999",
        "challenge_type": "challenge_causal_interpretation",
        "team": "H",
    }
    res = client.post("/api/challenge", json=payload)
    assert res.status_code == 404
    assert "snapshot_not_found" in res.json()["detail"]


def test_challenge_invalid_claim_rejected(client):
    state = client.post("/api/control", json={"action": "focus", "chapter": "A"}).json()
    snap_id = state["snapshot_id"]

    # Challenge against a completely bogus claim ID must return 404
    payload = {
        "claim_id": "totally_bogus_unregistered_claim_id_xyz",
        "snapshot_id": snap_id,
        "challenge_type": "challenge_causal_interpretation",
        "team": "H",
    }
    res = client.post("/api/challenge", json=payload)
    assert res.status_code == 404
    assert "claim_not_found" in res.json()["detail"]


def test_challenge_idempotency(client):
    state = client.post("/api/control", json={"action": "focus", "chapter": "A"}).json()
    snap_id = state["snapshot_id"]

    payload = {
        "claim_id": "claim-possession-without-penetration-h",
        "snapshot_id": snap_id,
        "challenge_type": "challenge_causal_interpretation",
        "team": "H",
    }
    # First submission
    res1 = client.post("/api/challenge", json=payload)
    assert res1.status_code == 200
    revisions1 = res1.json()["revisions"]
    assert len(revisions1) == 1

    # Second identical submission must not create duplicate revision entries
    res2 = client.post("/api/challenge", json=payload)
    assert res2.status_code == 200
    revisions2 = res2.json()["revisions"]
    assert len(revisions2) == 1


def test_gate_2_0_strict_event_and_metric_rejection():
    events = [
        {"event_id": "ev-1", "timestamp_seconds": 10.0, "team": "H"},
        {"event_id": "ev-2", "timestamp_seconds": 20.0, "team": "N"},
    ]
    # 1. Claim referencing a non-existent event ID (ev-9999) must be rejected
    claim_bad_event = {
        "claim_id": "c-bad-ev",
        "claim_level": 1,
        "text": "Harbor FC completed a pass.",
        "event_ids": ["ev-9999"],
        "metric_ids": ["shots"],
    }
    verdict_ev = publication_gate_2_0(claim_bad_event, match_events=events)
    assert verdict_ev.status == "rejected"
    assert any("ev-9999" in v for v in verdict_ev.rule_violations)

    # 2. Claim referencing a non-existent metric ID (e.g. xG_fake_metric) must be rejected
    claim_bad_metric = {
        "claim_id": "c-bad-metric",
        "claim_level": 1,
        "text": "Harbor FC completed a pass.",
        "event_ids": ["ev-1"],
        "metric_ids": ["xG_fake_metric"],
    }
    verdict_metric = publication_gate_2_0(claim_bad_metric, match_events=events)
    assert verdict_metric.status == "rejected"
    assert any("xG_fake_metric" in v for v in verdict_metric.rule_violations)
