"""Historical-match clock, score and coverage semantics through the HTTP API."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from matchlens.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    with TestClient(app) as c:
        assert c.post("/api/sessions").status_code == 200
        yield c


def _switch(client, match_id: str) -> dict:
    res = client.post("/api/control", json={"action": "set_match", "match_id": match_id})
    assert res.status_code == 200, res.text
    return res.json()


def test_historical_match_uses_its_own_clock_and_never_projects_final_score(client):
    state = _switch(client, "sb_wc2022_final")
    assert state["format_seconds"] == 5400
    assert state["score"] == {"H": 0, "N": 0}
    assert state["official_score"] == {"H": 3, "N": 3}
    assert state["match_context"]["observed_end"] < 5400
    assert state["coverage"]["continuous"] is False

    res = client.post("/api/control", json={"action": "seek", "at": 720})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["at"] == 720
    assert body["score"] == {"H": 0, "N": 0}
    assert body["snapshot_as_of"] == 720

    early = client.post("/api/control", json={"action": "seek", "at": 1400}).json()
    assert early["score"] == {"H": 1, "N": 0}, "as-of score must follow observed goals only"
    assert early["official_score"] == {"H": 3, "N": 3}


def test_seek_clamps_to_match_context_duration(client):
    _switch(client, "sb_wc2022_final")
    res = client.post("/api/control", json={"action": "seek", "at": 99999})
    assert res.status_code == 200, res.text
    assert res.json()["at"] == 5400


def test_partial_coverage_reports_unknown_not_zero(client):
    _switch(client, "sb_wc2022_final")
    client.post("/api/control", json={"action": "seek", "at": 360})
    state = client.get("/api/state").json()
    receipt = state["receipts"]["H.possession.current"]
    assert receipt["denominator"] == 0
    assert receipt["value"] is None
    assert receipt["status"] == "unobserved"

    answer = client.post("/api/ask", json={"intent_id": "possession_vs_penetration"}).json()
    assert "Unknown, not zero" in answer["answer"]


def test_evidence_graph_respects_match_context_clock(client):
    ok = client.get("/api/matches/sb_wc2022_final/evidence-graph?at=2000")
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["as_of"] == 2000
    assert body["snapshot_id"]
    bad = client.get("/api/matches/sb_wc2022_final/evidence-graph?at=5401")
    assert bad.status_code == 422
    assert "at_outside_match_context" in bad.text


def test_synthetic_match_still_reports_complete_coverage(client):
    res = client.post("/api/control", json={"action": "seek", "at": 360})
    assert res.status_code == 200
    state = client.get("/api/state").json()
    assert state["coverage"]["continuous"] is True
    assert state["coverage"]["format_seconds"] == 720
    assert state["receipts"]["H.possession.current"]["status"] == "ok"


def test_story_approval_ignores_caller_fields_by_construction():
    import inspect

    from matchlens.stories import MatchStoryEngine

    params = inspect.signature(MatchStoryEngine.generate_story).parameters
    assert "verified_claims" not in params
    assert "status" not in params
    assert "gate_passed" not in params


def test_story_endpoint_never_claims_broadcast_approval_without_editorial(client):
    story = client.get("/api/matches/sb_wc2022_final/story").json()
    assert story["approval_status"] in ("draft_pending_gate", "draft_pending_editorial")
    assert story["approved_claims_count"] == 0
    assert story["snapshot_id"]
    assert all("gate_status" in c for c in story["claims"])


def test_fabricated_editorial_approval_is_rejected(client):
    res = client.post("/api/story/editorial-approval", json={
        "match_id": "sb_wc2022_final",
        "snapshot_id": "snap-does-not-exist",
        "claim_id": "claim-invented-claim",
        "approver": "Nobody",
        "decision": "approved",
    })
    assert res.status_code == 404
    assert "claim_not_registered" in res.text


def test_challenge_idempotency_key_conflict_and_distinct_payloads(client):
    state = client.post("/api/control", json={"action": "focus", "chapter": "A"}).json()
    snap_id = state["snapshot_id"]
    base = {
        "claim_id": "claim-possession-without-penetration-h",
        "snapshot_id": snap_id,
        "challenge_type": "check_counterevidence",
        "team": "H",
        "idempotency_key": "third-pass-key",
    }
    first = client.post("/api/challenge", json=base)
    assert first.status_code == 200, first.text

    conflict = client.post("/api/challenge", json={**base, "challenge_type": "check_comparison_window"})
    assert conflict.status_code == 409
    assert "idempotency_key_conflict" in conflict.text

    # A different, legitimate challenge of the same type must be stored separately.
    other = client.post("/api/challenge", json={
        **base,
        "idempotency_key": None,
        "challenge_type": "check_comparison_window",
        "user_concern": "Different window question",
    })
    assert other.status_code == 200, other.text
    outcomes = {(r["claim_id"], r["challenge_type"]) for r in other.json()["revisions"]}
    assert ("claim-possession-without-penetration-h", "check_counterevidence") in outcomes
    assert ("claim-possession-without-penetration-h", "check_comparison_window") in outcomes


def test_challenge_result_survives_process_restart(tmp_path, monkeypatch):
    """The same idempotency key returns the stored verdict in a new process."""
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    with TestClient(app) as first:
        first.post("/api/sessions")
        state = first.post("/api/control", json={"action": "focus", "chapter": "A"}).json()
        payload = {
            "claim_id": "claim-possession-without-penetration-h",
            "snapshot_id": state["snapshot_id"],
            "challenge_type": "check_counterevidence",
            "team": "H",
            "idempotency_key": "restart-key",
        }
        assert first.post("/api/challenge", json=payload).status_code == 200

    with TestClient(app) as second:
        second.post("/api/sessions")
        replay = second.post("/api/challenge", json=payload)
        assert replay.status_code == 200, replay.text
        assert replay.json()["reused"] is True
        assert replay.json()["result"]["outcome"] in ("maintained", "narrowed", "inconclusive")
