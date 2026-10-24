"""Provider-match semantics that the corpus depends on.

Three failure modes are covered here, each of which silently corrupted the
score or the completeness verdict before the fix:

1. A provider records one own goal twice (once for the beneficiary, once for
   the conceding side). The score must count it once.
2. A penalty shoot-out is a sequence of kicks, not a block of playing time. Its
   completeness is judged by recorded kicks, not by the span of the period.
3. A manifest entry the catalog cannot read must not make the match vanish
   without a trace.
"""
from __future__ import annotations

from typing import Any

from matchlens.completeness import (
    PENALTY_SHOOTOUT_MIN_KICKS_PER_TEAM,
    verify_dataset_completeness,
)
from matchlens.football import reduce_match


def _provider_event(
    index: int,
    *,
    period: int,
    clock: float,
    team: str,
    action: str,
    outcome: str,
    player: str | None = None,
) -> dict[str, Any]:
    return {
        "event_id": f"p{index:04d}",
        "period": period,
        "clock_seconds": clock,
        "team_id": team,
        "action_type": action,
        "outcome": outcome,
        "player_name": player,
        "possession_id": "pos-1",
    }


def test_own_goal_pair_is_counted_once_and_credits_the_beneficiary():
    """The provider emits the own goal twice; the score must move by one."""
    events = [
        _provider_event(1, period=1, clock=100.0, team="H", action="Pass", outcome="complete"),
        _provider_event(2, period=1, clock=180.0, team="H", action="Own Goal", outcome="own_goal_for"),
        _provider_event(3, period=1, clock=180.0, team="N", action="Own Goal", outcome="own_goal",
                        player="Mario Mandzukic"),
        _provider_event(4, period=1, clock=240.0, team="N", action="Pass", outcome="complete"),
    ]

    state = reduce_match(
        events,
        at=600,
        max_duration=600,
        is_synthetic=False,
        team_map={"H": "H", "N": "N"},
        home_team_id="H",
        away_team_id="N",
        continuous_coverage=True,
    )

    assert state["score"] == {"H": 1, "N": 0}, "one own goal is one goal"
    own_goals = [g for g in state["goals"] if g["own_goal"]]
    assert len(own_goals) == 1
    assert own_goals[0]["team"] == "H", "the beneficiary is credited"
    assert own_goals[0]["actor_name"] == "Mario Mandzukic"
    assert state["goals"][0]["event_id"] == "p0003", (
        "the event that names the scorer becomes the evidence for the goal"
    )


def test_ordinary_goals_are_not_affected_by_the_own_goal_dedupe():
    events = [
        _provider_event(1, period=1, clock=100.0, team="H", action="Pass", outcome="complete"),
        _provider_event(2, period=1, clock=180.0, team="N", action="Shot", outcome="goal"),
        _provider_event(3, period=2, clock=3000.0, team="H", action="Shot", outcome="goal"),
    ]

    state = reduce_match(
        events,
        at=6000,
        max_duration=6000,
        is_synthetic=False,
        team_map={"H": "H", "N": "N"},
        home_team_id="H",
        away_team_id="N",
        continuous_coverage=True,
    )

    assert state["score"] == {"H": 1, "N": 1}
    assert len(state["goals"]) == 2


def test_shootout_is_judged_by_recorded_kicks_not_by_playing_time():
    """A shoot-out that ends after three kicks is complete, not partial."""
    events = []
    for index in range(60):
        events.append(
            _provider_event(
                index + 1,
                period=1,
                clock=60.0 + index * 40,
                team="H" if index % 2 else "N",
                action="Pass",
                outcome="complete",
            )
        )
    for index in range(60):
        events.append(
            _provider_event(
                61 + index,
                period=2,
                clock=2760.0 + index * 40,
                team="N" if index % 2 else "H",
                action="Pass",
                outcome="complete",
            )
        )
    for index in range(6):
        events.append(
            _provider_event(
                121 + index,
                period=5,
                clock=7200.0 + index * 25,
                team="H" if index % 2 else "N",
                action="Shot",
                outcome="goal" if index < 4 else "saved",
            )
        )

    report = verify_dataset_completeness(
        events,
        raw_event_count=len(events),
        expected_duration=6000,
        source_declaration="statsbomb_open_data",
        declared_complete=True,
        team_ids=["H", "N"],
    )

    shootout_row = next(row for row in report.coverage_by_period if row["period"] == 5)
    assert shootout_row["completeness_rule"] == "recorded_kicks"
    assert shootout_row["shootout_kicks_ok"] is True
    assert shootout_row["shootout_kicks_by_team"] == {"H": 3, "N": 3}
    assert report.status == "COMPLETE_VERIFIED", report.known_missing_segments


def test_shootout_without_enough_kicks_is_reported_as_missing():
    events = []
    for index in range(60):
        events.append(
            _provider_event(
                index + 1,
                period=1,
                clock=60.0 + index * 40,
                team="H" if index % 2 else "N",
                action="Pass",
                outcome="complete",
            )
        )
    for index in range(60):
        events.append(
            _provider_event(
                61 + index,
                period=2,
                clock=2760.0 + index * 40,
                team="N" if index % 2 else "H",
                action="Pass",
                outcome="complete",
            )
        )
    events.append(
        _provider_event(121, period=5, clock=7200.0, team="H", action="Shot", outcome="goal")
    )

    report = verify_dataset_completeness(
        events,
        raw_event_count=len(events),
        expected_duration=6000,
        source_declaration="statsbomb_open_data",
        declared_complete=True,
        team_ids=["H", "N"],
    )

    assert report.status == "PARTIAL_OBSERVED"
    assert any("shoot-out" in segment for segment in report.known_missing_segments)
    assert PENALTY_SHOOTOUT_MIN_KICKS_PER_TEAM == 3


def test_catalog_reports_a_manifest_entry_it_cannot_read(monkeypatch, tmp_path):
    """A malformed manifest entry must be visible, not silently dropped."""
    from matchlens import catalog as catalog_module

    manifest = tmp_path / "source_manifest.json"
    manifest.write_text(
        '{"matches": [{"match_id": "sb_broken", "metadata": {"match_id": "sb_broken", '
        '"label": "Broken", "unexpected_field": 1}}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(catalog_module, "SOURCE_MANIFEST_PATH", manifest)
    catalog_module.MatchCatalog._manifest_cache = {}

    matches = catalog_module.MatchCatalog.list_matches()
    rejections = catalog_module.MatchCatalog.manifest_rejections()

    assert all(m.match_id != "sb_broken" for m in matches)
    assert any(r["match_id"] == "sb_broken" for r in rejections)
    assert "unexpected_field" in rejections[0]["error"]
