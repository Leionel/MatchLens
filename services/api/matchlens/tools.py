"""Bounded, typed football tools shared by the planner and MAF agents.

Tools receive a frozen snapshot/state and return serializable observations.
There is no SQL, Python, network or filesystem execution path here.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .football import Snapshot, build_sequences, build_tactical_explorer
from .metrics import MetricsService


class ToolError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int
    tool: str
    args: dict[str, Any]
    status: Literal["ok", "unavailable", "error", "skipped"]
    result: Any = None
    result_sha256: str | None = None
    summary: str = ""
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class ToolContext:
    match_id: str
    snapshot: Snapshot
    state: dict
    team: str = "H"
    xt_model: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


TOOL_BUDGET = {
    "get_match_context": 1,
    "query_metric": 14,
    "compare_windows": 3,
    "search_events": 2,
    "get_possession_sequence": 2,
    "get_player_actions": 2,
    "get_spatial_distribution": 1,
    "get_attacking_channels": 1,
    "explain_oaai_contributors": 2,
    "find_counterevidence": 2,
    "compare_matches": 1,
    "check_data_sufficiency": 2,
}
MAX_TOOL_CALLS = sum(TOOL_BUDGET.values())


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:20]


class FootballToolRegistry:
    """Execute a small allow-list of football tools with per-tool budgets."""

    def __init__(self, context: ToolContext, max_calls: int = MAX_TOOL_CALLS):
        self.context = context
        self.max_calls = min(max_calls, MAX_TOOL_CALLS)
        self.calls: list[ToolCall] = []
        self.used: dict[str, int] = {}

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - len(self.calls))

    def call(self, name: str, args: dict[str, Any] | None = None) -> ToolCall:
        args = dict(args or {})
        if name not in TOOL_BUDGET:
            raise ToolError("tool_not_registered")
        if len(self.calls) >= self.max_calls:
            raise ToolError("tool_budget_exhausted")
        if self.used.get(name, 0) >= TOOL_BUDGET[name]:
            raise ToolError(f"tool_budget_exhausted:{name}")
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            raise ToolError("tool_not_implemented")
        started = time.perf_counter()
        self.used[name] = self.used.get(name, 0) + 1
        try:
            result = handler(**args)
            status: Literal["ok", "unavailable", "error", "skipped"] = "ok"
            error = None
            summary = self._summary(name, result)
        except ToolError:
            raise
        except (TypeError, ValueError, KeyError) as exc:
            result = None
            status = "error"
            error = str(exc)[:300]
            summary = f"{name} failed: {error}"
        call = ToolCall(
            sequence=len(self.calls) + 1,
            tool=name,
            args=args,
            status=status,
            result=result,
            result_sha256=_sha(result) if result is not None else None,
            summary=summary,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            error=error,
        )
        self.calls.append(call)
        return call

    @staticmethod
    def _summary(name: str, result: Any) -> str:
        if isinstance(result, dict):
            if "status" in result:
                return f"{name}: {result.get('status')}"
            if "value" in result:
                return f"{name}: {result.get('value')}"
            if "count" in result:
                return f"{name}: {result.get('count')} records"
        return f"{name}: ok"

    # ------------------------------------------------------------------ tools
    def _tool_get_match_context(self) -> dict:
        data = self.context.snapshot.data
        return {
            "match_id": self.context.match_id,
            "snapshot_id": self.context.snapshot.id,
            "as_of": data.get("as_of"),
            "coverage": data.get("coverage", {}),
            "dataset_revision": data.get("dataset_revision") or data.get("data_version"),
            "score": data.get("score", {}),
        }

    def _tool_query_metric(
        self,
        metric_id: str,
        team: str | None = None,
        window: Literal["previous", "current", "match"] = "current",
    ) -> dict:
        return MetricsService.query(
            self.context.snapshot,
            metric_id,
            team=team or self.context.team,
            window=window,
            match_id=self.context.match_id,
        ).model_dump()

    def _tool_compare_windows(self, metric_id: str, team: str | None = None) -> dict:
        team = team or self.context.team
        previous = MetricsService.query(
            self.context.snapshot, metric_id, team=team, window="previous", match_id=self.context.match_id
        )
        current = MetricsService.query(
            self.context.snapshot, metric_id, team=team, window="current", match_id=self.context.match_id
        )
        delta = (
            float(current.value) - float(previous.value)
            if isinstance(current.value, (int, float)) and isinstance(previous.value, (int, float))
            else None
        )
        return {
            "metric_id": metric_id,
            "team": team,
            "previous": previous.model_dump(),
            "current": current.model_dump(),
            "delta": delta,
            "comparable": previous.status == "ok" and current.status == "ok",
        }

    def _tool_search_events(
        self,
        *,
        team: str | None = None,
        kind: str | None = None,
        start: float | None = None,
        end: float | None = None,
        limit: int = 20,
    ) -> dict:
        if limit < 1 or limit > 50:
            raise ToolError("event_limit_out_of_bounds")
        events = self.context.state.get("events", [])
        selected = []
        for event in events:
            if team and event.get("team") != team:
                continue
            if kind and event.get("kind") != kind:
                continue
            t = float(event.get("t", 0.0))
            if start is not None and t < float(start):
                continue
            if end is not None and t > float(end):
                continue
            selected.append(event)
            if len(selected) >= limit:
                break
        return {
            "count": len(selected),
            "events": [
                {
                    "event_id": e.get("id"),
                    "t": e.get("t"),
                    "team": e.get("team"),
                    "kind": e.get("kind"),
                    "actor": e.get("actor"),
                    "outcome": e.get("outcome"),
                    "start": e.get("start"),
                    "end": e.get("end"),
                }
                for e in selected
            ],
        }

    def _tool_get_possession_sequence(self, sequence_id: str) -> dict:
        sequences = build_sequences(self.context.state)
        sequence = next(
            (s for s in sequences if s.get("sequence_id") == sequence_id),
            None,
        )
        if sequence is None:
            raise ToolError("sequence_not_found")
        return {
            "sequence_id": sequence["sequence_id"],
            "possession_id": sequence.get("possession_id"),
            "team": sequence.get("team"),
            "start_t": sequence.get("start_t"),
            "end_t": sequence.get("end_t"),
            "event_ids": sequence.get("event_ids", []),
            "events": sequence.get("events_detail", []),
        }

    def _tool_get_player_actions(
        self,
        player_id: str,
        *,
        start: float | None = None,
        end: float | None = None,
        limit: int = 20,
    ) -> dict:
        if limit < 1 or limit > 50:
            raise ToolError("event_limit_out_of_bounds")
        actions = []
        for event in self.context.state.get("events", []):
            if str(event.get("actor")) != str(player_id):
                continue
            t = float(event.get("t", 0.0))
            if start is not None and t < float(start):
                continue
            if end is not None and t > float(end):
                continue
            actions.append({
                "event_id": event.get("id"),
                "t": t,
                "kind": event.get("kind"),
                "outcome": event.get("outcome"),
                "start": event.get("start"),
                "end": event.get("end"),
            })
            if len(actions) >= limit:
                break
        if not actions:
            raise ToolError("player_not_found_or_no_actions")
        return {"player_id": player_id, "count": len(actions), "actions": actions}

    def _tool_get_spatial_distribution(self, team: str | None = None) -> dict:
        team = team or self.context.team
        tactical = build_tactical_explorer(self.context.state, team)
        return {
            "team": team,
            "zones": tactical.get("zones", {}),
            "zone_cells": [
                {k: cell.get(k) for k in ("cell_id", "name", "third", "channel", "count", "percentage")}
                for cell in tactical.get("zone_cells", [])
            ],
        }

    def _tool_get_attacking_channels(self, team: str | None = None) -> dict:
        team = team or self.context.team
        tactical = build_tactical_explorer(self.context.state, team)
        return {
            "team": team,
            "channels": tactical.get("channels", {}),
            "attacking_channels": tactical.get("attacking_channels", {}),
            "territorial_progression": tactical.get("territorial_progression", {}),
        }

    def _tool_explain_oaai_contributors(
        self,
        *,
        at: float | None = None,
        team: str | None = None,
        limit: int = 8,
    ) -> dict:
        from .oaai import compute_oaai_contribution_ledger

        if limit < 1 or limit > 20:
            raise ToolError("ledger_limit_out_of_bounds")
        data = self.context.snapshot.data
        target = float(at if at is not None else data.get("as_of", 0.0))
        return compute_oaai_contribution_ledger(
            self.context.state.get("events", []),
            at=target,
            team=team or self.context.team,
            dead_intervals=data.get("dead_intervals", []),
            xt_model=self.context.xt_model,
            limit=limit,
        )

    def _tool_find_counterevidence(self, assertion: str = "", team: str | None = None) -> dict:
        team = team or self.context.team
        metrics = {}
        for metric_id in ("shots", "entries", "high_recoveries", "transition_shots", "goals"):
            value = MetricsService.query(
                self.context.snapshot, metric_id, team=team, window="current", match_id=self.context.match_id
            )
            metrics[metric_id] = value.model_dump()
        contrary = []
        if assertion in ("attacking_threat_increased", "possession_without_penetration"):
            if not metrics["shots"]["value"]:
                contrary.append("shots.current is zero")
            if not metrics["entries"]["value"]:
                contrary.append("entries.current is zero")
        if assertion == "recoveries_followed_by_shots" and not metrics["transition_shots"]["value"]:
            contrary.append("transition_shots.current is zero")
        if assertion == "goal_sequence" and not metrics["goals"]["value"]:
            contrary.append("goals.current is zero")
        return {
            "assertion": assertion,
            "team": team,
            "metrics": metrics,
            "counterevidence": contrary,
            "coverage": self.context.snapshot.data.get("coverage", {}),
        }

    def _tool_compare_matches(self, match_ids: list[str], metric_id: str = "shots") -> dict:
        if not match_ids or len(match_ids) > 3:
            raise ToolError("match_comparison_limit")
        from .catalog import MatchCatalog

        summary = MatchCatalog.get_batch_summary(match_ids)
        return {
            "match_ids": match_ids,
            "metric_id": metric_id,
            "summary": summary,
        }

    def _tool_check_data_sufficiency(
        self,
        *,
        start: float | None = None,
        end: float | None = None,
    ) -> dict:
        data = self.context.snapshot.data
        coverage = data.get("coverage", {})
        events = self.context.state.get("events", [])
        window_start = float(start if start is not None else 0.0)
        window_end = float(end if end is not None else data.get("as_of", 0.0))
        window_events = [
            e for e in events
            if window_start <= float(e.get("t", 0.0)) <= window_end
        ]
        warnings = []
        if coverage.get("continuous") is False:
            warnings.append("partial_event_coverage")
        if len(window_events) < 10:
            warnings.append("low_event_sample")
        completeness = data.get("completeness") or {}
        if completeness.get("status") and completeness.get("status") != "COMPLETE_VERIFIED":
            warnings.append(f"completeness_{str(completeness.get('status')).lower()}")
        return {
            "coverage": coverage,
            "completeness": completeness,
            "window_event_count": len(window_events),
            "warnings": warnings,
            "sufficient_for_match_level_claim": not warnings,
        }
