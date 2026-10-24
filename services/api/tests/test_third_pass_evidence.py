"""Evidence graph integrity: real relations, stable IDs, no fake zeros."""
from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from matchlens.evidence import build_evidence_graph
from matchlens.football import freeze, generate_match
from matchlens.main import app
from matchlens.registry import ClaimRecord, ClaimRegistry


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    with TestClient(app) as c:
        assert c.post("/api/sessions").status_code == 200
        yield c


def test_graph_contains_real_event_receipt_claim_gate_chain(client):
    story = client.get("/api/matches/syn_default/story").json()
    snapshot_id = story["snapshot_id"]
    graph = client.get(f"/api/matches/syn_default/evidence-graph?at=720").json()
    assert graph["snapshot_id"] == snapshot_id
    types = {n["type"] for n in graph["nodes"]}
    assert {"match", "snapshot", "event", "metric_receipt", "claim", "gate_verdict"} <= types

    relations = {e["relation"] for e in graph["edges"]}
    assert {"observes_at", "records", "computes", "evaluates", "gated_by", "supported_by"} <= relations

    claim_nodes = [n for n in graph["nodes"] if n["type"] == "claim"]
    assert claim_nodes
    approved = [n for n in claim_nodes if n["gate_status"] == "approved"]
    assert approved
    assert all(n["published"] is False for n in claim_nodes)
    assert graph["published_claim_count"] == 0
    assert graph["unpublished_claim_count"] == len(claim_nodes)

    # Every supported_by edge from a claim resolves to a real receipt node.
    node_map = {n["id"]: n for n in graph["nodes"]}
    for edge in graph["edges"]:
        if edge["relation"] == "supported_by":
            assert edge["target"] in node_map
            target = node_map[edge["target"]]
            assert target["type"] in ("metric_receipt", "event")


def test_graph_ids_are_stable_across_calls(client):
    first = client.get("/api/matches/syn_default/evidence-graph?at=540").json()
    second = client.get("/api/matches/syn_default/evidence-graph?at=540").json()
    assert [n["id"] for n in first["nodes"]] == [n["id"] for n in second["nodes"]]
    expected = "snapshot-" + hashlib.sha256(first["snapshot_id"].encode()).hexdigest()[:20]
    assert expected in {n["id"] for n in first["nodes"]}


def test_missing_receipt_becomes_evidence_gap_not_zero():
    snap = freeze(generate_match(), 720)
    registry = ClaimRegistry()
    record = ClaimRecord(
        record_id=f"syn_default::{snap.id}::claim-missing",
        claim_id="claim-missing",
        match_id="syn_default",
        snapshot_id=snap.id,
        as_of=720,
        assertion="goal_sequence",
        subject_team="H",
        claim_level=1,
        statement="Synthetic test claim referencing an absent receipt.",
        evidence_scope={"metric_ids": ["H.absent.metric"], "event_ids": []},
        evidence_hash="test",
        gate_status="approved",
    )
    registry.records[record.record_id] = record

    class Ctx:
        home_team_name = "Harbor FC"
        away_team_name = "Northbridge United"
        provider = "synthetic"
        data_coverage = "C0"
        mode = "synthetic_replay"
        data_version = "1.0.0"
        official_home_score = 1
        official_away_score = 0

    graph = build_evidence_graph(match_id="syn_default", match_context=Ctx(), snapshot=snap, registry=registry)
    gaps = [n for n in graph["nodes"] if n["type"] == "evidence_gap"]
    assert len(gaps) == 1
    assert gaps[0]["value"] is None
    assert gaps[0]["reason"] == "receipt_missing"
    assert not any(
        n["type"] == "metric_receipt" and n["metric_id"] == "H.absent.metric"
        for n in graph["nodes"]
    )


def test_editorial_approval_marks_claim_published_and_challenge_links_revision(client, monkeypatch):
    monkeypatch.setenv("MATCHLENS_PRODUCER_TOKEN", "producer-test")
    story = client.get("/api/matches/syn_default/story").json()
    snapshot_id = story["snapshot_id"]
    approved_claim = next(c for c in story["claims"] if c["gate_status"] == "approved")

    res = client.post(
        "/api/story/editorial-approval",
        headers={"X-MatchLens-Token": "producer-test"},
        json={
            "match_id": "syn_default",
            "snapshot_id": snapshot_id,
            "claim_id": approved_claim["claim_id"],
            "decision": "approved",
            "note": "Reviewed against receipts.",
        },
    )
    assert res.status_code == 200, res.text

    challenge = client.post("/api/challenge", json={
        "claim_id": approved_claim["claim_id"],
        "snapshot_id": snapshot_id,
        "challenge_type": "check_counterevidence",
        "team": "H",
    })
    assert challenge.status_code == 200, challenge.text

    graph = client.get(f"/api/matches/syn_default/evidence-graph?at=720").json()
    types = {n["type"] for n in graph["nodes"]}
    assert {"challenge", "revision"} <= types
    assert graph["published_claim_count"] == 1
    relations = {(e["relation"]) for e in graph["edges"]}
    assert {"challenged_by", "produced", "gated_by"} <= relations
    published = [n for n in graph["nodes"] if n["type"] == "claim" and n["published"]]
    assert len(published) == 1
    assert published[0]["evidence_hash"]


def test_gate20_rejects_empty_evidence_scope():
    from matchlens.gate import publication_gate_2_0

    verdict = publication_gate_2_0(
        {
            "claim_id": "claim-empty-scope",
            "claim_level": 2,
            "text": "Possession increased.",
            "evidence_scope": {},
            "assumptions": ["none"],
            "counterevidence": [],
            "verification_method": "none",
            "metric_versions": {"oaai": "1.0.0"},
        },
        [],
    )
    assert verdict.status == "rejected"
    assert any("no event or metric" in v.lower() for v in verdict.rule_violations)
