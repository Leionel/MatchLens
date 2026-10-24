"""Auditable football investigation planner.

This is a deterministic investigation slice, not an LLM run. It turns a selected
anomaly (OAAI point, event, sequence or metric) into a bounded tool plan,
retrieves real evidence, proposes competing explanations and produces a gate
preview. Every tool call is receipted with the frozen snapshot identity.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import assertion_supported, evidence_summary, required_refs
from .football import Snapshot, build_sequences, event_attacking_x
from .gate import publication_gate_2_0
from .metrics import MetricsService


class ToolReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence: int
    tool: str
    args: dict[str, Any]
    status: Literal["ok", "unavailable", "skipped"]
    snapshot_id: str
    dataset_revision: str | None
    result_sha256: str | None = None
    summary: str = ""


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding_id: str
    level: Literal[1, 2, 3, 4]
    statement: str
    event_ids: list[str] = Field(default_factory=list)
    metric_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class CandidateExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    explanation_id: str
    hypothesis: str
    status: Literal["supported", "qualified", "rejected", "insufficient_evidence"]
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
    persisted: bool = False


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
    execution_mode: Literal["deterministic_planner"] = "deterministic_planner"
    agent_status: Literal["not_run", "run"] = "not_run"
    dataset_revision: str | None
    coverage: dict[str, Any]
    tool_receipts: list[ToolReceipt]
    findings: list[Finding]
    explanations: list[CandidateExplanation]
    gate_preview: GatePreview
    not_inferable: list[str]
    unresolved: list[str]


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:20]


def _short(value: Any, limit: int = 500) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "..."


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
    ) -> InvestigationPlan:
        team = "N" if team == "N" else "H"
        events = state.get("events", [])
        coverage = snapshot.data.get("coverage", {})
        dataset_revision = snapshot.data.get("dataset_revision") or snapshot.data.get("data_version")
        receipts: list[ToolReceipt] = []
        counter = 0

        def receipt(tool: str, args: dict, result: Any, *, status: str = "ok", summary: str = "") -> None:
            nonlocal counter
            counter += 1
            receipts.append(ToolReceipt(
                sequence=counter,
                tool=tool,
                args=args,
                status=status,  # type: ignore[arg-type]
                snapshot_id=snapshot.id,
                dataset_revision=dataset_revision,
                result_sha256=_hash(result) if result is not None else None,
                summary=summary,
            ))

        receipt(
            "get_match_context",
            {"match_id": match_id},
            {"as_of": snapshot.data.get("as_of"), "coverage": coverage, "dataset_revision": dataset_revision},
            summary=f"Frozen at {snapshot.data.get('as_of')}s; coverage={coverage.get('score_status')}",
        )

        focus_events: list[dict] = []
        focus_sequence = None
        focus_label = focus_id or "latest observed moment"

        # Resolve the user's focus to real events.
        if focus_type == "event" and focus_id:
            focus_events = [e for e in events if str(e.get("id")) == str(focus_id)]
            if focus_events:
                seqs = build_sequences(state)
                focus_sequence = next(
                    (s for s in seqs if focus_id in s["event_ids"]),
                    None,
                )
        elif focus_type in ("sequence", "moment") and focus_id:
            seqs = build_sequences(state)
            focus_sequence = next(
                (s for s in seqs if s["sequence_id"] == focus_id or str(s["possession_id"]) == str(focus_id)),
                None,
            )
            if focus_sequence:
                focus_events = [e for e in events if e.get("id") in focus_sequence["event_ids"]]
        elif focus_type == "metric" and focus_id:
            metric = MetricsService.query(snapshot, focus_id, team=team, window="current", match_id=match_id)
            receipt("query_metric", {"metric_id": focus_id, "team": team, "window": "current"}, metric.model_dump(), summary=f"{focus_id}: {metric.value} ({metric.status})")
            focus_events = [e for e in events if str(e.get("id")) in set(metric.event_ids)]
        else:
            from .oaai import compute_oaai

            oaai = compute_oaai(events, smoothing_mode="causal")
            receipt("explain_oaai_contributors", {"team": team}, {"change_points": oaai.get("change_points", [])[:5]}, summary="OAAI change-point candidates")
            points = oaai.get("change_points", [])
            if points:
                point = max(points, key=lambda p: abs(float(p.get("oaai_amplitude", 0))))
                focus_events = [
                    e for e in events
                    if str(e.get("id")) in {c.get("event_id") for c in point.get("top_contributors", [])}
                ]
                focus_label = f"OAAI change point @ {point.get('at')}s"
                receipt("get_possession_sequence", {"event_ids": [e.get("id") for e in focus_events]}, {"count": len(focus_events)}, summary="Contributors at the selected OAAI change point")

        # Query a fixed comparable metric panel; every missing value stays null.
        metric_ids = ["possession", "shots", "entries", "high_recoveries", "transition_shots", "goals"]
        metrics: dict[str, Any] = {}
        for metric_id in metric_ids:
            value = MetricsService.query(snapshot, metric_id, team=team, window="current", match_id=match_id)
            metrics[metric_id] = value.model_dump()
            receipt("query_metric", {"metric_id": metric_id, "team": team, "window": "current"}, value.model_dump(), summary=f"{metric_id}: {value.value} ({value.status})")

        receipt("search_events", {"team": team, "limit": 12}, [e.get("id") for e in focus_events[:12]], summary=f"{len(focus_events)} focus events")

        # Competing explanations are deterministic predicates over observed facts.
        explanations: list[CandidateExplanation] = []
        trans = metrics["transition_shots"]["value"]
        high = metrics["high_recoveries"]["value"]
        entries = metrics["entries"]["value"]
        shots = metrics["shots"]["value"]
        possession = metrics["possession"]["value"]

        if isinstance(trans, (int, float)) and trans >= 2:
            explanations.append(CandidateExplanation(
                explanation_id="expl-transition",
                hypothesis="A recovery-to-shot pattern is present in this window.",
                status="supported",
                supporting_evidence=[f"{team}.transition_shots.current", f"{team}.high_recoveries.current"],
                counterevidence=[],
                verification="Count shots within 10s of a recovery in the same possession.",
                limitations=["This is a temporal association, not evidence of a pressing plan."],
            ))
        else:
            explanations.append(CandidateExplanation(
                explanation_id="expl-transition",
                hypothesis="A recovery-to-shot pattern explains the selected event.",
                status="insufficient_evidence",
                supporting_evidence=[],
                counterevidence=[f"{team}.transition_shots.current"],
                verification="Requires at least two linked recovery-to-shot chains.",
                limitations=["The current window contains fewer than two linked chains."],
            ))

        if isinstance(entries, (int, float)) and isinstance(shots, (int, float)):
            explanations.append(CandidateExplanation(
                explanation_id="expl-progression",
                hypothesis="Recorded final-third progression is present alongside the attacking activity.",
                status="supported" if entries > 0 else "insufficient_evidence",
                supporting_evidence=[f"{team}.entries.current", f"{team}.shots.current"],
                counterevidence=[],
                verification="Trace final-third entries and shots in the selected possession chain.",
                limitations=["Entry and shot counts are on-ball observations; chance quality is not measured."],
            ))

        explanations.append(CandidateExplanation(
            explanation_id="expl-pressing-intent",
            hypothesis="The opponent's pressing structure caused the turnover.",
            status="insufficient_evidence",
            supporting_evidence=[],
            counterevidence=[f"{team}.high_recoveries.current"],
            verification="Requires 22-player off-ball tracking and pressure distances.",
            limitations=["The snapshot contains on-ball events only."],
        ))

        findings: list[Finding] = []
        focus_ids = [str(e.get("id")) for e in focus_events if e.get("id")]
        if focus_events:
            first = focus_events[0]
            findings.append(Finding(
                finding_id="finding-focus",
                level=1,
                statement=(
                    f"Selected {focus_label}: {len(focus_events)} recorded event(s) between "
                    f"{first.get('t')}s and {focus_events[-1].get('t')}s."
                ),
                event_ids=focus_ids,
                metric_ids=[],
                limitations=["Recorded events only; no off-ball positions."],
            ))
        if isinstance(possession, (int, float)):
            findings.append(Finding(
                finding_id="finding-possession",
                level=2,
                statement=f"Controlled possession share in the current window is {possession:g}%.",
                metric_ids=[f"{team}.possession.current"],
                limitations=["Possession share measures controlled time, not territory or intent."],
            ))

        gate_preview = cls._gate_preview(snapshot, team, metrics, focus_sequence)
        if gate_preview.assertion != "none":
            receipt("publication_gate_2_0", {"assertion": gate_preview.assertion, "refs": gate_preview.refs}, gate_preview.model_dump(), summary=f"Gate preview: {gate_preview.status}")

        not_inferable = [
            "Opponent defensive line height, compactness and pressing intent.",
            "Individual player fatigue, injury or coaching instructions.",
            "Causal effect of a tactical change without a counterfactual design.",
        ]
        unresolved = [
            "Chance quality requires a calibrated xG model.",
            "Cross-match base rates require complete, comparable matches.",
        ]
        if coverage.get("continuous") is False:
            unresolved.append("Partial event coverage: unobserved intervals remain Unknown.")

        return InvestigationPlan(
            investigation_id="inv-" + _hash({"snapshot": snapshot.id, "focus": focus_id, "team": team, "question": question}),
            match_id=match_id,
            snapshot_id=snapshot.id,
            as_of=int(snapshot.data.get("as_of", 0)),
            team=team,
            focus_type=focus_type,
            focus_id=focus_id,
            question=question,
            dataset_revision=dataset_revision,
            coverage=coverage,
            tool_receipts=receipts,
            findings=findings,
            explanations=explanations,
            gate_preview=gate_preview,
            not_inferable=not_inferable,
            unresolved=unresolved,
        )

    @staticmethod
    def _gate_preview(
        snapshot: Snapshot,
        team: str,
        metrics: dict[str, Any],
        sequence: dict | None,
    ) -> GatePreview:
        assertion = "none"
        if (
            isinstance(metrics["transition_shots"]["value"], (int, float))
            and metrics["transition_shots"]["value"] >= 2
            and assertion_supported("recoveries_followed_by_shots", snapshot, team)
        ):
            assertion = "recoveries_followed_by_shots"
        elif (
            isinstance(metrics["shots"]["value"], (int, float))
            and isinstance(metrics["entries"]["value"], (int, float))
            and metrics["shots"]["value"] > 0
            and metrics["entries"]["value"] > 0
            and assertion_supported("attacking_threat_increased", snapshot, team)
        ):
            assertion = "attacking_threat_increased"
        elif assertion_supported("possession_without_penetration", snapshot, team):
            assertion = "possession_without_penetration"
        elif metrics["goals"]["value"]:
            assertion = "goal_sequence"
        if assertion == "none":
            return GatePreview(assertion="none", refs=[], status="not_formed", statement="No gate-eligible assertion from this focus.")
        refs = sorted(required_refs(assertion, team))
        claim = {
            "claim_id": f"claim-{assertion.replace('_', '-')}-{team.lower()}",
            "claim_level": 3 if assertion == "recoveries_followed_by_shots" else 2,
            "text": evidence_summary(assertion, snapshot, team)[1],
            "evidence_scope": {"event_ids": [e for r in refs for e in snapshot.data.get("receipts", {}).get(r, {}).get("event_ids", [])], "metric_ids": refs},
            "assumptions": ["Frozen snapshot receipts are the evidence boundary."],
            "counterevidence": [],
            "verification_method": "Gate 2.0 preview; not persisted",
            "metric_versions": {"oaai": "1.0.0"},
        }
        verdict = publication_gate_2_0(claim, snapshot.data.get("events", []), catalog_metric_ids=set(snapshot.data.get("receipts", {})))
        return GatePreview(
            assertion=assertion,
            refs=refs,
            status=verdict.status,  # type: ignore[arg-type]
            violations=verdict.rule_violations,
            statement=evidence_summary(assertion, snapshot, team)[1],
            persisted=False,
        )
