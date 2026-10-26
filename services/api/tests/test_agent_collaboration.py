"""R6.3: the plan must state who actually produced it.

The whole submission rests on one distinction being visible: a deterministic
plan is not a two-agent plan, and the UI must never be able to blur them. These
tests pin the data the UI renders.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from matchlens.investigation import _collaboration_summary
from matchlens.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    # The suite must never spend budget: no provider key on this server.
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with TestClient(app) as c:
        assert c.post("/api/sessions").status_code == 200
        yield c


def _investigate(client, **overrides):
    body = {
        "match_id": "syn_default",
        "at": 420,
        "team": "H",
        "focus_type": "moment",
        "question": "Why did attacking activity change around this moment?",
        "execution_mode": "deterministic_planner",
    }
    body.update(overrides)
    response = client.post("/api/investigate", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _seek(client, at: int = 420) -> None:
    assert client.post("/api/control", json={"action": "set_match", "match_id": "syn_default"}).status_code == 200
    assert client.post("/api/control", json={"action": "seek", "at": at}).status_code == 200


# ── Deterministic plans say so ───────────────────────────────────────────────

def test_deterministic_plan_reports_no_agent_stages(client):
    _seek(client)
    plan = _investigate(client)

    collaboration = plan["collaboration"]
    assert collaboration["mode"] == "deterministic_planner"
    assert collaboration["analyst"] is None
    assert collaboration["verifier"] is None
    assert collaboration["requests"] == 0
    assert collaboration["model"] is None
    # The stages the planner really walked, in order.
    assert collaboration["stages"][0] == "CREATED"
    assert "APPROVED" in collaboration["stages"] or "WITHHELD" in collaboration["stages"]
    assert collaboration["gate"]["status"] == plan["gate_preview"]["status"]


def test_requesting_an_agent_without_a_key_degrades_and_says_why(client):
    _seek(client)
    plan = _investigate(client, execution_mode="maf_agent")

    # No key on this server, so the deterministic planner produced the plan and
    # the panel must not claim a model ran.
    assert plan["execution_mode"] == "deterministic_planner"
    assert plan["agent_status"] == "not_run"
    assert plan["agent_error"] == "model_not_configured"
    assert plan["collaboration"]["mode"] == "deterministic_planner"
    assert plan["collaboration"]["analyst"] is None
    assert any("no model provider" in text for text in plan["unresolved"])


# ── A model-backed plan reports the real division of labour ──────────────────

def _registry(tools: list[str]):
    return SimpleNamespace(calls=[SimpleNamespace(tool=name) for name in tools])


def _decision(**overrides):
    base = dict(
        claim_id="claim-1",
        verdict="qualify",
        selected_variant="conservative",
        reason="The primary wording overstates the window; the conservative variant stays inside the receipts.",
        limitations=["Single window only."],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_agent_summary_separates_analyst_and_verifier_work():
    gate = SimpleNamespace(status="qualified", violations=[])
    summary = _collaboration_summary(
        mode="maf_agent",
        history=[{"state": "ANALYSING"}, {"state": "HANDOFF"}, {"state": "VERIFYING"}, {"state": "GATED"}],
        gate=gate,
        requests=6,
        model="deepseek-flash",
        analyst_registry=_registry(["get_evidence", "query_metric"]),
        verifier_registry=_registry(["get_evidence", "find_counterevidence"]),
        draft={"claims": [{"id": "claim-1", "assertion": "recoveries_followed_by_shots"}]},
        draft_sha256="abc123",
        review=SimpleNamespace(decisions=[_decision()]),
    )

    assert summary["mode"] == "maf_agent"
    assert summary["requests"] == 6
    assert summary["stages"] == ["ANALYSING", "HANDOFF", "VERIFYING", "GATED"]

    analyst = summary["analyst"]
    assert analyst["tool_calls"] == 2
    assert analyst["tools"] == ["get_evidence", "query_metric"]
    assert analyst["claim_id"] == "claim-1"
    assert analyst["assertion"] == "recoveries_followed_by_shots"
    assert analyst["draft_sha256"] == "abc123"

    verifier = summary["verifier"]
    assert verifier["tool_calls"] == 2
    # The flag that makes the claim checkable: did the verifier really look for
    # evidence against the draft?
    assert verifier["counterevidence_checked"] is True
    assert verifier["decisions"][0]["verdict"] == "qualify"
    assert verifier["decisions"][0]["selected_variant"] == "conservative"
    assert verifier["decisions"][0]["claim_id"] == "claim-1"


def test_verifier_without_a_counterevidence_query_is_not_called_checked():
    gate = SimpleNamespace(status="approved", violations=[])
    summary = _collaboration_summary(
        mode="maf_agent",
        history=[{"state": "VERIFYING"}],
        gate=gate,
        requests=2,
        model="deepseek-flash",
        analyst_registry=_registry(["get_evidence"]),
        verifier_registry=_registry(["get_evidence", "query_metric"]),
        draft={"claims": [{"id": "claim-2", "assertion": "goal_sequence"}]},
        draft_sha256="def456",
        review=SimpleNamespace(decisions=[_decision(verdict="publish", selected_variant=None)]),
    )
    assert summary["verifier"]["counterevidence_checked"] is False
    assert summary["verifier"]["decisions"][0]["verdict"] == "publish"


def test_a_withheld_draft_is_reported_as_withheld():
    gate = SimpleNamespace(status="rejected", violations=["publication_gate: unbound_spelled_number"])
    summary = _collaboration_summary(
        mode="maf_agent",
        history=[{"state": "GATED"}],
        gate=gate,
        requests=4,
        model="deepseek-flash",
        analyst_registry=_registry(["get_evidence"]),
        verifier_registry=_registry(["get_evidence", "find_counterevidence"]),
        draft={"claims": [{"id": "claim-3", "assertion": "goal_sequence"}]},
        draft_sha256="ghi789",
        review=SimpleNamespace(decisions=[_decision(claim_id="claim-3", verdict="withhold", selected_variant=None)]),
    )
    assert summary["gate"]["status"] == "rejected"
    assert summary["gate"]["violations"] == ["publication_gate: unbound_spelled_number"]
    assert summary["verifier"]["decisions"][0]["verdict"] == "withhold"
