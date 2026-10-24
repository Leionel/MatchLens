"""Auditable football investigation planner and bounded state machine.

The planner is deterministic. It turns a question and a typed focus into an
intent, a scope, a bounded tool plan, evidence-backed findings, competing
explanations, counterevidence checks and a Gate 2.0 preview. It never persists a
claim; promotion is an explicit user action followed by the real registry gate.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import assertion_supported, evidence_summary, required_refs
from .football import Snapshot, build_sequences, build_tactical_explorer
from .gate import publication_gate_2_0
from .metrics import MetricsService
from .tools import FootballToolRegistry, ToolCall, ToolContext, ToolError


IntentType = Literal[
    "WHY_CHANGE",
    "WHO_CONTRIBUTED",
    "COMPARE_WINDOWS",
    "FIND_COUNTEREVIDENCE",
    "CHECK_SAMPLE",
    "EXPLAIN_SEQUENCE",
    "COMPARE_MATCHES",
    "UNKNOWN",
]
InvestigationState = Literal[
    "CREATED",
    "PLANNING",
    "QUERYING",
    "EVIDENCE_REVIEW",
    "HYPOTHESIS_FORMED",
    "COUNTEREVIDENCE_CHECK",
    "VERIFICATION",
    "NEEDS_MORE_EVIDENCE",
    "APPROVED",
    "QUALIFIED",
    "WITHHELD",
    "FAILED",
    "CANCELLED",
]

STATE_TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"PLANNING", "FAILED", "CANCELLED"},
    "PLANNING": {"QUERYING", "FAILED", "CANCELLED"},
    "QUERYING": {"EVIDENCE_REVIEW", "NEEDS_MORE_EVIDENCE", "FAILED", "CANCELLED"},
    "EVIDENCE_REVIEW": {"HYPOTHESIS_FORMED", "NEEDS_MORE_EVIDENCE", "WITHHELD", "CANCELLED"},
    "HYPOTHESIS_FORMED": {"COUNTEREVIDENCE_CHECK", "VERIFICATION", "CANCELLED"},
    "COUNTEREVIDENCE_CHECK": {"VERIFICATION", "NEEDS_MORE_EVIDENCE", "WITHHELD", "CANCELLED"},
    "NEEDS_MORE_EVIDENCE": {"PLANNING", "WITHHELD", "CANCELLED"},
    "VERIFICATION": {"APPROVED", "QUALIFIED", "WITHHELD", "FAILED", "CANCELLED"},
    "APPROVED": set(),
    "QUALIFIED": set(),
    "WITHHELD": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}


class ToolReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence: int
    tool: str
    args: dict[str, Any]
    status: Literal["ok", "unavailable", "skipped", "error"]
    snapshot_id: str
    dataset_revision: str | None
    result_sha256: str | None = None
    summary: str = ""
    duration_ms: float = 0.0
    error: str | None = None


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding_id: str
    level: Literal[1, 2, 3, 4]
    statement: str
    event_ids: list[str] = Field(default_factory=list)
    metric_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class CandidateExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    explanation_id: str
    hypothesis: str
    status: Literal["supported", "qualified", "rejected", "insufficient_evidence"]
    claim_level: int = 2
    supporting_evidence: list[str]
    counterevidence: list[str]
    verification: str
    limitations: list[str]


class GatePreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assertion: str
    refs: list[str]
    status: Literal["approved", "disputed", "rejected", "not_formed"]
    violations: list[str] = Field(default_factory=list)
    statement: str = ""
    claim_level: int = 1
    persisted: bool = False


class InvestigationScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_id: str
    team: str
    focus_type: str
    focus_id: str | None = None
    start_s: float
    end_s: float
    metric_id: str | None = None
    player_id: str | None = None
    sequence_id: str | None = None
    zone_id: str | None = None
    compare_match_ids: list[str] = Field(default_factory=list)


class InvestigationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    investigation_id: str
    match_id: str
    snapshot_id: str
    as_of: int
    team: str
    focus_type: str
    focus_id: str | None
    question: str
    intent: IntentType
    intent_confidence: float = 0.0
    scope: InvestigationScope
    state: InvestigationState
    state_history: list[dict[str, Any]] = Field(default_factory=list)
    execution_mode: Literal["deterministic_planner"] = "deterministic_planner"
    agent_status: Literal["not_run", "run"] = "not_run"
    dataset_revision: str | None
    coverage: dict[str, Any]
    completeness: dict[str, Any] = Field(default_factory=dict)
    selected_metrics: list[str] = Field(default_factory=list)
    oaai_ledger: dict[str, Any] | None = None
    tool_receipts: list[ToolReceipt]
    findings: list[Finding]
    explanations: list[CandidateExplanation]
    gate_preview: GatePreview
    not_inferable: list[str]
    unresolved: list[str]
    required_scope: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:20]


class InvestigationRun:
    def __init__(self, investigation_id: str):
        self.investigation_id = investigation_id
        self.state: InvestigationState = "CREATED"
        self.history: list[dict[str, Any]] = [{"state": "CREATED", "at": time.time(), "reason": "created"}]

    def transition(self, target: InvestigationState, reason: str = "") -> None:
        if target != self.state and target not in STATE_TRANSITIONS.get(self.state, set()):
            raise ValueError(f"invalid_investigation_transition:{self.state}->{target}")
        if target == self.state:
            return
        self.state = target
        self.history.append({"state": target, "at": time.time(), "reason": reason[:300]})


def classify_intent(question: str, focus_type: str) -> tuple[IntentType, float]:
    text = (question or "").strip().lower()
    if not text:
        if focus_type in ("sequence",):
            return "EXPLAIN_SEQUENCE", 0.55
        if focus_type in ("player",):
            return "WHO_CONTRIBUTED", 0.55
        return "WHY_CHANGE", 0.55

    groups: list[tuple[IntentType, tuple[str, ...]]] = [
        ("CHECK_SAMPLE", ("sample", "enough data", "coverage", "sufficient", "样本", "数据够", "覆盖", "不够")),
        ("FIND_COUNTEREVIDENCE", ("counter", "contradict", "against", "反证", "反驳", "相反", "不支持")),
        ("COMPARE_MATCHES", ("other match", "another match", "across matches", "两场", "另一场", "跨场", "不同比赛")),
        ("WHO_CONTRIBUTED", ("who", "which player", "contributed", "谁", "哪位", "哪名", "贡献")),
        ("EXPLAIN_SEQUENCE", ("sequence", "possession", "this move", "序列", "控球", "这波", "进攻序列")),
        ("WHY_CHANGE", ("why", "what caused", "what produced", "explain", "reason", "为什么", "为何", "原因", "怎么", "如何", "解释")),
        ("COMPARE_WINDOWS", ("compare", "difference", "before", "after", "对比", "比较", "之前", "之后")),
    ]
    for intent, needles in groups:
        if any(needle in text for needle in needles):
            return intent, 0.9
    if focus_type == "metric":
        # A named metric is already an in-scope explanation target; only the
        # wording is ambiguous, so fall back instead of rejecting the question.
        return "WHY_CHANGE", 0.6
    return "UNKNOWN", 0.2


def _window_for(focus_time: float) -> tuple[float, float]:
    return max(0.0, focus_time - 180.0), max(0.0, focus_time)


class InvestigationPlanner:
    @classmethod
    def run(
        cls,
        *,
        match_id: str,
        snapshot: Snapshot,
        state: dict,
        team: str = "H",
        focus_type: str = "moment",
        focus_id: str | None = None,
        question: str = "",
        compare_match_ids: list[str] | None = None,
        xt_model: Any = None,
    ) -> InvestigationPlan:
        started = time.perf_counter()
        team = "N" if team == "N" else "H"
        events = state.get("events", [])
        coverage = snapshot.data.get("coverage", {})
        completeness = snapshot.data.get("completeness", {}) or {}
        dataset_revision = snapshot.data.get("dataset_revision") or snapshot.data.get("data_version")
        intent, confidence = classify_intent(question, focus_type)
        as_of = int(snapshot.data.get("as_of", 0))
        investigation_id = "inv-" + _hash({
            "snapshot": snapshot.id,
            "focus_type": focus_type,
            "focus": focus_id,
            "team": team,
            "question": question,
            "intent": intent,
        })
        run = InvestigationRun(investigation_id)
        run.transition("PLANNING", "intent and scope")

        receipts: list[ToolReceipt] = []
        registry = FootballToolRegistry(
            ToolContext(
                match_id=match_id,
                snapshot=snapshot,
                state=state,
                team=team,
                xt_model=xt_model,
            ),
            max_calls=18,
        )

        def use(tool: str, **args) -> ToolCall | None:
            try:
                call = registry.call(tool, args)
            except ToolError as exc:
                receipts.append(ToolReceipt(
                    sequence=len(receipts) + 1,
                    tool=tool,
                    args=args,
                    status="skipped",
                    snapshot_id=snapshot.id,
                    dataset_revision=dataset_revision,
                    summary=f"{tool}: {exc.code}",
                    error=exc.code,
                ))
                return None
            receipts.append(ToolReceipt(
                sequence=len(receipts) + 1,
                tool=call.tool,
                args=call.args,
                status=call.status,  # type: ignore[arg-type]
                snapshot_id=snapshot.id,
                dataset_revision=dataset_revision,
                result_sha256=call.result_sha256,
                summary=call.summary,
                duration_ms=call.duration_ms,
                error=call.error,
            ))
            return call

        context_call = use("get_match_context")
        sufficiency_call = use("check_data_sufficiency", start=0, end=as_of)

        if intent == "UNKNOWN":
            run.transition("FAILED", "question requires a concrete football scope")
            return cls._finish(
                run=run,
                investigation_id=investigation_id,
                match_id=match_id,
                snapshot=snapshot,
                team=team,
                question=question,
                intent=intent,
                confidence=confidence,
                focus_type=focus_type,
                focus_id=focus_id,
                scope=InvestigationScope(
                    match_id=match_id, team=team, focus_type=focus_type, focus_id=focus_id,
                    start_s=max(0.0, as_of - 180.0), end_s=float(as_of),
                ),
                dataset_revision=dataset_revision,
                coverage=coverage,
                completeness=completeness,
                receipts=receipts,
                findings=[],
                explanations=[],
                gate=GatePreview(assertion="none", refs=[], status="not_formed"),
                selected=[],
                unresolved=[
                    "The question was not mapped to a supported football intent. "
                    "Select a moment, event, sequence, player, zone or metric and ask why, who, compare, or check sample."
                ],
                required_scope=["focus_type", "focus_id", "intent"],
                started=started,
            )

        try:
            focus_events, focus_sequence, focus_time, focus_label = cls._resolve_focus(
                state=state,
                snapshot=snapshot,
                focus_type=focus_type,
                focus_id=focus_id,
                team=team,
                intent=intent,
                registry=registry,
                use=use,
            )
        except ToolError as exc:
            run.transition("FAILED", exc.code)
            return cls._finish(
                run=run,
                investigation_id=investigation_id,
                match_id=match_id,
                snapshot=snapshot,
                team=team,
                question=question,
                intent=intent,
                confidence=confidence,
                focus_type=focus_type,
                focus_id=focus_id,
                scope=InvestigationScope(
                    match_id=match_id, team=team, focus_type=focus_type, focus_id=focus_id,
                    start_s=max(0.0, as_of - 180.0), end_s=float(as_of),
                ),
                dataset_revision=dataset_revision,
                coverage=coverage,
                completeness=completeness,
                receipts=receipts,
                findings=[],
                explanations=[],
                gate=GatePreview(assertion="none", refs=[], status="not_formed"),
                selected=[],
                unresolved=[f"The selected focus is invalid: {exc.code}. No generic fallback was substituted."],
                required_scope=[f"valid_{focus_type}_id"],
                started=started,
            )

        start_s, end_s = _window_for(focus_time)
        scope = InvestigationScope(
            match_id=match_id,
            team=team,
            focus_type=focus_type,
            focus_id=focus_id,
            start_s=start_s,
            end_s=end_s,
            metric_id=focus_id if focus_type == "metric" else None,
            player_id=focus_id if focus_type == "player" else None,
            sequence_id=focus_id if focus_type == "sequence" else None,
            zone_id=focus_id if focus_type == "zone" else None,
            compare_match_ids=list(compare_match_ids or []),
        )

        if intent == "COMPARE_MATCHES" and not scope.compare_match_ids:
            run.transition("WITHHELD", "comparison match IDs required")
            return cls._finish(
                run=run,
                investigation_id=investigation_id,
                match_id=match_id,
                snapshot=snapshot,
                team=team,
                question=question,
                intent=intent,
                confidence=confidence,
                focus_type=focus_type,
                focus_id=focus_id,
                scope=scope,
                dataset_revision=dataset_revision,
                coverage=coverage,
                completeness=completeness,
                receipts=receipts,
                findings=[],
                explanations=[],
                gate=GatePreview(assertion="none", refs=[], status="not_formed"),
                selected=[],
                unresolved=["Cross-match comparison requires explicit match IDs in this request."],
                required_scope=["compare_match_ids"],
                started=started,
            )

        run.transition("QUERYING", f"{intent} tool plan")
        metrics: dict[str, Any] = {}
        ledger: dict[str, Any] | None = None
        selected_metrics = cls._metric_plan(intent, focus_type)

        def query(metric_id: str, window: Literal["previous", "current", "match"] = "current") -> None:
            call = use("query_metric", metric_id=metric_id, team=team, window=window)
            if call is not None and isinstance(call.result, dict):
                metrics[f"{metric_id}.{window}"] = call.result

        for metric_id in selected_metrics:
            query(metric_id)
            if (
                intent in ("COMPARE_WINDOWS", "WHY_CHANGE")
                and focus_type != "sequence"
                and metric_id in ("possession", "shots", "entries")
            ):
                query(metric_id, "previous")

        if intent in ("WHY_CHANGE", "WHO_CONTRIBUTED", "EXPLAIN_SEQUENCE") or focus_type in ("moment", "oaai_point"):
            ledger_call = use("explain_oaai_contributors", at=focus_time, team=team, limit=8)
            if ledger_call is not None and isinstance(ledger_call.result, dict):
                ledger = ledger_call.result

        if focus_sequence is not None:
            use("get_possession_sequence", sequence_id=focus_sequence["sequence_id"])
            use("search_events", team=team, start=focus_sequence.get("start_t"), end=focus_sequence.get("end_t"), limit=30)

        if intent == "CHECK_SAMPLE":
            use("check_data_sufficiency", start=start_s, end=end_s)
        if intent == "FIND_COUNTEREVIDENCE":
            assertion = cls._choose_assertion(metrics, focus_events, intent)
            use("find_counterevidence", assertion=assertion, team=team)
        if intent == "COMPARE_MATCHES":
            use("compare_matches", match_ids=scope.compare_match_ids, metric_id="shots")
        if focus_type == "player" and focus_id:
            use("get_player_actions", player_id=focus_id, start=start_s, end=end_s, limit=20)
        if focus_type == "zone":
            use("get_spatial_distribution", team=team)
        if intent in ("WHO_CONTRIBUTED", "FIND_COUNTEREVIDENCE", "WHY_CHANGE"):
            use("get_attacking_channels", team=team)

        run.transition("EVIDENCE_REVIEW", f"{len(receipts)} tool receipts")
        findings = cls._findings(
            snapshot=snapshot,
            team=team,
            focus_label=focus_label,
            focus_events=focus_events,
            focus_sequence=focus_sequence,
            metrics=metrics,
            ledger=ledger,
            coverage=coverage,
            completeness=completeness,
        )
        run.transition("HYPOTHESIS_FORMED", f"{len(findings)} findings")
        explanations = cls._explanations(metrics, ledger, focus_events, coverage)
        run.transition("COUNTEREVIDENCE_CHECK", "alternatives checked against receipts")

        gate = cls._gate_preview(
            snapshot=snapshot,
            team=team,
            metrics=metrics,
            focus_sequence=focus_sequence,
            focus_events=focus_events,
            intent=intent,
        )
        if gate.status == "not_formed":
            run.transition("WITHHELD", "no gate-eligible assertion")
            final_state = "WITHHELD"
        else:
            run.transition("VERIFICATION", "Gate 2.0 preview")
            if gate.status == "approved":
                run.transition("APPROVED", "Gate 2.0 approved preview")
                final_state = "APPROVED"
            elif gate.status == "disputed":
                run.transition("QUALIFIED", "Gate 2.0 disputed preview")
                final_state = "QUALIFIED"
            else:
                run.transition("WITHHELD", "Gate 2.0 rejected preview")
                final_state = "WITHHELD"

        unresolved = [
            "Chance quality requires a calibrated xG model.",
            "Cross-match base rates require complete, comparable matches.",
        ]
        if coverage.get("continuous") is False:
            unresolved.append("Partial event coverage: unobserved intervals remain Unknown.")
        if any(explanation.status == "insufficient_evidence" for explanation in explanations):
            unresolved.append("At least one candidate explanation lacks the evidence needed to test it.")

        return cls._finish(
            run=run,
            investigation_id=investigation_id,
            match_id=match_id,
            snapshot=snapshot,
            team=team,
            question=question,
            intent=intent,
            confidence=confidence,
            focus_type=focus_type,
            focus_id=focus_id,
            scope=scope,
            dataset_revision=dataset_revision,
            coverage=coverage,
            completeness=completeness,
            receipts=receipts,
            findings=findings,
            explanations=explanations,
            gate=gate,
            selected=selected_metrics,
            unresolved=unresolved,
            required_scope=[],
            started=started,
            state=final_state,
            ledger=ledger,
        )

    # ------------------------------------------------------------- focus/scope
    @staticmethod
    def _resolve_focus(
        *,
        state: dict,
        snapshot: Snapshot,
        focus_type: str,
        focus_id: str | None,
        team: str,
        intent: str,
        registry: FootballToolRegistry,
        use,
    ) -> tuple[list[dict], dict | None, float, str]:
        events = state.get("events", [])
        sequences = build_sequences(state)
        as_of = float(snapshot.data.get("as_of", 0.0))

        if focus_type == "event":
            if not focus_id:
                raise ToolError("event_id_required")
            event = next((e for e in events if str(e.get("id")) == str(focus_id)), None)
            if event is None:
                raise ToolError("invalid_focus_event")
            sequence = next((s for s in sequences if focus_id in s.get("event_ids", [])), None)
            return [event], sequence, float(event.get("t", as_of)), f"event {focus_id}"

        if focus_type == "sequence":
            if not focus_id:
                raise ToolError("sequence_id_required")
            sequence = next((s for s in sequences if s.get("sequence_id") == focus_id), None)
            if sequence is None:
                raise ToolError("invalid_focus_sequence")
            focus_events = [e for e in events if e.get("id") in set(sequence.get("event_ids", []))]
            return focus_events, sequence, float(sequence.get("end_t", as_of)), f"sequence {focus_id}"

        if focus_type in ("moment", "oaai_point"):
            from .oaai import compute_oaai

            oaai = compute_oaai(
                events,
                smoothing_mode="causal",
                t_end=as_of,
                dead_intervals=snapshot.data.get("dead_intervals", []),
            )
            points = oaai.get("change_points", [])
            if focus_id:
                point = next((p for p in points if p.get("change_point_id") == focus_id), None)
                if point is None:
                    raise ToolError("invalid_focus_moment")
            else:
                if not points:
                    raise ToolError("no_oaai_change_point")
                point = max(points, key=lambda p: float(p.get("at", 0.0)))
            point_events = [
                e for e in events
                if str(e.get("id")) in {c.get("event_id") for c in point.get("top_contributors", [])}
            ]
            return point_events, None, as_of, f"OAAI {point.get('change_point_id')}"

        if focus_type == "metric":
            if not focus_id:
                raise ToolError("metric_id_required")
            call = use("query_metric", metric_id=focus_id, team=team, window="current")
            if call is None or call.status != "ok" or not isinstance(call.result, dict):
                raise ToolError("invalid_focus_metric")
            metric = call.result
            metric_events = [
                e for e in events if str(e.get("id")) in set(metric.get("event_ids", []))
            ]
            return metric_events, None, as_of, f"metric {focus_id}"

        if focus_type == "player":
            if not focus_id:
                raise ToolError("player_id_required")
            player_events = [e for e in events if str(e.get("actor")) == str(focus_id)]
            if not player_events:
                raise ToolError("invalid_focus_player")
            return player_events[:50], None, as_of, f"player {focus_id}"

        if focus_type == "zone":
            if not focus_id:
                raise ToolError("zone_id_required")
            tactical = build_tactical_explorer(state, team)
            cell = next((c for c in tactical.get("zone_cells", []) if c.get("cell_id") == focus_id), None)
            if cell is None:
                raise ToolError("invalid_focus_zone")
            zone_events = [e for e in events if str(e.get("id")) in set(cell.get("event_ids", []))]
            return zone_events, None, as_of, f"zone {focus_id}"

        if focus_type == "chart":
            return [], None, as_of, "chart selection"

        raise ToolError("unsupported_focus_type")

    @staticmethod
    def _metric_plan(intent: str, focus_type: str) -> list[str]:
        plans = {
            "WHY_CHANGE": ["possession", "shots", "entries", "high_recoveries", "transition_shots", "goals", "oaai"],
            "WHO_CONTRIBUTED": ["oaai", "shots", "entries", "passes", "carries"],
            "COMPARE_WINDOWS": ["possession", "shots", "entries", "high_recoveries", "transition_shots", "goals", "oaai"],
            "FIND_COUNTEREVIDENCE": ["shots", "entries", "high_recoveries", "transition_shots", "goals", "possession"],
            "CHECK_SAMPLE": ["possession", "shots", "entries", "goals"],
            "EXPLAIN_SEQUENCE": ["passes", "carries", "entries", "shots", "recoveries"],
            "COMPARE_MATCHES": [],
        }
        return plans.get(intent, ["possession", "shots", "entries"])

    # ----------------------------------------------------------- findings/gate
    @classmethod
    def _findings(
        cls,
        *,
        snapshot: Snapshot,
        team: str,
        focus_label: str,
        focus_events: list[dict],
        focus_sequence: dict | None,
        metrics: dict[str, Any],
        ledger: dict[str, Any] | None,
        coverage: dict[str, Any],
        completeness: dict[str, Any],
    ) -> list[Finding]:
        findings: list[Finding] = []
        focus_ids = [str(e.get("id")) for e in focus_events if e.get("id")]
        if focus_events:
            findings.append(Finding(
                finding_id="finding-focus",
                level=1,
                statement=(
                    f"{focus_label}: {len(focus_events)} recorded event(s) between "
                    f"{focus_events[0].get('t')}s and {focus_events[-1].get('t')}s."
                ),
                event_ids=focus_ids,
                limitations=["Recorded on-ball events only; no off-ball positions."],
            ))
        if focus_sequence is not None:
            findings.append(Finding(
                finding_id="finding-sequence",
                level=1,
                statement=(
                    f"Sequence {focus_sequence.get('sequence_id')} contains "
                    f"{len(focus_sequence.get('event_ids', []))} recorded events."
                ),
                event_ids=list(focus_sequence.get("event_ids", [])),
                limitations=["Sequence boundaries are derived from recorded possession, not tracking."],
            ))
        if ledger and ledger.get("contributions"):
            top = ledger["contributions"][:5]
            findings.append(Finding(
                finding_id="finding-oaai-ledger",
                level=2,
                statement=(
                    f"OAAI team contribution at {ledger.get('at')}s is "
                    f"{ledger.get('raw_team_intensity')}; the top recorded contributors are listed."
                ),
                event_ids=[row.get("event_id") for row in top if row.get("event_id")],
                metric_ids=[f"{team}.oaai.current"],
                assumptions=["Contribution is an algebraic decomposition of the OAAI formula."],
                limitations=["OAAI is an activity index, not psychological momentum or causal proof."],
            ))
        for metric_id in ("possession", "shots", "entries", "high_recoveries", "transition_shots", "goals"):
            metric = metrics.get(f"{metric_id}.current")
            if not metric or metric.get("status") != "ok":
                continue
            findings.append(Finding(
                finding_id=f"finding-{metric_id}",
                level=1 if metric_id in ("shots", "entries", "high_recoveries", "transition_shots", "goals") else 2,
                statement=(
                    f"{metric.get('definition', metric_id)}: {metric.get('value')} "
                    f"{metric.get('unit', '')} in the current window."
                ),
                event_ids=list(metric.get("event_ids", [])),
                metric_ids=[f"{team}.{metric_id}.current"],
                limitations=list(metric.get("limitations", [])),
            ))
        if coverage:
            findings.append(Finding(
                finding_id="finding-coverage",
                level=1,
                statement=(
                    f"Coverage status is {completeness.get('status', 'unknown')}; "
                    f"continuous={coverage.get('continuous')}; events={coverage.get('event_count')}."
                ),
                limitations=["Unobserved intervals remain Unknown, not zero."],
            ))
        return findings

    @staticmethod
    def _explanations(
        metrics: dict[str, Any],
        ledger: dict[str, Any] | None,
        focus_events: list[dict],
        coverage: dict[str, Any],
    ) -> list[CandidateExplanation]:
        explanations: list[CandidateExplanation] = []
        transition = metrics.get("transition_shots.current", {}).get("value")
        shots = metrics.get("shots.current", {}).get("value")
        entries = metrics.get("entries.current", {}).get("value")
        possession = metrics.get("possession.current", {}).get("value")

        if isinstance(transition, (int, float)) and transition >= 2:
            explanations.append(CandidateExplanation(
                explanation_id="expl-transition",
                hypothesis="A recovery-to-shot pattern is present in the selected window.",
                status="supported",
                claim_level=3,
                supporting_evidence=["transition_shots.current", "high_recoveries.current"],
                counterevidence=[],
                verification="Count shots within ten seconds of a recovery in the same possession.",
                limitations=["This is a temporal association, not evidence of a pressing plan."],
            ))
        else:
            explanations.append(CandidateExplanation(
                explanation_id="expl-transition",
                hypothesis="A recovery-to-shot pattern explains the selected activity.",
                status="insufficient_evidence",
                claim_level=3,
                supporting_evidence=[],
                counterevidence=["transition_shots.current < 2 or unavailable"],
                verification="Requires at least two linked recovery-to-shot chains.",
                limitations=["The current window does not contain enough linked chains."],
            ))

        if isinstance(entries, (int, float)) and isinstance(shots, (int, float)):
            explanations.append(CandidateExplanation(
                explanation_id="expl-progression",
                hypothesis="Recorded final-third progression is present alongside the attacking activity.",
                status="supported" if entries > 0 and shots > 0 else "insufficient_evidence",
                claim_level=2,
                supporting_evidence=["entries.current", "shots.current"],
                counterevidence=[] if entries > 0 and shots > 0 else ["entries.current or shots.current is zero"],
                verification="Trace final-third entries and shots in the selected possession chain.",
                limitations=["Entry and shot counts are on-ball observations; chance quality is not measured."],
            ))

        if ledger and ledger.get("contributions"):
            positive = sum(row.get("team_contribution", 0.0) for row in ledger["contributions"] if row.get("team_contribution", 0.0) > 0)
            negative = sum(row.get("team_contribution", 0.0) for row in ledger["contributions"] if row.get("team_contribution", 0.0) < 0)
            explanations.append(CandidateExplanation(
                explanation_id="expl-oaai-contributors",
                hypothesis="The selected OAAI peak is explained by the recorded contribution ledger.",
                status="supported" if positive > abs(negative) else "qualified",
                claim_level=2,
                supporting_evidence=[row.get("event_id") for row in ledger["contributions"][:4] if row.get("event_id")],
                counterevidence=[row.get("event_id") for row in ledger["contributions"] if row.get("team_contribution", 0.0) < 0][:3],
                verification="Sum weighted event contributions at the selected time.",
                limitations=["Formula attribution does not establish tactical causality."],
            ))

        explanations.append(CandidateExplanation(
            explanation_id="expl-pressing-intent",
            hypothesis="The opponent's pressing structure caused the turnover.",
            status="insufficient_evidence",
            claim_level=4,
            supporting_evidence=[],
            counterevidence=["high_recoveries.current is a location count, not pressure or structure."],
            verification="Requires 22-player off-ball tracking, pressure distances and a causal design.",
            limitations=["The snapshot contains on-ball events only."],
        ))
        if coverage.get("continuous") is False:
            explanations.append(CandidateExplanation(
                explanation_id="expl-coverage",
                hypothesis="The observed pattern is representative of the full match.",
                status="insufficient_evidence",
                claim_level=2,
                supporting_evidence=[],
                counterevidence=["Coverage is partial; unobserved intervals remain Unknown."],
                verification="Requires COMPLETE_VERIFIED coverage.",
                limitations=["Partial fixtures cannot support full-match or per-90 claims."],
            ))
        return explanations

    @staticmethod
    def _choose_assertion(metrics: dict[str, Any], focus_events: list[dict], intent: str = "") -> str:
        goals = metrics.get("goals.current", {}).get("value")
        transition = metrics.get("transition_shots.current", {}).get("value")
        shots = metrics.get("shots.current", {}).get("value")
        entries = metrics.get("entries.current", {}).get("value")
        if intent == "WHO_CONTRIBUTED":
            if isinstance(shots, (int, float)) and isinstance(entries, (int, float)) and shots > 0 and entries > 0:
                return "attacking_threat_increased"
            if isinstance(goals, (int, float)) and goals > 0:
                return "goal_sequence"
            return "none"
        if isinstance(goals, (int, float)) and goals > 0:
            return "goal_sequence"
        if isinstance(transition, (int, float)) and transition >= 2:
            return "recoveries_followed_by_shots"
        if isinstance(shots, (int, float)) and isinstance(entries, (int, float)) and shots > 0 and entries > 0:
            return "attacking_threat_increased"
        return "possession_without_penetration"

    @classmethod
    def _gate_preview(
        cls,
        *,
        snapshot: Snapshot,
        team: str,
        metrics: dict[str, Any],
        focus_sequence: dict | None,
        focus_events: list[dict],
        intent: str,
    ) -> GatePreview:
        if intent in ("UNKNOWN", "CHECK_SAMPLE", "COMPARE_MATCHES"):
            return GatePreview(assertion="none", refs=[], status="not_formed")
        assertion = cls._choose_assertion(metrics, focus_events, intent)
        if assertion != "none" and not assertion_supported(assertion, snapshot, team):
            assertion = "none"
        if assertion == "none":
            return GatePreview(assertion="none", refs=[], status="not_formed")
        refs = sorted(required_refs(assertion, team))
        level = {
            "goal_sequence": 1,
            "possession_without_penetration": 2,
            "attacking_threat_increased": 2,
            "recoveries_followed_by_shots": 3,
        }.get(assertion, 2)
        event_ids = sorted({
            event_id
            for ref in refs
            for event_id in snapshot.data.get("receipts", {}).get(ref, {}).get("event_ids", [])
        })
        statement = evidence_summary(assertion, snapshot, team)[1]
        claim = {
            "claim_id": f"claim-{assertion.replace('_', '-')}-{team.lower()}",
            "claim_level": level,
            "text": statement,
            "evidence_scope": {"event_ids": event_ids, "metric_ids": refs},
            "assumptions": ["Frozen snapshot receipts are the evidence boundary."],
            "counterevidence": [],
            "verification_method": "Gate 2.0 preview; not persisted",
            "metric_versions": {"oaai": "1.0.0"},
        }
        verdict = publication_gate_2_0(
            claim,
            snapshot.data.get("events", []),
            catalog_metric_ids=set(snapshot.data.get("receipts", {})),
        )
        return GatePreview(
            assertion=assertion,
            refs=refs,
            status=verdict.status,  # type: ignore[arg-type]
            violations=verdict.rule_violations,
            statement=statement,
            claim_level=level,
            persisted=False,
        )

    @staticmethod
    def _finish(
        *,
        run: InvestigationRun,
        investigation_id: str,
        match_id: str,
        snapshot: Snapshot,
        team: str,
        question: str,
        intent: IntentType,
        confidence: float,
        focus_type: str,
        focus_id: str | None,
        scope: InvestigationScope,
        dataset_revision: str | None,
        coverage: dict[str, Any],
        completeness: dict[str, Any],
        receipts: list[ToolReceipt],
        findings: list[Finding],
        explanations: list[CandidateExplanation],
        gate: GatePreview,
        selected: list[str],
        unresolved: list[str],
        required_scope: list[str],
        started: float,
        state: str | None = None,
        ledger: dict[str, Any] | None = None,
    ) -> InvestigationPlan:
        final_state: InvestigationState = (state or run.state)  # type: ignore[assignment]
        not_inferable = [
            "Opponent defensive line height, compactness and pressing intent.",
            "Individual player fatigue, injury or coaching instructions.",
            "Causal effect of a tactical change without a counterfactual design.",
        ]
        return InvestigationPlan(
            investigation_id=investigation_id,
            match_id=match_id,
            snapshot_id=snapshot.id,
            as_of=int(snapshot.data.get("as_of", 0)),
            team=team,
            focus_type=focus_type,
            focus_id=focus_id,
            question=question,
            intent=intent,
            intent_confidence=confidence,
            scope=scope,
            state=final_state,
            state_history=list(run.history),
            dataset_revision=dataset_revision,
            coverage=coverage,
            completeness=completeness,
            selected_metrics=selected,
            oaai_ledger=ledger,
            tool_receipts=receipts,
            findings=findings,
            explanations=explanations,
            gate_preview=gate,
            not_inferable=not_inferable,
            unresolved=unresolved,
            required_scope=required_scope,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
        )


class InvestigationStore:
    """Small durable store for pending investigation plans."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else None
        self.plans: dict[str, InvestigationPlan] = {}
        self._load()

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            for raw in payload.get("investigations", []):
                plan = InvestigationPlan.model_validate(raw)
                self.plans[plan.investigation_id] = plan
        except Exception:
            self.plans = {}

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "investigations-v1",
            "investigations": [plan.model_dump() for plan in self.plans.values()],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def save(self, plan: InvestigationPlan) -> InvestigationPlan:
        self.plans[plan.investigation_id] = plan
        self._save()
        return plan

    def get(self, investigation_id: str) -> InvestigationPlan | None:
        return self.plans.get(investigation_id)

    def cancel(self, investigation_id: str) -> InvestigationPlan:
        plan = self.plans.get(investigation_id)
        if plan is None:
            raise KeyError("investigation_not_found")
        if plan.state in ("APPROVED", "QUALIFIED", "WITHHELD", "FAILED", "CANCELLED"):
            raise ValueError("investigation_terminal")
        plan.state = "CANCELLED"
        plan.state_history.append({"state": "CANCELLED", "at": time.time(), "reason": "cancelled by user"})
        self._save()
        return plan
