"""Broadcast rundown store, projections and export manifest.

Only registry claims that are gate-approved, editorially approved and on a
current/qualified lifecycle revision can enter a rundown or export. Reading a
rundown revalidates every item against the current registry and dataset revision.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .registry import ClaimRecord


class RundownItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order: int
    claim_id: str
    revision_id: str | None = None
    snapshot_id: str
    statement: str
    evidence_hash: str
    dataset_revision: str | None = None
    claim_level: int
    gate_status: str = "approved"


class Rundown(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_id: str
    snapshot_id: str
    dataset_revision: str | None = None
    as_of: int | None = None
    items: list[RundownItem] = Field(default_factory=list)
    updated_at: float = Field(default_factory=time.time)
    updated_by: str = "system"


class RundownValidationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order: int
    claim_id: str
    revision_id: str | None
    valid: bool
    reasons: list[str] = Field(default_factory=list)
    statement: str
    evidence_hash: str
    dataset_revision: str | None = None


class RundownValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valid: bool
    items: list[RundownValidationItem]
    stale_items: list[str] = Field(default_factory=list)
    dataset_revision: str | None = None
    checked_at: float = Field(default_factory=time.time)


class ExportManifestItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str
    revision_id: str | None
    statement: str
    evidence_hash: str
    dataset_revision: str | None = None
    gate_status: str
    editorial_status: str
    editorial_approver: str | None = None
    editorial_at: float | None = None
    valid: bool
    reasons: list[str] = Field(default_factory=list)


class ExportManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest_id: str
    match_id: str
    snapshot_id: str
    dataset_revision: str | None = None
    generated_at: float = Field(default_factory=time.time)
    generated_by: str
    valid: bool
    items: list[ExportManifestItem] = Field(default_factory=list)
    stale_items: list[str] = Field(default_factory=list)
    package_sha256: str | None = None


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def public_claim_projection(record: ClaimRecord) -> dict[str, Any]:
    return {
        "claim_id": record.claim_id,
        "assertion": record.assertion,
        "statement": record.statement,
        "claim_level": record.claim_level,
        "gate_status": record.gate_status,
        "gate_version": record.gate_version,
        "lifecycle_status": record.lifecycle_status,
        "evidence_hash": record.evidence_hash,
        "dataset_revision": record.dataset_revision,
        "as_of": record.as_of,
        "published": record.broadcastable,
    }


def producer_claim_projection(record: ClaimRecord) -> dict[str, Any]:
    return {
        **public_claim_projection(record),
        "source_run": record.source_run,
        "gate_violations": list(record.gate_violations),
        "current_revision_id": record.current_revision_id,
        "revision_count": record.revision_count,
        "editorial_status": record.editorial_status,
        "editorial_approver": record.editorial_approver,
        "editorial_role": record.editorial_role,
        "editorial_note": record.editorial_note,
        "editorial_at": record.editorial_at,
        "editorial_version": record.editorial_version,
        "editorial_history": list(record.editorial_history),
    }


class BroadcastStore:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else None
        self.rundowns: dict[str, Rundown] = {}
        self._load()

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for raw in data.get("rundowns", []):
                rundown = Rundown.model_validate(raw)
                self.rundowns[f"{rundown.match_id}:{rundown.snapshot_id}"] = rundown
        except Exception:
            self.rundowns = {}

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": "rundown-v2", "rundowns": [r.model_dump() for r in self.rundowns.values()]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def build(
        self,
        *,
        match_id: str,
        snapshot_id: str,
        claims: list[ClaimRecord],
        claim_ids: list[str],
        dataset_revision: str | None,
        actor: str,
    ) -> Rundown:
        by_id = {r.claim_id: r for r in claims}
        ordered = []
        seen = set()
        for claim_id in claim_ids:
            if claim_id in seen:
                raise ValueError("duplicate_claim_in_rundown")
            seen.add(claim_id)
            record = by_id.get(claim_id)
            if record is None:
                raise ValueError(f"claim_not_registered:{claim_id}")
            if record.snapshot_id != snapshot_id or record.match_id != match_id:
                raise ValueError(f"claim_scope_mismatch:{claim_id}")
            if record.dataset_revision and dataset_revision and record.dataset_revision != dataset_revision:
                raise ValueError(f"claim_dataset_mismatch:{claim_id}")
            if not record.broadcastable:
                raise ValueError(f"claim_not_broadcastable:{claim_id}")
            if not record.current_revision_id:
                raise ValueError(f"claim_missing_current_revision:{claim_id}")
            ordered.append(RundownItem(
                order=len(ordered) + 1,
                claim_id=record.claim_id,
                revision_id=record.current_revision_id,
                snapshot_id=record.snapshot_id,
                statement=record.statement,
                evidence_hash=record.evidence_hash,
                dataset_revision=record.dataset_revision or dataset_revision,
                claim_level=record.claim_level,
                gate_status=record.gate_status,
            ))
        if not ordered:
            raise ValueError("empty_rundown")
        rundown = Rundown(
            match_id=match_id,
            snapshot_id=snapshot_id,
            dataset_revision=dataset_revision,
            as_of=claims[0].as_of if claims else None,
            items=ordered,
            updated_by=actor,
        )
        self.rundowns[f"{match_id}:{snapshot_id}"] = rundown
        self._save()
        return rundown

    def get(self, match_id: str, snapshot_id: str) -> Rundown | None:
        return self.rundowns.get(f"{match_id}:{snapshot_id}")

    def validate(
        self,
        rundown: Rundown,
        *,
        claims: list[ClaimRecord],
        dataset_revision: str | None,
        require_editorial: bool = True,
    ) -> RundownValidation:
        by_id = {r.claim_id: r for r in claims}
        items: list[RundownValidationItem] = []
        stale: list[str] = []
        for item in rundown.items:
            record = by_id.get(item.claim_id)
            reasons: list[str] = []
            if record is None:
                reasons.append("claim_not_registered")
            else:
                check = self._validity(record, dataset_revision, require_editorial)
                reasons.extend(check["reasons"])
                if record.current_revision_id != item.revision_id:
                    reasons.append("rundown_revision_mismatch")
                if record.statement != item.statement:
                    reasons.append("rundown_statement_changed")
                if record.evidence_hash != item.evidence_hash:
                    reasons.append("rundown_evidence_changed")
            valid = not reasons
            if not valid:
                stale.append(item.claim_id)
            items.append(RundownValidationItem(
                order=item.order,
                claim_id=item.claim_id,
                revision_id=item.revision_id,
                valid=valid,
                reasons=reasons,
                statement=record.statement if record else item.statement,
                evidence_hash=record.evidence_hash if record else item.evidence_hash,
                dataset_revision=record.dataset_revision if record else item.dataset_revision,
            ))
        return RundownValidation(
            valid=bool(items) and not stale,
            items=items,
            stale_items=stale,
            dataset_revision=dataset_revision,
        )

    @staticmethod
    def _validity(record: ClaimRecord, dataset_revision: str | None, require_editorial: bool) -> dict:
        reasons: list[str] = []
        if record.gate_status != "approved":
            reasons.append(f"gate_{record.gate_status}")
        if record.lifecycle_status not in ("current", "qualified"):
            reasons.append(f"lifecycle_{record.lifecycle_status}")
        if require_editorial and record.editorial_status != "approved":
            reasons.append("editorial_not_approved")
        if record.dataset_revision and dataset_revision and record.dataset_revision != dataset_revision:
            reasons.append("dataset_revision_mismatch")
        return {"reasons": reasons}

    def manifest(
        self,
        *,
        rundown: Rundown,
        validation: RundownValidation,
        claims: list[ClaimRecord],
        dataset_revision: str | None,
        actor: str,
        package_payload: str,
    ) -> ExportManifest:
        by_id = {r.claim_id: r for r in claims}
        items: list[ExportManifestItem] = []
        for item in validation.items:
            record = by_id.get(item.claim_id)
            items.append(ExportManifestItem(
                claim_id=item.claim_id,
                revision_id=item.revision_id,
                statement=item.statement,
                evidence_hash=item.evidence_hash,
                dataset_revision=item.dataset_revision,
                gate_status=record.gate_status if record else "missing",
                editorial_status=record.editorial_status if record else "missing",
                editorial_approver=record.editorial_approver if record else None,
                editorial_at=record.editorial_at if record else None,
                valid=item.valid,
                reasons=item.reasons,
            ))
        manifest = ExportManifest(
            manifest_id="manifest-" + _sha({
                "match_id": rundown.match_id,
                "snapshot_id": rundown.snapshot_id,
                "dataset_revision": dataset_revision,
                "items": [i.model_dump() for i in items],
            })[:20],
            match_id=rundown.match_id,
            snapshot_id=rundown.snapshot_id,
            dataset_revision=dataset_revision,
            generated_by=actor,
            valid=validation.valid,
            items=items,
            stale_items=validation.stale_items,
            package_sha256=_sha(package_payload),
        )
        return manifest
