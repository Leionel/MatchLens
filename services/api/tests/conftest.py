"""Shared fixtures for the Slice C acceptance suites.

The ``client`` fixture boots the app against an isolated runtime directory —
the same pattern the other suites define locally; no test may share a live
runtime state across files.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from matchlens.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    with TestClient(app) as c:
        assert c.post("/api/sessions").status_code == 200
        yield c
