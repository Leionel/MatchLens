"""Fifth-pass tests: metric windows, completeness, immutable revisions and
the investigation-to-broadcast vertical slice."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from matchlens.catalog import MatchCatalog
from matchlens.completeness import verify_dataset_completeness
from matchlens.football import generate_match
from matchlens.main import app, freeze_match_snapshot, freeze_with_context
from matchlens.metrics import MetricsService
from matchlens.oaai import compute_oaai_contribution_ledger
from matchlens.registry import ClaimRegistry


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("MATCHLENS_PRODUCER_TOKEN", "producer-test")
    with TestClient(app) as c:
        assert c.post("/api/sessions").status_code == 200
        yield c


def _default_snapshot(at: int = 720):
    ctx = MatchCatalog.get_match_context("syn_default")
    return freeze_with_context(
        generate_match(), ctx, at, seed=17, scenario="default", match_id=None
    )


def test_goals_metric_respects_team_and_window():
    snap = _default_snapshot(720)
    current = MetricsService.query(snap, "goals", team="H", window="current")
    previous = MetricsService.query(snap, "goals", team="H", window="previous")
    match = MetricsService.query(snap, "goals", team="H", window="match")
    away = MetricsService.query(snap, "goals", team="N", window="current")

    assert current.status == previous.status == match.status == "ok"
    assert current.value == 1
    assert previous.value == 0
    assert match.value == 1
    assert away.value == 0
    assert current.details["window_start"] == 540
    assert current.details["window_end"] == 720
    assert current.event_ids


def test_oaai_metric_respects_team_and_window_and_ledger_recomputes():
    snap = _default_snapshot(720)
    home = MetricsService.query(snap, "oaai", team="H", window="current")
    away = MetricsService.query(snap, "oaai", team="N", window="current")
    assert home.status == away.status == "ok"
    assert home.value != away.value
    assert home.details["peak_at"] >= 540
    assert home.event_ids
    assert set(home.event_ids) <= {event["id"] for event in snap.data["events"]}

    ledger = compute_oaai_contribution_ledger(
        snap.data["events"],
        at=home.details["peak_at"],
        team="H",
        dead_intervals=snap.data.get("dead_intervals", []),
    )
    assert abs(ledger["raw_team_intensity"] - sum(row["team_contribution"] for row in ledger["contributions"])) < 1e-6
    assert ledger["contributions"][0]["event_id"] in {event["id"] for event in snap.data["events"]}


def test_completeness_rejects_sparse_fixture_and_accepts_verified_periods():
    sparse = [
        {"event_id": "a", "period": 1, "clock_seconds": 0.0, "team": "H"},
        {"event_id": "b", "period": 2, "clock_seconds": 5390.0, "team": "N"},
    ]
    report = verify_dataset_completeness(
        sparse,
        raw_event_count=2,
        expected_duration=5400,
        declared_complete=True,
        team_ids=["H", "N"],
    )
    assert report.status != "COMPLETE_VERIFIED"
    assert report.status in ("SPARSE_SAMPLE_FIXTURE", "PARTIAL_OBSERVED")
    assert report.known_missing_segments

    complete = []
    for index in range(300):
        complete.append({
            "event_id": f"p1-{index}",
            "period": 1,
            "clock_seconds": 100 + index * 8,
            "team": "H" if index % 2 else "N",
        })
        complete.append({
            "event_id": f"p2-{index}",
            "period": 2,
            "clock_seconds": 2800 + index * 8,
            "team": "N" if index % 2 else "H",
        })
    verified = verify_dataset_completeness(
        complete,
        raw_event_count=600,
        expected_duration=5400,
        declared_complete=True,
        team_ids=["H", "N"],
    )
    assert verified.status == "COMPLETE_VERIFIED"
    assert verified.verified and verified.confidence == 1.0


def test_import_does_not_mark_end_time_as_complete(tmp_path):
    from matchlens.ingest import import_match

    source = Path(__file__).resolve().parents[1] / "matchlens" / "data" / "matches" / "sb_wc2022_final.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps(payload["events"]), encoding="utf-8")
    receipt = import_match(
        source_path=raw,
        match_id="sparse_import",
        data_dir=tmp_path / "matches",
        receipt_dir=tmp_path / "receipts",
        home_team="Argentina",
        away_team="France",
        home_provider_team_id="779",
        away_provider_team_id="771",
        competition="FIFA World Cup",
        season="2022",
        license_ref="Test license",
        source_declared_complete=True,
    )
    assert receipt["coverage_level"] == "C1_PARTIAL"
    assert receipt["completeness_status"] != "COMPLETE_VERIFIED"


def test_catalog_listing_agrees_with_context_completeness():
    """Hub cards and the match context must report the same verified completeness."""
    listed = {m.match_id: m for m in MatchCatalog.list_matches()}
    assert listed, "catalog must list at least one match"

    for match_id, meta in listed.items():
        ctx = MatchCatalog.get_match_context(match_id)
        assert meta.completeness_status == ctx.completeness_status, match_id
        assert bool(meta.continuous_coverage) is bool(ctx.continuous_coverage), match_id

    synthetic = [m for m in listed.values() if m.match_id.startswith("syn_")]
    assert synthetic
    for meta in synthetic:
        assert meta.completeness_status == "COMPLETE_VERIFIED"
        assert meta.continuous_coverage is True
        assert meta.completeness and meta.completeness["synthetic"] is True


def test_investigation_intent_changes_plan_and_invalid_focus_is_rejected(client):
    why = client.post("/api/investigate", json={
        "match_id": "syn_default", "at": 720, "team": "H",
        "focus_type": "moment", "question": "What produced the attacking activity?",
    })
    who = client.post("/api/investigate", json={
        "match_id": "syn_default", "at": 720, "team": "H",
        "focus_type": "moment", "question": "Who contributed most?",
    })
    unknown = client.post("/api/investigate", json={
        "match_id": "syn_default", "at": 720, "team": "H",
        "focus_type": "moment", "question": "Is the pitch green?",
    })
    invalid_event = client.post("/api/investigate", json={
        "match_id": "syn_default", "at": 720, "team": "H",
        "focus_type": "event", "focus_id": "NOPE", "question": "Why?",
    })
    invalid_sequence = client.post("/api/investigate", json={
        "match_id": "syn_default", "at": 720, "team": "H",
        "focus_type": "sequence", "focus_id": "1", "question": "Explain this sequence",
    })

    invalid_metric = client.post("/api/investigate", json={
        "match_id": "syn_default", "at": 720, "team": "H",
        "focus_type": "metric", "question": "Tell me about it",
    })
    metric_focus = client.post("/api/investigate", json={
        "match_id": "syn_default", "at": 720, "team": "H",
        "focus_type": "metric", "focus_id": "oaai", "question": "The OAAI value here",
    })

    assert why.status_code == who.status_code == unknown.status_code == 200
    assert metric_focus.status_code == 200
    why_plan, who_plan = why.json(), who.json()
    assert why_plan["intent"] == "WHY_CHANGE"
    assert who_plan["intent"] == "WHO_CONTRIBUTED"
    assert why_plan["selected_metrics"] != who_plan["selected_metrics"]
    assert unknown.json()["intent"] == "UNKNOWN"
    assert unknown.json()["state"] == "FAILED"
    assert invalid_event.json()["state"] == "FAILED"
    assert "invalid_focus_event" in " ".join(invalid_event.json()["unresolved"])
    assert invalid_sequence.json()["state"] == "FAILED"
    assert "invalid_focus_sequence" in " ".join(invalid_sequence.json()["unresolved"])
    assert "metric_id_required" in " ".join(invalid_metric.json()["unresolved"])
    metric_plan = metric_focus.json()
    assert metric_plan["intent"] == "WHY_CHANGE"
    assert metric_plan["state"] != "FAILED"
    assert metric_plan["scope"]["metric_id"] == "oaai"
    assert "oaai" in metric_plan["selected_metrics"]
    assert why_plan["state_history"]


def test_investigation_promotes_claim_then_withdrawal_invalidates_it(client):
    res = client.post("/api/investigate", json={
        "match_id": "syn_default", "at": 720, "team": "H",
        "focus_type": "moment", "question": "What produced the attacking activity?",
    })
    plan = res.json()
    assert plan["gate_preview"]["persisted"] is False
    if plan["gate_preview"]["status"] != "approved":
        pytest.skip("current fixture has no gate-approved assertion at this point")

    promoted = client.post(f"/api/investigations/{plan['investigation_id']}/promote")
    assert promoted.status_code == 200, promoted.text
    claim = promoted.json()["claim"]
    original_statement = claim["statement"]

    withdrawn = client.post("/api/challenge", json={
        "claim_id": claim["claim_id"],
        "snapshot_id": claim["snapshot_id"],
        "challenge_type": "withdraw_claim",
        "team": "H",
    })
    assert withdrawn.status_code == 200, withdrawn.text

    engine = client.app.state.engine
    record = engine.registry.get(claim["match_id"], claim["snapshot_id"], claim["claim_id"])
    assert record is not None and record.lifecycle_status == "withdrawn"
    history = engine.registry.revision_history(claim["match_id"], claim["snapshot_id"], claim["claim_id"])
    assert history[0].statement == original_statement
    assert history[-1].statement.startswith("Withdrawn.")
    assert not engine.registry.claim_validity(record, require_editorial=False)["valid"]


def test_public_producer_projection_and_stale_rundown(client):
    headers = {"X-MatchLens-Token": "producer-test"}
    state = client.post("/api/control", json={"action": "focus", "chapter": "A"}).json()
    snapshot_id = state["snapshot_id"]
    story = client.get("/api/matches/syn_default/story?as_of=360&mode=recap").json()
    assert story["snapshot_id"] == snapshot_id

    public = client.get("/api/broadcast/queue", params={
        "match_id": "syn_default", "snapshot_id": snapshot_id,
    }).json()
    assert public["projection"] == "public"
    assert public["records"]
    for record in public["records"]:
        assert "editorial_approver" not in record
        assert "editorial_note" not in record
        assert "editorial_history" not in record

    producer = client.get("/api/broadcast/queue/producer", params={
        "match_id": "syn_default", "snapshot_id": snapshot_id,
    }, headers=headers)
    assert producer.status_code == 200
    records = producer.json()["records"]
    assert any("editorial_history" in record for record in records)
    claim = next(record for record in records if record["gate_status"] == "approved")
    approved = client.post("/api/story/editorial-approval", headers=headers, json={
        "match_id": "syn_default", "snapshot_id": snapshot_id,
        "claim_id": claim["claim_id"], "decision": "approved",
    })
    assert approved.status_code == 200, approved.text

    rundown = client.post("/api/broadcast/rundown", headers=headers, json={
        "match_id": "syn_default", "snapshot_id": snapshot_id,
        "claim_ids": [claim["claim_id"]],
    })
    assert rundown.status_code == 200, rundown.text
    checked = client.get("/api/broadcast/rundown", params={
        "match_id": "syn_default", "snapshot_id": snapshot_id,
    }).json()
    assert checked["valid"] is True
    assert checked["items"][0]["revision_id"]

    exported = client.post("/api/broadcast/export", headers=headers, json={
        "match_id": "syn_default", "snapshot_id": snapshot_id,
        "perspective": "media", "export_format": "json",
    })
    assert exported.status_code == 200, exported.text
    assert exported.json()["manifest"]["valid"] is True
    assert exported.json()["manifest"]["items"][0]["revision_id"]

    client.post("/api/challenge", json={
        "claim_id": claim["claim_id"],
        "snapshot_id": snapshot_id,
        "challenge_type": "withdraw_claim",
        "team": "H",
    })
    stale = client.get("/api/broadcast/rundown", params={
        "match_id": "syn_default", "snapshot_id": snapshot_id,
    }).json()
    assert stale["valid"] is False
    assert claim["claim_id"] in stale["stale_items"]
    blocked = client.post("/api/broadcast/export", headers=headers, json={
        "match_id": "syn_default", "snapshot_id": snapshot_id,
        "perspective": "media", "export_format": "json",
    })
    assert blocked.status_code == 409


def test_oaai_ledger_api_and_idempotency_owner_scope(client):
    ledger = client.get("/api/oaai/ledger", params={
        "match_id": "syn_default", "at": 690, "team": "H", "limit": 8,
    }).json()
    assert ledger["team"] == "H"
    assert ledger["contributions"]
    assert abs(
        ledger["top_team_intensity"]
        - sum(row["team_contribution"] for row in ledger["contributions"])
    ) < 1e-6
    assert abs(
        ledger["raw_team_intensity"]
        - ledger["top_team_intensity"]
        - ledger["unlisted_team_intensity"]
    ) < 1e-6

    registry = ClaimRegistry()
    common = dict(
        idempotency_key="same-key",
        match_id="syn_default",
        snapshot_id="snap-x",
        claim_id="claim-x",
        challenge_type="check_counterevidence",
        result={"outcome": "maintained"},
    )
    registry.remember_challenge(request_payload={"owner": "a"}, owner_id="a", **common)
    registry.remember_challenge(request_payload={"owner": "b"}, owner_id="b", **common)
    assert registry.find_idempotency_key("same-key", owner_id="a", match_id="syn_default") is not None
    assert registry.find_idempotency_key("same-key", owner_id="c", match_id="syn_default") is None
