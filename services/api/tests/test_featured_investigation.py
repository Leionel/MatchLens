"""The Match Hub's featured investigation must be a deterministic, disclosed pick.

``/api/featured`` exists so a first-time visitor lands on one real, in-clock
moment instead of an 87-row catalog. The tests pin the contract that makes it
trustworthy: provider provenance outranks a bigger synthetic fixture, the
moment must sit inside the replayable clock, every narrative string is derived
from recorded values, and a selection with no usable change point degrades to
an explicit fallback instead of a fabricated highlight.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

import matchlens.catalog as catalog_module  # noqa: E402
import matchlens.main as main_module  # noqa: E402
from matchlens.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    with TestClient(app) as c:
        yield c


def _fake_change_point(**overrides):
    point = {
        "change_point_id": "CP-07",
        "at": 3000.0,
        "oaai_amplitude": 1.5,
        "leading_team": "H",
        "change_type": "home_surge",
        "claim_level": 2,
        "disclaimer": "指标归因仅代表公式分解，不代表战术因果。",
        "window_seconds": 45,
        "top_contributors": [
            {
                "event_id": "sb_3795221_01000",
                "t": 2995.0,
                "team": "H",
                "actor": "Harry Kane",
                "kind": "shot",
                "outcome": "saved",
                "contribution": 0.7,
                "magnitude": 0.7,
                "explanation": "Shot attempt (0.70)",
            }
        ],
    }
    point.update(overrides)
    return point


@pytest.fixture()
def two_candidate_catalog(monkeypatch):
    """A provider match and a synthetic fixture, the synthetic with more events."""
    from matchlens.catalog import MatchCatalog

    real = MatchCatalog.get_match("sb_3795221")
    synthetic = MatchCatalog.get_match("syn_default")
    assert real is not None and synthetic is not None
    synthetic = synthetic.model_copy(update={"events_count": 4000, "analysis_ready": True, "dataset_installed": True})
    real = real.model_copy(update={"events_count": 400, "analysis_ready": True, "dataset_installed": True})
    monkeypatch.setattr(MatchCatalog, "list_matches", classmethod(lambda cls: [synthetic, real]))
    return real


def test_provider_provenance_outranks_a_larger_synthetic(client, two_candidate_catalog, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "compute_oaai",
        lambda *a, **k: {"change_points": [_fake_change_point()]},
    )
    response = client.get("/api/featured")
    assert response.status_code == 200
    data = response.json()
    assert data["fallback"] is False
    assert data["featured"]["match_id"] == "sb_3795221"
    assert data["featured"]["provenance_kind"] == "provider_payload"
    moment = data["featured"]["moment"]
    assert moment["at"] == 3000.0
    assert moment["leading_team"] == "H"
    assert moment["team_name"] == "England"
    # Narrative strings are assembled from recorded values only.
    assert "England" in data["featured"]["what_changed"]
    assert "formula attribution" in data["featured"]["what_changed"]
    assert data["featured"]["question"].startswith("What produced England")
    assert len(data["featured"]["supporting_events"]) == 1
    assert data["featured"]["supporting_events"][0]["actor"] == "Harry Kane"
    assert "no model" in data["algorithm"]


def test_change_point_outside_the_replayable_clock_is_skipped(client, two_candidate_catalog, monkeypatch):
    # A stoppage-time amplitude spike beyond the replayable clock must not be
    # featured: the replay cannot seek there, so the journey would dead-end.
    monkeypatch.setattr(
        main_module,
        "compute_oaai",
        lambda *a, **k: {"change_points": [_fake_change_point(at=99999.0)]},
    )
    data = client.get("/api/featured").json()
    assert data["fallback"] is True
    assert data["featured"] is None
    assert "replayable clock" in data["fallback_reason"]


def test_no_candidates_degrades_to_an_explicit_fallback(client, two_candidate_catalog, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "compute_oaai",
        lambda *a, **k: {"change_points": []},
    )
    data = client.get("/api/featured").json()
    assert data["fallback"] is True
    assert data["featured"] is None
    assert data["candidates_considered"] >= 1
    assert data["fallback_reason"]


def test_featured_response_is_memoised_per_catalog_signature(client, two_candidate_catalog, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "compute_oaai",
        lambda *a, **k: {"change_points": [_fake_change_point()]},
    )
    first = client.get("/api/featured").json()
    second = client.get("/api/featured").json()
    assert first == second
    assert len(client.app.state.engine.featured_cache) == 1
