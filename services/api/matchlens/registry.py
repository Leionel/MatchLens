"""Durable claim and challenge registry.

Approval is never accepted from a caller-supplied boolean. A record is
publishable only when this registry has executed a gate against a frozen
snapshot and stored the resulting verdict, evidence hash and source run.
Editorial approval is a separate, explicitly attributed decision.
"""
from __future__ import annotations

import hashlib
import json
import time
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

    @property
    def broadcastable(self) -> bool:
        return self.gate_status == "approved" and self.editorial_status == "approved"


class ChallengeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_hash: str
    idempotency_key: Optional[str] = None
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
        self._load()

    # ---------------------------------------------------------------- persistence
    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for raw in data.get("claims", []):
                record = ClaimRecord.model_validate(raw)
                self.records[record.record_id] = record
            for raw in data.get("challenges", []):
                record = ChallengeRecord.model_validate(raw)
                self.challenges[record.request_hash] = record
        except Exception:
            # A corrupt registry is not silently replaced with approvals.
            self.records = {}
            self.challenges = {}

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "claim-registry-v1",
            "saved_at": time.time(),
            "claims": [r.model_dump() for r in self.records.values()],
            "challenges": [r.model_dump() for r in self.challenges.values()],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

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
        )
        self.records[record.record_id] = record
        self._save()
        return record

    def editorial_decision(
        self,
        match_id: str,
        snapshot_id: str,
        claim_id: str,
        *,
        approver: str,
        decision: Literal["approved", "rejected"],
        note: str | None = None,
    ) -> ClaimRecord:
        record = self.get(match_id, snapshot_id, claim_id)
        if record is None:
            raise KeyError("claim_not_registered")
        if record.gate_status != "approved":
            raise ValueError("gate_not_approved")
        if not approver.strip():
            raise ValueError("approver_required")
        record.editorial_status = decision
        record.editorial_approver = approver.strip()
        record.editorial_note = note
        record.editorial_at = time.time()
        self._save()
        return record

    # ------------------------------------------------------------------ challenges
    def remember_challenge(
        self,
        *,
        request_payload: dict[str, Any],
        idempotency_key: str | None,
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

    def find_idempotency_key(self, key: str) -> Optional[ChallengeRecord]:
        return next((r for r in self.challenges.values() if r.idempotency_key == key), None)
