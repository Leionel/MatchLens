"""Fourth-pass trust, identity, revision and investigation contracts."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from matchlens.catalog import MatchCatalog
from matchlens.football import generate_match, reduce_match
from matchlens.main import Engine, app
from matchlens.registry import ClaimRegistry


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_RUNTIME_DIR", str(tmp_path))
    with TestClient(app) as c:
        assert c.post("/api/sessions").status_code == 200
        yield c


def test_stale_agent_run_never_writes_claims_into_a_new_match(tmp_path):
    async def scenario():
        engine = Engine(tmp_path, None)
        s = engine.sessions.setdefault("stale", None)
        from matchlens.main import Session

        s = Session("stale", "local", at=360)
        engine.sessions[s.id] = s
        snap = engine.snapshot_for(s, 360)
        started, release = asyncio.Event(), asyncio.Event()

        async def fake_runner(run, progress):
            started.set()
            await release.wait()
            return {
                "status": "completed",
                "origin": "fault_injection",
                "accepted": [{
                    "claim_id": "claim-stale-fixture",
                    "assertion": "goal_sequence",
                    "claim_level": 1,
                    "analyst": "fixture",
                    "refs": ["H.goals.match"],
                    "as_of": 360,
                    "evidence_scope": {"event_ids": [], "metric_ids": ["H.goals.match"]},
                }],
                "rejected": [],
            }

        engine.runner.analyse = fake_runner
        assert engine.start_analysis(s, snap, "manual")
        await started.wait()
        # The match changes while the model is still running.
        s.match_id = "syn_transitions"
        s.epoch += 1
        release.set()
        await asyncio.gather(s.task, return_exceptions=True)
        assert not any(
            r.match_id == "syn_transitions" and r.source_run == s.run_info.get("run_id")
            for r in engine.registry.records.values()
        ) if s.run_info else True
        assert not any(r.match_id == "syn_transitions" for r in engine.registry.records.values())
        run_files = list((tmp_path / "runs").glob("*.json"))
        assert run_files
        record = json.loads(run_files[-1].read_text())
        assert any(a.get("type") == "superseded" for a in record["audit"])
        engine.ledger.close()

    asyncio.run(scenario())


def test_editorial_approval_requires_server_identity(client, monkeypatch):
    monkeypatch.setenv("MATCHLENS_PRODUCER_TOKEN", "producer-secret")
    story = client.get("/api/matches/syn_default/story?as_of=720").json()
    claim = next(c for c in story["claims"] if c["gate_status"] == "approved")

    anonymous = client.post("/api/story/editorial-approval", json={
        "match_id": "syn_default",
        "snapshot_id": story["snapshot_id"],
        "claim_id": claim["claim_id"],
        "decision": "approved",
    })
    assert anonymous.status_code == 403

    wrong = client.post(
        "/api/story/editorial-approval",
        headers={"X-MatchLens-Token": "wrong"},
        json={
            "match_id": "syn_default",
            "snapshot_id": story["snapshot_id"],
            "claim_id": claim["claim_id"],
            "decision": "approved",
        },
    )
    assert wrong.status_code == 403

    ok = client.post(
        "/api/story/editorial-approval",
        headers={"X-MatchLens-Token": "producer-secret"},
        json={
            "match_id": "syn_default",
            "snapshot_id": story["snapshot_id"],
            "claim_id": claim["claim_id"],
            "decision": "approved",
            "note": "Reviewed.",
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["editorial_approver"] == "producer"
    assert body["editorial_role"] == "producer"
    assert body["editorial_history"][0]["approver"] == "producer"
    # Same decision is idempotent and does not invent a new version.
    again = client.post(
        "/api/story/editorial-approval",
        headers={"X-MatchLens-Token": "producer-secret"},
        json={
            "match_id": "syn_default",
            "snapshot_id": story["snapshot_id"],
            "claim_id": claim["claim_id"],
            "decision": "approved",
        },
    )
    assert again.status_code == 200
    assert again.json()["editorial_version"] == body["editorial_version"]


def test_editorial_rejected_gate_claim_cannot_be_approved():
    from matchlens.football import freeze

    snap = freeze(generate_match(), 720)
    registry = ClaimRegistry()
    record = registry.verify_and_register(snap, "syn_default", "recoveries_caused_shots", "H")
    assert record.gate_status == "rejected"
    with pytest.raises(ValueError, match="gate_not_approved"):
        registry.editorial_decision(
            "syn_default", snap.id, record.claim_id,
            approver="producer", role="producer", decision="approved",
        )


def test_claim_revision_history_is_append_only():
    from matchlens.football import freeze

    snap = freeze(generate_match(), 720)
    registry = ClaimRegistry()
    record = registry.verify_and_register(snap, "syn_default", "goal_sequence", "H")
    original = record.statement
    v1 = registry.apply_challenge_revision(
        record, outcome="maintained", rationale="checked", challenge_request_hash="h1"
    )
    v2 = registry.apply_challenge_revision(
        record, outcome="narrowed", rationale="window narrowed", challenge_request_hash="h2"
    )
    assert v1.version == 2 and v2.version == 3
    assert v2.parent_revision_id == v1.revision_id
    assert v2.status == "qualified"
    assert record.lifecycle_status == "qualified"
    assert not record.broadcastable
    history = registry.revision_history("syn_default", snap.id, record.claim_id)
    assert [r.version for r in history] == [1, 2, 3]
    assert history[0].statement == original
    assert history[0].status == "superseded"


def test_dataset_revision_hashes_content_not_file_metadata(tmp_path, monkeypatch):
    import matchlens.catalog as catalog_module

    source = Path(__file__).resolve().parents[1] / "matchlens" / "data" / "matches" / "sb_wc2022_final.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    data["metadata"]["match_id"] = "fixture_revision"
    target = tmp_path / "fixture_revision.json"
    target.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(catalog_module, "MATCHES_DIR", tmp_path)
    before = MatchCatalog.data_version("fixture_revision")
    stat = target.stat()
    data["events"][5]["location"][0] = 90.0 if data["events"][5]["location"][0] != 90.0 else 90.0
    target.write_text(json.dumps(data), encoding="utf-8")
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    after = MatchCatalog.data_version("fixture_revision")
    assert before != after


def test_story_as_of_does_not_leak_future_events(client):
    early = client.get("/api/matches/syn_default/story?as_of=100&mode=live").json()
    late = client.get("/api/matches/syn_default/story?as_of=720&mode=recap").json()
    assert early["as_of"] == 100 and early["mode"] == "live"
    assert late["as_of"] == 720 and late["mode"] == "recap"
    events = MatchCatalog.load_normalized_events("syn_default")
    state = reduce_match(events, 100, max_duration=720, is_synthetic=False, continuous_coverage=True)
    allowed = {e["id"] for e in state["events"]}
    for chapter in early["chapters"]:
        assert set(chapter["supporting_event_ids"]) <= allowed
    assert early["claims"] == [] or all(c["as_of"] <= 100 for c in early["claims"])
    assert late["gate_verified_claims_count"] >= early["gate_verified_claims_count"]


def test_metrics_registry_reuses_receipts_and_reports_unavailable_xg(client):
    definitions = client.get("/api/metrics").json()
    assert any(m["metric_id"] == "shots" for m in definitions["metrics"])
    shots = client.get("/api/metrics/shots?match_id=syn_default&at=540&team=H&window=current").json()
    assert shots["status"] == "ok"
    assert isinstance(shots["value"], int)
    xg = client.get("/api/metrics/xg?match_id=syn_default&at=540&team=H").json()
    assert xg["status"] == "not_available"
    assert xg["value"] is None


def test_investigation_returns_receipted_plan_without_persisting_claim(client):
    res = client.post("/api/investigate", json={
        "match_id": "syn_default",
        "at": 540,
        "team": "H",
        "focus_type": "moment",
        "question": "What produced the shots?",
    })
    assert res.status_code == 200, res.text
    plan = res.json()
    assert plan["agent_status"] == "not_run"
    assert plan["execution_mode"] == "deterministic_planner"
    assert plan["tool_receipts"]
    assert all(r["snapshot_id"] == plan["snapshot_id"] for r in plan["tool_receipts"])
    assert plan["gate_preview"]["persisted"] is False
    assert plan["not_inferable"]
    assert plan["as_of"] <= 540


def test_statsbomb_import_requires_explicit_identity_and_license(tmp_path):
    from matchlens.ingest import ImportError, import_match

    raw = [{
        "id": "e1", "index": 1, "period": 1, "minute": 0, "second": 1,
        "type": {"name": "Pass"}, "team": {"id": 779, "name": "Argentina"},
        "player": {"id": 1, "name": "A"}, "possession": 1,
        "location": [60.0, 40.0], "pass": {"end_location": [70.0, 40.0]},
    }]
    source = tmp_path / "raw.json"
    source.write_text(json.dumps(raw), encoding="utf-8")
    args = dict(
        source_path=source, match_id="fixture_full",
        data_dir=tmp_path / "matches", receipt_dir=tmp_path / "receipts",
        home_team="Argentina", away_team="France",
        home_provider_team_id="779", away_provider_team_id="771",
        competition="Test", season="2026", license_ref="Test license",
    )
    receipt = import_match(**args)
    assert receipt["event_count"] == 1
    assert receipt["coverage_level"] == "C1_PARTIAL"
    assert (tmp_path / "matches" / "fixture_full.json").exists()
    assert (tmp_path / "receipts" / "fixture_full.json").exists()
    with pytest.raises(ImportError, match="target_exists"):
        import_match(**args)
    args["license_ref"] = ""
    with pytest.raises(ImportError, match="license_required"):
        import_match(**{**args, "force": True})


def test_broadcast_requires_editorial_approval_and_producer_identity(client, monkeypatch):
    monkeypatch.setenv("MATCHLENS_PRODUCER_TOKEN", "producer-secret")
    story = client.get("/api/matches/syn_default/story?as_of=720&mode=recap").json()
    claim = next(c for c in story["claims"] if c["gate_status"] == "approved")
    headers = {"X-MatchLens-Token": "producer-secret"}

    anonymous = client.post("/api/broadcast/rundown", json={
        "match_id": "syn_default",
        "snapshot_id": story["snapshot_id"],
        "claim_ids": [claim["claim_id"]],
    })
    assert anonymous.status_code == 403

    before = client.post(
        "/api/broadcast/rundown",
        headers=headers,
        json={"match_id": "syn_default", "snapshot_id": story["snapshot_id"], "claim_ids": [claim["claim_id"]]},
    )
    assert before.status_code == 409

    approved = client.post(
        "/api/story/editorial-approval",
        headers=headers,
        json={
            "match_id": "syn_default",
            "snapshot_id": story["snapshot_id"],
            "claim_id": claim["claim_id"],
            "decision": "approved",
        },
    )
    assert approved.status_code == 200

    rundown = client.post(
        "/api/broadcast/rundown",
        headers=headers,
        json={"match_id": "syn_default", "snapshot_id": story["snapshot_id"], "claim_ids": [claim["claim_id"]]},
    )
    assert rundown.status_code == 200, rundown.text
    assert rundown.json()["items"][0]["claim_id"] == claim["claim_id"]

    exported = client.post(
        "/api/broadcast/export",
        headers=headers,
        json={"match_id": "syn_default", "snapshot_id": story["snapshot_id"], "export_format": "json"},
    )
    assert exported.status_code == 200, exported.text
    body = exported.json()
    assert body["export_format"] == "json"
    assert body["approved_by"] == ["producer"]
    assert claim["claim_id"] in body["claim_ids"]
