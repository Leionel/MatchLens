"""OpenAPI and response-contract checks for the third-pass surface."""
from __future__ import annotations

from fastapi.testclient import TestClient

from matchlens.main import app


def test_openapi_exposes_third_pass_endpoints():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    required = [
        "/api/state",
        "/api/control",
        "/api/challenge",
        "/api/matches/{match_id}/story",
        "/api/story/editorial-approval",
        "/api/matches/{match_id}/evidence-graph",
        "/api/matches/compare",
        "/api/benchmark/abc",
        "/api/matches/{match_id}/validation",
        "/api/metrics",
        "/api/metrics/{metric_id}",
        "/api/investigate",
        "/api/claims/history",
        "/api/broadcast/queue",
        "/api/broadcast/rundown",
        "/api/broadcast/export",
    ]
    for path in required:
        assert path in paths, path


def test_story_and_graph_response_contracts():
    with TestClient(app) as client:
        client.post("/api/sessions")
        story = client.get("/api/matches/syn_default/story")
        assert story.status_code == 200
        body = story.json()
        assert {
            "story_id", "match_id", "snapshot_id", "approval_status",
            "chapters", "summary_verdict", "approved_claims_count",
            "gate_verified_claims_count", "coverage", "claims",
        } <= set(body)
        assert body["approval_status"] in (
            "approved_for_broadcast", "draft_pending_gate",
            "draft_pending_editorial", "contested",
        )

        graph = client.get("/api/matches/syn_default/evidence-graph?at=360")
        assert graph.status_code == 200
        graph_body = graph.json()
        assert {
            "nodes", "edges", "snapshot_id", "data_version",
            "published_claim_count", "unpublished_claim_count", "coverage",
        } <= set(graph_body)
        for node in graph_body["nodes"]:
            assert "source" in node and "data_version" in node


def test_benchmark_response_has_no_fabricated_cost_or_accuracy():
    with TestClient(app) as client:
        res = client.get("/api/benchmark/abc?match_id=syn_default")
    assert res.status_code == 200
    body = res.json()
    assert body["live_model_status"] == "not_run"
    for cfg in body["configurations"]:
        assert cfg["token_cost_usd"] is None
        assert cfg["is_live_model_evaluation"] is False
        assert cfg["empirical_accuracy_measured"] is False
        assert 0.0 <= cfg["contract_agreement_rate"] <= 1.0
