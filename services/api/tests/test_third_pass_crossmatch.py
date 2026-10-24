"""Cross-match comparability, coverage and load-status semantics."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from matchlens.catalog import MatchCatalog
from matchlens.main import app


def test_cross_match_withholds_per90_for_partial_fixture():
    with TestClient(app) as client:
        res = client.get("/api/matches/compare?match_ids=syn_default,sb_wc2022_final")
    assert res.status_code == 200, res.text
    summary = res.json()["batch_summary"]
    assert summary["comparable"] is False
    assert "mixed_coverage_or_duration" in " ".join(summary["warnings"])
    assert summary["per_match"]["syn_default"]["rate_status"] == "comparable"
    assert summary["per_match"]["sb_wc2022_final"]["rate_status"] == "withheld_partial_coverage"
    assert summary["per_match"]["sb_wc2022_final"]["passes_per_90"] is None
    assert summary["per_match"]["sb_wc2022_final"]["sample_size_events"] == 12
    assert summary["load_status"]["sb_wc2022_final"]["status"] == "ok"


def test_same_team_cross_match_rates_are_comparable():
    summary = MatchCatalog.get_batch_summary(["syn_default", "syn_counterattack"])
    assert summary["comparable"] is True
    harbor = summary["team_summaries"]["Harbor FC"]
    assert set(harbor["matches"]) == {"syn_default", "syn_counterattack"}
    assert harbor["continuous_matches"] == 2
    assert len(harbor["per_90_available"]) == 2
    assert summary["trend"][0]["rate_status"] == "comparable"


def test_load_status_distinguishes_missing_parse_error_unsupported_and_zero(tmp_path, monkeypatch):
    import matchlens.catalog as catalog_module

    base_meta = {
        "label": "Fixture",
        "competition": "Test",
        "season": "2026",
        "home_team": "Alpha",
        "away_team": "Beta",
        "home_score": 0,
        "away_score": 0,
        "coverage_level": "C1",
        "description": "status fixture",
        "license_ref": "test",
        "events_count": 0,
        "format_seconds": 5400,
        "home_provider_team_id": "1",
        "away_provider_team_id": "2",
    }
    (tmp_path / "fixture_zero.json").write_text(json.dumps({
        "metadata": {**base_meta, "match_id": "fixture_zero", "data_provider": "statsbomb_open_data"},
        "events": [],
    }), encoding="utf-8")
    (tmp_path / "fixture_bad.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "fixture_unsupported.json").write_text(json.dumps({
        "metadata": {**base_meta, "match_id": "fixture_unsupported", "data_provider": "commercial_feed"},
        "events": [],
    }), encoding="utf-8")

    monkeypatch.setattr(catalog_module, "MATCHES_DIR", tmp_path)
    _, status = MatchCatalog.load_multiple_matches_with_status(
        ["fixture_zero", "fixture_bad", "fixture_unsupported", "does_not_exist"]
    )
    assert status["fixture_zero"]["status"] == "zero_events"
    assert status["fixture_bad"]["status"] == "parse_error"
    assert status["fixture_unsupported"]["status"] == "unsupported"
    assert status["does_not_exist"]["status"] == "missing"
