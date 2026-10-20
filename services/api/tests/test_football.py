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


def test_cross_scenario_stalemate_reduces_legally_and_withholds_goal():
    from matchlens.contracts import assertion_supported
    events = generate_match(seed=17, scenario="stalemate")
    full = reduce_match(events, 720)
    assert full["score"] == {"H": 0, "N": 0}
    assert full["ended"] is True
    snap = freeze(events, 720)
    assert snap.data["receipts"]["H.goals.match"]["value"] == 0
    assert not assertion_supported("goal_sequence", snap)


def test_auto_moment_detection_invariants():
    from matchlens.football import detect_moments
    events = generate_match(17)
    assert detect_moments(reduce_match(events, 100)) == []
    m_360 = detect_moments(reduce_match(events, 360))
    assert len(m_360) >= 1
    assert any(m["assertion"] == "possession_without_penetration" for m in m_360)
    m_540 = detect_moments(reduce_match(events, 540))
    assert any(m["assertion"] == "recoveries_followed_by_shots" for m in m_540)
    m_720 = detect_moments(reduce_match(events, 720))
    assert any(m["assertion"] == "goal_sequence" for m in m_720)


def test_r1_all_six_scenarios_and_both_team_intelligence():
    from matchlens.contracts import assertion_supported, evidence_summary
    from matchlens.football import (
        SCENARIOS,
        both_team_receipts,
        build_player_spotlight,
        build_sequences,
        build_tactical_explorer,
        detect_moments,
    )

    expected_scores = {
        "default": {"H": 1, "N": 0},
        "stalemate": {"H": 0, "N": 0},
        "counterattack": {"H": 0, "N": 1},
        "transitions": {"H": 1, "N": 1},
        "balanced": {"H": 1, "N": 1},
        "comeback": {"H": 2, "N": 1},
    }
    assert set(SCENARIOS) == set(expected_scores)
    for sc, exp_score in expected_scores.items():
        events = generate_match(seed=17, scenario=sc)
        state = reduce_match(events, 720)
        assert state["ended"] is True
        assert state["score"] == exp_score
        receipts = both_team_receipts(state)
        assert receipts["H.goals.match"]["value"] == exp_score["H"]
        assert receipts["N.goals.match"]["value"] == exp_score["N"]

    # Counterattack scenario: Northbridge scores and has N.goals.match supported
    ca_events = generate_match(seed=17, scenario="counterattack")
    ca_snap = freeze(ca_events, 720)
    assert assertion_supported("goal_sequence", ca_snap, team="N")
    assert not assertion_supported("goal_sequence", ca_snap, team="H")
    fan_n, analyst_n = evidence_summary("goal_sequence", ca_snap, team="N")
    assert "Northbridge scored" in fan_n and "Northbridge has 1 recorded goal" in analyst_n
    ca_moments = detect_moments(reduce_match(ca_events, 720))
    assert any(m["team"] == "N" and m["assertion"] == "goal_sequence" for m in ca_moments)

    # Possession sequences, tactical explorer, and player spotlight
    default_state = reduce_match(generate_match(17, "default"), 720)
    seqs = build_sequences(default_state)
    assert len(seqs) >= 10
    goal_seq = next(s for s in seqs if s["outcome"] == "goal" and s["team"] == "H")
    assert goal_seq["territory_gained"] > 0
    assert len(goal_seq["start_coords"]) == 2 and len(goal_seq["end_coords"]) == 2
    assert len(goal_seq["events_detail"]) == len(goal_seq["event_ids"])
    assert goal_seq["events_detail"][0]["seq_step"] == 1
    assert "actor_name" in goal_seq["events_detail"][0]
    assert "gain_m" in goal_seq["events_detail"][0]

    tac_h = build_tactical_explorer(default_state, "H")
    tac_n = build_tactical_explorer(default_state, "N")
    assert tac_h["attack_direction"] == "right" and tac_n["attack_direction"] == "left"
    assert len(tac_h["nodes"]) == 4 and len(tac_n["nodes"]) == 4
    assert "channels" in tac_h and "attacking_channels" in tac_h
    assert set(tac_h["channels"]) >= {"left", "center", "right"}
    assert tac_h["territorial_progression"]["high_recovery_threshold_x"] == 70.0
    assert tac_n["territorial_progression"]["high_recovery_threshold_x"] == 35.0
    assert len(tac_h["final_third_entries"]) == tac_h["territorial_progression"]["final_third_entries_count"]

    players = build_player_spotlight(default_state)
    assert len(players) == 8
    assert sum(p["goals"] for p in players) == 1
