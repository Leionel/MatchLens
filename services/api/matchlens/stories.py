"""Broadcast story engine bound to a trusted claim registry.

Story approval is derived exclusively from persisted gate verdicts and
editorial decisions. Caller-supplied booleans/status strings are ignored by
design: there is no parameter through which a caller can claim approval.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .football import event_attacking_x
from .oaai import compute_oaai
from .registry import ClaimRecord, ClaimRegistry
from .schema import NormalizedEvent


AudiencePerspective = Literal["coach", "media", "fan"]


class StoryChapter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chapter_id: str
    title: str
    minute_span: str
    time_start_s: float
    time_end_s: float
    narrative: str
    dominant_team: str
    oaai_trend: Literal["home_surge", "away_surge", "balanced_stalemate", "chaotic_turnovers", "unobserved"]
    verified_claim_refs: list[str]
    supporting_event_ids: list[str]
    tactical_tags: list[str]


class MatchStory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    story_id: str
    match_id: str
    snapshot_id: str
    headline: str
    subtitle: str
    perspective: AudiencePerspective
    generated_at: str
    approval_status: Literal[
        "approved_for_broadcast",
        "draft_pending_gate",
        "draft_pending_editorial",
        "contested",
    ]
    chapters: list[StoryChapter]
    summary_verdict: str
    approved_claims_count: int
    gate_verified_claims_count: int
    coverage: dict[str, Any]
    dataset_revision: str | None = None
    stale_claim_ids: list[str] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)


class PerspectiveViewData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    perspective: AudiencePerspective
    title: str
    description: str
    primary_metrics: list[dict[str, Any]]
    highlighted_sequences: list[str]
    recommended_focus_areas: list[str]


class ExportPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    export_format: Literal["json", "svg", "markdown"]
    filename: str
    payload: str
    signature: str


def _event_time(ev: Any) -> float:
    for attr in ("clock_seconds", "timestamp_seconds", "t", "second"):
        val = getattr(ev, attr, None) if not isinstance(ev, dict) else ev.get(attr)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
    return 0.0


def _event_id(ev: Any, fallback: str = "") -> str:
    for attr in ("event_id", "id", "index"):
        val = getattr(ev, attr, None) if not isinstance(ev, dict) else ev.get(attr)
        if val is not None:
            return str(val)
    return fallback


def _team(ev: Any) -> str:
    val = ev.get("team") if isinstance(ev, dict) else getattr(ev, "team", None)
    if val in ("H", "N"):
        return val
    val = ev.get("team_id") if isinstance(ev, dict) else getattr(ev, "team_id", "")
    return "H" if str(val) == "H" else "N" if str(val) == "N" else ""


def _kind(ev: Any) -> str:
    val = ev.get("kind") if isinstance(ev, dict) else getattr(ev, "action_type", None)
    if hasattr(val, "value"):
        val = val.value
    value = str(val or "").lower()
    for key in ("shot", "pass", "carry", "recovery", "restart"):
        if key in value:
            return key
    return "other"


def _coords(ev: Any, point: str) -> list[float] | None:
    value = ev.get(point) if isinstance(ev, dict) else None
    return value if isinstance(value, (list, tuple)) and len(value) >= 2 and value[0] is not None else None


class MatchStoryEngine:
    """Generates descriptive, evidence-bound narratives for a frozen snapshot."""

    @classmethod
    def generate_story(
        cls,
        match_id: str,
        events: list[dict[str, Any] | NormalizedEvent],
        registry: ClaimRegistry,
        snapshot_id: str,
        perspective: AudiencePerspective = "media",
        *,
        coverage: dict[str, Any] | None = None,
        dataset_revision: str | None = None,
        claim_ids: list[str] | None = None,
    ) -> MatchStory:
        if registry is None or not snapshot_id:
            raise ValueError("trusted_claim_registry_required")
        records = registry.records_for(match_id, snapshot_id)
        if claim_ids is not None:
            allowed = set(claim_ids)
            records = [record for record in records if record.claim_id in allowed]
        validity = {
            r.claim_id: registry.claim_validity(r, dataset_revision=dataset_revision)
            for r in records
        }
        stale_claim_ids = [claim_id for claim_id, check in validity.items() if not check["valid"]]
        valid_records = [r for r in records if validity[r.claim_id]["valid"]]
        gate_approved = [
            r for r in valid_records
            if r.gate_status == "approved" and r.lifecycle_status in ("current", "qualified")
        ]
        editorial_approved = [r for r in valid_records if r.broadcastable]
        rejected_editorially = [
            r for r in records
            if r.editorial_status == "rejected" or r.lifecycle_status == "withdrawn"
        ]

        coverage = coverage or {}
        duration = float(coverage.get("format_seconds") or 5400.0)
        start_clock = float(coverage.get("observed_start") or 0.0)
        end_clock = float(coverage.get("observed_end") or max((_event_time(e) for e in events), default=0.0))
        if end_clock <= 900.0 and duration <= 900.0:
            phase_boundaries = [
                (0.0, duration / 3.0, "0'–4'"),
                (duration / 3.0, duration * 2.0 / 3.0, "4'–8'"),
                (duration * 2.0 / 3.0, duration, "8'–12'"),
            ]
        else:
            phase_boundaries = [
                (0.0, duration / 3.0, "0'–30'"),
                (duration / 3.0, duration * 2.0 / 3.0, "30'–60'"),
                (duration * 2.0 / 3.0, duration, "60'–90'+"),
            ]

        oaai_dict = compute_oaai(events, smoothing_mode="causal") if events else {}
        oaai_points = oaai_dict.get("timeline", []) if isinstance(oaai_dict, dict) else []

        chapters: list[StoryChapter] = []
        for idx, (start_t, end_t, span) in enumerate(phase_boundaries):
            phase_events = [
                e for e in events
                if start_t <= _event_time(e) <= end_t
            ]
            shots = [e for e in phase_events if _kind(e) == "shot"]
            goals = [e for e in shots if str(e.get("outcome") if isinstance(e, dict) else getattr(e, "outcome", "")).lower() in ("goal", "own_goal", "own_goal_for")]
            passes = [e for e in phase_events if _kind(e) == "pass"]
            recoveries = [e for e in phase_events if _kind(e) == "recovery"]
            entries = 0
            progressive = 0
            for e in passes:
                if not isinstance(e, dict):
                    continue
                ax_s = event_attacking_x(e, point="start")
                ax_e = event_attacking_x(e, point="end")
                if ax_s is None or ax_e is None:
                    continue
                if ax_s <= 70 < ax_e:
                    entries += 1
                if ax_e - ax_s >= 12:
                    progressive += 1

            phase_points = [
                p for p in oaai_points
                if start_t <= float(p.get("timestamp_seconds", p.get("t", 0.0))) <= end_t
            ]
            avg_wave = (
                sum(float(p.get("oaai_value", p.get("smoothed_oaai", 0.0))) for p in phase_points) / len(phase_points)
                if phase_points else None
            )
            if avg_wave is None:
                dominant, trend = "NONE", "unobserved"
            elif avg_wave > 0.15:
                dominant, trend = "H", "home_surge"
            elif avg_wave < -0.15:
                dominant, trend = "N", "away_surge"
            else:
                dominant, trend = "NONE", "balanced_stalemate"

            goal_text = f"{len(goals)} goal(s)" if goals else "no goal"
            loc_note = "Locations are recorded for these events." if all(
                _coords(e, "start") for e in phase_events
            ) else "Some events have no recorded location; they are excluded from spatial counts."
            if perspective == "fan":
                narrative = (
                    f"{span}: {len(shots)} shot attempt(s), {goal_text} recorded. "
                    "All numbers come from the match event log; off-ball movement is not observed."
                )
                tags = ["recorded_events", f"shots_{len(shots)}", f"goals_{len(goals)}"]
            elif perspective == "coach":
                narrative = (
                    f"Phase {span}: {len(phase_events)} recorded on-ball actions, "
                    f"{len(passes)} passes, {progressive} progressive passes, {entries} final-third entries, "
                    f"{len(recoveries)} recoveries, {len(shots)} shots. These are event counts, "
                    "not proof of tactical intent; no off-ball positioning data is available. " + loc_note
                )
                tags = ["recorded_events", "progression_counts", "recovery_counts"]
            else:
                narrative = (
                    f"During {span}, {len(phase_events)} on-ball events were recorded: "
                    f"{len(passes)} passes, {len(shots)} shots and {goal_text}. "
                    "No off-ball positioning or tactical causation is measured."
                )
                tags = ["broadcast_factual", "recorded_events"]

            refs = [
                r.claim_id for r in gate_approved
                if max(0, r.as_of - 180) <= end_t and r.as_of >= start_t
            ]
            chapters.append(StoryChapter(
                chapter_id=f"chap-{idx+1}",
                title=["Opening phase", "Middle phase", "Final phase"][idx],
                minute_span=span,
                time_start_s=round(start_t, 1),
                time_end_s=round(end_t, 1),
                narrative=narrative,
                dominant_team=dominant,
                oaai_trend=trend,
                verified_claim_refs=refs,
                supporting_event_ids=[_event_id(e) for e in phase_events if _event_id(e)][:20],
                tactical_tags=tags,
            ))

        if rejected_editorially:
            approval_status = "contested"
        elif editorial_approved:
            approval_status = "approved_for_broadcast"
        elif gate_approved:
            approval_status = "draft_pending_editorial"
        else:
            approval_status = "draft_pending_gate"

        observed_note = (
            f"Observed event coverage ends at {end_clock:.0f}s of {duration:.0f}s."
            if end_clock and end_clock < duration - 1 else "Full continuous coverage."
        )
        if approval_status == "approved_for_broadcast":
            summary_verdict = (
                f"{len(editorial_approved)} claim(s) passed Gate 2.0 and carry an attributed editorial approval. "
                "The narrative remains a descriptive event summary; causal tactics are not asserted."
            )
            subtitle = "Gate-verified and editorially approved descriptive match summary"
        elif approval_status == "draft_pending_editorial":
            summary_verdict = (
                f"{len(gate_approved)} claim(s) passed the deterministic gate, but no editorial approval is recorded. "
                "This story is a draft and must not be broadcast as approved."
            )
            subtitle = "Draft: gate verified, editorial approval pending"
        elif approval_status == "contested":
            summary_verdict = "An editorial rejection exists for this snapshot; the story is contested."
            subtitle = "Contested: editorial review rejected at least one registered claim"
        else:
            summary_verdict = (
                "No gate-approved claim is registered for this snapshot. "
                "Only a short descriptive event summary is provided."
            )
            subtitle = "Draft: no gate-approved claims registered"

        return MatchStory(
            story_id=f"story-{match_id}-{perspective}-{snapshot_id[-10:]}",
            match_id=match_id,
            snapshot_id=snapshot_id,
            headline=f"Match summary: {match_id.replace('_', ' ').title()}",
            subtitle=subtitle,
            perspective=perspective,
            generated_at=datetime.now(timezone.utc).isoformat(),
            approval_status=approval_status,
            chapters=chapters,
            summary_verdict=f"{summary_verdict} {observed_note}",
            approved_claims_count=len(editorial_approved),
            gate_verified_claims_count=len(gate_approved),
            coverage=coverage,
            dataset_revision=dataset_revision,
            stale_claim_ids=stale_claim_ids,
            claims=[
                {
                    "claim_id": r.claim_id,
                    "assertion": r.assertion,
                    "claim_level": r.claim_level,
                    "gate_status": r.gate_status,
                    "gate_version": r.gate_version,
                    "gate_violations": r.gate_violations,
                    "editorial_status": r.editorial_status,
                    "editorial_approver": r.editorial_approver,
                    "evidence_hash": r.evidence_hash,
                    "source_run": r.source_run,
                    "as_of": r.as_of,
                    "dataset_revision": r.dataset_revision,
                    "lifecycle_status": r.lifecycle_status,
                    "revision_count": r.revision_count,
                    "evidence_scope": r.evidence_scope,
                }
                for r in valid_records
            ],
        )


class PerspectiveManager:
    """Metric hierarchy descriptions; no fabricated sequence identifiers."""

    @staticmethod
    def get_perspective_view(perspective: AudiencePerspective, match_id: str) -> PerspectiveViewData:
        if perspective == "coach":
            return PerspectiveViewData(
                perspective="coach",
                title="Coach & Tactical Analyst Perspective",
                description="Prioritizes recorded recoveries, channel progression and zone differentials. Off-ball shape is unavailable.",
                primary_metrics=[
                    {"label": "Post-turnover recovery counts", "importance": "critical", "source": "BL-03"},
                    {"label": "Action Density Differential (recorded actions)", "importance": "high", "source": "BL-04"},
                    {"label": "Attacking Channel Progression", "importance": "high", "source": "BL-08"},
                ],
                highlighted_sequences=[],
                recommended_focus_areas=["Zones with the highest recorded action share", "Recovery-to-shot chains"],
            )
        if perspective == "fan":
            return PerspectiveViewData(
                perspective="fan",
                title="Supporter & Deep Fan Perspective",
                description="Focuses on recorded shots, goals and progressive sequences.",
                primary_metrics=[
                    {"label": "Recorded goals and shots", "importance": "critical", "source": "Event stream"},
                    {"label": "Progressive passing sequences", "importance": "high", "source": "S2 Explorer"},
                    {"label": "Key recorded events", "importance": "medium", "source": "Event stream"},
                ],
                highlighted_sequences=[],
                recommended_focus_areas=["Recorded goals", "Final-third entries"],
            )
        return PerspectiveViewData(
            perspective="media",
            title="Broadcast & Commentary Perspective",
            description="Presents recorded event counts, OAAI change-points and explicitly unapproved/approved story state.",
            primary_metrics=[
                {"label": "OAAI momentum pulse (model output)", "importance": "critical", "source": "BL-02"},
                {"label": "Recorded match changes", "importance": "high", "source": "Event stream"},
                {"label": "Gate verdicts and editorial status", "importance": "critical", "source": "Claim registry"},
            ],
            highlighted_sequences=[],
            recommended_focus_areas=["Recorded goals", "Gate-verified claims"],
        )


class StoryExportEngine:
    """Exports structured data, SVG graphic badges, and formatted reports."""

    @staticmethod
    def export_story_package(story: MatchStory, export_format: Literal["json", "svg", "markdown"]) -> ExportPackage:
        if export_format == "json":
            payload = story.model_dump_json(indent=2)
            filename = f"{story.story_id}.json"
        elif export_format == "markdown":
            lines = [
                f"# {story.headline}",
                f"*{story.subtitle}*",
                f"**Perspective**: {story.perspective.upper()} | **Approval**: {story.approval_status}",
                f"**Snapshot**: {story.snapshot_id}",
                "",
                "---",
                "",
            ]
            for chap in story.chapters:
                lines.append(f"### {chap.minute_span}: {chap.title}")
                lines.append(f"> **OAAI trend**: {chap.oaai_trend} | **Dominant**: {chap.dominant_team}")
                lines.append("")
                lines.append(chap.narrative)
                lines.append("")
                lines.append(f"*Gate-verified claims*: {', '.join(chap.verified_claim_refs) or 'None'}")
                lines.append(f"*Tags*: {', '.join(chap.tactical_tags)}")
                lines.append("")
            lines.append("---")
            lines.append(f"**Verdict**: {story.summary_verdict}")
            payload = "\n".join(lines)
            filename = f"{story.story_id}.md"
        else:
            badge, color = {
                "approved_for_broadcast": ("EDITORIAL + GATE APPROVED", "#34d399"),
                "draft_pending_editorial": ("GATE VERIFIED · EDITORIAL PENDING", "#fbbf24"),
                "draft_pending_gate": ("NOT APPROVED · NO GATE CLAIM", "#f87171"),
                "contested": ("CONTESTED · NOT FOR BROADCAST", "#f87171"),
            }[story.approval_status]
            payload = (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 200" width="600" height="200">\n'
                f'  <rect width="600" height="200" rx="12" fill="#0b0f19" stroke="#1e293b" stroke-width="2"/>\n'
                f'  <text x="24" y="36" fill="#38bdf8" font-size="14" font-family="monospace">MATCHLENS BROADCAST CARD</text>\n'
                f'  <text x="24" y="70" fill="#f8fafc" font-size="20" font-weight="bold" font-family="sans-serif">{story.headline}</text>\n'
                f'  <text x="24" y="100" fill="#94a3b8" font-size="14" font-family="sans-serif">Chapters: {len(story.chapters)} | Claims: {story.approved_claims_count}</text>\n'
                f'  <rect x="24" y="125" width="240" height="28" rx="6" fill="{color}" fill-opacity="0.2"/>\n'
                f'  <text x="36" y="144" fill="{color}" font-size="12" font-weight="bold" font-family="sans-serif">{badge}</text>\n'
                f'</svg>'
            )
            filename = f"{story.story_id}.svg"

        return ExportPackage(
            export_format=export_format,
            filename=filename,
            payload=payload,
            signature=f"sha256-evidence-{story.snapshot_id[-16:]}",
        )
