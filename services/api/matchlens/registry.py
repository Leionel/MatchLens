"""Durable claim and challenge registry.

Approval is never accepted from a caller-supplied boolean. A record is
publishable only when this registry has executed a gate against a frozen
snapshot and stored the resulting verdict, evidence hash and source run.
Editorial approval is a separate, explicitly attributed decision.

Persistence format and legacy migration
---------------------------------------
The on-disk format is ``claim-registry-v2`` (claims + challenges + revisions +
supersessions). A legacy ``claim-registry-v1`` payload is migrated on load,
without ever destroying the source file:

1. The source file is copied **byte for byte** to a timestamped sibling backup
   (``<name>.v1.bak-<YYYYmmddTHHMMSSZ>.json``). An existing backup with
   identical content is reused, so repeated loads never multiply backups.
2. The legacy payload is mapped onto the v2 model in memory. A legacy claim
   without any revision history receives one *derived* revision that restates
   the gate verdict already stored on that claim. A derived revision is a
   reconstruction, not a historical fact: the legacy file never recorded a
   review event for that claim. It is flagged as such in
   ``ClaimRevision.review_result`` and ``ClaimRevision.rationale``.
3. The legacy file itself keeps its original bytes until an explicit
   ``_save()`` succeeds. If the backup could not be written, the original file
   is never overwritten: the migrated state is written to a sidecar file and
   the failure is recorded.

A corrupt payload never becomes an approved claim. Entries that fail
validation are skipped and reported through ``ClaimRegistry.load_errors``;
a payload that cannot be parsed at all leaves the registry empty rather than
inventing approvals.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .contracts import assertion_supported, evidence_summary, required_refs, team_label
from .football import Snapshot
from .gate import publication_gate_2_0

CLAIM_LEVELS = {
    "goal_sequence": 1,
    "possession_without_penetration": 2,
    "attacking_threat_increased": 2,
    "recoveries_followed_by_shots": 3,
    "recoveries_caused_shots": 4,
}

REGISTRY_VERSION = "claim-registry-v2"
LEGACY_REGISTRY_VERSIONS = ("claim-registry-v1",)
#: Label used for the sibling backup files written next to a legacy registry.
LEGACY_BACKUP_LABEL = "v1"
#: Suffix of the sidecar file used when the legacy source cannot be backed up.
UNBACKED_MIGRATION_SUFFIX = ".v2-unbacked.json"


class ClaimRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    claim_id: str
    match_id: str
    snapshot_id: str
    as_of: int
    assertion: str
    subject_team: Literal["H", "N"]
    claim_level: int
    statement: str
    evidence_scope: dict[str, Any]
    evidence_hash: str
    gate_version: str = "2.0"
    gate_status: Literal["approved", "disputed", "rejected"]
    gate_violations: list[str] = Field(default_factory=list)
    source_run: str = "deterministic_gate"
    agent_verified_at: float = Field(default_factory=time.time)
    editorial_status: Literal["pending", "approved", "rejected"] = "pending"
    editorial_approver: Optional[str] = None
    editorial_note: Optional[str] = None
    editorial_at: Optional[float] = None
    editorial_role: Optional[str] = None
    editorial_version: int = 0
    editorial_history: list[dict[str, Any]] = Field(default_factory=list)
    dataset_revision: Optional[str] = None
    lifecycle_status: Literal["current", "qualified", "disputed", "withdrawn", "superseded"] = "current"
    current_revision_id: Optional[str] = None
    revision_count: int = 0

    @property
    def broadcastable(self) -> bool:
        return (
            self.gate_status == "approved"
            and self.editorial_status == "approved"
            and self.lifecycle_status in ("current", "qualified")
            and self.current_revision_id is not None
        )


class ClaimRevision(BaseModel):
    """Immutable snapshot of a claim's conclusion state.

    Revisions are append-only. A revision never rewrites the original statement
    or evidence scope; later review creates a new revision and supersedes the
    previous `current` one.
    """
    model_config = ConfigDict(extra="forbid")

    revision_id: str
    claim_record_id: str
    claim_id: str
    match_id: str
    snapshot_id: str
    version: int
    parent_revision_id: Optional[str] = None
    status: Literal["current", "qualified", "disputed", "withdrawn", "superseded"]
    outcome: Literal["maintained", "narrowed", "withdrawn", "inconclusive", "rejected", "editorial"]
    statement: str
    evidence_scope: dict[str, Any]
    evidence_hash: str
    gate_status: str
    editorial_status: str
    dataset_revision: Optional[str] = None
    claim_level: int = 1
    assumptions: list[str] = Field(default_factory=list)
    counterevidence: list[str] = Field(default_factory=list)
    verification_method: str = ""
    gate_violations: list[str] = Field(default_factory=list)
    review_result: dict[str, Any] = Field(default_factory=dict)
    challenge_request_hash: Optional[str] = None
    rationale: str = ""
    created_by: str = "system"
    created_at: float = Field(default_factory=time.time)


class SupersessionEvent(BaseModel):
    """Immutable record that a later revision became current."""
    model_config = ConfigDict(extra="forbid")

    event_id: str
    claim_record_id: str
    from_revision_id: str
    to_revision_id: str
    reason: str
    created_by: str = "system"
    created_at: float = Field(default_factory=time.time)


class ChallengeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_hash: str
    idempotency_key: Optional[str] = None
    owner_id: Optional[str] = None
    match_id: str
    snapshot_id: str
    claim_id: str
    challenge_type: str
    result: dict[str, Any]
    created_at: float = Field(default_factory=time.time)


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


class ClaimRegistry:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else None
        self.records: dict[str, ClaimRecord] = {}
        self.challenges: dict[str, ChallengeRecord] = {}
        self.revisions: dict[str, list[ClaimRevision]] = {}
        self.supersessions: list[SupersessionEvent] = []
        #: Load/migration anomalies. Non-empty means the persisted state could
        #: not be taken at face value; it never means "approved".
        self.load_errors: list[str] = []
        #: Write-time anomalies (for example a blocked legacy overwrite).
        self.persistence_errors: list[str] = []
        #: Version string found in the source file, if any.
        self.source_version: Optional[str] = None
        #: True when the source payload was a legacy (non-v2) registry.
        self.migrated: bool = False
        #: Version string of the migrated source payload.
        self.migrated_from_version: Optional[str] = None
        #: Path of the byte-for-byte backup of the migrated source file.
        self.migration_backup_path: Optional[Path] = None
        #: When True the source file must not be overwritten (backup failed).
        self._persist_blocked: bool = False
        self._load()

    # ---------------------------------------------------------------- persistence
    def _load(self) -> None:
        """Load the registry, migrating a legacy payload without destroying it."""
        if not self.path or not self.path.exists():
            return
        try:
            raw_text = self.path.read_text(encoding="utf-8")
        except Exception as exc:
            self.load_errors.append(f"registry_unreadable: {exc}")
            self._reset_state()
            return
        try:
            data = json.loads(raw_text)
        except Exception as exc:
            # A corrupt registry is not silently replaced with approvals.
            self.load_errors.append(f"registry_unparsable_json: {exc}")
            self._reset_state()
            return
        if not isinstance(data, dict):
            self.load_errors.append("registry_payload_not_object")
            self._reset_state()
            return

        version = data.get("version")
        if version == REGISTRY_VERSION:
            self.source_version = REGISTRY_VERSION
            self._load_entries(data)
            self._reconcile_pointers()
            return

        self._load_legacy(data, version)

    def _reset_state(self) -> None:
        self.records = {}
        self.challenges = {}
        self.revisions = {}
        self.supersessions = []

    def _load_entries(self, data: dict[str, Any]) -> None:
        """Load every collection, skipping (and reporting) invalid entries."""
        for key, model in (
            ("claims", ClaimRecord),
            ("challenges", ChallengeRecord),
            ("revisions", ClaimRevision),
            ("supersessions", SupersessionEvent),
        ):
            try:
                entries = self._entries(data, key)
            except TypeError as exc:
                self.load_errors.append(f"{key}_container_invalid: {exc}")
                continue
            for raw in entries:
                try:
                    item = model.model_validate(raw)
                except Exception as exc:
                    self.load_errors.append(f"{key[:-1]}_entry_invalid: {exc}")
                    continue
                if key == "claims":
                    self.records[item.record_id] = item
                elif key == "challenges":
                    self.challenges[item.request_hash] = item
                elif key == "revisions":
                    self.revisions.setdefault(item.claim_record_id, []).append(item)
                else:
                    self.supersessions.append(item)

    def _entries(self, data: dict[str, Any], key: str) -> list[Any]:
        value = data.get(key)
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError(f"'{key}' must be a list, got {type(value).__name__}")
        return value

    def _reconcile_pointers(self) -> None:
        """Make the current-revision pointer agree with the loaded history.

        A pointer that cannot be resolved is cleared so that the affected
        record can never be treated as broadcastable; the anomaly is reported
        instead of being silently absorbed. A missing pointer with an intact
        history is completed from the latest revision, which is what
        ``claim_validity`` itself treats as the current one.
        """
        for record in self.records.values():
            history = self.revisions.get(record.record_id, [])
            if record.current_revision_id:
                known = {r.revision_id for r in history}
                if record.current_revision_id not in known:
                    self.load_errors.append(f"current_pointer_unresolved: {record.record_id}")
                    record.current_revision_id = None
                    continue
            elif history:
                record.current_revision_id = history[-1].revision_id
                self.load_errors.append(f"current_pointer_derived: {record.record_id}")
            if not history:
                self.load_errors.append(f"revision_payload_missing: {record.record_id}")
                continue
            if record.revision_count and record.revision_count != len(history):
                self.load_errors.append(f"revision_count_mismatch: {record.record_id}")

    def _load_legacy(self, data: dict[str, Any], version: Any) -> None:
        """Migrate a legacy registry payload in memory, never in place."""
        self.source_version = version if isinstance(version, str) else None
        self.migrated = True
        self.migrated_from_version = self.source_version or "(missing)"
        if version is not None and self.source_version not in LEGACY_REGISTRY_VERSIONS:
            self.load_errors.append(f"unknown_registry_version: {version!r}")

        # 1. Protect the source file before anything can overwrite it.
        backup = self._backup_legacy_source()
        if backup is None:
            # The legacy source cannot be protected, so it must not be
            # overwritten. The migrated state stays usable in memory.
            self._persist_blocked = True
        else:
            self.migration_backup_path = backup

        # 2. Load the legacy collections with the same fail-closed tolerance.
        self._load_entries(data)

        # 3. Revision history: keep what the file actually recorded, otherwise
        #    derive a first revision from the stored gate verdict.
        raw_revisions = data.get("revisions")
        has_revision_history = isinstance(raw_revisions, list) and len(raw_revisions) > 0
        if has_revision_history:
            self._reconcile_pointers()
            return
        self._derive_initial_revisions()
        self._reconcile_pointers()

    def _backup_legacy_source(self) -> Optional[Path]:
        """Copy the legacy source file to a timestamped sibling backup.

        The copy is byte-for-byte. An existing backup whose content already
        matches the source is reused, so loading the same legacy file twice
        never produces a second backup.
        """
        if not self.path:
            return None
        parent = self.path.parent
        stem = self.path.stem
        try:
            source_bytes = self.path.read_bytes()
        except Exception as exc:
            self.load_errors.append(f"legacy_source_unreadable: {exc}")
            return None
        try:
            existing = sorted(parent.glob(f"{stem}.{LEGACY_BACKUP_LABEL}.bak-*.json"))
        except Exception:
            existing = []
        for candidate in existing:
            try:
                if candidate.read_bytes() == source_bytes:
                    return candidate
            except Exception:
                continue
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = parent / f"{stem}.{LEGACY_BACKUP_LABEL}.bak-{stamp}.json"
        counter = 1
        while target.exists():
            target = parent / f"{stem}.{LEGACY_BACKUP_LABEL}.bak-{stamp}-{counter}.json"
            counter += 1
        try:
            shutil.copyfile(self.path, target)
        except Exception as exc:
            self.load_errors.append(f"legacy_backup_failed: {exc}")
            return None
        return target

    def _derive_initial_revisions(self) -> None:
        """Derive a first revision for legacy claims that have no history.

        The derived revision restates the gate verdict already stored on the
        record. It is a reconstruction of the legacy state, **not** a
        historical review event: the legacy file recorded no revision for it.
        """
        for record in self.records.values():
            if self.revisions.get(record.record_id):
                continue
            approved = record.gate_status == "approved"
            status = "current" if approved else "disputed"
            outcome = "maintained" if approved else "rejected"
            revision = ClaimRevision(
                revision_id=_canonical_hash({
                    "record_id": record.record_id,
                    "version": 1,
                    "evidence_hash": record.evidence_hash,
                    "statement": record.statement,
                    "scope": record.evidence_scope,
                    "status": status,
                    "outcome": outcome,
                    "source": "legacy_v1_derivation",
                })[:20],
                claim_record_id=record.record_id,
                claim_id=record.claim_id,
                match_id=record.match_id,
                snapshot_id=record.snapshot_id,
                version=1,
                parent_revision_id=None,
                status=status,
                outcome=outcome,
                statement=record.statement,
                evidence_scope=dict(record.evidence_scope),
                evidence_hash=record.evidence_hash,
                gate_status=record.gate_status,
                editorial_status=record.editorial_status,
                dataset_revision=record.dataset_revision,
                claim_level=record.claim_level,
                gate_violations=list(record.gate_violations),
                review_result={
                    "derived_revision": True,
                    "derived_from": self.migrated_from_version,
                    "note": (
                        "Derived by the legacy registry migration: this revision restates "
                        "the gate verdict already stored on the migrated record. It is not an "
                        "independent historical review event."
                    ),
                },
                rationale=(
                    "Derived initial revision migrated from a legacy "
                    f"{self.migrated_from_version} registry; no historical revision payload "
                    "existed for this claim."
                ),
                created_by="legacy_migration",
                created_at=record.agent_verified_at,
            )
            self.revisions.setdefault(record.record_id, []).append(revision)
            record.current_revision_id = revision.revision_id
            record.revision_count = 1
            if record.lifecycle_status == "current":
                record.lifecycle_status = status  # type: ignore[assignment]
            else:
                # A legacy lifecycle decision (withdrawn, qualified, ...) is a
                # recorded fact and is never overwritten by the derivation.
                self.load_errors.append(
                    f"legacy_lifecycle_preserved: {record.record_id} keeps "
                    f"lifecycle_status={record.lifecycle_status}"
                )

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": REGISTRY_VERSION,
            "saved_at": time.time(),
            "claims": [r.model_dump() for r in self.records.values()],
            "challenges": [r.model_dump() for r in self.challenges.values()],
            "revisions": [r.model_dump() for rs in self.revisions.values() for r in rs],
            "supersessions": [e.model_dump() for e in self.supersessions],
        }
        target = self.path
        if self._persist_blocked:
            # The legacy source could not be backed up, so it must not be
            # overwritten. Persist beside it and report the blocked write.
            target = self.path.with_name(self.path.stem + UNBACKED_MIGRATION_SUFFIX)
            self.persistence_errors.append(
                f"legacy_source_not_overwritten: {self.path.name}; migrated state written to "
                f"{target.name}"
            )
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        # Windows can hold the destination with a stale handle for a moment
        # after the previous write (indexer/AV), so the atomic replace retries
        # briefly instead of failing a persisted state machine mid-write.
        for attempt in range(6):
            try:
                tmp.replace(target)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.02 * (attempt + 1))

    # ------------------------------------------------------------------- registry
    @staticmethod
    def record_id(match_id: str, snapshot_id: str, claim_id: str) -> str:
        return f"{match_id}::{snapshot_id}::{claim_id}"

    def get(self, match_id: str, snapshot_id: str, claim_id: str) -> Optional[ClaimRecord]:
        return self.records.get(self.record_id(match_id, snapshot_id, claim_id))

    def records_for(self, match_id: str, snapshot_id: str) -> list[ClaimRecord]:
        return [
            r for r in self.records.values()
            if r.match_id == match_id and r.snapshot_id == snapshot_id
        ]

    def revision_history(self, match_id: str, snapshot_id: str, claim_id: str) -> list[ClaimRevision]:
        record = self.get(match_id, snapshot_id, claim_id)
        return list(self.revisions.get(record.record_id, [])) if record else []

    def supersessions_for(self, match_id: str, snapshot_id: str, claim_id: str) -> list[SupersessionEvent]:
        record = self.get(match_id, snapshot_id, claim_id)
        if record is None:
            return []
        return [e for e in self.supersessions if e.claim_record_id == record.record_id]

    def claim_validity(
        self,
        record: ClaimRecord,
        *,
        snapshot: Snapshot | None = None,
        dataset_revision: str | None = None,
        require_editorial: bool = False,
    ) -> dict[str, Any]:
        """Read-time publication validity for Story, Rundown and Export."""
        reasons: list[str] = []
        if record.gate_status != "approved":
            reasons.append(f"gate_{record.gate_status}")
        if record.lifecycle_status not in ("current", "qualified"):
            reasons.append(f"lifecycle_{record.lifecycle_status}")
        if record.editorial_status == "rejected":
            reasons.append("editorial_rejected")
        if require_editorial and record.editorial_status != "approved":
            reasons.append("editorial_not_approved")

        expected_revision = dataset_revision
        if expected_revision is None and snapshot is not None:
            expected_revision = snapshot.data.get("dataset_revision") or snapshot.data.get("data_version")
        if record.dataset_revision and expected_revision and record.dataset_revision != expected_revision:
            reasons.append("dataset_revision_mismatch")

        history = self.revisions.get(record.record_id, [])
        current = history[-1] if history else None
        if current is None:
            reasons.append("missing_revision_payload")
        elif record.current_revision_id != current.revision_id:
            reasons.append("current_pointer_mismatch")
        if current is not None and current.gate_status != "approved":
            reasons.append("current_revision_gate_not_approved")
        if current is not None and current.evidence_hash != record.evidence_hash:
            reasons.append("revision_evidence_hash_mismatch")

        return {
            "valid": not reasons,
            "reasons": reasons,
            "claim_id": record.claim_id,
            "current_revision_id": record.current_revision_id,
            "statement": record.statement,
            "evidence_hash": record.evidence_hash,
            "dataset_revision": record.dataset_revision,
            "lifecycle_status": record.lifecycle_status,
            "gate_status": record.gate_status,
            "editorial_status": record.editorial_status,
        }

    def _append_revision(
        self,
        record: ClaimRecord,
        *,
        status: Literal["current", "qualified", "disputed", "withdrawn", "superseded"],
        outcome: Literal["maintained", "narrowed", "withdrawn", "inconclusive", "rejected", "editorial"],
        rationale: str = "",
        created_by: str = "system",
        challenge_request_hash: str | None = None,
        statement: str | None = None,
        evidence_scope: dict[str, Any] | None = None,
        evidence_hash: str | None = None,
        gate_status: str | None = None,
        gate_violations: list[str] | None = None,
        claim_level: int | None = None,
        assumptions: list[str] | None = None,
        counterevidence: list[str] | None = None,
        verification_method: str | None = None,
        review_result: dict[str, Any] | None = None,
        as_of: int | None = None,
    ) -> ClaimRevision:
        history = self.revisions.setdefault(record.record_id, [])
        previous = history[-1] if history else None
        version = len(history) + 1
        next_statement = record.statement if statement is None else statement
        next_scope = dict(record.evidence_scope if evidence_scope is None else evidence_scope)
        next_hash = record.evidence_hash if evidence_hash is None else evidence_hash
        next_gate = record.gate_status if gate_status is None else gate_status
        if next_gate not in ("approved", "disputed", "rejected"):
            raise ValueError("invalid_gate_status")
        revision = ClaimRevision(
            revision_id=_canonical_hash({
                "record_id": record.record_id,
                "version": version,
                "evidence_hash": next_hash,
                "statement": next_statement,
                "scope": next_scope,
                "status": status,
                "outcome": outcome,
            })[:20],
            claim_record_id=record.record_id,
            claim_id=record.claim_id,
            match_id=record.match_id,
            snapshot_id=record.snapshot_id,
            version=version,
            parent_revision_id=previous.revision_id if previous else None,
            status=status,
            outcome=outcome,
            statement=next_statement,
            evidence_scope=next_scope,
            evidence_hash=next_hash,
            gate_status=next_gate,
            gate_violations=list(gate_violations or []),
            editorial_status=record.editorial_status,
            dataset_revision=record.dataset_revision,
            claim_level=record.claim_level if claim_level is None else claim_level,
            assumptions=list(record.evidence_scope.get("assumptions", []) if assumptions is None else assumptions),
            counterevidence=list(counterevidence or []),
            verification_method=verification_method or "",
            review_result=dict(review_result or {}),
            challenge_request_hash=challenge_request_hash,
            rationale=rationale,
            created_by=created_by,
        )
        history.append(revision)
        if previous is not None:
            self.supersessions.append(SupersessionEvent(
                event_id=_canonical_hash({
                    "from": previous.revision_id,
                    "to": revision.revision_id,
                    "reason": rationale,
                })[:20],
                claim_record_id=record.record_id,
                from_revision_id=previous.revision_id,
                to_revision_id=revision.revision_id,
                reason=rationale,
                created_by=created_by,
            ))
        record.statement = next_statement
        record.evidence_scope = next_scope
        record.evidence_hash = next_hash
        record.gate_status = next_gate  # type: ignore[assignment]
        record.gate_violations = list(gate_violations) if gate_violations is not None else record.gate_violations
        if claim_level is not None:
            record.claim_level = claim_level
        if as_of is not None:
            record.as_of = as_of
        record.current_revision_id = revision.revision_id
        record.revision_count = version
        record.lifecycle_status = status
        return revision

    def apply_challenge_revision(
        self,
        record: ClaimRecord,
        *,
        outcome: str,
        rationale: str,
        challenge_request_hash: str,
        actor: str = "challenge",
        revised_card: dict[str, Any] | None = None,
        gate_status: str | None = None,
        gate_violations: list[str] | None = None,
    ) -> ClaimRevision:
        """Append a new revision without rewriting any prior payload.

        A narrowed claim must supply a new statement/evidence scope. If its
        re-gate is not approved, it is recorded as disputed rather than
        qualified, so the old statement cannot be quietly republished.
        """
        status_by_outcome = {
            "maintained": "current",
            "narrowed": "qualified",
            "withdrawn": "withdrawn",
            "inconclusive": "disputed",
            "rejected": "disputed",
        }
        if outcome not in status_by_outcome:
            raise ValueError("invalid_revision_outcome")
        status = status_by_outcome[outcome]
        statement: str | None = None
        scope: dict[str, Any] | None = None
        evidence_hash: str | None = None
        claim_level: int | None = None
        assumptions: list[str] | None = None
        counterevidence: list[str] | None = None
        verification_method: str | None = None
        review_result: dict[str, Any] = {
            "outcome": outcome,
            "rationale": rationale,
            "challenge_request_hash": challenge_request_hash,
        }

        if outcome == "narrowed":
            if not revised_card:
                raise ValueError("narrowed_requires_revised_statement")
            statement = str(revised_card.get("text") or revised_card.get("analyst") or "").strip()
            if not statement:
                raise ValueError("narrowed_requires_statement_text")
            if statement == record.statement:
                raise ValueError("narrowed_statement_must_change")
            raw_scope = revised_card.get("evidence_scope") or {
                "event_ids": revised_card.get("event_ids", []),
                "metric_ids": revised_card.get("metric_ids", []),
            }
            scope = dict(raw_scope)
            if not scope.get("event_ids") and not scope.get("metric_ids"):
                raise ValueError("narrowed_requires_evidence_scope")
            evidence_hash = str(revised_card.get("evidence_hash") or _canonical_hash({
                "snapshot_id": record.snapshot_id,
                "claim_id": record.claim_id,
                "statement": statement,
                "scope": scope,
            }))
            claim_level = int(revised_card.get("claim_level", record.claim_level))
            assumptions = list(revised_card.get("assumptions", []))
            counterevidence = list(revised_card.get("counterevidence", []))
            verification_method = str(revised_card.get("verification_method", ""))
            if gate_status != "approved":
                status = "disputed"
                review_result["gate_rejected"] = True
                gate_violations = list(gate_violations or ["Narrowed statement did not pass the publication gate."])
        elif outcome == "withdrawn":
            statement = f"Withdrawn. Original statement: {record.statement} Reason: {rationale}"
            scope = dict(record.evidence_scope)
            evidence_hash = _canonical_hash({
                "snapshot_id": record.snapshot_id,
                "claim_id": record.claim_id,
                "withdrawal": rationale,
                "previous_evidence_hash": record.evidence_hash,
            })
        elif outcome == "maintained":
            statement = record.statement
            scope = dict(record.evidence_scope)
            evidence_hash = record.evidence_hash
        else:
            statement = f"{outcome.capitalize()} revision: {rationale}"
            scope = dict(record.evidence_scope)
            evidence_hash = _canonical_hash({
                "snapshot_id": record.snapshot_id,
                "claim_id": record.claim_id,
                "outcome": outcome,
                "rationale": rationale,
                "previous_evidence_hash": record.evidence_hash,
            })

        if outcome != "maintained":
            record.editorial_status = "pending"
            record.editorial_note = "Editorial approval reset by a later challenge revision."
            record.editorial_at = None
            record.editorial_approver = None
            record.editorial_role = None

        revision = self._append_revision(
            record,
            status=status,  # type: ignore[arg-type]
            outcome=outcome,  # type: ignore[arg-type]
            rationale=rationale,
            created_by=actor,
            challenge_request_hash=challenge_request_hash,
            statement=statement,
            evidence_scope=scope,
            evidence_hash=evidence_hash,
            gate_status=(
                (gate_status if gate_status in ("approved", "disputed", "rejected") else "disputed")
                if outcome == "narrowed"
                else ("rejected" if outcome == "rejected" else record.gate_status)
            ),
            gate_violations=gate_violations,
            claim_level=claim_level,
            assumptions=assumptions,
            counterevidence=counterevidence,
            verification_method=verification_method,
            review_result=review_result,
        )
        self._save()
        return revision

    def verify_and_register(
        self,
        snapshot: Snapshot,
        match_id: str,
        assertion: str,
        subject_team: Literal["H", "N"] = "H",
        *,
        source_run: str = "deterministic_gate",
    ) -> ClaimRecord:
        """Execute the real gate and persist its verdict for this snapshot."""
        team = "N" if subject_team == "N" else "H"
        claim_id = f"claim-{assertion.replace('_', '-')}-{team.lower()}"
        receipts = snapshot.data.get("receipts", {})
        refs = sorted(required_refs(assertion, team))
        missing = [ref for ref in refs if ref not in receipts]
        event_ids: list[str] = []
        for ref in refs:
            event_ids.extend(receipts.get(ref, {}).get("event_ids", []))
        event_ids = sorted(set(event_ids))
        evidence_hash = _canonical_hash({
            "snapshot_id": snapshot.id,
            "claim_id": claim_id,
            "refs": refs,
            "events": event_ids,
            "receipt_values": {ref: receipts.get(ref, {}).get("value") for ref in refs},
        })
        supported = not missing and assertion_supported(assertion, snapshot, team)
        fan, analyst = (
            evidence_summary(assertion, snapshot, team) if supported
            else ("Not published.", "Not published: required evidence is absent or unsupported.")
        )
        claim = {
            "claim_id": claim_id,
            "claim_level": CLAIM_LEVELS.get(assertion, 1),
            "text": analyst,
            "evidence_scope": {"event_ids": event_ids, "metric_ids": refs},
            "assumptions": [
                "Coordinates and clock are those of the frozen snapshot.",
                "Controlled possession excludes unobserved intervals.",
            ],
            "counterevidence": [],
            "verification_method": "Gate 2.0 deterministic receipt audit",
            "metric_versions": {"oaai": "1.0.0"},
        }
        verdict = publication_gate_2_0(
            claim,
            snapshot.data.get("events", []),
            catalog_metric_ids=set(receipts),
        )
        if missing:
            verdict.rule_violations.extend(f"Missing receipt reference '{ref}'." for ref in missing)
            verdict.status = "rejected"
            verdict.is_valid = False
        if verdict.status == "approved" and not supported:
            verdict.status = "rejected"
            verdict.is_valid = False
            verdict.rule_violations.append("Core assertion is not supported by the frozen receipts.")
        record = ClaimRecord(
            record_id=self.record_id(match_id, snapshot.id, claim_id),
            claim_id=claim_id,
            match_id=match_id,
            snapshot_id=snapshot.id,
            as_of=int(snapshot.data.get("as_of", 0)),
            assertion=assertion,
            subject_team=team,
            claim_level=CLAIM_LEVELS.get(assertion, 1),
            statement=analyst,
            evidence_scope={
                "event_ids": event_ids,
                "metric_ids": refs,
                "workspace": snapshot.data.get("coverage"),
                "team_label": team_label(snapshot, team),
            },
            evidence_hash=evidence_hash,
            gate_status=verdict.status,
            gate_violations=list(verdict.rule_violations),
            source_run=source_run,
            dataset_revision=snapshot.data.get("dataset_revision") or snapshot.data.get("data_version"),
        )
        existing = self.records.get(record.record_id)
        if (
            existing
            and existing.evidence_hash == record.evidence_hash
            and existing.gate_status == record.gate_status
        ):
            # Re-running the gate on identical evidence must not erase an
            # editorial decision already recorded against that evidence.
            return existing
        self.records[record.record_id] = record
        self._append_revision(
            record,
            status="current" if record.gate_status == "approved" else "disputed",
            outcome="maintained" if record.gate_status == "approved" else "rejected",
            rationale=f"Gate {record.gate_version}: {record.gate_status}",
            created_by="gate",
        )
        self._save()
        return record

    def register_verified_claim(
        self,
        match_id: str,
        snapshot_id: str,
        claim: dict[str, Any],
        *,
        source_run: str,
        gate_status: str,
        gate_violations: list[str] | None = None,
        gate_version: str = "publication_gate",
        dataset_revision: str | None = None,
    ) -> ClaimRecord:
        """Persist a claim that already passed the online publication gate."""
        refs = list(claim.get("refs") or claim.get("evidence_scope", {}).get("metric_ids", []))
        event_ids = list(claim.get("evidence_scope", {}).get("event_ids", []))
        evidence_hash = _canonical_hash({
            "snapshot_id": snapshot_id,
            "claim_id": claim.get("claim_id"),
            "refs": sorted(refs),
            "events": sorted(event_ids),
        })
        record = ClaimRecord(
            record_id=self.record_id(match_id, snapshot_id, str(claim.get("claim_id"))),
            claim_id=str(claim.get("claim_id")),
            match_id=match_id,
            snapshot_id=snapshot_id,
            as_of=int(claim.get("as_of", 0)),
            assertion=str(claim.get("assertion", "unknown")),
            subject_team="N" if str(claim.get("claim_id", "")).endswith("-n") else "H",
            claim_level=int(claim.get("claim_level", 1)),
            statement=str(claim.get("analyst", "")),
            evidence_scope={
                "event_ids": event_ids,
                "metric_ids": refs,
                "snapshot_as_of": claim.get("as_of"),
            },
            evidence_hash=evidence_hash,
            gate_version=gate_version,
            gate_status="approved" if gate_status == "approved" else "rejected",
            gate_violations=gate_violations or [],
            source_run=source_run,
            dataset_revision=dataset_revision,
        )
        existing = self.records.get(record.record_id)
        if existing and existing.evidence_hash == record.evidence_hash:
            return existing
        self.records[record.record_id] = record
        self._append_revision(
            record,
            status="current" if record.gate_status == "approved" else "disputed",
            outcome="maintained" if record.gate_status == "approved" else "rejected",
            rationale=f"Online gate {record.gate_version}: {record.gate_status}",
            created_by="online_gate",
        )
        self._save()
        return record

    def editorial_decision(
        self,
        match_id: str,
        snapshot_id: str,
        claim_id: str,
        *,
        approver: str,
        role: str = "producer",
        decision: Literal["approved", "rejected"] = "approved",
        note: str | None = None,
    ) -> ClaimRecord:
        record = self.get(match_id, snapshot_id, claim_id)
        if record is None:
            raise KeyError("claim_not_registered")
        if record.gate_status != "approved":
            raise ValueError("gate_not_approved")
        if record.lifecycle_status not in ("current", "qualified"):
            raise ValueError("claim_not_current")
        if role not in ("producer", "admin", "local-producer"):
            raise ValueError("editorial_role_required")
        if not approver.strip() or approver.strip() == "anonymous":
            raise ValueError("approver_required")
        if record.editorial_status == decision:
            return record
        previous = record.editorial_status
        record.editorial_status = decision
        record.editorial_approver = approver.strip()
        record.editorial_role = role
        record.editorial_note = note
        record.editorial_at = time.time()
        record.editorial_version += 1
        record.editorial_history.append({
            "version": record.editorial_version,
            "decision": decision,
            "previous_status": previous,
            "approver": record.editorial_approver,
            "role": role,
            "note": note,
            "at": record.editorial_at,
            "dataset_revision": record.dataset_revision,
        })
        self._append_revision(
            record,
            status=record.lifecycle_status,
            outcome="editorial",
            rationale=f"Editorial {decision} by {record.editorial_approver} ({role})",
            created_by=record.editorial_approver,
        )
        self._save()
        return record

    def editorial_history(self, match_id: str, snapshot_id: str, claim_id: str) -> list[dict[str, Any]]:
        record = self.get(match_id, snapshot_id, claim_id)
        return list(record.editorial_history) if record else []

    # ------------------------------------------------------------------ challenges
    def remember_challenge(
        self,
        *,
        request_payload: dict[str, Any],
        idempotency_key: str | None,
        owner_id: str | None = None,
        match_id: str,
        snapshot_id: str,
        claim_id: str,
        challenge_type: str,
        result: dict[str, Any],
    ) -> ChallengeRecord:
        request_hash = _canonical_hash(request_payload)
        record = ChallengeRecord(
            request_hash=request_hash,
            idempotency_key=idempotency_key,
            owner_id=owner_id,
            match_id=match_id,
            snapshot_id=snapshot_id,
            claim_id=claim_id,
            challenge_type=challenge_type,
            result=result,
        )
        self.challenges[request_hash] = record
        self._save()
        return record

    def find_challenge(self, request_payload: dict[str, Any]) -> Optional[ChallengeRecord]:
        return self.challenges.get(_canonical_hash(request_payload))

    def find_idempotency_key(
        self,
        key: str,
        *,
        owner_id: str | None = None,
        match_id: str | None = None,
    ) -> Optional[ChallengeRecord]:
        for record in self.challenges.values():
            if record.idempotency_key != key:
                continue
            if owner_id is not None and record.owner_id not in (None, owner_id):
                continue
            if match_id is not None and record.match_id != match_id:
                continue
            return record
        return None
