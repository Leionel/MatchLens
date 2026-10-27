"""R6.5 correctness regressions: rate budgets and frozen plan scores.

The browser CI hit a 429 storm: sequential tests share one session and one
source address, so the per-session stream/control budgets and the per-source
featured budget designed for one human were exhausted, and EventSource's
immediate reconnect turned a single 429 into a loop. These tests pin the
budgets a normal browsing session must never exhaust.

The investigation plan now also carries the score frozen at its own snapshot:
a broadcast preview rendered from the live clock would pair an old conclusion
with a new score once the viewer keeps scrubbing.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from matchlens.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    with TestClient(app) as c:
        assert c.post("/api/sessions", json={}).status_code == 200
        yield c


def _investigate(client: TestClient, at: int, request_key: str) -> dict:
    res = client.post(
        "/api/investigate",
        json={
            "match_id": "syn_default",
            "at": at,
            "team": "H",
            "focus_type": "moment",
            "focus_id": None,
            "question": "Why did attacking activity change around this moment?",
            "execution_mode": "deterministic_planner",
            "request_key": request_key,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_control_budget_absorbs_normal_replay_activity(client):
    """A live viewer scrubbing and toggling playback must not hit 429."""
    codes = set()
    for i in range(105):
        action = "play" if i % 2 else "pause"
        codes.add(client.post("/api/control", json={"action": action}).status_code)
    assert codes == {200}


def test_featured_budget_covers_catalog_browsing(client):
    """Paging the hub (and an E2E suite) must not exhaust the featured pick."""
    codes = set()
    for _ in range(35):
        codes.add(client.get("/api/featured").status_code)
    assert codes == {200}


def test_stream_budget_covers_workspace_navigation(client):
    """Opening the stream repeatedly across workspaces must not 429."""
    eng = client.app.state.engine
    for i in range(60):
        # Does not raise; the 61st connect within the window would.
        eng.rates.check("stream:budget-test", 60)
    with pytest.raises(Exception) as exc:
        eng.rates.check("stream:budget-test", 60)
    assert "429" in str(getattr(exc.value, "status_code", exc.value)) or "rate" in str(exc.value).lower()


def test_plan_carries_the_score_frozen_at_its_snapshot(client):
    """The plan's score pair belongs to its own snapshot, not to the clock."""
    events = client.app.state.engine.events_for_match("syn_default")
    goal_at = min(
        float(e.t)
        for e in events
        if getattr(e, "kind", "") == "shot" and "goal" in str(getattr(e, "outcome", "")).lower()
    )
    before = _investigate(client, 30, "r65-before-goal")
    after = _investigate(client, int(goal_at) + 1, "r65-after-goal")

    assert before["score"] == {"H": 0, "N": 0}
    assert after["score"] == {"H": 1, "N": 0}
    # Both plans describe the same match at different frozen moments.
    assert before["match_id"] == after["match_id"] == "syn_default"
    assert before["as_of"] < after["as_of"]
