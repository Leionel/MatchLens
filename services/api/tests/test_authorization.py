"""Cross-session ownership, producer roles and browser-session hardening."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from matchlens.investigation import InvestigationPlan
from matchlens.main import COOKIE, app


@pytest.fixture()
def clients(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("MATCHLENS_PRODUCER_TOKEN", "producer-test")
    with TestClient(app) as first:
        assert first.post("/api/sessions").status_code == 200
        # A second, independent cookie jar against the same lifespan-managed
        # engine. It must never inherit the first session's identity.
        second = TestClient(app)
        assert second.post("/api/sessions").status_code == 200
        yield first, second


def _investigate(client: TestClient, question: str = "What produced the attacking activity?") -> dict:
    response = client.post(
        "/api/investigate",
        json={
            "match_id": "syn_default",
            "at": 720,
            "team": "H",
            "focus_type": "moment",
            "question": question,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_private_investigation_is_owner_scoped_and_legacy_is_fail_closed(clients):
    first, second = clients
    plan = _investigate(first)
    investigation_id = plan["investigation_id"]
    # The owner key is the server session credential and is never echoed.
    assert "owner_session_id" not in plan
    assert app.state.engine.investigations.get(investigation_id).owner_session_id

    assert first.get(f"/api/investigations/{investigation_id}").status_code == 200
    assert second.get(f"/api/investigations/{investigation_id}").status_code == 404
    assert second.post(f"/api/investigations/{investigation_id}/cancel").status_code == 404
    assert second.post(f"/api/investigations/{investigation_id}/promote").status_code == 404

    second_list = second.get("/api/investigations?match_id=syn_default").json()
    assert second_list["count"] == 0
    assert second_list["scope"] == "session_owner"
    first_ids = {
        row["investigation_id"]
        for row in first.get("/api/investigations?match_id=syn_default").json()["investigations"]
    }
    assert investigation_id in first_ids

    # Same question, same snapshot: two sessions must not collide into one
    # store record because the owner is part of the investigation identity.
    other = _investigate(second)
    assert other["investigation_id"] != investigation_id

    # Promotion writes a public claim but still requires ownership of the
    # private draft. The owner can promote an approved preview.
    assert plan["gate_preview"]["status"] == "approved"
    promoted = first.post(f"/api/investigations/{investigation_id}/promote")
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["gate_status"] == "approved"

    # A record from an older store has no owner. It is readable by the
    # independent producer role only, never by an arbitrary browser session.
    engine = app.state.engine
    legacy = InvestigationPlan.model_validate(plan).model_copy(update={"owner_session_id": None})
    engine.investigations.save(legacy)
    assert first.get(f"/api/investigations/{investigation_id}").status_code == 404
    producer = first.get(
        f"/api/investigations/{investigation_id}",
        headers={"X-MatchLens-Token": "producer-test"},
    )
    assert producer.status_code == 200
    producer_list = first.get(
        "/api/investigations?match_id=syn_default",
        headers={"X-MatchLens-Token": "producer-test"},
    ).json()
    assert producer_list["scope"] == "producer_all"
    assert any(row["legacy_unowned"] for row in producer_list["investigations"])


def test_agent_runs_are_owner_scoped(clients):
    first, second = clients
    engine = app.state.engine
    engine.agent_runs.create(
        run_id="arun-owner-test",
        trigger="investigation",
        match_id="syn_default",
        snapshot_id="snap-test",
        model="deepseek-flash",
        prompt_version="test",
        owner_session_id=next(iter(engine.sessions)),
    )
    engine.agent_runs.create(
        run_id="arun-legacy-test",
        trigger="investigation",
        match_id="syn_default",
        snapshot_id="snap-test",
        model="deepseek-flash",
        prompt_version="test",
        owner_session_id=None,
    )

    first_runs = first.get("/api/agent-runs").json()
    assert first_runs["scope"] == "session_owner"
    assert {row["run_id"] for row in first_runs["runs"]} == {"arun-owner-test"}
    assert "budget" not in first_runs
    assert second.get("/api/agent-runs").json()["runs"] == []
    assert second.get("/api/agent-runs/arun-owner-test").status_code == 404
    assert second.post("/api/agent-runs/arun-owner-test/cancel").status_code == 404
    assert first.get("/api/agent-runs/arun-owner-test").status_code == 200
    assert first.get("/api/agent-runs/arun-legacy-test").status_code == 404

    producer = first.get(
        "/api/agent-runs",
        headers={"X-MatchLens-Token": "producer-test"},
    ).json()
    assert producer["scope"] == "producer_all"
    assert "budget" in producer
    assert {row["run_id"] for row in producer["runs"]} == {"arun-owner-test", "arun-legacy-test"}
    assert (
        first.get(
            "/api/agent-runs/arun-legacy-test",
            headers={"X-MatchLens-Token": "producer-test"},
        ).status_code
        == 200
    )


def test_session_cookie_flags_csrf_and_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    with TestClient(app) as client:
        response = client.post("/api/sessions")
        assert response.status_code == 200
        set_cookie = response.headers.get("set-cookie", "")
        assert "HttpOnly" in set_cookie
        assert "SameSite=strict" in set_cookie.lower() or "samesite=strict" in set_cookie.lower()
        assert "Path=/" in set_cookie
        session_id = response.cookies.get(COOKIE) or client.cookies.get(COOKIE)

        assert client.post(
            "/api/control",
            json={"action": "pause"},
            headers={"Origin": "https://evil.example", "Host": "testserver"},
        ).status_code == 403
        assert client.post(
            "/api/control",
            json={"action": "pause"},
            headers={"Sec-Fetch-Site": "cross-site"},
        ).status_code == 403

    # A restart loses in-memory sessions. The old cookie is not silently
    # promoted into a fresh anonymous session; the client must bootstrap again.
    with TestClient(app) as restarted:
        stale = restarted.get("/api/state", cookies={COOKIE: session_id})
        assert stale.status_code == 401
        assert restarted.post("/api/sessions").status_code == 200
