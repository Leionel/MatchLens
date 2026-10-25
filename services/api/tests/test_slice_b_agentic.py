"""Slice B offline contract tests: agentic investigation, run lifecycle and
the recorded-replay benchmark harness.

Every test here runs without a live model dispatch. The recorded replay arm
replays genuine recorded model outputs from previously authorized runs;
live-model results stay Not Run by design (no authorized paid budget).
"""
from __future__ import annotations

import asyncio
import pathlib

import pytest
from fastapi.testclient import TestClient

from matchlens.agents import AgentRunner, Run
from matchlens.football import freeze, generate_match, reduce_match
from matchlens.investigation import AgentInvestigationError, InvestigationCancelled, run_maf_investigation
from matchlens.main import InvestigationBody, app, run_investigation_plan
from matchlens.runstore import AgentRunStore, InvalidAgentRunTransition, TERMINAL_STATES
from matchlens.tools import (
    MAX_TOOL_CALLS,
    FootballToolRegistry,
    ToolContext,
    ToolError,
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("MATCHLENS_PRODUCER_TOKEN", "producer-test")
    with TestClient(app) as c:
        # Investigation drafts are private to a server-side session, so the
        # client must own one before it can create or list them.
        assert c.post("/api/sessions").status_code == 200
        # Guarantee that no test in this module can dispatch a paid request.
        c.app.state.engine.runner.key = None
        yield c


def _snap_and_state(at: int = 540):
    snap = freeze(generate_match(), at)
    state = reduce_match(generate_match(), at)
    return snap, state


def _body(**overrides) -> InvestigationBody:
    payload = {"match_id": "syn_default", "at": 540, "question": "Why did the attacking activity change?"}
    payload.update(overrides)
    return InvestigationBody(**payload)


# ---------------------------------------------------------------------------
# 1. Agent Run lifecycle (roadmap C-09)
# ---------------------------------------------------------------------------

def test_agent_run_lifecycle_rejects_invalid_transitions_and_persists(tmp_path):
    path = tmp_path / "agent_runs.json"
    store = AgentRunStore(path)
    record = store.create(
        run_id="arun-lifecycle", trigger="investigation", match_id="syn_default",
        snapshot_id="snap-x", model="deepseek-flash", prompt_version="p",
    )
    assert record.state == "QUEUED"

    for state in ("ANALYSING", "HANDOFF", "VERIFYING", "GATED", "PUBLISHED"):
        store.transition("arun-lifecycle", state, reason="walk")
    assert store.get("arun-lifecycle").state == "PUBLISHED"

    # Invalid transitions are rejected, not coerced.
    with pytest.raises(InvalidAgentRunTransition):
        store.transition("arun-lifecycle", "ANALYSING")
    with pytest.raises(ValueError):
        store.create(run_id="arun-lifecycle", trigger="manual", match_id="m",
                     snapshot_id="s", model="deepseek-flash", prompt_version="p")
    with pytest.raises(ValueError):
        store.cancel("arun-lifecycle")

    # Cancel path and terminal freeze.
    store.create(run_id="arun-cancel", trigger="manual", match_id="m",
                 snapshot_id="s", model="deepseek-flash", prompt_version="p")
    store.cancel("arun-cancel", reason="test cancel")
    assert store.get("arun-cancel").state == "CANCELLED"
    for terminal in ("PUBLISHED", "WITHHELD", "FAILED", "CANCELLED"):
        rid = f"arun-t-{terminal}"
        store.create(run_id=rid, trigger="manual", match_id="m",
                     snapshot_id="s", model="deepseek-flash", prompt_version="p")
        if terminal in ("PUBLISHED", "WITHHELD"):
            for state in ("ANALYSING", "HANDOFF", "VERIFYING", "GATED"):
                store.transition(rid, state)
            store.finish(rid, state=terminal, reason="terminal", origin="live_model")
        elif terminal == "FAILED":
            store.transition(rid, "ANALYSING")
            store.finish(rid, state="FAILED", reason="x", error="x")
        else:
            store.cancel(rid)
        assert store.get(rid).state == terminal

    # Records survive a reload from disk.
    reloaded = AgentRunStore(path)
    assert reloaded.get("arun-lifecycle").state == "PUBLISHED"
    assert reloaded.get("arun-cancel").state == "CANCELLED"


def test_session_run_lifecycle_records_completion_withheld(tmp_path):
    async def scenario():
        from matchlens.main import Engine, Session

        engine = Engine(tmp_path, "fault-injection-not-a-live-key")
        calls = []

        async def fake_runner(run, progress):
            calls.append(run.id)
            await progress("analysing")
            await progress("verifying")
            return {"status": "completed", "origin": "fault_injection", "accepted": [], "rejected": []}

        engine.runner.analyse = fake_runner
        s = Session("lifecycle-withheld", "local", at=360)
        snap = freeze(engine.events, 360)
        assert engine.start_analysis(s, snap, "manual")
        run_id = s.run_info["run_id"]
        await s.task
        record = engine.agent_runs.get(run_id)
        assert record is not None
        assert record.trigger == "manual"
        assert record.state == "WITHHELD"
        states = [entry["state"] for entry in record.state_history]
        assert "ANALYSING" in states and "VERIFYING" in states and "GATED" in states
        assert record.accepted_count == 0
        # The audit snapshot was persisted with the record.
        assert any(entry.get("type") == "trigger" for entry in record.audit)
        reloaded = AgentRunStore(tmp_path / "agent_runs.json")
        assert reloaded.get(run_id).state == "WITHHELD"
        engine.ledger.close()

    asyncio.run(scenario())


def test_session_run_lifecycle_records_cancellation(tmp_path):
    async def scenario():
        from matchlens.main import Engine, Session

        engine = Engine(tmp_path, "fault-injection-not-a-live-key")

        async def fake_runner(run, progress):
            await asyncio.Event().wait()  # never completes; cancelled below

        engine.runner.analyse = fake_runner
        s = Session("lifecycle-cancel", "local", at=360)
        snap = freeze(engine.events, 360)
        assert engine.start_analysis(s, snap, "manual")
        run_id = s.run_info["run_id"]
        s.invalidate()
        await asyncio.gather(s.task, return_exceptions=True)
        record = engine.agent_runs.get(run_id)
        assert record.state == "CANCELLED"
        assert engine.agent_runs.get(run_id).state in TERMINAL_STATES
        engine.ledger.close()

    asyncio.run(scenario())


def test_no_agent_run_record_without_model_key(tmp_path):
    async def scenario():
        from matchlens.main import Engine, Session

        engine = Engine(tmp_path, None)
        s = Session("no-record", "local", at=360)
        snap = freeze(engine.events, 360)
        assert engine.start_analysis(s, snap, "manual") in (True, False)
        # Deterministic fallback runs create no agent run record.
        assert engine.runner.key is None
        assert all(record.trigger != "manual" or record.match_id != "syn_default"
                   for record in engine.agent_runs.list()) if engine.agent_runs.list() else True
        engine.ledger.close()

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 2. Investigation execution modes (isomorphic contract)
# ---------------------------------------------------------------------------

def test_deterministic_investigation_api_stays_default(client):
    res = client.post("/api/investigate", json={
        "match_id": "syn_default", "at": 540, "team": "H",
        "focus_type": "moment", "question": "Why did the attacking activity change?",
    })
    assert res.status_code == 200
    plan = res.json()
    assert plan["execution_mode"] == "deterministic_planner"
    assert plan["agent_status"] == "not_run"
    assert plan["agent_run_id"] is None
    assert plan["tool_receipts"], "deterministic plan keeps real tool receipts"


def test_maf_agent_mode_without_model_falls_back_honestly(client):
    engine = client.app.state.engine
    assert engine.runner.key is None
    res = client.post("/api/investigate", json={
        "match_id": "syn_default", "at": 540, "team": "H",
        "focus_type": "moment", "question": "Why did the attacking activity change?",
        "execution_mode": "maf_agent",
    })
    assert res.status_code == 200
    plan = res.json()
    assert plan["execution_mode"] == "deterministic_planner"
    assert plan["agent_status"] == "not_run"
    assert plan["agent_error"] == "model_not_configured"
    assert any("deterministic planner" in item for item in plan["unresolved"])
    # No paid request was reserved by the fallback.
    assert engine.ledger.summary()["requests_reserved"] == 0


def test_maf_agent_mode_without_runway_falls_back(client):
    engine = client.app.state.engine
    engine.runner.key = "fault-injection-not-a-live-key"
    engine.ledger.max_requests = 0
    try:
        res = client.post("/api/investigate", json={
            "match_id": "syn_default", "at": 540, "team": "H",
            "focus_type": "moment", "question": "Why did the attacking activity change?",
            "execution_mode": "maf_agent",
        })
        assert res.status_code == 200
        plan = res.json()
        assert plan["agent_error"] == "agent_budget_no_runway"
        assert plan["agent_status"] == "not_run"
        assert engine.ledger.summary()["requests_reserved"] == 0
    finally:
        engine.runner.key = None
        engine.ledger.max_requests = 32


def test_maf_agent_mode_failure_degrades_to_isomorphic_plan(client):
    engine = client.app.state.engine
    engine.runner.key = "fault-injection-not-a-live-key"

    async def failing_stage(*args, **kwargs):
        raise ValueError("fault_injection_agent_failure")

    engine.runner.stage_with_registry = failing_stage
    try:
        snap, state = _snap_and_state(540)
        plan = asyncio.run(run_investigation_plan(
            engine, _body(execution_mode="maf_agent"), snap, state, "test-owner"
        ))
        assert plan.execution_mode == "deterministic_planner"
        assert plan.agent_status == "failed"
        assert plan.agent_error == "invalid_agent_output"
        assert plan.agent_run_id is not None
        assert plan.agent_run is not None and plan.agent_run["state"] == "FAILED"
        assert any("failed" in item for item in plan.unresolved)
        # The failed run record exists with the failure reason and zero spend.
        record = engine.agent_runs.get(plan.agent_run_id)
        assert record is not None and record.state == "FAILED"
        assert record.error == "invalid_agent_output"
        assert engine.ledger.summary()["requests_reserved"] == 0
        # Isomorphic with the deterministic plan: identical field contract.
        deterministic = asyncio.run(run_investigation_plan(engine, _body(), snap, state, "test-owner"))
        assert set(plan.model_dump().keys()) == set(deterministic.model_dump().keys())
    finally:
        engine.runner.key = None


def test_maf_agent_mode_unknown_intent_never_dispatches(client):
    engine = client.app.state.engine
    engine.runner.key = "fault-injection-not-a-live-key"
    try:
        res = client.post("/api/investigate", json={
            "match_id": "syn_default", "at": 540, "team": "H",
            "focus_type": "moment",
            "question": "What is the meaning of life?",
            "execution_mode": "maf_agent",
        })
        assert res.status_code == 200
        plan = res.json()
        assert plan["state"] == "FAILED"
        assert plan["agent_error"] == "agent_mode_unsupported_intent"
        assert plan["agent_status"] == "not_run"
        assert engine.ledger.summary()["requests_reserved"] == 0
    finally:
        engine.runner.key = None


def test_maf_cancellation_closes_run_before_model_dispatch(client):
    engine = client.app.state.engine
    engine.runner.key = "fault-injection-not-a-live-key"
    dispatched: list[str] = []

    async def stage(*args, **kwargs):
        dispatched.append(kwargs.get("role", "unexpected"))
        raise AssertionError("a cancelled investigation must not dispatch a model")

    engine.runner.stage_with_registry = stage
    cancel_event = asyncio.Event()
    cancel_event.set()
    try:
        snap, state = _snap_and_state(540)
        with pytest.raises(InvestigationCancelled):
            asyncio.run(run_maf_investigation(
                runner=engine.runner,
                run_store=engine.agent_runs,
                match_id="syn_default",
                snapshot=snap,
                state=state,
                team="H",
                focus_type="moment",
                question="Why did the attacking activity change?",
                owner_session_id="test-owner",
                cancel_event=cancel_event,
            ))
        assert dispatched == []
        runs = [r for r in engine.agent_runs.runs.values() if r.trigger == "investigation"]
        assert runs and runs[-1].state == "CANCELLED"
        assert any(entry["state"] == "CANCELLED" for entry in runs[-1].state_history)
        assert engine.ledger.summary()["requests_reserved"] == 0
    finally:
        engine.runner.key = None


def test_cancel_event_aborts_an_in_flight_provider_call():
    async def scenario():
        snap, _state = _snap_and_state(540)
        cancel_event = asyncio.Event()
        run = Run("arun-in-flight", snap, cancel_event=cancel_event)

        async def never_returns():
            await asyncio.Event().wait()

        pending = asyncio.create_task(AgentRunner._await_with_cancel(run, never_returns()))
        await asyncio.sleep(0)
        cancel_event.set()
        with pytest.raises(InvestigationCancelled):
            await pending

    asyncio.run(scenario())


def test_cancel_endpoint_remembers_a_pre_registration_cancel(client):
    # A cancel that wins the race against POST /api/investigate is remembered
    # and the request returns a server-confirmed cancellation, not a plan.
    res = client.post("/api/investigation-requests/phone-cancel-key/cancel")
    assert res.status_code == 200
    payload = res.json()
    assert payload["state"] == "cancel_requested"
    assert payload["active"] is False

    res = client.post("/api/investigate", json={
        "match_id": "syn_default", "at": 540, "team": "H",
        "focus_type": "moment", "question": "Why did the attacking activity change?",
        "request_key": "phone-cancel-key",
    })
    assert res.status_code == 409
    cancelled = res.json()
    assert cancelled["cancelled"] is True
    assert cancelled["state"] == "CANCELLED"


# ---------------------------------------------------------------------------
# 3. Registry contract for model-selected tools
# ---------------------------------------------------------------------------

def test_registry_blocks_unregistered_tools_and_enforces_budgets():
    snap, state = _snap_and_state(360)
    registry = FootballToolRegistry(
        ToolContext(match_id="syn_default", snapshot=snap, state=state, team="H"),
        max_calls=MAX_TOOL_CALLS,
    )
    with pytest.raises(ToolError):
        registry.call("arbitrary_python", {})
    # Per-tool budget: get_match_context allows exactly one call.
    assert registry.call("get_match_context", {}).status == "ok"
    with pytest.raises(ToolError):
        registry.call("get_match_context", {})
    # Bad arguments become an error receipt returned to the model, not a crash.
    call = registry.call("query_metric", {"metric_id": "not_a_metric", "team": "H"})
    assert call.status == "error"
    assert call.error is not None and call.result is None


# ---------------------------------------------------------------------------
# 4. Agent-runs API (C-09 observability)
# ---------------------------------------------------------------------------

def test_agent_runs_api_endpoints(client):
    res = client.get("/api/agent-runs")
    assert res.status_code == 200
    body = res.json()
    assert "runs" in body and body["scope"] == "session_owner"
    # Deployment-wide spend is producer-only operational information.
    assert "budget" not in body
    producer = client.get(
        "/api/agent-runs", headers={"X-MatchLens-Token": "producer-test"}
    ).json()
    assert "budget" in producer and producer["scope"] == "producer_all"
    assert client.get("/api/agent-runs/does-not-exist").status_code == 404
    assert client.post("/api/agent-runs/does-not-exist/cancel").status_code == 404


# ---------------------------------------------------------------------------
# 5. Recorded-replay contract benchmark (no paid model, no synthetic metrics)
# ---------------------------------------------------------------------------

def test_recorded_replay_benchmark_executes_and_live_arms_not_run():
    from matchlens.benchmark import run_agent_contract_benchmark

    suite = run_agent_contract_benchmark()
    assert suite.live_model_status == "not_run"
    arms = {arm.arm: arm for arm in suite.arms}
    assert set(arms) == {
        "deterministic_gate", "recorded_replay_analyst_verifier",
        "live_single_agent", "live_self_review", "live_analyst_verifier", "live_pair_plus_tools",
    }
    replay = arms["recorded_replay_analyst_verifier"]
    # The repository ships recorded run receipts; if they disappear the arm
    # must say Not Run rather than invent a result.
    if replay.records_found:
        assert replay.status == "executed"
        assert replay.records_replayed == replay.records_found
        assert replay.token_cost_usd is None and replay.token_source == "not_run"
        assert replay.is_live_model_evaluation is False
    else:
        assert replay.status == "not_run"
    for arm_name in ("live_single_agent", "live_self_review", "live_analyst_verifier", "live_pair_plus_tools"):
        arm = arms[arm_name]
        assert arm.status == "not_run"
        assert arm.is_live_model_evaluation is True
        assert arm.token_cost_usd is None
        assert arm.gate_accepted is None and arm.gate_rejected is None
    assert "NOT RUN" in suite.summary
