"""Minimum real-provider integration used by the clean CI job.

Skipped when the payload is not installed (the clean-checkout backend job runs
without provider data); the dedicated real-match CI job fetches one match and
executes this file against it.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from matchlens.catalog import MatchCatalog
from matchlens.football import freeze
from matchlens.main import Engine, freeze_match_snapshot
from matchlens.metrics import MetricsService

MATCH_ID = "sb_3795221"


@pytest.fixture(scope="module")
def installed_meta():
    meta = MatchCatalog.get_match(MATCH_ID)
    if meta is None or not meta.analysis_ready:
        pytest.skip(f"{MATCH_ID} is not installed in this checkout")
    return meta


@pytest.fixture(scope="module")
def engine():
    return Engine(Path(tempfile.mkdtemp()), None)


def test_provider_identity_score_and_completeness(installed_meta):
    assert installed_meta.provenance_kind == "provider_payload"
    assert installed_meta.data_provider == "statsbomb_open_data"
    assert installed_meta.analysis_ready is True
    assert installed_meta.verification_basis == "manifest_import_receipt"
    assert installed_meta.dataset_sha256
    assert installed_meta.home_provider_team_id == "768"
    assert installed_meta.away_provider_team_id == "776"
    assert installed_meta.home_score == 2 and installed_meta.away_score == 1

    ctx = MatchCatalog.get_match_context(MATCH_ID)
    assert ctx.provider == "statsbomb_open_data"
    assert ctx.home_team_name == "England"
    assert ctx.away_team_name == "Denmark"
    assert ctx.completeness_status == "COMPLETE_VERIFIED"
    assert ctx.continuous_coverage is True
    assert ctx.event_count == 4691


def test_independent_score_verification_matches_provider(installed_meta):
    from matchlens.score import verify_score

    events = MatchCatalog.load_normalized_events(MATCH_ID)
    result = verify_score(events, installed_meta)
    assert result["status"] == "verified"
    assert result["recorded"] == {"H": 2, "N": 1}
    assert result["provider_declared"] == {"H": 2, "N": 1}
    assert result["shootout"] == {"H": 0, "N": 0}
    assert result["goal_event_ids"]
    assert result["consistent"] is True


def test_clock_reaches_recorded_extra_time_stoppage(installed_meta):
    ctx = MatchCatalog.get_match_context(MATCH_ID)
    assert ctx.nominal_duration == 7200
    assert ctx.duration == 7200
    assert ctx.period == 4
    assert ctx.observed_end == pytest.approx(7871.779, abs=0.01)
    assert ctx.replayable_end == pytest.approx(ctx.observed_end)
    assert ctx.as_of == pytest.approx(ctx.observed_end)
    assert ctx.stoppage_time > 1500
    assert [row["period"] for row in ctx.periods] == [1, 2, 3, 4]
    assert ctx.shootout_clock is None


def test_full_replay_includes_events_past_the_nominal_clock(engine, installed_meta):
    ctx = engine.match_context(MATCH_ID)
    nominal, _ = freeze_match_snapshot(engine, MATCH_ID, 7200)
    full, state = freeze_match_snapshot(engine, MATCH_ID, int(ctx.observed_end) + 1)

    assert full.data["as_of"] > 7200
    assert len(full.data["events"]) > len(nominal.data["events"])
    assert max(event["t"] for event in full.data["events"]) > 7200
    assert full.data["coverage"]["replayable_end"] > 7200
    assert full.data["coverage"]["format_seconds"] == 7200
    assert len(full.data["events"]) == 4691
    assert full.data["score"] == {"H": 2, "N": 1}
    assert state["score"] == {"H": 2, "N": 1}


def test_no_future_information_before_a_seek(engine, installed_meta):
    snap, state = freeze_match_snapshot(engine, MATCH_ID, 3600)
    assert snap.data["as_of"] == 3600
    assert all(event["t"] <= 3600 for event in state["events"])
    # The final 2-1 score must never be projected back onto a first-half clock.
    # At 60:00 the recorded score is 1-1 (Denmark scored, then Kjaer's own goal).
    assert snap.data["score"] == {"H": 1, "N": 1}
    assert snap.data["official_score"] == {"H": 2, "N": 1}


def test_metric_registry_reads_the_real_match_end_to_end(engine, installed_meta):
    ctx = engine.match_context(MATCH_ID)
    snap, state = freeze_match_snapshot(engine, MATCH_ID, int(ctx.observed_end) + 1)
    home = MetricsService.query(snap, "goals", team="H", window="match", match_id=MATCH_ID)
    away = MetricsService.query(snap, "goals", team="N", window="match", match_id=MATCH_ID)
    assert home.status == away.status == "ok"
    assert home.value == 2 and away.value == 1
    assert home.event_ids and all(not event_id.startswith("syn_") for event_id in home.event_ids)
    assert home.dataset_revision


def test_investigation_uses_the_same_full_provider_state(engine, installed_meta):
    from matchlens.investigation import InvestigationPlanner

    ctx = engine.match_context(MATCH_ID)
    snap, state = freeze_match_snapshot(engine, MATCH_ID, int(ctx.observed_end) + 1)
    plan = InvestigationPlanner.run(
        match_id=MATCH_ID,
        snapshot=snap,
        state=state,
        team="H",
        focus_type="moment",
        question="What produced the attacking activity?",
        xt_model=engine.xt_model,
    )
    assert plan.match_id == MATCH_ID
    assert plan.completeness["status"] == "COMPLETE_VERIFIED"
    assert plan.tool_receipts and all(receipt.status == "ok" for receipt in plan.tool_receipts)
    assert plan.as_of >= 7871
    assert all(not str(event_id).startswith("syn_") for finding in plan.findings for event_id in finding.event_ids)


def test_synthetic_and_provider_do_not_cross_contaminate(engine, installed_meta):
    ctx = engine.match_context(MATCH_ID)
    provider, _ = freeze_match_snapshot(engine, MATCH_ID, int(ctx.observed_end) + 1)
    synthetic, _ = freeze_match_snapshot(engine, "syn_default", 720)
    assert provider.id != synthetic.id
    assert synthetic.data["format_seconds"] == 720
    assert provider.data["format_seconds"] == 7200
