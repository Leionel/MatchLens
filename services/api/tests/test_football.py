import pytest

from matchlens.football import CHAPTERS, freeze, generate_match, reduce_match


def test_reproducible_legal_prefix_and_continuity():
    events = generate_match(17)
    assert events == generate_match(17)
    assert events != generate_match(18)
    assert 140 <= len(events) <= 180
    full = reduce_match(events, 720)
    for chapter in CHAPTERS:
        prefix = reduce_match(events, chapter["at"])
        assert prefix["events"] == full["events"][:len(prefix["events"])]
        assert all(e["t"] <= chapter["at"] for e in prefix["events"])
    assert full["score"] == {"H": 1, "N": 0}
    assert sum(i["end"]-i["start"] for i in full["intervals"]) == 718  # two dead-ball seconds


def test_arithmetic_oracle_and_active_discovery():
    events = generate_match()
    a = freeze(events, 360).data["receipts"]
    assert (a["H.possession.previous"]["numerator"], a["H.possession.current"]["numerator"]) == (80, 150)
    assert a["H.possession.current"]["denominator"] == 180
    assert (a["H.shots.previous"]["value"], a["H.shots.current"]["value"]) == (2, 0)
    assert (a["H.entries.previous"]["value"], a["H.entries.current"]["value"]) == (2, 0)
    b = freeze(events, 540).data["receipts"]
    assert b["H.transition_shots.current"]["value"] == 2
    assert [c["seconds"] for c in b["H.transition_shots.current"]["chains"]] == [8, 8]
    assert b["H.high_recoveries.current"]["value"] == 4
    c = freeze(events, 720).data
    chain = c["receipts"]["H.goals.match"]["chains"][0]
    raw = {e["id"]: e for e in c["events"]}
    assert raw[chain[0]]["kind"] == "recovery"
    assert raw[chain[-1]]["outcome"] == "goal"
    assert all(raw[i]["team"] == "H" for i in chain)


@pytest.mark.parametrize("change", [{"seq": 4}, {"actor": "N8"}, {"start": (1, 1)}, {"end": (106, 30)}, {"receiver": "H6"}, {"team": "N"}])
def test_illegal_event_rejected(change):
    events = list(generate_match())
    events[1] = events[1].model_copy(update=change)
    with pytest.raises(ValueError):
        reduce_match(tuple(events), 720)


def test_snapshot_content_address_and_no_mutation_or_future():
    snap = freeze(generate_match(), 360)
    copy = snap.data
    copy["receipts"]["H.shots.current"]["value"] = 99
    assert snap.data["receipts"]["H.shots.current"]["value"] == 0
    assert snap.id == freeze(generate_match(), 360).id
    assert snap.id != freeze(generate_match(), 540).id
    assert max(e["t"] for e in snap.data["events"]) == 360


def test_goal_must_end_in_goal_mouth_and_markers_cannot_score():
    events = list(generate_match())
    goal = next(i for i, e in enumerate(events) if e.outcome == "goal")
    events[goal] = events[goal].model_copy(update={"end": (90, 34)})
    with pytest.raises(ValueError, match="goal_outside_goal_mouth"):
        reduce_match(tuple(events), 720)
    events = list(generate_match())
    events[0] = events[0].model_copy(update={"outcome": "goal"})
    with pytest.raises(ValueError, match="illegal_event_payload"):
        reduce_match(tuple(events), 720)
