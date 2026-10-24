"""Third-pass football semantics contract tests.

These tests are derived from the actual failure modes found in the audit:
- possession attributed to the *next* owner
- possession_id incrementing on every event
- legal zero coordinates replaced by pitch centre
- name-substring home-team inference
- half-time / shootout / own-goal score leaks
- partial coverage treated as continuous control
"""
from __future__ import annotations

import pytest

from matchlens.adapters.statsbomb import StatsBombAdapter
from matchlens.football import (
    build_sequences,
    freeze,
    generate_match,
    metric_receipts,
    reduce_match,
)
from matchlens.schema import ActionType, NormalizedEvent, RawSourceRecord


def _src(idx: int = 0) -> RawSourceRecord:
    return RawSourceRecord(
        provider="statsbomb_open_data",
        provider_event_id=f"raw-{idx}",
        schema_version="1.1",
        license_ref="test-license",
    )


def ev(
    idx: int,
    t: float,
    team: str,
    action: ActionType,
    *,
    period: int = 1,
    outcome: str = "complete",
    x: float | None = 40.0,
    y: float | None = 34.0,
    end_x: float | None = None,
    end_y: float | None = None,
    possession: str | None = None,
    player: str | None = "P1",
    own_goal: bool = False,
) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=f"sb_m_{idx:04d}",
        match_id="m",
        source=_src(idx),
        period=period,
        clock_seconds=float(t),
        team_id=team,
        provider_team_id=team,
        possession_id=possession,
        player_id=player,
        player_name=player,
        action_type=action,
        outcome=outcome,
        is_own_goal=True if own_goal else None,
        x=x,
        y=y,
        end_x=end_x,
        end_y=end_y,
    )


TEAM_MAP = {"ARG": "H", "FRA": "N"}


def norm(events, at, **kwargs):
    params = dict(
        max_duration=5400,
        is_synthetic=False,
        team_map=TEAM_MAP,
        coordinate_frame="team_relative",
        continuous_coverage=False,
    )
    params.update(kwargs)
    return reduce_match(events, at, **params)


def test_same_team_consecutive_passes_keep_one_possession():
    events = [
        ev(1, 0, "ARG", ActionType.RESTART, x=52.5, y=34.0),
        ev(2, 3, "ARG", ActionType.PASS, end_x=55.0, end_y=34.0),
        ev(3, 6, "ARG", ActionType.PASS, x=55.0, end_x=60.0, end_y=30.0),
    ]
    state = norm(events, 10)
    assert [e["possession_id"] for e in state["events"]] == [1, 1, 1]
    assert len(state["possessions"]) == 1
    assert len(state["intervals"]) == 1
    assert state["intervals"][0]["team"] == "H"
    assert state["intervals"][0]["start"] == 0
    # Partial coverage: the observation window must not be treated as control.
    assert state["intervals"][0]["end"] == 6


def test_possession_time_belongs_to_previous_owner_not_next_event():
    events = [
        ev(1, 0, "ARG", ActionType.PASS, end_x=45.0),
        ev(2, 10, "ARG", ActionType.PASS, x=45.0, end_x=50.0),
        ev(3, 20, "FRA", ActionType.RECOVERY, x=50.0, y=34.0),
        ev(4, 25, "FRA", ActionType.PASS, x=50.0, end_x=40.0),
    ]
    state = norm(events, 30)
    assert state["intervals"][0]["team"] == "H"
    assert state["intervals"][0]["end"] == 20
    assert state["intervals"][1]["team"] == "N"
    assert state["intervals"][1]["start"] == 20
    assert sum(i["end"] - i["start"] for i in state["intervals"]) == 25
    assert [p["team"] for p in state["possessions"]] == ["H", "N"]


def test_multiple_events_at_same_timestamp_do_not_break_possession():
    events = [
        ev(1, 0, "ARG", ActionType.RESTART, x=52.5, y=34.0),
        ev(2, 5, "ARG", ActionType.PASS, end_x=60.0),
        ev(3, 5, "ARG", ActionType.CARRY, x=60.0, end_x=62.0),
    ]
    state = norm(events, 8)
    assert len(state["events"]) == 3
    assert {e["possession_id"] for e in state["events"]} == {1}
    assert len(state["intervals"]) == 1


def test_zero_and_pitch_boundary_coordinates_are_preserved():
    events = [
        ev(1, 0, "ARG", ActionType.PASS, x=0.0, y=0.0, end_x=105.0, end_y=68.0),
        ev(2, 5, "ARG", ActionType.PASS, x=105.0, y=68.0, end_x=0.0, end_y=0.0),
    ]
    state = norm(events, 6)
    assert state["events"][0]["start"] == [0.0, 0.0]
    assert state["events"][0]["end"] == [105.0, 68.0]
    assert state["events"][1]["start"] == [105.0, 68.0]
    assert state["events"][1]["located"] is True


def test_missing_location_is_unknown_never_pitch_centre():
    events = [
        ev(1, 0, "ARG", ActionType.PASS, x=None, y=None, end_x=None, end_y=None),
        ev(2, 4, "ARG", ActionType.PASS, x=None, y=None, end_x=None, end_y=None),
    ]
    state = norm(events, 5)
    for e in state["events"]:
        assert e["start"] is None
        assert e["end"] is None
        assert e["located"] is False
    assert state["ball"] is None
    # Possession time is still observable even when the location is missing.
    assert len(state["intervals"]) == 1


def test_half_time_break_is_not_attributed_as_possession():
    events = [
        ev(1, 100, "ARG", ActionType.PASS, end_x=60.0),
        ev(2, 2700, "FRA", ActionType.PASS, period=2, x=60.0, end_x=55.0),
    ]
    state = norm(events, 2800)
    assert state["intervals"][0]["end"] == 100
    assert state["intervals"][1]["start"] == 2700
    gaps = [g for g in state["unobserved_intervals"] if g["reason"] == "period_break"]
    assert gaps and gaps[0]["start"] == 100 and gaps[0]["end"] == 2700
    assert state["events"][0]["attack_direction"] in ("left_to_right", "right_to_left")


def test_goal_and_restart_create_new_possession_and_correct_score():
    events = [
        ev(1, 0, "ARG", ActionType.PASS, end_x=80.0),
        ev(2, 10, "ARG", ActionType.SHOT, x=95.0, y=34.0, outcome="goal"),
        ev(3, 12, "FRA", ActionType.RESTART, x=52.5, y=34.0),
        ev(4, 15, "FRA", ActionType.PASS, x=52.5, end_x=45.0),
    ]
    state = norm(events, 20)
    assert state["score"] == {"H": 1, "N": 0}
    assert state["score_basis"] == "observed_prefix"
    assert state["events"][1]["possession_id"] == 1
    assert state["events"][2]["possession_id"] == 2
    assert state["possessions"][1]["start_reason"] in ("goal_restart", "restart")


def test_own_goal_credits_opponent_and_shootout_does_not_change_score():
    og = [
        ev(1, 0, "ARG", ActionType.PASS, end_x=40.0),
        ev(2, 5, "ARG", ActionType.OWN_GOAL, x=5.0, y=34.0, outcome="own_goal", own_goal=True),
    ]
    state = norm(og, 10)
    assert state["score"] == {"H": 0, "N": 1}

    shootout = [
        ev(1, 5400, "ARG", ActionType.SHOT, period=5, outcome="goal", x=90.0, y=34.0),
    ]
    so = norm(shootout, 5400)
    assert so["score"] == {"H": 0, "N": 0}
    assert so["shootout_score"] == {"H": 1, "N": 0}


def test_partial_coverage_does_not_extend_possession_to_match_end():
    events = [
        ev(1, 298, "ARG", ActionType.PASS, end_x=60.0),
        ev(2, 300, "ARG", ActionType.PASS, x=60.0, end_x=65.0),
    ]
    state = norm(events, 5400)
    assert state["coverage"]["continuous"] is False
    assert state["coverage"]["observed_end"] == 300
    assert state["coverage"]["event_coverage"] is None
    assert sum(i["end"] - i["start"] for i in state["intervals"]) == 2
    tail = [g for g in state["unobserved_intervals"] if g["reason"] == "coverage_end"]
    assert tail == [{"start": 300, "end": 5400, "reason": "coverage_end"}]
    assert state["coverage"]["controlled_seconds"] == 2


def test_data_gap_is_unknown_not_continuous_possession():
    events = [
        ev(1, 0, "ARG", ActionType.PASS, end_x=50.0),
        ev(2, 300, "ARG", ActionType.PASS, x=50.0, end_x=55.0),
    ]
    state = norm(events, 310)
    assert sum(i["end"] - i["start"] for i in state["intervals"]) == 0  # both events are instants
    gaps = [g for g in state["unobserved_intervals"] if g["reason"] == "data_gap"]
    assert gaps and gaps[0]["start"] == 0 and gaps[0]["end"] == 300
    assert len(state["possessions"]) == 2


def test_unmapped_provider_team_is_rejected_not_guessed():
    events = [ev(1, 0, "Atlantis", ActionType.PASS, end_x=50.0)]
    with pytest.raises(ValueError, match="unmapped_provider_team"):
        norm(events, 5)


def test_shots_sequences_and_metrics_share_one_possession_identity():
    events = [
        ev(1, 0, "ARG", ActionType.RECOVERY, x=70.0, y=34.0),
        ev(2, 3, "ARG", ActionType.PASS, x=70.0, end_x=85.0),
        ev(3, 6, "ARG", ActionType.SHOT, x=85.0, y=34.0, outcome="saved"),
        ev(4, 8, "FRA", ActionType.RECOVERY, x=1.0, y=34.0),
    ]
    state = norm(events, 10)
    seqs = build_sequences(state)
    h_seq = next(s for s in seqs if s["team"] == "H")
    assert h_seq["event_ids"] == ["sb_m_0001", "sb_m_0002", "sb_m_0003"]
    assert h_seq["outcome"] == "shot_saved"
    receipts = metric_receipts(state)
    assert receipts["H.shots.current"]["value"] == 1
    assert receipts["H.shots.current"]["event_ids"] == ["sb_m_0003"]
    assert receipts["N.shots.current"]["value"] == 0


def test_synthetic_and_normalized_reducers_agree_on_possession_boundaries():
    synthetic = generate_match()
    state = reduce_match(synthetic, 720)
    # Each synthetic possession is contiguous and numbered from one.
    ids = [p["possession_id"] for p in state["possessions"]]
    assert ids == list(range(1, len(ids) + 1))
    assert all(p["end_t"] >= p["start_t"] for p in state["possessions"])
    normalized = [
        ev(1, 0, "ARG", ActionType.RESTART, x=52.5, y=34.0),
        ev(2, 5, "ARG", ActionType.PASS, end_x=60.0),
        ev(3, 10, "FRA", ActionType.RECOVERY, x=60.0),
    ]
    n_state = norm(normalized, 12)
    assert [p["possession_id"] for p in n_state["possessions"]] == [1, 2]


def test_adapter_preserves_provider_possession_and_team_ids():
    raw = {
        "id": "abc",
        "index": 4,
        "period": 1,
        "minute": 0,
        "second": 1,
        "timestamp": "00:00:01.200",
        "type": {"name": "Pass"},
        "team": {"id": 771, "name": "France"},
        "player": {"id": 5503, "name": "Kylian Mbappe"},
        "possession": 2,
        "location": [60.0, 40.0],
        "pass": {"end_location": [54.0, 28.0]},
    }
    adapter = StatsBombAdapter(match_id="m")
    norm_ev = adapter.normalize_event(raw)
    assert norm_ev.provider_team_id == "771"
    assert norm_ev.team_id == "771"
    assert norm_ev.possession_id == "2"
    assert norm_ev.player_id == "5503"


def test_freeze_snapshot_uses_supplied_format_and_never_leaks_future_score():
    events = [
        ev(1, 0, "ARG", ActionType.PASS, end_x=50.0),
        ev(2, 60, "ARG", ActionType.SHOT, x=95.0, y=34.0, outcome="goal"),
        ev(3, 3000, "FRA", ActionType.PASS, period=2, x=40.0, end_x=45.0),
    ]
    snap = freeze(
        events,
        100,
        match_id="sb_test",
        scenario="historical",
        format_seconds=5400,
        team_map=TEAM_MAP,
        coordinate_frame="team_relative",
        continuous_coverage=False,
        official_score={"H": 1, "N": 0},
    )
    data = snap.data
    assert data["format_seconds"] == 5400
    assert data["score"] == {"H": 1, "N": 0}
    assert data["score_basis"] == "observed_prefix"
    assert data["coverage"]["observed_end"] == 60
    assert snap.context.format_seconds == 5400
