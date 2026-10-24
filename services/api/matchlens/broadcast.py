"""Broadcast rundown store and export helpers.

Only registry claims that are gate-approved, editorially approved and on the
current lifecycle revision can enter a rundown or export.
"""
from __future__ import annotations

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
    snapshot_id: str
    statement: str
    evidence_hash: str
    dataset_revision: str | None = None
    claim_level: int


class Rundown(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_id: str
    snapshot_id: str
    dataset_revision: str | None = None
    items: list[RundownItem] = Field(default_factory=list)
    updated_at: float = Field(default_factory=time.time)
    updated_by: str = "system"


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
        payload = {"version": "rundown-v1", "rundowns": [r.model_dump() for r in self.rundowns.values()]}
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
            ordered.append(RundownItem(
                order=len(ordered) + 1,
                claim_id=record.claim_id,
                snapshot_id=record.snapshot_id,
                statement=record.statement,
                evidence_hash=record.evidence_hash,
                dataset_revision=record.dataset_revision or dataset_revision,
                claim_level=record.claim_level,
            ))
        if not ordered:
            raise ValueError("empty_rundown")
        rundown = Rundown(
            match_id=match_id,
            snapshot_id=snapshot_id,
            dataset_revision=dataset_revision,
            items=ordered,
            updated_by=actor,
        )
        self.rundowns[f"{match_id}:{snapshot_id}"] = rundown
        self._save()
        return rundown

    def get(self, match_id: str, snapshot_id: str) -> Rundown | None:
        return self.rundowns.get(f"{match_id}:{snapshot_id}")
