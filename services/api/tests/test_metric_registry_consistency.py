"""Metric registry consistency across every publishing surface.

Story, chart, ask, agent and export all quote the same numbers. That is only
true if they all read the metric registry and the registry has exactly one
formula per (team, window, snapshot). These tests pin that invariant down:

- the discrete windows and the equivalent explicit ranges agree;
- the same (team, window, snapshot) never changes between calls or surfaces;
- an observation is bound to the snapshot it was taken from;
- an unobserved window stays unobserved instead of collapsing to zero.
"""
from __future__ import annotations

import pytest

from matchlens.catalog import MatchCatalog
from matchlens.football import generate_match, reduce_match
from matchlens.main import freeze_with_context
from matchlens.metrics import MetricsService
from matchlens.registry import ClaimRegistry
from matchlens.stories import MatchStoryEngine

MATCH_ID = "syn_default"
TEAMS = ("H", "N")
WINDOWS = ("previous", "current", "match")
#: Metrics that the discrete windows and the range flavour must agree on.
RECEIPT_METRICS = ("shots", "goals", "entries", "high_recoveries", "transition_shots", "possession")


@pytest.fixture(scope="module")
def snapshot():
    ctx = MatchCatalog.get_match_context(MATCH_ID)
    return freeze_with_context(generate_match(), ctx, 720, seed=17, scenario="default")


def _window_bounds(as_of: int, window: str) -> tuple[float, float]:
    if window == "match":
        return 0.0, float(as_of)
    if window == "previous":
        return float(max(0, as_of - 360)), float(max(0, as_of - 180))
    return float(max(0, as_of - 180)), float(as_of)


def test_discrete_window_and_equivalent_range_agree(snapshot):
    """The range flavour is the same formula, not a second implementation."""
    as_of = int(snapshot.data["as_of"])
    for team in TEAMS:
        for window in WINDOWS:
            start, end = _window_bounds(as_of, window)
            for metric_id in RECEIPT_METRICS:
                discrete = MetricsService.query(snapshot, metric_id, team=team, window=window)
                ranged = MetricsService.query_range(
                    snapshot, metric_id, team=team, start_s=start, end_s=end
                )
                assert discrete.status == ranged.status, f"{metric_id}/{window}/{team}"
                assert discrete.value == ranged.value, f"{metric_id}/{window}/{team}"
                assert discrete.event_ids == ranged.event_ids, f"{metric_id}/{window}/{team}"


def test_same_team_window_snapshot_is_stable_across_calls(snapshot):
    for team in TEAMS:
        for window in WINDOWS:
            first = MetricsService.query(snapshot, "shots", team=team, window=window)
            second = MetricsService.query(snapshot, "shots", team=team, window=window)
            assert first.value == second.value
            assert first.event_ids == second.event_ids
            assert first.snapshot_id == second.snapshot_id == snapshot.id


def test_observation_is_bound_to_its_snapshot(snapshot):
    observation = MetricsService.query(snapshot, "goals", team="H", window="current")
    assert observation.snapshot_id == snapshot.id

    later = freeze_with_context(
        generate_match(), MatchCatalog.get_match_context(MATCH_ID), 600, seed=17, scenario="default"
    )
    other = MetricsService.query(later, "goals", team="H", window="current")
    assert other.snapshot_id == later.id
    assert other.snapshot_id != observation.snapshot_id


def test_batched_range_matches_single_range(snapshot):
    """Batching must not change a value."""
    as_of = int(snapshot.data["as_of"])
    start, end = _window_bounds(as_of, "current")
    batched = MetricsService.query_range_many(
        snapshot, list(RECEIPT_METRICS), team="H", start_s=start, end_s=end
    )
    assert [v.metric_id for v in batched] == list(RECEIPT_METRICS)
    for value in batched:
        single = MetricsService.query_range(snapshot, value.metric_id, team="H", start_s=start, end_s=end)
        assert value.value == single.value
        assert value.event_ids == single.event_ids


def test_illegal_range_is_reported_not_fabricated(snapshot):
    as_of = int(snapshot.data["as_of"])
    for start, end, reason in (
        (as_of, as_of, "range_end_not_after_start"),
        (-1.0, 100.0, "range_start_before_match_clock"),
        (0.0, as_of + 10_000, "range_beyond_snapshot_as_of"),
    ):
        value = MetricsService.query_range(snapshot, "shots", team="H", start_s=start, end_s=end)
        assert value.status == "not_applicable"
        assert value.value is None
        assert value.details.get("reason") == reason


def test_unobserved_window_stays_unobserved(snapshot):
    """An empty window must report no measurement, not zero."""
    value = MetricsService.query_range(snapshot, "shots", team="H", start_s=0.0, end_s=0.5)
    assert value.value is None
    assert value.status in ("unobserved", "ok")


def test_teams_never_share_a_value_by_accident(snapshot):
    for window in WINDOWS:
        home = MetricsService.query(snapshot, "shots", team="H", window=window)
        away = MetricsService.query(snapshot, "shots", team="N", window=window)
        assert home.team == "H"
        assert away.team == "N"


def test_chart_endpoint_publishes_the_registry_value():
    """The chart surface reads the registry rather than recomputing."""
    from fastapi.testclient import TestClient

    from matchlens.main import app

    with TestClient(app) as client:
        client.post("/api/sessions")
        client.post("/api/control", json={"action": "set_match", "match_id": MATCH_ID})
        client.post("/api/control", json={"action": "seek", "at": 720})
        response = client.get(
            "/api/metrics/shots",
            params={"team": "H", "window": "current", "match_id": MATCH_ID, "at": 720},
        )
        assert response.status_code == 200
        payload = response.json()
        state = client.get("/api/state").json()

    ctx = MatchCatalog.get_match_context(MATCH_ID)
    snapshot = freeze_with_context(generate_match(), ctx, 720, seed=17, scenario="default")
    direct = MetricsService.query(snapshot, "shots", team="H", window="current")
    assert payload["value"] == direct.value
    assert payload["event_ids"] == direct.event_ids

    # The chart payload carries the same receipt for the same frozen clock.
    chart_receipt = state["receipts"]["H.shots.current"]
    assert chart_receipt["value"] == direct.value
    assert chart_receipt["event_ids"] == direct.event_ids
    assert chart_receipt["status"] == direct.status


def test_story_metric_refs_match_the_registry(snapshot, tmp_path):
    """The story quotes the registry; it never recomputes a number."""
    registry = ClaimRegistry(tmp_path / "claims.json")
    record = registry.verify_and_register(snapshot, MATCH_ID, "goal_sequence", "H")
    assert record.gate_status == "approved"

    events = reduce_match(generate_match(), 720)["events"]
    story = MatchStoryEngine.generate_story(
        MATCH_ID,
        events,
        registry,
        snapshot.id,
        "media",
        coverage=snapshot.data["coverage"],
        dataset_revision=snapshot.data.get("dataset_revision"),
        snapshot=snapshot,
    )

    refs = [ref for chapter in story.chapters for ref in chapter.metric_refs]
    assert refs, "a story without metric references cannot be audited"
    for ref in refs:
        assert ref["snapshot_id"] == snapshot.id
        assert ref["status"] in ("ok", "unobserved", "not_applicable", "not_calibrated")
        if ref["status"] != "ok":
            # An unobserved reference must not carry a fabricated number.
            assert ref["value"] is None
            continue
        observed = MetricsService.query_range(
            snapshot,
            ref["metric_id"],
            team=ref["team"],
            start_s=ref["window_start_s"],
            end_s=ref["window_end_s"],
        )
        assert observed.value == ref["value"], ref["metric_id"]
        assert observed.event_ids == ref["event_ids"], ref["metric_id"]
        assert ref["metric_version"]
        # A deterministic metric claims no model; a model-backed one names it.
        if ref["metric_id"] == "oaai":
            assert ref["model_version"]
        else:
            assert ref["model_version"] is None


def test_receipt_metric_ids_are_registered():
    registered = {definition.metric_id for definition in MetricsService.definitions()}
    for metric_id in RECEIPT_METRICS:
        assert metric_id in registered


def test_shot_events_in_a_window_match_the_registry(snapshot):
    """The registry's shot count is the event count, not a separate tally."""
    as_of = int(snapshot.data["as_of"])
    start, end = _window_bounds(as_of, "current")
    expected = [
        e for e in snapshot.data["events"]
        if e.get("team") == "H" and e.get("kind") == "shot"
        and start < float(e.get("t", 0)) <= end
    ]
    observed = MetricsService.query(snapshot, "shots", team="H", window="current")
    assert observed.value == len(expected)
