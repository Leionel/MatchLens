"""Persisted agent-run lifecycle (roadmap C-09).

A model run is a first-class bounded state machine, not a hidden
request/response. The store records the architecture §9.3 lifecycle
``QUEUED → ANALYSING → TOOL_WAIT → HANDOFF → VERIFYING → GATED/WITHHELD/
FAILED/CANCELLED`` together with the run's audit trail, so a run can be
inspected, cancelled or explained after the fact. Only the same run identity
that was frozen at QUEUED may move the record forward; invalid transitions are
rejected, not silently coerced.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AgentRunState = Literal[
    "QUEUED",
    "ANALYSING",
    "TOOL_WAIT",
    "HANDOFF",
    "VERIFYING",
    "GATED",
    "PUBLISHED",
    "WITHHELD",
    "FAILED",
    "CANCELLED",
]

AGENT_STATE_TRANSITIONS: dict[str, set[str]] = {
    "QUEUED": {"ANALYSING", "FAILED", "CANCELLED"},
    "ANALYSING": {"TOOL_WAIT", "HANDOFF", "FAILED", "CANCELLED"},
    "TOOL_WAIT": {"ANALYSING", "FAILED", "CANCELLED"},
    "HANDOFF": {"VERIFYING", "FAILED", "CANCELLED"},
    "VERIFYING": {"TOOL_WAIT", "GATED", "FAILED", "CANCELLED"},
    "GATED": {"PUBLISHED", "WITHHELD"},
    "PUBLISHED": set(),
    "WITHHELD": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}

TERMINAL_STATES = frozenset({"PUBLISHED", "WITHHELD", "FAILED", "CANCELLED"})


class InvalidAgentRunTransition(ValueError):
    pass


class AgentRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    trigger: Literal["manual", "automatic", "investigation"]
    match_id: str
    snapshot_id: str
    investigation_id: str | None = None
    dataset_revision: str | None = None
    epoch: int = 0
    model: str | None = None
    prompt_version: str | None = None
    state: AgentRunState = "QUEUED"
    state_history: list[dict[str, Any]] = Field(default_factory=list)
    audit: list[dict[str, Any]] = Field(default_factory=list)
    requests: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    origin: str = "not_run"
    error: str | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class AgentRunStore:
    """Durable JSON store for agent-run lifecycle records.

    Mirrors ``InvestigationStore``: atomic tmp-file replace, load on init,
    single-writer (one uvicorn worker).
    """

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else None
        self.runs: dict[str, AgentRunRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            for raw in payload.get("runs", []):
                record = AgentRunRecord.model_validate(raw)
                self.runs[record.run_id] = record
        except Exception:
            self.runs = {}

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "agent-runs-v1",
            "runs": [record.model_dump() for record in self.runs.values()],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        # Windows can hold the destination with a stale handle for a moment
        # after the previous write (indexer/AV); retry briefly instead of
        # failing a persisted lifecycle record mid-write.
        for attempt in range(6):
            try:
                tmp.replace(self.path)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.02 * (attempt + 1))

    def create(
        self,
        *,
        run_id: str,
        trigger: str,
        match_id: str,
        snapshot_id: str,
        model: str | None,
        prompt_version: str | None,
        investigation_id: str | None = None,
        dataset_revision: str | None = None,
        epoch: int = 0,
        audit: list[dict[str, Any]] | None = None,
    ) -> AgentRunRecord:
        if run_id in self.runs:
            raise ValueError("agent_run_already_exists")
        record = AgentRunRecord(
            run_id=run_id,
            trigger=trigger,  # type: ignore[arg-type]
            match_id=match_id,
            snapshot_id=snapshot_id,
            investigation_id=investigation_id,
            dataset_revision=dataset_revision,
            epoch=epoch,
            model=model,
            prompt_version=prompt_version,
            state="QUEUED",
            state_history=[{"state": "QUEUED", "at": time.time(), "reason": "run identity frozen"}],
            audit=list(audit or []),
        )
        self.runs[record.run_id] = record
        self._save()
        return record

    def get(self, run_id: str) -> AgentRunRecord | None:
        return self.runs.get(run_id)

    def list(self, limit: int = 50) -> list[AgentRunRecord]:
        records = sorted(self.runs.values(), key=lambda r: r.created_at, reverse=True)
        return records[: max(0, limit)]

    def transition(self, run_id: str, target: AgentRunState, reason: str = "") -> AgentRunRecord:
        record = self.runs.get(run_id)
        if record is None:
            raise KeyError("agent_run_not_found")
        state = record.state
        if target != state and target not in AGENT_STATE_TRANSITIONS.get(state, set()):
            raise InvalidAgentRunTransition(f"invalid_agent_run_transition:{state}->{target}")
        if target == state:
            return record
        record.state = target
        record.state_history.append({"state": target, "at": time.time(), "reason": reason[:300]})
        record.updated_at = time.time()
        self._save()
        return record

    def attach(self, run_id: str, audit_entries: list[dict[str, Any]], requests: int | None = None) -> AgentRunRecord:
        """Persist an incremental audit snapshot while the run is live."""
        record = self.runs.get(run_id)
        if record is None:
            raise KeyError("agent_run_not_found")
        if audit_entries:
            record.audit.extend(audit_entries[len(record.audit):])
        if requests is not None:
            record.requests = requests
        record.updated_at = time.time()
        self._save()
        return record

    def finish(
        self,
        run_id: str,
        *,
        state: AgentRunState,
        reason: str,
        error: str | None = None,
        origin: str | None = None,
        accepted_count: int = 0,
        rejected_count: int = 0,
        audit_entries: list[dict[str, Any]] | None = None,
        requests: int | None = None,
    ) -> AgentRunRecord:
        """Move a run into its terminal state with the final audit snapshot."""
        record = self.runs.get(run_id)
        if record is None:
            raise KeyError("agent_run_not_found")
        if audit_entries:
            record.audit.extend(audit_entries[len(record.audit):])
        if requests is not None:
            record.requests = requests
        record.accepted_count = accepted_count
        record.rejected_count = rejected_count
        record.origin = origin or record.origin
        record.error = error
        record.updated_at = time.time()
        self.transition(run_id, state, reason)
        return record

    def cancel(self, run_id: str, reason: str = "cancelled by user") -> AgentRunRecord:
        record = self.runs.get(run_id)
        if record is None:
            raise KeyError("agent_run_not_found")
        if record.state in TERMINAL_STATES:
            raise ValueError("agent_run_terminal")
        return self.transition(run_id, "CANCELLED", reason)
