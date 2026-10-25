"""Nominal vs observed vs replayable match clocks."""
from __future__ import annotations

import pytest

from matchlens.catalog import MatchCatalog
from matchlens.clock import build_match_clock
from matchlens.football import freeze


def _event(event_id: str, t: float, period: int, *, outcome: str = "complete") -> dict:
    return {
        "id": event_id,
        "t": t,
        "period": period,
        "kind": "shot" if outcome == "goal" else "pass",
        "team": "H" if int(t) % 2 == 0 else "N",
        "actor": "Player",
        "start": [50.0, 34.0],
        "end": [60.0, 34.0],
        "outcome": outcome,
        "coordinate_frame": "fixed",
    }


def test_build_clock_separates_nominal_observed_and_replayable():
    events = [
        _event("p1-a", 0, 1),
        _event("p1-b", 2700, 1),
        _event("p1-c", 2710, 1),
        _event("p2-a", 2700, 2),
        _event("p2-b", 5400, 2),
        _event("p2-c", 5500, 2),
        _event("p3-a", 5400, 3),
        _event("p3-b", 6300, 3),
        _event("p3-c", 6400, 3),
        _event("p4-a", 6300, 4),
        _event("p4-b", 7200, 4),
        _event("p4-c", 7300, 4),
    ]
    clock = build_match_clock(events, nominal_duration=7800, synthetic=False)

    assert clock["nominal_duration"] == 7200
    assert clock["observed_end"] == 7300
    assert clock["replayable_end"] == 7300
    assert clock["as_of"] == 7300
    assert clock["period"] == 4
    assert clock["stoppage_time_seconds"] == pytest.approx(10 + 100 + 100 + 100)
    assert [row["period"] for row in clock["periods"]] == [1, 2, 3, 4]
    assert clock["shootout_clock"] is None


def test_clock_exposes_every_recorded_stoppage_event_and_no_future_leak():
    events = [
        _event("late-1", 7100, 4),
        _event("late-2", 7200, 4),
        _event("late-3", 7300, 4),
    ]
    nominal = freeze(
        events,
        7200,
        match_id="sb_clock_probe",
        scenario="historical",
        format_seconds=7200,
        replayable_end=7300,
        teams={"H": "Home", "N": "Away"},
        coordinate_frame="fixed",
        continuous_coverage=True,
    )
    full = freeze(
        events,
        7300,
        match_id="sb_clock_probe",
        scenario="historical",
        format_seconds=7200,
        replayable_end=7300,
        teams={"H": "Home", "N": "Away"},
        coordinate_frame="fixed",
        continuous_coverage=True,
    )

    assert nominal.data["as_of"] == 7200
    assert [event["t"] for event in nominal.data["events"]] == [7100, 7200]
    # An ordinary-clock snapshot keeps its historical shape.
    assert "replayable_end" not in nominal.data
    assert nominal.data["coverage"]["format_seconds"] == 7200

    assert full.data["as_of"] == 7300
    assert [event["t"] for event in full.data["events"]] == [7100, 7200, 7300]
    assert full.data["format_seconds"] == 7200
    assert full.data["replayable_end"] == 7300
    assert full.data["coverage"]["replayable_end"] == 7300
    # The nominal 7200 clock must not be mistaken for the last replayable one.
    assert full.data["as_of"] > full.data["format_seconds"]


def test_shootout_is_reported_separately_from_playing_time():
    events = [
        _event("p1", 0, 1),
        _event("p1b", 2800, 1),
        _event("p2", 5400, 2),
        _event("p2b", 6000, 2),
        _event("so-1", 7200, 5, outcome="goal"),
        _event("so-2", 7210, 5),
    ]
    clock = build_match_clock(events, nominal_duration=6000, synthetic=False)

    assert clock["nominal_duration"] == 5400
    assert clock["period"] == 5
    assert clock["replayable_end"] == 7210
    assert clock["shootout_clock"] is not None
    assert clock["shootout_clock"]["kick_count"] == 2
    assert clock["shootout_clock"]["goals_by_team"]["H"] == 1
    # A shoot-out contributes kicks, never nominal playing minutes.
    assert clock["stoppage_time_seconds"] == pytest.approx(100 + 600)

    snap = freeze(
        events,
        7210,
        match_id="sb_shootout_probe",
        scenario="historical",
        format_seconds=5400,
        replayable_end=7210,
        teams={"H": "Home", "N": "Away"},
        coordinate_frame="fixed",
        continuous_coverage=True,
    )
    assert snap.data["as_of"] == 7210
    assert sum(snap.data["shootout_score"].values()) == 1
    assert snap.data["score"] == {"H": 0, "N": 0}


def test_own_goal_pair_is_counted_once_and_matches_the_score():
    from matchlens.football import freeze, metric_receipts

    events = [
        _event("og-scorer", 1000, 1, outcome="own_goal"),
        _event("og-credit", 1000, 1, outcome="own_goal_for"),
        _event("goal-h", 2000, 1, outcome="goal"),
    ]
    # The owning side of an own goal is the conceding team; both records must
    # credit the same beneficiary exactly once.
    events[0]["team"] = "N"
    events[1]["team"] = "H"
    events[2]["team"] = "H"
    snap = freeze(
        events,
        2100,
        match_id="sb_own_goal_probe",
        scenario="historical",
        format_seconds=5400,
        teams={"H": "Home", "N": "Away"},
        coordinate_frame="fixed",
        continuous_coverage=True,
    )
    state = dict(snap.data)
    state["at"] = state["as_of"]
    receipts = metric_receipts(state)
    assert snap.data["score"] == {"H": 2, "N": 0}
    assert receipts["H.goals.match"]["value"] == 2
    assert receipts["N.goals.match"]["value"] == 0
    assert "og-scorer" in receipts["H.goals.match"]["event_ids"]
    assert "og-credit" in receipts["H.goals.match"]["event_ids"]


def test_real_match_stoppage_is_replayable_when_installed():
    meta = MatchCatalog.get_match("sb_3795221")
    if meta is None or not meta.analysis_ready:
        pytest.skip("sb_3795221 is not installed in this checkout")

    from matchlens.main import Engine, freeze_match_snapshot

    import tempfile
    from pathlib import Path

    ctx = MatchCatalog.get_match_context("sb_3795221")
    assert ctx.duration == 7200
    assert ctx.observed_end > 7200
    assert ctx.replayable_end == pytest.approx(ctx.observed_end)
    assert ctx.stoppage_time > 0

    engine = Engine(Path(tempfile.mkdtemp()), None)
    nominal, _ = freeze_match_snapshot(engine, "sb_3795221", 7200)
    full, _ = freeze_match_snapshot(engine, "sb_3795221", int(ctx.observed_end) + 1)
    assert len(full.data["events"]) > len(nominal.data["events"])
    assert max(event["t"] for event in full.data["events"]) > 7200
    assert full.data["score"] == nominal.data["score"] == {"H": 2, "N": 1}
