"""Fault-injection and deterministic tests; these do not call a live model."""
import asyncio
import json
import shutil
import time
from pathlib import Path
import pytest

from matchlens.football import freeze, generate_match
from matchlens.agents import AgentRunner, Run
from matchlens.main import Engine, Session


def test_goal_snapshot_never_reads_final_whistle_early(tmp_path):
    engine = Engine(tmp_path, None)
    s = Session("goal-boundary", "local", at=690)
    view = engine.view(s)
    assert view["active_moment"]["at"] == 690
    snap = s.snapshots[view["snapshot_id"]]
    assert snap.data["as_of"] == 690
    assert max(e["t"] for e in snap.data["events"]) <= view["at"]
    assert "match-winning" not in view["active_moment"]["summary"]
    engine.ledger.close()


def test_fast_replay_latches_prefix_safe_moments_once(tmp_path):
    engine = Engine(tmp_path, None)
    s = Session("fast-replay", "local", at=0)
    engine.view(s)
    s.at = 720
    view = engine.view(s)
    assert {m.get("assertion") for m in view["moments"]} >= {"possession_without_penetration", "recoveries_followed_by_shots", "goal_sequence"}
    for moment in view["moments"]:
        snap = freeze(engine.events, moment["at"])
        assert max(e["t"] for e in snap.data["events"]) <= moment["at"]
    assert engine.view(s)["moments"] == view["moments"]
    engine.ledger.close()


def test_known_failed_historical_card_cannot_reenter_recap(tmp_path):
    source = Path(__file__).resolve().parents[3] / "evidence/r0.1/runs/run-6a11dba6df6014fd.json"
    (tmp_path / "runs").mkdir()
    shutil.copyfile(source, tmp_path / "runs" / source.name)
    engine = Engine(tmp_path, None)
    view = engine.view(Session("history", "local", at=360, focus="A"))
    assert not engine.saved_runs and not view["history"]
    engine.ledger.close()


def _write_reusable_run(tmp_path: Path) -> tuple[str, object]:
    """Create a run receipt from the current reducer, without a live model."""
    from matchlens.contracts import ClaimDraft, VerifierDecision, publication_gate

    snap = freeze(generate_match(), 720)
    draft = ClaimDraft.model_validate({
        "snapshot_id": snap.id,
        "claims": [{
            "id": "claim-goal-sequence",
            "assertion": "goal_sequence",
            "primary": {
                "id": "primary",
                "scope": "match",
                "refs": ["H.goals.match"],
                "fan": "Harbor scored {{H.goals.match}} goal(s). Follow the recorded on-ball sequence.",
                "analyst": "The recorded goal receipt is {{H.goals.match}}. The chain is on-ball only.",
            },
        }],
    })
    review = VerifierDecision.model_validate({
        "snapshot_id": snap.id,
        "decisions": [{
            "claim_id": "claim-goal-sequence",
            "verdict": "publish",
            "selected_variant": "primary",
            "reason": "Typed assertion and frozen receipt references pass the publication gate.",
            "limitations": [],
        }],
    })
    audit = [
        {"type": t, "role": role, "snapshot_id": snap.id}
        for t in ("tool", "tool_receipt")
        for role in ("Analyst", "Verifier")
    ] + [{"type": "handoff", "snapshot_id": snap.id}]
    checked = publication_gate(draft, review, snap, audit)
    assert len(checked["accepted"]) == 1
    result = {
        "status": "completed",
        "origin": "test_fixture",
        "accepted": checked["accepted"],
        "rejected": checked["rejected"],
        "requests": 2,
        "model": "deterministic-fixture",
        "prompt_version": "test",
    }
    run_id = "run-third-pass-fixture"
    record = {
        "run_id": run_id,
        "snapshot_id": snap.id,
        "evidence": snap.data,
        "prompt_version": "test",
        "bound_epoch": 0,
        "current_epoch": 0,
        "draft": draft.model_dump(),
        "review": review.model_dump(),
        "result": result,
        "audit": audit,
        "requests": 2,
        "raw_outputs": [],
    }
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / f"{run_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return snap.id, snap


def test_real_goal_receipt_revalidates_without_relabeling_its_snapshot(tmp_path):
    snap_id, _snap = _write_reusable_run(tmp_path)
    engine = Engine(tmp_path, None)
    s = Session("real-history", "local", at=720, focus="C")
    view = engine.view(s)
    assert view["snapshot_id"] == snap_id
    assert len(view["result"]["accepted"]) == 1
    assert view["result"]["reused"]
    for card in view["history"]:
        assert card["historical"]
        assert s.snapshots[card["snapshot_id"]].id == card["snapshot_id"]
        assert "recorded on-ball events" in card["fan"]
    engine.ledger.close()


def test_old_semantics_snapshot_is_never_relabelled(tmp_path):
    """A pre-third-pass receipt must be rejected, not silently rehashed."""
    source = Path(__file__).resolve().parents[3] / "evidence/r0.2/runs/run-c-verify-a359468b.json"
    (tmp_path / "runs").mkdir()
    shutil.copyfile(source, tmp_path / "runs" / source.name)
    engine = Engine(tmp_path, None)
    view = engine.view(Session("stale-history", "local", at=720, focus="C"))
    assert not engine.saved_runs
    assert not view["history"]
    engine.ledger.close()


def test_actual_rejected_quantity_is_caught_before_handoff():
    source = Path(__file__).resolve().parents[3] / "evidence/r0.2/runs/run-c-verify-29254a79.json"
    record = json.loads(source.read_text())
    raw = next(item["text"] for item in record["raw_outputs"] if item["role"] == "Analyst")
    snap = freeze(generate_match(), 720)
    # Keep the recorded model prose, but bind it to the current snapshot ID so
    # the numeric-prose assertion is what actually fails.
    raw = raw.replace(record["snapshot_id"], snap.id)
    with pytest.raises(ValueError, match="unbound_spelled_number"):
        AgentRunner.validate_stage(raw, "Analyst", Run("offline-actual-draft", snap))


def test_automatic_workflow_does_not_pause_replay_or_repeat_a_candidate(tmp_path, monkeypatch):
    monkeypatch.setenv("MATCHLENS_AUTO_ANALYSE", "1")
    async def scenario():
        engine = Engine(tmp_path, "fault-injection-not-a-live-key")
        started, release = asyncio.Event(), asyncio.Event()
        calls = []
        async def fake_runner(run, progress):
            calls.append(run)
            await progress("analysing")
            started.set()
            await release.wait()
            return {"status": "completed", "origin": "fault_injection", "accepted": [], "rejected": []}
        engine.runner.analyse = fake_runner
        s = Session("automatic", "local", at=360, paused=False, anchor_at=360)
        engine.view(s)
        await started.wait()
        assert not s.paused
        engine.view(s)
        assert len(calls) == 1
        s.anchor_at = 370
        s.anchor_time = time.monotonic()
        assert engine.view(s)["at"] >= 370
        release.set()
        await s.task
        view = engine.view(s)
        assert not s.paused and view["result"]["as_of"] == 360
        assert len(calls) == 1
        record = json.loads((tmp_path / "runs" / f"{calls[0].id}.json").read_text())
        assert record["audit"][0]["source"] == "automatic"
        assert not engine.admissions
        engine.ledger.close()
    asyncio.run(scenario())


def test_insufficient_whole_workflow_allowance_starts_no_task(tmp_path):
    engine = Engine(tmp_path, "fault-injection-not-a-live-key")
    engine.ledger.max_requests = 5
    s = Session("no-runway", "local", at=360)
    snap = freeze(engine.events, 360)
    assert not engine.start_analysis(s, snap, "automatic")
    assert s.task is None and s.analyses == 0
    assert engine.ledger.summary()["requests_reserved"] == 0
    engine.ledger.close()


def test_cancel_before_first_task_step_releases_admission(tmp_path):
    async def scenario():
        engine = Engine(tmp_path, None)
        s = Session("cancel-before-start", "local", at=360)
        assert engine.start_analysis(s, freeze(engine.events, 360), "manual")
        s.invalidate()
        await asyncio.gather(s.task, return_exceptions=True)
        assert not engine.admissions and not s.cache
        assert engine.ledger.summary()["requests_reserved"] == 0
        engine.ledger.close()
    asyncio.run(scenario())
