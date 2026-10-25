"""Data availability contract and manifest portability."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from matchlens import catalog as catalog_module
from matchlens.catalog import MatchCatalog


def _manifest_entry(match_id: str, dataset_path: str, checksum: str, *, period_status: str = "COMPLETE_VERIFIED") -> dict:
    return {
        "match_id": match_id,
        "dataset_path": dataset_path,
        "dataset_sha256": checksum,
        "stage": "final",
        "completeness": {
            "status": period_status,
            "observed_periods": [1, 2],
            "expected_periods": [1, 2],
        },
        "metadata": {
            "match_id": match_id,
            "label": "Home vs Away",
            "competition": "Test Cup",
            "season": "2024",
            "match_date": "2024-05-01",
            "home_team": "Home",
            "away_team": "Away",
            "home_score": 1,
            "away_score": 0,
            "coverage_level": "C1",
            "data_provider": "statsbomb_open_data",
            "description": "test payload",
            "license_ref": "test licence",
            "events_count": 11,
            "format_seconds": 5400,
            "home_provider_team_id": "1",
            "away_provider_team_id": "2",
            "provenance_kind": "provider_payload",
            "continuous_coverage": period_status == "COMPLETE_VERIFIED",
            "source_declared_complete": True,
            "completeness_status": period_status,
        },
    }


@pytest.fixture()
def isolated_catalog(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    datasets = repo / "data" / "datasets"
    datasets.mkdir(parents=True)
    manifest_path = repo / "data" / "source_manifest.json"
    monkeypatch.setattr(catalog_module, "REPO_ROOT", repo)
    monkeypatch.setattr(catalog_module, "SOURCE_MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(catalog_module, "MATCHES_DIR", repo / "services" / "api" / "matchlens" / "data" / "matches")
    # The class-level memo is keyed by the manifest path, but a test must not
    # inherit another test's cached catalog.
    monkeypatch.setattr(MatchCatalog, "_manifest_cache", {})
    monkeypatch.setattr(MatchCatalog, "_entries_cache", {})
    monkeypatch.setattr(MatchCatalog, "_resolved_path_cache", {})
    monkeypatch.setattr(MatchCatalog, "_dataset_path_cache", {})
    monkeypatch.setattr(MatchCatalog, "_dataset_revision_cache", {})
    monkeypatch.setattr(MatchCatalog, "_event_cache", {})
    monkeypatch.setattr(MatchCatalog, "_completeness_cache", {})
    monkeypatch.setattr(MatchCatalog, "_dataset_digest_cache", {})
    yield repo, manifest_path, datasets


def _write_manifest(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"matches": entries}, indent=2), encoding="utf-8")


def _write_dataset(path: Path, *, events: list[dict] | None = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "home_provider_team_id": "1",
            "away_provider_team_id": "2",
        },
        "events": events or [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_windows_manifest_paths_resolve_portably_and_reject_escapes():
    expected = (catalog_module.REPO_ROOT / "data" / "datasets" / "sb_1.json").resolve()
    assert MatchCatalog.resolve_manifest_path("data\\datasets\\sb_1.json") == expected
    assert MatchCatalog.resolve_manifest_path("data/datasets/sb_1.json") == expected
    assert MatchCatalog.resolve_manifest_path("../outside.json") is None
    assert MatchCatalog.resolve_manifest_path("/etc/passwd") is None
    assert MatchCatalog.resolve_manifest_path("C:\\Windows\\system.ini") is None
    assert MatchCatalog.resolve_manifest_path("") is None


def test_catalogued_match_is_listed_but_cannot_be_analysed(isolated_catalog):
    _repo, manifest_path, _datasets = isolated_catalog
    _write_manifest(
        manifest_path,
        [_manifest_entry("sb_missing", "data/datasets/sb_missing.json", "0" * 64)],
    )

    listed = {m.match_id: m for m in MatchCatalog.list_matches()}
    meta = listed["sb_missing"]
    assert meta.availability_status == "CATALOGUED"
    assert meta.analysis_ready is False
    assert meta.dataset_installed is False
    assert meta.availability_reason and "not_imported" in meta.availability_reason
    assert meta.install_hint and "sb_missing" in meta.install_hint
    with pytest.raises(FileNotFoundError):
        MatchCatalog.get_match_context("sb_missing")
    ready, reason = MatchCatalog.verify_analysis_ready("sb_missing")
    assert ready is False
    assert reason and "not_imported" in reason


def test_materialized_and_tampered_dataset_fail_closed(isolated_catalog):
    repo, manifest_path, datasets = isolated_catalog
    dataset = datasets / "sb_tamper.json"
    digest = _write_dataset(dataset)
    _write_manifest(
        manifest_path,
        [_manifest_entry("sb_tamper", "data/datasets/sb_tamper.json", digest)],
    )
    listed = {m.match_id: m for m in MatchCatalog.list_matches()}
    # The import receipt says the file is complete; the listing trusts it and
    # points at a materialised payload. Content is checked on use.
    assert listed["sb_tamper"].analysis_ready is True
    ready, reason = MatchCatalog.verify_analysis_ready("sb_tamper")
    assert ready is False
    assert reason and "no_events" in reason

    dataset.write_text(dataset.read_text(encoding="utf-8") + " ", encoding="utf-8")
    ready, reason = MatchCatalog.verify_analysis_ready("sb_tamper")
    assert ready is False
    assert reason and "integrity" in reason

    # A bad checksum must not be mistaken for a missing dataset.
    _write_manifest(
        manifest_path,
        [_manifest_entry("sb_tamper", "data/datasets/sb_tamper.json", "f" * 64)],
    )
    with pytest.raises(ValueError):
        MatchCatalog.get_match_context("sb_tamper")


def _ingest_module():
    import importlib.util

    path = Path(__file__).resolve().parents[3] / "scripts" / "ingest_statsbomb_corpus.py"
    spec = importlib.util.spec_from_file_location("ingest_statsbomb_corpus_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_partial_import_merges_manifest_and_is_idempotent():
    module = _ingest_module()
    corpus = {"provider": {"base_url": "https://example.invalid/data"}}

    def entry(match_id: str) -> dict:
        return {
            "match_id": match_id,
            "competition_id": 1,
            "season_id": 2,
            "provider_match_id": int(match_id.split("_")[-1]),
            "stage": "final",
        }

    entries = [entry("sb_1"), entry("sb_2")]
    existing = {
        "sb_1": {"match_id": "sb_1", "dataset_path": "data/datasets/sb_1.json", "old": True},
        "sb_2": {"match_id": "sb_2", "dataset_path": "data/datasets/sb_2.json", "old": True},
    }
    row = {
        "match_id": "sb_2",
        "dataset_path": "data/datasets/sb_2.json",
        "dataset_sha256": "a" * 64,
        "receipt": {
            "completeness": {"status": "COMPLETE_VERIFIED"},
            "source_sha256": "b" * 64,
        },
        "metadata": {
            "match_id": "sb_2",
            "home_provider_team_id": "1",
            "away_provider_team_id": "2",
        },
    }

    first = module.merge_manifest_entries(existing, [row], entries, corpus)
    assert list(first) == ["sb_1", "sb_2"]
    # The unselected entry survives the partial import untouched.
    assert first["sb_1"] == existing["sb_1"]
    assert first["sb_2"]["dataset_sha256"] == "a" * 64
    assert first["sb_2"]["source"]["source_sha256"] == "b" * 64

    second = module.merge_manifest_entries(first, [row], entries, corpus)
    assert second == first


def test_manifest_with_windows_path_is_read_on_any_platform(isolated_catalog):
    _repo, manifest_path, datasets = isolated_catalog
    dataset = datasets / "sb_win.json"
    digest = _write_dataset(dataset)
    _write_manifest(
        manifest_path,
        [_manifest_entry("sb_win", "data\\datasets\\sb_win.json", digest)],
    )
    meta = MatchCatalog.get_match("sb_win")
    assert meta is not None
    assert meta.availability_status == "ANALYSIS_READY"
    assert meta.dataset_path is not None
    assert "\\" not in meta.dataset_path
