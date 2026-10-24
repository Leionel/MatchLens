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

from .football import Snapshot
from .metrics import MetricValue, MetricsService
from .registry import ClaimRecord, ClaimRegistry
from .schema import NormalizedEvent


AudiencePerspective = Literal["coach", "media", "fan"]

# Metrics the story reports per phase. Every one of them is observed through
# the metric registry (`MetricsService.query_range`), never recomputed here.
PHASE_METRIC_IDS: tuple[str, ...] = (
    "shots",
    "goals",
    "passes",
    "recoveries",
    "entries",
    "progressive_passes",
)

_METRIC_PHRASES: dict[str, tuple[str, str]] = {
    "shots": ("shot", "shots"),
    "goals": ("goal", "goals"),
    "passes": ("completed pass", "completed passes"),
    "recoveries": ("recovery", "recoveries"),
    "entries": ("final-third entry", "final-third entries"),
    "progressive_passes": ("progressive pass", "progressive passes"),
}

# Minimum absolute difference between the two teams' observed OAAI intensity
# before a phase is called a surge instead of a stalemate.
OAAI_TREND_THRESHOLD = 0.15

# Upper bound on the event slots copied into a chapter metric reference.
METRIC_REF_EVENT_LIMIT = 100


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
    # Provenance of every number quoted in the narrative. Additive only: the
    # approval semantics above are unchanged.
    metric_refs: list[dict[str, Any]] = Field(default_factory=list)


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


def _coords(ev: Any, point: str) -> list[float] | None:
    value = ev.get(point) if isinstance(ev, dict) else None
    return value if isinstance(value, (list, tuple)) and len(value) >= 2 and value[0] is not None else None


def _observed_number(value: float | int | None) -> str:
    """Render an observed metric value.

    An unobserved metric is never printed as zero; it is printed as
    "not observed" so the narrative cannot imply a measurement that the
    registry did not make.
    """
    if value is None:
        return "not observed"
    if isinstance(value, float):
        return f"{value:.2f}" if not float(value).is_integer() else str(int(value))
    return str(int(value))


def _metric_phrase(metric_id: str, value: float | int | None) -> str:
    """Noun phrase for an observed metric value (singular / plural)."""
    singular, plural = _METRIC_PHRASES[metric_id]
    if value == 1:
        return singular
    return plural


def _snapshot_for_metrics(
    events: list[dict[str, Any] | NormalizedEvent],
    snapshot_id: str,
    match_id: str,
    coverage: dict[str, Any] | None,
) -> Snapshot:
    """Minimal frozen snapshot for callers that only hold the event log.

    The story engine needs the event log and the frozen clock to query the
    registry; every number it publishes is computed by the registry from
    these inputs.
    """
    payload = {
        "schema": "evidence-v2",
        "match_id": match_id,
        "as_of": int(max((_event_time(e) for e in events), default=0.0)),
        "events": [e if isinstance(e, dict) else e.model_dump() for e in events],
        "intervals": [],
        "coverage": coverage or {},
        "score": {"H": 0, "N": 0},
    }
    return Snapshot(id=snapshot_id, canonical=json.dumps(payload, default=str))


def _metric_ref(
    observation: MetricValue,
    *,
    phase_start: float,
    phase_end: float,
    window_start: float,
    window_end: float,
    truncated: bool,
) -> dict[str, Any]:
    """Provenance record of one registry observation used by a chapter."""
    event_ids = list(observation.event_ids)
    ref: dict[str, Any] = {
        "metric_id": observation.metric_id,
        "team": observation.team,
        "window": observation.window,
        "window_start_s": window_start,
        "window_end_s": window_end,
        "phase_start_s": phase_start,
        "phase_end_s": phase_end,
        "window_truncated": truncated,
        "value": observation.value,
        "status": observation.status,
        "unit": observation.unit,
        "definition": observation.definition,
        "version": observation.version,
        "metric_version": observation.metric_version,
        "computation_version": observation.computation_version,
        "model_version": observation.model_version,
        "coverage_status": observation.coverage_status,
        "dataset_revision": observation.dataset_revision,
        "snapshot_id": observation.snapshot_id,
        "match_id": observation.match_id,
        "event_count": len(event_ids),
        "event_ids": event_ids[:METRIC_REF_EVENT_LIMIT],
        "event_ids_truncated": len(event_ids) > METRIC_REF_EVENT_LIMIT,
    }
    if observation.metric_id == "oaai" and "peak_at" in observation.details:
        ref["peak_at"] = observation.details["peak_at"]
    return ref


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
        snapshot: Snapshot | None = None,
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

        # Every number quoted below is observed through the metric registry.
        # The story engine never recomputes a metric of its own.
        metric_snapshot = snapshot or _snapshot_for_metrics(events, snapshot_id, match_id, coverage)
        snapshot_as_of = int(metric_snapshot.data.get("as_of", 0))

        chapters: list[StoryChapter] = []
        for idx, (start_t, end_t, span) in enumerate(phase_boundaries):
            phase_events = [
                e for e in events
                if start_t <= _event_time(e) <= end_t
            ]
            # The phase covers the whole match, the snapshot is frozen at
            # `as_of`. A phase that runs past the frozen clock is observed up
            # to the frozen clock only, and the truncation is recorded.
            obs_end = min(float(end_t), float(snapshot_as_of))
            truncated = obs_end < float(end_t)
            observable = obs_end > float(start_t)

            observations: dict[str, dict[str, MetricValue]] = {"H": {}, "N": {}}
            metric_refs: list[dict[str, Any]] = []
            for team in ("H", "N"):
                if not observable:
                    continue
                values = MetricsService.query_range_many(
                    metric_snapshot,
                    list(PHASE_METRIC_IDS),
                    team=team,
                    start_s=float(start_t),
                    end_s=obs_end,
                    match_id=match_id,
                )
                for observation in values:
                    observations[team][observation.metric_id] = observation
                    metric_refs.append(
                        _metric_ref(
                            observation,
                            phase_start=float(start_t),
                            phase_end=float(end_t),
                            window_start=float(start_t),
                            window_end=obs_end,
                            truncated=truncated,
                        )
                    )

            # OAAI trend comes from the registry observation of both teams.
            oaai_values: dict[str, MetricValue] = {}
            for team in ("H", "N"):
                if not observable:
                    continue
                observation = MetricsService.query_range(
                    metric_snapshot,
                    "oaai",
                    team=team,
                    start_s=float(start_t),
                    end_s=obs_end,
                    match_id=match_id,
                )
                oaai_values[team] = observation
                metric_refs.append(
                    _metric_ref(
                        observation,
                        phase_start=float(start_t),
                        phase_end=float(end_t),
                        window_start=float(start_t),
                        window_end=obs_end,
                        truncated=truncated,
                    )
                )

            home_oaai = oaai_values.get("H")
            away_oaai = oaai_values.get("N")
            home_value = home_oaai.value if home_oaai else None
            away_value = away_oaai.value if away_oaai else None
            if home_value is None and away_value is None:
                dominant, trend = "NONE", "unobserved"
            elif home_value is None:
                dominant, trend = "N", "away_surge"
            elif away_value is None:
                dominant, trend = "H", "home_surge"
            else:
                gap = float(home_value) - float(away_value)
                if gap > OAAI_TREND_THRESHOLD:
                    dominant, trend = "H", "home_surge"
                elif gap < -OAAI_TREND_THRESHOLD:
                    dominant, trend = "N", "away_surge"
                else:
                    dominant, trend = "NONE", "balanced_stalemate"

            def _team_line(team: str) -> str:
                label = "Home" if team == "H" else "Away"
                parts = []
                for metric_id in PHASE_METRIC_IDS:
                    observation = observations.get(team, {}).get(metric_id)
                    if observation is None:
                        parts.append(f"not observed {_metric_phrase(metric_id, None)}")
                    else:
                        parts.append(
                            f"{_observed_number(observation.value)} {_metric_phrase(metric_id, observation.value)}"
                        )
                return f"{label} recorded " + ", ".join(parts)

            def _team_value(team: str, metric_id: str) -> str:
                observation = observations.get(team, {}).get(metric_id)
                return _observed_number(observation.value if observation else None)

            home_line = _team_line("H")
            away_line = _team_line("N")
            truncated_note = (
                f" Observed up to {obs_end:.0f}s; the remainder of this phase is not yet in the snapshot."
                if truncated else ""
            )
            loc_note = "Locations are recorded for these events." if all(
                _coords(e, "start") for e in phase_events
            ) else "Some events have no recorded location; they are excluded from spatial counts."
            if perspective == "fan":
                narrative = (
                    f"{span}: {home_line}; {away_line}. "
                    "All numbers come from the match event log; off-ball movement is not observed."
                    + truncated_note
                )
                tags = [
                    "recorded_events",
                    f"shots_H{_team_value('H', 'shots')}_N{_team_value('N', 'shots')}",
                    f"goals_H{_team_value('H', 'goals')}_N{_team_value('N', 'goals')}",
                ]
            elif perspective == "coach":
                narrative = (
                    f"Phase {span}: {home_line}; {away_line}. These are event counts, "
                    "not proof of tactical intent; no off-ball positioning data is available. "
                    + loc_note + truncated_note
                )
                tags = ["recorded_events", "progression_counts", "recovery_counts"]
            else:
                narrative = (
                    f"During {span}, {home_line}; {away_line}. "
                    "No off-ball positioning or tactical causation is measured."
                    + truncated_note
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
                metric_refs=metric_refs,
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
