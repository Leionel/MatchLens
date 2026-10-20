import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
import httpx
from fastapi.testclient import TestClient

from matchlens.agents import AgentRunner, Run
from matchlens.budget import BudgetExceeded, BudgetLedger
from matchlens.football import freeze, generate_match
from matchlens.main import Engine, Session, app


def test_budget_reserves_durably_before_send_and_never_refunds(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db", max_requests=4, max_usd=.06)
    def attempt(_):
        try:
            return ledger.reserve("fault-injection", "Analyst")
        except BudgetExceeded:
            return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(attempt, range(10)))
    assert len([i for i in ids if i]) == 3
    ledger.close()
    reopened = BudgetLedger(tmp_path / "budget.db", max_requests=4, max_usd=.06)
    assert reopened.summary()["requests_reserved"] == 3
    with pytest.raises(BudgetExceeded):
        reopened.reserve("retry", "Verifier")
    reopened.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with TestClient(app) as client:
        yield client


def test_session_focus_evidence_and_missing_model_fallback(client):
    assert client.get("/api/state").status_code == 401
    assert client.post("/api/sessions").status_code == 200
    cookie = client.cookies.get("matchlens_session")
    client.post("/api/sessions")
    assert cookie == client.cookies.get("matchlens_session")
    a = client.post("/api/control", json={"action": "focus", "chapter": "A"}).json()
    assert a["at"] == 360 and a["paused"]
    ev = client.get("/api/evidence/"+a["snapshot_id"]).json()
    assert ev["receipts"]["H.shots.current"]["value"] == 0
    assert client.get("/api/evidence/not-in-session").status_code == 404
    assert client.post("/api/analyse").status_code == 202
    for _ in range(50):
        s = client.get("/api/state").json()
        if s["result"]:
            break
    assert s["result"]["origin"] == "deterministic"
    assert s["result"]["error"] == "model_not_configured"
    old_epoch = s["epoch"]
    b = client.post("/api/control", json={"action": "focus", "chapter": "B"}).json()
    assert b["epoch"] > old_epoch and b["result"] is None
    resumed = client.post("/api/control", json={"action": "exit_focus"}).json()
    assert resumed["focus"] is None and not resumed["paused"]
    # Detected moments can now be investigated without freezing replay.
    assert client.post("/api/analyse").status_code == 202
    assert client.get("/api/missing").headers["content-type"].startswith("application/json")


def test_same_origin_and_creation_limits(client):
    assert client.post("/api/sessions", headers={"Origin": "https://attacker.example"}).status_code == 403
    for _ in range(8):
        client.cookies.clear()
        assert client.post("/api/sessions").status_code == 200
    client.cookies.clear()
    assert client.post("/api/sessions").status_code == 503


def test_late_result_cannot_publish_after_epoch_change(tmp_path):
    # Fault injection deliberately ignores cancellation; this is NOT a model quality test.
    async def scenario():
        eng = Engine(tmp_path, None)
        s = Session("test", "local", at=360, focus="A")
        snap = freeze(eng.events, 360)
        s.snapshots[snap.id] = snap
        started, release = asyncio.Event(), asyncio.Event()
        async def late_runner(run, progress):
            started.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
            return {"status": "completed", "origin": "fault_injection", "accepted": [], "rejected": []}
        eng.runner.analyse = late_runner
        run = Run("late-test", snap)
        s.task = asyncio.create_task(eng.execute(s, snap, 0, run))
        await started.wait()
        s.invalidate()
        s.focus, s.at = "B", 540
        release.set()
        await s.task
        assert not s.cache and s.run_info is None
        record = json.loads((tmp_path / "runs" / "late-test.json").read_text())
        assert any(e["type"] == "superseded" for e in record["audit"])
        eng.ledger.close()
    asyncio.run(scenario())


def test_provider_error_no_retry_and_budget_prevents_transport(tmp_path, monkeypatch):
    import matchlens.agents as agent_module
    real_client = httpx.AsyncClient
    dispatched = []
    def fail(request):
        dispatched.append(request)
        return httpx.Response(503, json={"error": {"message": "Injected test failure", "type": "server_error"}})
    class InjectedHTTPClient(real_client):
        def __init__(self, **kw):
            super().__init__(transport=httpx.MockTransport(fail), **kw)
    monkeypatch.setattr(agent_module.httpx, "AsyncClient", InjectedHTTPClient)
    async def scenario():
        ledger = BudgetLedger(tmp_path / "limited.db", max_requests=1)
        runner = AgentRunner("test-credential-not-live", ledger)
        async def progress(status):
            pass
        first = await runner.analyse(Run("injected-503", freeze(generate_match(), 360)), progress)
        assert first["status"] == "fallback" and not first["accepted"]
        assert len(dispatched) == 1 and ledger.summary()["requests_reserved"] == 1
        blocked = await runner.analyse(Run("blocked-before-send", freeze(generate_match(), 360)), progress)
        assert blocked["error"] == "inference_budget_exhausted"
        assert len(dispatched) == 1  # SDK hook rejected before MockTransport, not after it.
        ledger.close()
    asyncio.run(scenario())


def test_timeout_has_no_unreviewed_card(tmp_path):
    async def scenario():
        ledger = BudgetLedger(tmp_path / "timeout.db")
        runner = AgentRunner("test-credential-not-live", ledger, deadline=.02)
        async def slow_stage(*args):
            await asyncio.sleep(1)
        runner.stage = slow_stage
        async def progress(status):
            pass
        result = await runner.analyse(Run("injected-timeout", freeze(generate_match(), 360)), progress)
        assert result["error"] == "analysis_timeout" and not result["accepted"]
        assert ledger.summary()["requests_reserved"] == 0
        ledger.close()
    asyncio.run(scenario())


def test_other_session_cannot_read_snapshot(client):
    client.post("/api/sessions")
    state = client.post("/api/control", json={"action": "focus", "chapter": "A"}).json()
    client.cookies.clear()
    client.post("/api/sessions")
    assert client.get("/api/evidence/"+state["snapshot_id"]).status_code == 404


def test_detected_goal_focus_preserves_actual_event_time(client):
    client.post("/api/sessions")
    state = client.post("/api/control", json={"action": "focus", "chapter": "C"}).json()
    goal = next(m for m in state["moments"] if m.get("assertion") == "goal_sequence")
    focused = client.post("/api/control", json={"action": "focus_moment", "moment_id": goal["id"]}).json()
    assert focused["at"] == 690 and focused["paused"]
    evidence = client.get("/api/evidence/"+focused["snapshot_id"]).json()
    assert evidence["as_of"] == 690 and max(e["t"] for e in evidence["events"]) == 690
    assert evidence["snapshot_id"] == focused["snapshot_id"]
    assert client.post("/api/control", json={"action": "focus_moment", "moment_id": "not-detected"}).status_code == 409
