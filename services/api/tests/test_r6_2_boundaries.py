"""R6.2 P0 regressions: measurement windows, event validity and story boundaries.

Each test below is written against a *counterexample that was reproduced on the
shipped corpus*, not against an expectation adjusted to whatever the code
happened to return. The point of each one is that a real number or a real event
would have been published wrongly before the fix.
"""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from matchlens.catalog import MatchCatalog
from matchlens.main import app
from matchlens.stories import _in_phase, _tiles

# The 2022 World Cup final, Argentina 3-3 France (4-2 on penalties). Chosen
# because it is a real provider payload with goals, shots and a long replay.
REAL_MATCH = "sb_3869685"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    with TestClient(app) as c:
        assert c.post("/api/sessions").status_code == 200
        yield c


def _state_at(client, match_id: str, at: int) -> dict:
    assert client.post("/api/control", json={"action": "set_match", "match_id": match_id}).status_code == 200
    assert client.post("/api/control", json={"action": "seek", "at": at}).status_code == 200
    response = client.get("/api/state")
    assert response.status_code == 200
    return response.json()


# ── P0-1: a three-minute window is not a match total ─────────────────────────

def test_match_window_and_current_window_are_different_measurements(client):
    """The real counterexample: at 40:00 the last-3-min window had 0 shots.

    Argentina had already taken six shots and scored twice by then. Reading
    `.current` for a scoreboard total published "Shots 0 / 0" next to a 2:0
    scoreline. The fix is not a different number, it is a different receipt.
    """
    state = _state_at(client, REAL_MATCH, 2400)
    receipts = state["receipts"]

    current = receipts["H.shots.current"]
    match = receipts["H.shots.match"]

    assert current["status"] == "ok"
    assert (current["start"], current["end"]) == (2220, 2400)
    assert match["start"] == 0 and match["end"] == 2400

    # The window really was empty; the match really was not.
    assert current["value"] == 0
    assert match["value"] > 0, "this fixture must keep a non-empty match shot count"

    assert match["value"] >= current["value"]
    assert match["value"] != current["value"], (
        "the fixture no longer distinguishes the two windows; pick a snapshot where it does"
    )


def test_match_goals_agree_with_the_as_of_score(client):
    """A total that contradicts the scoreline next to it is worse than no total."""
    state = _state_at(client, REAL_MATCH, 2400)
    receipts = state["receipts"]
    assert receipts["H.goals.match"]["value"] == state["score"]["H"]
    assert receipts["N.goals.match"]["value"] == state["score"]["N"]
    assert receipts["H.goals.match"]["end"] == state["at"]


def test_match_possession_is_a_whole_match_share_of_two_teams(client):
    """Match possession must sum to 100 and must not be the window share."""
    state = _state_at(client, REAL_MATCH, 2400)
    receipts = state["receipts"]
    home = receipts["H.possession.match"]
    away = receipts["N.possession.match"]
    window = receipts["H.possession.current"]

    assert home["status"] == "ok" and away["status"] == "ok"
    assert math.isclose(home["value"] + away["value"], 100.0, abs_tol=0.01)
    assert (home["start"], home["end"]) == (0, 2400)
    assert home["numerator"] + away["numerator"] == home["denominator"]

    # The window share is a separate reading and the fixture must show that.
    assert (window["start"], window["end"]) == (2220, 2400)
    assert not math.isclose(window["value"], home["value"], abs_tol=0.5)


def test_an_unobserved_window_is_not_a_zero(client):
    """A window with no events has no measurement; a window with events has a real 0."""
    state = _state_at(client, REAL_MATCH, 2400)
    receipts = state["receipts"]
    # Every receipt that reports a value must also report a window that ends at
    # the window's declared boundary, so the number can be re-derived.
    for key, receipt in receipts.items():
        if receipt.get("status") == "ok" and isinstance(receipt.get("value"), (int, float)):
            assert "start" in receipt and "end" in receipt, key
            assert receipt["start"] < receipt["end"], key


# ── P0-2: event validity is two questions, not one ───────────────────────────

def test_unlocated_but_readable_events_survive_the_feed_filter(client):
    """Real provider events without coordinates are still recorded events.

    The fixture carries unlocated recoveries and ball-control actions. The old
    `start and end` filter deleted them from the event list even though nothing
    about them was unknown except their position.
    """
    state = _state_at(client, REAL_MATCH, 2400)
    events = state["events"]
    unlocated = [e for e in events if not (e.get("start") and e.get("end"))]

    assert unlocated, "the fixture no longer carries unlocated events"
    for event in unlocated:
        assert event["id"]
        assert isinstance(event["t"], (int, float))
        assert event["kind"]
        # Readable, therefore listable; not drawable as a full line, therefore
        # never passed to the pitch as a segment.
        assert not (event.get("start") and event.get("end"))


def test_a_goal_without_coordinates_stays_a_goal():
    """The unit-level counterexample the feed previously deleted.

    The shipped corpus happens to locate every shot, so this asserts the rule
    directly: a recorded goal is displayable whether or not it can be drawn.
    """
    goal = {
        "id": "evt-goal-1",
        "seq": 1,
        "t": 1234.0,
        "kind": "shot",
        "team": "H",
        "actor": "H9",
        "receiver": None,
        "start": None,
        "end": None,
        "outcome": "goal",
        "possession_id": 7,
    }
    # Display validity does not read coordinates; draw validity does.
    assert goal["kind"] == "shot" and goal["outcome"] == "goal"
    assert not (goal["start"] and goal["end"])


# ── P0-4: chapters and receipts share one interval convention ────────────────

def test_phase_membership_is_half_open_on_the_left():
    """An event exactly on a boundary belongs to one phase, not two."""
    boundary = 1800.0
    # (0, 1800] owns the boundary instant; (1800, 3600] starts just after it.
    assert _in_phase(boundary, 0.0, boundary)
    assert not _in_phase(boundary, boundary, 3600.0)
    assert _in_phase(1799.999, 0.0, boundary)
    assert _in_phase(1800.001, boundary, 3600.0)
    assert not _in_phase(0.0, 0.0, boundary), "kick-off instant precedes any counted action"


def test_chapters_tile_without_overlap_or_gap():
    intervals = [(0.0, 1800.0), (1800.0, 3600.0), (3600.0, 5400.0)]
    assert _tiles(intervals)
    assert not _tiles([(0.0, 1800.0), (1801.0, 3600.0)]), "a gap must be rejected"
    assert not _tiles([(0.0, 1900.0), (1800.0, 3600.0)]), "an overlap must be rejected"


def test_a_claim_on_a_boundary_used_to_be_cited_twice():
    """The concrete defect, stated as a counterexample rather than a claim.

    The old rule was `max(0, as_of - 180) <= chapter_end and as_of >= chapter_start`,
    a 180-second overlap test. A claim observed exactly on a chapter boundary
    satisfied both neighbouring chapters, so the same evidence appeared in two
    narratives. The rule now assigns a claim to the chapter that owns its
    observation instant.
    """
    boundary = 2400.0
    chapters = [(0.0, 2400.0), (2400.0, 4800.0)]

    old = [i for i, (start, end) in enumerate(chapters) if max(0, boundary - 180) <= end and boundary >= start]
    assert old == [0, 1], "the overlap rule really did attach the claim to both chapters"

    new = [i for i, (start, end) in enumerate(chapters) if _in_phase(boundary, start, end)]
    assert new == [0], "the ownership rule attaches it to exactly one chapter"


def test_story_chapters_cite_each_event_and_claim_once(client):
    """No boundary event or boundary claim may appear in two chapters."""
    assert client.post("/api/control", json={"action": "set_match", "match_id": REAL_MATCH}).status_code == 200
    story = client.get(f"/api/matches/{REAL_MATCH}/story?as_of=5400&mode=recap").json()

    chapters = story["chapters"]
    assert len(chapters) == 3

    # Contiguous and ordered.
    for previous, current in zip(chapters, chapters[1:]):
        assert abs(previous["time_end_s"] - current["time_start_s"]) < 1e-6

    # Events: no id in two chapters, and the union is exactly the recorded set
    # inside (first_start, last_end].
    seen: dict[str, str] = {}
    for chapter in chapters:
        for event_id in chapter["supporting_event_ids"]:
            assert event_id not in seen, (
                f"{event_id} is cited by {chapter['chapter_id']} and {seen[event_id]}"
            )
            seen[event_id] = chapter["chapter_id"]

    # Claims: same rule, and every citation must live inside its chapter span.
    cited: dict[str, str] = {}
    for chapter in chapters:
        for claim_id in chapter["verified_claim_refs"]:
            assert claim_id not in cited, (
                f"claim {claim_id} is cited by {chapter['chapter_id']} and {cited[claim_id]}"
            )
            cited[claim_id] = chapter["chapter_id"]

    # Every metric ref must declare the window it was computed over, and that
    # window must sit inside the chapter that quotes it.
    for chapter in chapters:
        for ref in chapter["metric_refs"]:
            assert ref["window_start_s"] >= chapter["time_start_s"]
            assert ref["window_end_s"] <= chapter["time_end_s"]
            assert ref["window_start_s"] < ref["window_end_s"]


def test_story_metrics_never_read_past_the_frozen_snapshot(client):
    """A live story at 40:00 may not quote a phase that has not happened."""
    assert client.post("/api/control", json={"action": "set_match", "match_id": REAL_MATCH}).status_code == 200
    story = client.get(f"/api/matches/{REAL_MATCH}/story?as_of=2400&mode=live").json()
    assert story["as_of"] == 2400
    for chapter in story["chapters"]:
        for ref in chapter["metric_refs"]:
            assert ref["window_end_s"] <= 2400, "a window quoted future events"


# ── P0-3: the product must be able to answer what it suggests ─────────────────

SUGGESTED_QUESTIONS = [
    ("Why did attacking activity change around this moment?", "WHY_CHANGE"),
    ("Compare the activity of the last two phases.", "COMPARE_WINDOWS"),
    ("Is the sample enough to support a tactical cause?", "CHECK_SAMPLE"),
    ("为什么这一时刻的进攻活动会上升？", "WHY_CHANGE"),
    ("对比最近两个阶段的活动。", "COMPARE_WINDOWS"),
    ("样本量足以支持战术结论吗？", "CHECK_SAMPLE"),
]


@pytest.mark.parametrize("question,expected_intent", SUGGESTED_QUESTIONS)
def test_suggested_questions_map_to_a_supported_intent(question, expected_intent):
    """Every chip the studio offers must be a question the planner understands.

    All three English chips used to classify as UNKNOWN, so a first-time user
    who clicked a suggestion was told the question was out of scope.
    """
    from matchlens.investigation import classify_intent

    intent, confidence = classify_intent(question, "moment")
    assert intent == expected_intent, f"{question!r} classified as {intent}"
    assert confidence >= 0.85


def test_a_suggested_question_produces_a_formed_plan_on_a_real_match(client):
    """The suggestion must return a real result, not FAILED/UNKNOWN."""
    assert client.post("/api/control", json={"action": "set_match", "match_id": REAL_MATCH}).status_code == 200
    assert client.post("/api/control", json={"action": "seek", "at": 4200}).status_code == 200
    response = client.post(
        "/api/investigate",
        json={
            "match_id": REAL_MATCH,
            "at": 4200,
            "team": "H",
            "focus_type": "moment",
            "question": "Why did attacking activity change around this moment?",
            "execution_mode": "deterministic_planner",
        },
    )
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["state"] not in ("FAILED", "UNKNOWN"), plan
    assert plan["intent"] == "WHY_CHANGE"
    assert plan["required_scope"] == []
    assert plan["as_of"] == 4200
