"""Slice C-1 acceptance: cross-match team & player profiles.

Layered like the corpus tests: structural assertions always run on unit-level
aggregates; provider-backed assertions are skipped - never silently passed -
when the datasets are absent (the provider agreement keeps payloads out of
version control).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from matchlens.catalog import MatchCatalog
from matchlens.football import freeze, generate_match
from matchlens.metrics import MetricsService
from matchlens.profiles import (
    PLAYER_METRICS,
    TEAM_METRICS,
    ProfileMatchRow,
    ProfileMatchMetricValue,
    _metric_aggregate,
    align_windows_by_period,
    build_player_profile,
    build_team_profile,
    compute_player_minutes,
    discover_team_matches,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATASET_DIR = REPO_ROOT / "data" / "datasets"


def _imported_provider_matches() -> list[str]:
    out = []
    for m in MatchCatalog.list_matches():
        if m.provenance_kind == "provider_payload" and m.completeness_status not in (None, "DATASET_NOT_IMPORTED"):
            if DATASET_DIR.exists():
                out.append(m.match_id)
    return out


def _team_with_two_matches() -> tuple[str, list[str]] | None:
    ids = _imported_provider_matches()
    if len(ids) < 2:
        return None
    by_team: dict[str, list[str]] = {}
    for mid in ids:
        meta = MatchCatalog.get_match(mid)
        assert meta is not None
        by_team.setdefault(meta.home_team, []).append(mid)
        by_team.setdefault(meta.away_team, []).append(mid)
    for team, mids in by_team.items():
        if len(mids) >= 2:
            return team, mids[:2]
    return None


def _frozen_snapshot(match_id: str):
    from matchlens.main import _resolve_profile_snapshot

    class _EngStub:
        def match_context(self, mid):
            return MatchCatalog.get_match_context(mid)

        def events_for_match(self, mid, scenario=None):
            return MatchCatalog.load_normalized_events(mid)

    ctx = MatchCatalog.get_match_context(match_id)
    return _resolve_profile_snapshot(_EngStub(), match_id, ctx)


def _make_row(metric_values: dict[str, float], *, continuous: bool, minutes: float = 5400.0) -> ProfileMatchRow:
    metrics = {
        mid: ProfileMatchMetricValue(metric_id=mid, value=v, status="ok", unit="count")
        for mid, v in metric_values.items()
    }
    return ProfileMatchRow(
        match_id=f"m_{abs(hash(tuple(metric_values.items()))) % 100000}",
        label="unit row",
        competition="unit",
        season="1",
        side="H",
        side_team_name="T",
        opponent_name="O",
        minutes_basis_seconds=minutes,
        coverage_status="COMPLETE_VERIFIED" if continuous else "PARTIAL_PREFIX",
        continuous_coverage=continuous,
        provenance_kind="provider_payload",
        included_in_rates=True,
        metrics=metrics,
    )


# --------------------------------------------------------------- unit level


def test_per_90_uses_only_complete_coverage_matches():
    rows = [
        _make_row({"shots": 10}, continuous=True, minutes=5400.0),
        _make_row({"shots": 5}, continuous=False, minutes=5400.0),
    ]
    agg = _metric_aggregate("shots", rows, windowed=False)
    # Raw total includes the partial match; the rate must not.
    assert agg.absolute_total == 15
    assert agg.per_90 == 10.0
    assert agg.per_90_basis["total_value"] == 10
    assert agg.per_90_basis["matches_with_complete_coverage"] == 1
    assert agg.rate_status == "comparable"


def test_per_90_withheld_without_any_complete_match():
    rows = [_make_row({"shots": 7}, continuous=False)]
    agg = _metric_aggregate("shots", rows, windowed=False)
    assert agg.per_90 is None
    assert agg.rate_status == "withheld_no_complete_matches"
    assert agg.absolute_total == 7


def test_possession_aggregates_as_mean_of_shares_never_a_sum():
    rows = [
        _make_row({"possession": 60.0}, continuous=True),
        _make_row({"possession": 50.0}, continuous=True),
    ]
    agg = _metric_aggregate("possession", rows, windowed=False)
    assert agg.absolute_total == 55.0
    assert agg.per_90 is None
    assert agg.rate_status == "comparable_mean_of_match_shares"


def test_aggregate_reports_distribution_without_inference():
    rows = [
        _make_row({"shots": 4}, continuous=True),
        _make_row({"shots": 8}, continuous=True),
    ]
    agg = _metric_aggregate("shots", rows, windowed=False)
    assert agg.sample_size == 2
    assert agg.per_match_mean == 6.0
    assert agg.per_match_median == 6.0
    assert agg.per_match_min == 4 and agg.per_match_max == 8
    assert [pv["value"] for pv in agg.per_match_values] == [4, 8]
    assert any("No confidence interval" in n for n in agg.notes)


def test_player_minutes_methods_are_flagged_not_invented():
    from matchlens.schema import NormalizedEvent, RawSourceRecord, ActionType

    def ev(pid, clock, action=ActionType.PASS, role=None, sub_off=None, sub_on=None):
        return NormalizedEvent(
            event_id=f"e{pid}_{clock}_{sub_off or ''}{sub_on or ''}",
            match_id="m",
            source=RawSourceRecord(provider="statsbomb_open_data", provider_event_id="1", schema_version="1", license_ref="test"),
            period=1,
            clock_seconds=clock,
            team_id="H",
            player_id=pid,
            player_name=f"P{pid}",
            action_type=action,
            outcome="complete",
            lineup_role=role,
            substitution_off_player_id=sub_off,
            substitution_on_player_id=sub_on,
        )

    events = [
        ev("1", 0.0, role="starter"),
        ev("1", 100.0, sub_off="1"),  # starter subbed off at 100s
        ev("2", 100.0, sub_on="2"),   # substitute enters at 100s
        ev("3", 50.0),                 # no records at all -> fallback span
    ]
    m1 = compute_player_minutes(events, "1", observed_end=5400.0)
    assert m1["method"] == "substitution_derived" and m1["seconds"] == 100.0
    m2 = compute_player_minutes(events, "2", observed_end=5400.0)
    assert m2["method"] == "substitution_derived" and m2["seconds"] == 5300.0
    m3 = compute_player_minutes(events, "3", observed_end=5400.0)
    assert m3["method"] == "event_span_fallback" and m3["seconds"] == 0.0
    m4 = compute_player_minutes(events, "4", observed_end=5400.0)
    assert m4["method"] == "no_records" and m4["seconds"] == 0.0


def test_aligned_windows_never_merge_periods():
    events_a = [
        {"period": 1, "t": 10.0}, {"period": 1, "t": 2600.0},
        {"period": 2, "t": 2800.0}, {"period": 2, "t": 5300.0},
        {"period": 5, "t": 7400.0},
    ]
    events_b = [
        {"period": 1, "t": 5.0}, {"period": 1, "t": 2700.0},
        {"period": 2, "t": 2760.0}, {"period": 2, "t": 5320.0},
    ]
    alignment = align_windows_by_period([("a", events_a), ("b", events_b)])
    periods = [w["period"] for w in alignment["windows"]]
    assert periods == [1, 2]  # shootout (5) never participates
    w1 = next(w for w in alignment["windows"] if w["period"] == 1)
    # Intersection of the two observed spans: start = max(starts), end = min(ends).
    assert w1["start_s"] == 10.0 and w1["end_s"] == 2600.0
    assert w1["length_seconds"] == 2590.0


# --------------------------------------------------------------- API level


def test_team_profile_excludes_synthetic_and_carries_denominators(client):
    team_info = _team_with_two_matches()
    if team_info is None:
        pytest.skip("provider datasets not imported in this checkout")
    team, ids = team_info
    res = client.get("/api/profiles/team", params={"team": team, "match_ids": ",".join(ids)})
    assert res.status_code == 200, res.text
    data = res.json()

    # The route refuses a match the team is not part of instead of skipping it.
    stray = client.get("/api/profiles/team", params={"team": team, "match_ids": "syn_default"})
    assert stray.status_code == 422

    # Synthetic rows are excluded inside the builder (provenance gate).
    from matchlens.profiles import build_team_profile as _build

    snap0, _state0 = _frozen_snapshot(ids[0])
    meta0 = MatchCatalog.get_match(ids[0])
    synthetic_row = {
        "match_id": "syn_default",
        "label": "synthetic",
        "competition": "sim",
        "season": "1",
        "side": "H",
        "side_team_name": "Harbor FC",
        "opponent_name": "Northbridge United",
        "provider_team_ids": [],
        "provenance_kind": "synthetic",
        "continuous_coverage": True,
        "snapshot": snap0,
        "state": {"events": []},
    }
    provider_row = {
        "match_id": ids[0],
        "label": meta0.label,
        "competition": meta0.competition,
        "season": meta0.season,
        "match_date": meta0.match_date,
        "side": "H" if meta0.home_team == team else "N",
        "side_team_name": team,
        "opponent_name": meta0.away_team if meta0.home_team == team else meta0.home_team,
        "provider_team_ids": [meta0.home_provider_team_id],
        "provenance_kind": "provider_payload",
        "coverage_status": meta0.completeness_status,
        "continuous_coverage": bool(snap0.data.get("coverage", {}).get("continuous")),
        "dataset_revision": snap0.data.get("dataset_revision"),
        "snapshot": snap0,
        "state": {"events": []},
    }
    built = _build(team=team, rows=[synthetic_row, provider_row])
    assert built.provenance_kinds.keys() == {"provider_payload"}
    assert {e["match_id"] for e in built.scope["excluded"]} == {"syn_default"}
    assert [r.match_id for r in built.matches] == [ids[0]]

    # Denominators, coverage and provenance travel with every row.
    for row in data["matches"]:
        assert row["provenance_kind"] == "provider_payload"
        assert row["minutes_basis_seconds"] > 0
        assert set(row["metrics"].keys()) == set(TEAM_METRICS)

    complete = [r for r in data["matches"] if r["continuous_coverage"]]
    shots = data["aggregates"]["shots"]
    if complete:
        assert shots["rate_status"] == "comparable"
        assert shots["per_90_basis"]["total_minutes_seconds"] == sum(r["minutes_basis_seconds"] for r in complete)
        assert shots["per_90_basis"]["matches_with_complete_coverage"] == len(complete)
    else:
        assert shots["rate_status"] == "withheld_no_complete_matches" and shots["per_90"] is None

    # Per-match registry values equal a direct MetricsService observation.
    row = data["matches"][0]
    snap, _state = _frozen_snapshot(row["match_id"])
    side = row["side"]
    direct = MetricsService.query(snap, "shots", team=side, window="match")
    assert row["metrics"]["shots"]["value"] == direct.value
    assert any("confidence interval" in n for n in shots["notes"])


def test_profile_rows_disclose_clock_bounding(client):
    team_info = _team_with_two_matches()
    if team_info is None:
        pytest.skip("provider datasets not imported in this checkout")
    team, ids = team_info
    res = client.get("/api/profiles/team", params={"team": team, "match_ids": ",".join(ids)})
    assert res.status_code == 200
    data = res.json()
    for row in data["matches"]:
        assert isinstance(row["clock_bounded_at_duration"], bool)
        if row["clock_bounded_at_duration"]:
            assert any("nominal" in l and ("excluded" in l or "bounded" in l) for l in data["limitations"])


def test_player_profile_matches_registry_formula_on_filtered_stream(client):
    team_info = _team_with_two_matches()
    if team_info is None:
        pytest.skip("provider datasets not imported in this checkout")
    team, ids = team_info
    res = client.get("/api/profiles/players", params={"match_ids": ids[0], "limit": 20})
    assert res.status_code == 200
    players = res.json()["players"]
    if not players:
        pytest.skip("no players indexed for this match")
    player = players[0]

    res = client.get(
        "/api/profiles/player",
        params={"player_id": player["player_id"], "match_ids": player["match_ids"][:2]},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert set(data["aggregates"].keys()) == set(PLAYER_METRICS)
    assert data["minutes"]["total_minutes"] > 0
    assert data["minutes"]["methods"], "minutes methods must be reported"
    assert any("possession chains" in l for l in data["limitations"])

    # One row re-checked against a direct MetricsService run on a re-frozen,
    # player-scoped snapshot: the profile must not invent its own formula.
    from matchlens.profiles import _player_scoped_snapshot

    first_match = data["matches"][0]
    snap, _state = _frozen_snapshot(first_match["match_id"])
    player_snap, _name, count, _variants = _player_scoped_snapshot(snap, player["player_id"], allow_actor_match=False)
    direct = MetricsService.query(
        player_snap, "passes", team=first_match["side"], window="match"
    )
    assert first_match["metrics"]["passes"]["value"] == direct.value
    assert count > 0


def test_player_profile_honestly_rejects_absent_player(client):
    team_info = _team_with_two_matches()
    if team_info is None:
        pytest.skip("provider datasets not imported in this checkout")
    _team, ids = team_info
    res = client.get(
        "/api/profiles/player",
        params={"player_id": "99999999", "match_ids": ids[0]},
    )
    assert res.status_code == 422
    assert "player_not_in_match" in res.text


def test_team_discovery_lists_provenance(client):
    team_info = _team_with_two_matches()
    if team_info is None:
        pytest.skip("provider datasets not imported in this checkout")
    team, _ids = team_info
    res = client.get("/api/profiles/team-discovery", params={"team": team})
    assert res.status_code == 200
    data = res.json()
    assert data["match_count"] >= 1
    for row in data["matches"]:
        assert row["provenance_kind"] in ("provider_payload", "synthetic", "provider_schema_excerpt")
