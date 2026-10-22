"""Tests for Explain Any Chart Capability."""
import pytest
from fastapi.testclient import TestClient

from matchlens.main import app
from matchlens.football import generate_match, freeze
from matchlens.explain import explain_chart


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.post("/api/sessions")
        yield c


def test_explain_chart_oaai_momentum():
    events = generate_match(seed=17)
    snap = freeze(events, 360)
    result = explain_chart(snap, chart_type="oaai_momentum", team="H")
    assert result.chart_type == "oaai_momentum"
    assert "OAAI" in result.title
    assert "Harbor FC" in result.summary
    assert len(result.key_metrics) >= 3
    assert result.confidence_tier == "Level 2 (Formula Decomposition)"
    assert len(result.limitations) > 0


def test_explain_chart_density_differential():
    events = generate_match(seed=17)
    snap = freeze(events, 360)
    result = explain_chart(snap, chart_type="density_differential", team="H")
    assert result.chart_type == "density_differential"
    assert "Density Differential" in result.title
    assert any(m.metric == "Density Differential Formula" for m in result.key_metrics)


def test_explain_chart_xt_surface():
    events = generate_match(seed=17)
    snap = freeze(events, 360)
    result = explain_chart(snap, chart_type="xt_surface", team="H")
    assert result.chart_type == "xt_surface"
    assert "Expected Threat" in result.title
    assert any("Heuristic Threat Surface" in str(m.value) for m in result.key_metrics)
    assert any("Uncalibrated" in l for l in result.limitations)


def test_api_explain_endpoint(client):
    client.post("/api/control", json={"action": "focus", "chapter": "A"})
    res = client.post("/api/explain", json={"chart_type": "attacking_channels", "team": "H"})
    assert res.status_code == 200
    data = res.json()
    assert data["chart_type"] == "attacking_channels"
    assert "Final Third Entries" in [m["metric"] for m in data["key_metrics"]]
    assert "causal_disclaimer" in data
