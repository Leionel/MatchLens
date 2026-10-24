"""Registry migration integrity.

A legacy ``claim-registry-v1`` payload must be migrated without ever
destroying the source file, and a corrupt payload must never be mistaken for
a set of approved claims.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from matchlens import registry as registry_module
from matchlens.registry import ClaimRegistry

MATCH_ID = "syn_default"
SNAPSHOT_ID = "snap-migration"


def _record_id(claim_id: str) -> str:
    """The canonical record id used by the v1 writer."""
    return f"{MATCH_ID}::{SNAPSHOT_ID}::{claim_id}"


APPROVED_RECORD_ID = _record_id("claim-goal-sequence-h")
DISPUTED_RECORD_ID = _record_id("claim-attack-threat-h")
V2_RECORD_ID = _record_id("claim-goal-sequence-h")


def _legacy_claim(record_id: str, claim_id: str, gate_status: str, statement: str) -> dict:
    """A claim exactly as the v1 writer stored it."""
    return {
        "record_id": record_id,
        "claim_id": claim_id,
        "match_id": MATCH_ID,
        "snapshot_id": SNAPSHOT_ID,
        "as_of": 600,
        "assertion": "goal_sequence",
        "subject_team": "H",
        "claim_level": 1,
        "statement": statement,
        "evidence_scope": {"event_ids": ["e-1", "e-2"], "metric_ids": ["goals"]},
        "evidence_hash": f"hash-{record_id}",
        "gate_version": "2.0",
        "gate_status": gate_status,
        "gate_violations": [],
        "source_run": "deterministic_gate",
        "agent_verified_at": 1700000000.0,
        "editorial_status": "pending",
        "editorial_approver": None,
        "editorial_note": None,
        "editorial_at": None,
        "editorial_role": None,
        "editorial_version": 0,
        "editorial_history": [],
        "dataset_revision": "rev-migration",
        "lifecycle_status": "current",
        "current_revision_id": None,
        "revision_count": 0,
    }


def _legacy_challenge() -> dict:
    return {
        "request_hash": "challenge-hash-1",
        "idempotency_key": "idem-1",
        "match_id": MATCH_ID,
        "snapshot_id": SNAPSHOT_ID,
        "claim_id": "claim-goal-sequence-h",
        "challenge_type": "evidence_review",
        "result": {"outcome": "maintained"},
        "created_at": 1700000001.0,
    }


def _legacy_payload() -> dict:
    """A v1 file: no ``revisions`` key and no ``supersessions`` key."""
    return {
        "version": "claim-registry-v1",
        "saved_at": 1700000000.0,
        "claims": [
            _legacy_claim(
                APPROVED_RECORD_ID, "claim-goal-sequence-h", "approved", "Approved legacy statement."
            ),
            _legacy_claim(
                DISPUTED_RECORD_ID, "claim-attack-threat-h", "disputed", "Disputed legacy statement."
            ),
        ],
        "challenges": [_legacy_challenge()],
    }


def _v2_revision(revision_id: str, version: int, parent: str | None) -> dict:
    return {
        "revision_id": revision_id,
        "claim_record_id": V2_RECORD_ID,
        "claim_id": "claim-goal-sequence-h",
        "match_id": MATCH_ID,
        "snapshot_id": SNAPSHOT_ID,
        "version": version,
        "parent_revision_id": parent,
        "status": "current",
        "outcome": "maintained",
        "statement": "Native v2 statement.",
        "evidence_scope": {"event_ids": ["e-9"], "metric_ids": ["goals"]},
        "evidence_hash": "hash-v2",
        "gate_status": "approved",
        "editorial_status": "pending",
        "dataset_revision": "rev-migration",
        "claim_level": 1,
        "assumptions": [],
        "counterevidence": [],
        "verification_method": "",
        "gate_violations": [],
        "review_result": {},
        "challenge_request_hash": None,
        "rationale": "",
        "created_by": "gate",
        "created_at": 1700000000.0 + version,
    }


def _v2_payload() -> dict:
    return {
        "version": "claim-registry-v2",
        "saved_at": 1700000004.0,
        "claims": [
            {
                "record_id": V2_RECORD_ID,
                "claim_id": "claim-goal-sequence-h",
                "match_id": MATCH_ID,
                "snapshot_id": SNAPSHOT_ID,
                "as_of": 600,
                "assertion": "goal_sequence",
                "subject_team": "H",
                "claim_level": 1,
                "statement": "Native v2 statement.",
                "evidence_scope": {"event_ids": ["e-9"], "metric_ids": ["goals"]},
                "evidence_hash": "hash-v2",
                "gate_version": "2.0",
                "gate_status": "approved",
                "gate_violations": [],
                "source_run": "deterministic_gate",
                "agent_verified_at": 1700000000.0,
                "editorial_status": "approved",
                "editorial_approver": "Editor A",
                "editorial_note": None,
                "editorial_at": 1700000002.0,
                "editorial_role": "producer",
                "editorial_version": 1,
                "editorial_history": [],
                "dataset_revision": "rev-migration",
                "lifecycle_status": "current",
                "current_revision_id": "rev-2",
                "revision_count": 2,
            }
        ],
        "challenges": [],
        "revisions": [_v2_revision("rev-1", 1, None), _v2_revision("rev-2", 2, "rev-1")],
        "supersessions": [
            {
                "event_id": "sup-1",
                "claim_record_id": V2_RECORD_ID,
                "from_revision_id": "rev-1",
                "to_revision_id": "rev-2",
                "reason": "checked",
                "created_by": "challenge",
                "created_at": 1700000003.0,
            }
        ],
    }


def _write(path: Path, payload: dict) -> bytes:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path.read_bytes()


def _backups(tmp_path: Path) -> list[Path]:
    return sorted(tmp_path.glob("claims.v1.bak-*.json"))


def _files(tmp_path: Path) -> list[str]:
    return sorted(p.name for p in tmp_path.iterdir())


# --------------------------------------------------------------------------- legacy
def test_legacy_v1_registry_is_backed_up_and_migrated_without_rewriting_the_source(tmp_path):
    path = tmp_path / "claims.json"
    original = _write(path, _legacy_payload())
    original_sha = hashlib.sha256(original).hexdigest()

    registry = ClaimRegistry(path)

    # (a) the source file is untouched by the load: same bytes, same digest.
    assert path.read_bytes() == original
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_sha
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == "claim-registry-v1"

    # (b) exactly one backup, byte-identical to the original source.
    backups = _backups(tmp_path)
    assert len(backups) == 1
    assert backups[0].read_bytes() == original
    assert hashlib.sha256(backups[0].read_bytes()).hexdigest() == original_sha
    assert registry.migration_backup_path == backups[0]
    assert registry.migrated is True
    assert registry.migrated_from_version == "claim-registry-v1"
    # The load wrote nothing else next to the registry file.
    assert _files(tmp_path) == sorted(["claims.json", backups[0].name])

    # (c) + (d) one derived revision per legacy claim, pointed at by the record.
    for legacy in _legacy_payload()["claims"]:
        record = registry.records[legacy["record_id"]]
        history = registry.revisions[record.record_id]
        assert len(history) == 1
        revision = history[0]
        assert revision.version == 1
        assert revision.parent_revision_id is None
        assert record.current_revision_id == revision.revision_id
        assert record.revision_count == 1
        assert revision.statement == legacy["statement"]
        assert revision.evidence_scope == legacy["evidence_scope"]
        assert revision.evidence_hash == legacy["evidence_hash"]

    # (e) no pointer-class validity reasons for the migrated records.
    for record in registry.records.values():
        validity = registry.claim_validity(record)
        assert "missing_revision_payload" not in validity["reasons"]
        assert "current_pointer_mismatch" not in validity["reasons"]


def test_migrated_legacy_claims_expose_v2_equivalent_read_semantics(tmp_path):
    path = tmp_path / "claims.json"
    _write(path, _legacy_payload())

    registry = ClaimRegistry(path)

    # `get` / `records_for` / `revision_history` / `supersessions_for` behave as
    # they do for a native v2 registry.
    approved = registry.get(MATCH_ID, SNAPSHOT_ID, "claim-goal-sequence-h")
    assert approved is not None
    assert approved.gate_status == "approved"
    assert len(registry.records_for(MATCH_ID, SNAPSHOT_ID)) == 2
    history = registry.revision_history(MATCH_ID, SNAPSHOT_ID, "claim-goal-sequence-h")
    assert [r.version for r in history] == [1]
    assert registry.supersessions_for(MATCH_ID, SNAPSHOT_ID, "claim-goal-sequence-h") == []

    # The approved legacy claim is publishable under exactly the v2 semantics.
    validity = registry.claim_validity(approved, dataset_revision="rev-migration")
    assert validity["valid"] is True
    assert validity["reasons"] == []
    assert approved.broadcastable is False  # editorial approval is still pending

    # The disputed legacy claim stays rejected, not silently approved.
    disputed = registry.get(MATCH_ID, SNAPSHOT_ID, "claim-attack-threat-h")
    assert disputed is not None
    assert disputed.gate_status == "disputed"
    assert disputed.lifecycle_status == "disputed"
    assert disputed.broadcastable is False
    disputed_validity = registry.claim_validity(disputed)
    assert disputed_validity["valid"] is False
    assert "gate_disputed" in disputed_validity["reasons"]
    assert "lifecycle_disputed" in disputed_validity["reasons"]
    assert "current_revision_gate_not_approved" in disputed_validity["reasons"]

    # Legacy challenges survive the migration.
    assert "challenge-hash-1" in registry.challenges
    assert registry.challenges["challenge-hash-1"].idempotency_key == "idem-1"


def test_repeated_migration_is_idempotent_and_does_not_duplicate_backups_or_revisions(tmp_path):
    path = tmp_path / "claims.json"
    original = _write(path, _legacy_payload())

    first = ClaimRegistry(path)
    assert len(_backups(tmp_path)) == 1
    first_ids = {rid: revs[0].revision_id for rid, revs in first.revisions.items()}

    second = ClaimRegistry(path)

    # No second backup, and the source file is still the untouched legacy file.
    assert len(_backups(tmp_path)) == 1
    assert path.read_bytes() == original
    # The revision set is not duplicated and the derived ids are stable.
    assert {rid: len(revs) for rid, revs in second.revisions.items()} == {
        rid: 1 for rid in first.revisions
    }
    assert {rid: revs[0].revision_id for rid, revs in second.revisions.items()} == first_ids
    for record in second.records.values():
        assert record.revision_count == 1


def test_legacy_file_with_real_revision_history_keeps_that_history(tmp_path):
    payload = _legacy_payload()
    legacy_revision = _v2_revision("rev-legacy-1", 1, None)
    legacy_revision["claim_record_id"] = APPROVED_RECORD_ID
    payload["revisions"] = [legacy_revision]

    path = tmp_path / "claims.json"
    _write(path, payload)

    registry = ClaimRegistry(path)

    # The recorded history is kept verbatim, not replaced by a derivation.
    kept = registry.revisions[APPROVED_RECORD_ID]
    assert len(kept) == 1
    assert kept[0].revision_id == "rev-legacy-1"
    assert kept[0].created_by == "gate"
    # A record whose revision payload is absent stays unresolved and invalid.
    assert not registry.revisions.get(DISPUTED_RECORD_ID)
    disputed = registry.records[DISPUTED_RECORD_ID]
    assert disputed.current_revision_id is None
    assert registry.claim_validity(disputed)["valid"] is False
    assert "missing_revision_payload" in registry.claim_validity(disputed)["reasons"]


def test_derived_revision_is_labelled_as_reconstruction_not_history(tmp_path):
    path = tmp_path / "claims.json"
    _write(path, _legacy_payload())

    registry = ClaimRegistry(path)
    revision = registry.revisions[APPROVED_RECORD_ID][0]

    assert revision.created_by == "legacy_migration"
    assert revision.review_result["derived_revision"] is True
    assert revision.review_result["derived_from"] == "claim-registry-v1"
    assert "not an independent historical review event" in revision.review_result["note"]
    assert "no historical revision payload existed" in revision.rationale


def test_migrated_registry_round_trips_to_v2_on_save(tmp_path):
    path = tmp_path / "claims.json"
    legacy = _legacy_payload()
    original = _write(path, legacy)

    registry = ClaimRegistry(path)
    registry._save()

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["version"] == "claim-registry-v2"
    # The claim set is neither extended nor reduced by the round trip.
    assert {c["record_id"] for c in saved["claims"]} == {
        c["record_id"] for c in legacy["claims"]
    }
    assert len(saved["claims"]) == 2
    assert len(saved["revisions"]) == 2
    for claim in saved["claims"]:
        assert claim["revision_count"] == 1
        assert claim["current_revision_id"]
    # The backup still holds the untouched legacy source.
    backups = _backups(tmp_path)
    assert len(backups) == 1
    assert backups[0].read_bytes() == original


# ---------------------------------------------------------------------------- v2
def test_native_v2_registry_is_loaded_verbatim_without_backup(tmp_path):
    path = tmp_path / "claims.json"
    original = _write(path, _v2_payload())

    registry = ClaimRegistry(path)

    assert _backups(tmp_path) == []
    assert _files(tmp_path) == ["claims.json"]
    assert path.read_bytes() == original
    assert registry.migrated is False
    assert registry.source_version == "claim-registry-v2"
    assert registry.load_errors == []
    record = registry.records[V2_RECORD_ID]
    assert [r.revision_id for r in registry.revisions[V2_RECORD_ID]] == ["rev-1", "rev-2"]
    assert record.current_revision_id == "rev-2"
    assert record.revision_count == 2
    assert len(registry.supersessions) == 1
    assert registry.claim_validity(record)["valid"] is True


# ------------------------------------------------------------------------ corrupt
def test_corrupt_registry_fails_closed_without_raising(tmp_path):
    path = tmp_path / "claims.json"
    path.write_text('{"version": "claim-registry-v2", "claims": [', encoding="utf-8")

    registry = ClaimRegistry(path)

    assert registry.records == {}
    assert registry.challenges == {}
    assert registry.revisions == {}
    assert registry.supersessions == []
    assert registry.load_errors
    assert not any(r.gate_status == "approved" for r in registry.records.values())
    # The corrupt file is left exactly as it was.
    assert path.read_text(encoding="utf-8") == '{"version": "claim-registry-v2", "claims": ['


def test_broken_revision_entry_is_skipped_and_never_becomes_the_current_revision(tmp_path):
    payload = _v2_payload()
    payload["revisions"].append({"revision_id": "rev-broken", "totally": "invalid"})
    path = tmp_path / "claims.json"
    _write(path, payload)

    registry = ClaimRegistry(path)

    assert registry.load_errors
    assert any("revision_entry_invalid" in err for err in registry.load_errors)
    history = registry.revisions[V2_RECORD_ID]
    assert [r.revision_id for r in history] == ["rev-1", "rev-2"]
    assert all(r.revision_id != "rev-broken" for r in history)
    record = registry.records[V2_RECORD_ID]
    assert record.current_revision_id == "rev-2"


def test_claim_with_only_a_corrupt_revision_is_not_publishable(tmp_path):
    payload = _v2_payload()
    payload["revisions"] = [{"revision_id": "rev-broken", "totally": "invalid"}]
    payload["claims"][0]["current_revision_id"] = "rev-broken"
    payload["claims"][0]["revision_count"] = 1
    path = tmp_path / "claims.json"
    _write(path, payload)

    registry = ClaimRegistry(path)

    record = registry.records[V2_RECORD_ID]
    assert registry.load_errors
    assert not registry.revisions.get(V2_RECORD_ID)
    # The unresolvable pointer is cleared, so the claim cannot be published.
    assert record.current_revision_id is None
    assert record.broadcastable is False
    validity = registry.claim_validity(record)
    assert validity["valid"] is False
    assert "missing_revision_payload" in validity["reasons"]


def test_backup_failure_never_overwrites_the_legacy_source(tmp_path, monkeypatch):
    path = tmp_path / "claims.json"
    original = _write(path, _legacy_payload())

    def _boom(*_args, **_kwargs):
        raise OSError("backup device unavailable")

    monkeypatch.setattr(registry_module.shutil, "copyfile", _boom)

    registry = ClaimRegistry(path)

    # The registry is not cleared and the failure is reported, not hidden.
    assert len(registry.records) == 2
    assert registry.load_errors
    assert any("legacy_backup_failed" in err for err in registry.load_errors)
    assert registry.migration_backup_path is None

    registry._save()

    # The legacy source survives; the migrated state went to a sidecar file.
    assert path.read_bytes() == original
    assert registry.persistence_errors
    sidecar = tmp_path / "claims.v2-unbacked.json"
    assert sidecar.exists()
    assert json.loads(sidecar.read_text(encoding="utf-8"))["version"] == "claim-registry-v2"


def test_missing_version_is_treated_as_legacy_and_backed_up(tmp_path):
    path = tmp_path / "claims.json"
    payload = _legacy_payload()
    payload.pop("version")
    original = _write(path, payload)

    registry = ClaimRegistry(path)

    assert registry.migrated is True
    assert registry.migrated_from_version == "(missing)"
    assert len(_backups(tmp_path)) == 1
    assert _backups(tmp_path)[0].read_bytes() == original
    assert len(registry.revisions[APPROVED_RECORD_ID]) == 1


def test_unknown_future_version_is_reported_but_still_backed_up(tmp_path):
    path = tmp_path / "claims.json"
    payload = _legacy_payload()
    payload["version"] = "claim-registry-v99"
    original = _write(path, payload)

    registry = ClaimRegistry(path)

    assert registry.migrated is True
    assert any("unknown_registry_version" in err for err in registry.load_errors)
    assert len(_backups(tmp_path)) == 1
    assert _backups(tmp_path)[0].read_bytes() == original
    assert len(registry.revisions[APPROVED_RECORD_ID]) == 1


def test_broken_claim_entry_is_skipped_and_reported_without_losing_the_rest(tmp_path):
    payload = _legacy_payload()
    payload["claims"].append({"record_id": "rec-broken", "claim_id": "claim-broken"})
    path = tmp_path / "claims.json"
    _write(path, payload)

    registry = ClaimRegistry(path)

    assert any("claim_entry_invalid" in err for err in registry.load_errors)
    assert "rec-broken" not in registry.records
    assert len(registry.records) == 2
    assert len(registry.revisions[APPROVED_RECORD_ID]) == 1
    assert registry.claim_validity(registry.records[APPROVED_RECORD_ID])["valid"] is True
