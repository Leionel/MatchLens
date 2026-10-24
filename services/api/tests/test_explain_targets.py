"""Slice C-2 acceptance: Explain Any Chart targets.

Shot-location and cross-match explanations are verified against synthetic
snapshots (always available); existing chart semantics are guarded against
regression. All values must remain formula-decomposed and honestly labelled.
"""
from __future__ import annotations

import pytest

from matchlens.explain import explain_chart
from matchlens.football import freeze, generate_match


@pytest.fixture()
def synthetic_snapshot():
    return freeze(generate_match(), 719)


def _first_shot(snapshot):
    events = snapshot.data.get("events", [])
    return next((e for e in events if e.get("kind") == "shot"), None)


def test_shot_location_by_coordinates_reports_geometry_and_heuristics(synthetic_snapshot):
    shot = _first_shot(synthetic_snapshot)
    assert shot is not None
    x, y = shot["start"]
    result = explain_chart(
        synthetic_snapshot,
        "shot_location",
        team=shot["team"],
        shot_location=(float(x), float(y)),
    )
    assert result.chart_type == "shot_location"
    assert result.confidence_tier == "Level 2 (Formula Decomposition)"
    metrics = {m.metric: m for m in result.key_metrics}
    distance = metrics["Distance to goal centre"]
    assert 0.0 < float(distance.value) <= 105.0
    pre_xg = metrics["Pre-shot xG (geometric heuristic)"]
    assert 0.0 <= float(pre_xg.value) <= 1.0
    assert "geometric" in pre_xg.formula.lower() and "outcome" in pre_xg.formula.lower()
    assert any("uncalibrated" in l.lower() for l in result.limitations)
    # The nearest-shot observational context found the same shot.
    assert int(metrics["Nearest observed shots within 5m"].value) >= 1
    assert result.supporting_event_ids


def test_shot_location_by_event_id_binds_supporting_events(synthetic_snapshot):
    shot = _first_shot(synthetic_snapshot)
    assert shot is not None
    result = explain_chart(
        synthetic_snapshot,
        "shot_location",
        team=shot["team"],
        shot_event_id=str(shot["id"]),
    )
    assert result.supporting_event_ids == [str(shot["id"])]
    summary = result.summary
    assert str(shot["id"]) in summary


def test_shot_location_rejects_invalid_targets(synthetic_snapshot):
    with pytest.raises(ValueError, match="invalid_shot_event_id"):
        explain_chart(synthetic_snapshot, "shot_location", team="H", shot_event_id="E9999")
    non_shot = next(e for e in synthetic_snapshot.data["events"] if e.get("kind") == "pass")
    with pytest.raises(ValueError, match="event_is_not_a_shot"):
        explain_chart(synthetic_snapshot, "shot_location", team="H", shot_event_id=str(non_shot["id"]))
    with pytest.raises(ValueError, match="shot_location_or_shot_event_id_required"):
        explain_chart(synthetic_snapshot, "shot_location", team="H")


def test_cross_match_diff_uses_the_same_registry_formula_twice(synthetic_snapshot):
    other = freeze(generate_match(seed=23), 719)
    result = explain_chart(
        synthetic_snapshot,
        "cross_match_diff",
        team="H",
        metric_id="shots",
        compare_snapshot=other,
        compare_label="Seed 23 match",
    )
    assert result.chart_type == "cross_match_diff"
    assert result.confidence_tier == "Level 2 (Formula Decomposition)"
    comparison = result.comparison
    assert comparison is not None
    a = comparison["match_a"]
    b = comparison["match_b"]
    assert a["snapshot_id"] == synthetic_snapshot.id
    assert b["snapshot_id"] == other.id
    assert a["status"] == "ok" and b["status"] == "ok"
    assert comparison["diff"] == round(float(b["value"]) - float(a["value"]), 4)
    # Count metrics expose a per-90 pair built from the reported minute bases.
    assert comparison["per_90_a"] is not None and comparison["per_90_b"] is not None
    expected_a = round(float(a["value"]) * 5400.0 / float(a["minutes_basis_seconds"]), 2)
    assert comparison["per_90_a"] == expected_a
    assert any("Sample size is one match per side" in l for l in result.limitations)
    assert comparison["investigation_focus_type"] == "cross_match_diff"
    assert comparison["investigation_focus_id"] == "shots"


def test_cross_match_diff_requires_a_snapshot(synthetic_snapshot):
    with pytest.raises(ValueError, match="compare_snapshot_required"):
        explain_chart(synthetic_snapshot, "cross_match_diff", team="H", metric_id="shots")


def test_cross_match_diff_without_observed_value_publishes_no_difference():
    # A snapshot frozen at t=0 has no observed window: both sides are
    # unobserved, so no difference may be published.
    empty = freeze(generate_match(), 0)
    other = freeze(generate_match(seed=23), 719)
    result = explain_chart(empty, "cross_match_diff", team="H", metric_id="shots", compare_snapshot=other)
    comparison = result.comparison
    assert comparison is not None
    assert comparison["match_a"]["status"] != "ok"
    assert comparison["diff"] is None
    assert "not published" in result.summary.lower()


def test_existing_chart_semantics_unchanged(synthetic_snapshot):
    result = explain_chart(synthetic_snapshot, "oaai_momentum", team="H", point_timestamp=300.0)
    assert result.chart_type == "oaai_momentum"
    assert result.confidence_tier == "Level 2 (Formula Decomposition)"
    zone = explain_chart(synthetic_snapshot, "density_differential", team="H", zone_id="Z8")
    assert "ΔD(z)" in zone.summary
    with pytest.raises(ValueError, match="invalid_zone_id"):
        explain_chart(synthetic_snapshot, "density_differential", team="H", zone_id="Z99")
