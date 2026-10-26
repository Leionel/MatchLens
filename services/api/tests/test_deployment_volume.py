"""Deployment contract: the catalog must follow MATCHLENS_DATA_DIR.

A container images the code but not the licensed provider payloads, so the
manifest and the datasets are materialised at runtime on a mounted volume. If
the catalog ignored the mount, a deployed instance would list 80 matches and
serve none of them.

These tests are offline: they fabricate a tiny manifest and a placeholder
dataset on a temporary "volume" and assert that the catalog resolves and reads
them. `scripts/verify_deployment.py` covers the container-level contract
(COPY sources, .dockerignore, bootstrap idempotency) separately.
"""
from __future__ import annotations

import json

import pytest

from matchlens import catalog as catalog_module
from matchlens.catalog import MatchCatalog, data_root


@pytest.fixture()
def volume(tmp_path, monkeypatch):
    """A data directory outside the repository, like a mounted volume."""
    root = tmp_path / "volume"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("MATCHLENS_DATA_DIR", str(root))
    monkeypatch.setattr(MatchCatalog, "_manifest_cache", {})
    monkeypatch.setattr(MatchCatalog, "_entries_cache", {})
    monkeypatch.setattr(MatchCatalog, "_resolved_path_cache", {})
    monkeypatch.setattr(MatchCatalog, "_dataset_path_cache", {})
    monkeypatch.setattr(MatchCatalog, "_dataset_revision_cache", {})
    monkeypatch.setattr(MatchCatalog, "_event_cache", {})
    monkeypatch.setattr(MatchCatalog, "_completeness_cache", {})
    monkeypatch.setattr(MatchCatalog, "_dataset_digest_cache", {})
    monkeypatch.setattr(catalog_module, "SOURCE_MANIFEST_PATH", root / "source_manifest.json")
    return root


def test_data_root_prefers_the_environment(volume):
    assert data_root() == volume.resolve()


def test_data_root_falls_back_to_the_repository(monkeypatch, tmp_path):
    monkeypatch.delenv("MATCHLENS_DATA_DIR", raising=False)
    monkeypatch.setattr(catalog_module, "REPO_ROOT", tmp_path)
    assert data_root() == (tmp_path / "data").resolve()


def test_a_volume_relative_dataset_path_resolves_inside_the_volume(volume):
    """`data/datasets/x.json` must land on the volume, not in the image tree."""
    dataset = volume / "datasets" / "sb_test.json"
    dataset.write_text("{}", encoding="utf-8")
    resolved = MatchCatalog.resolve_manifest_path("data/datasets/sb_test.json")
    assert resolved == dataset.resolve()


def test_an_absolute_manifest_path_is_still_refused(volume):
    """The rebasing must not become a way to point the catalog anywhere."""
    assert MatchCatalog.resolve_manifest_path("/etc/passwd") is None
    assert MatchCatalog.resolve_manifest_path("data/../../etc/passwd") is None
    assert MatchCatalog.resolve_manifest_path("C:/Windows/system.ini") is None


def test_the_manifest_on_the_volume_is_the_one_that_is_read(volume):
    (volume / "source_manifest.json").write_text(
        json.dumps({"version": "matchlens-source-manifest-v1", "matches": []}),
        encoding="utf-8",
    )
    assert MatchCatalog.manifest_entries() == {}
