"""Football Analytics Registry.

One definition and one execution path for every metric used by charts, Ask,
Agent tools, cross-match comparisons and story claims. A metric never becomes
numeric zero merely because its denominator or location is unobserved.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .football import Snapshot, event_attacking_x, metric_receipts

MetricWindow = Literal["previous", "current", "match"]
MetricStatus = Literal["ok", "unobserved", "not_applicable", "missing_input", "not_calibrated", "not_available"]


class MetricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    label: str
    unit: str
    scope: Literal["team", "player", "match"]
    event_inputs: list[str]
    formula: str
    numerator_definition: str | None = None
    denominator_definition: str | None = None
    capabilities: list[str]
    missing_policy: str
    version: str = "football-v2"
    model_status: Literal["deterministic", "calibrated", "heuristic", "unavailable"] = "deterministic"
    limitations: list[str] = Field(default_factory=list)


class MetricValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    match_id: str
    snapshot_id: str
    team: str
    window: str
    value: float | int | None
    status: MetricStatus
    unit: str
    numerator: float | int | None = None
    denominator: float | int | None = None
    event_ids: list[str] = Field(default_factory=list)
    source_events: list[str] = Field(default_factory=list)
    definition: str
    version: str
    metric_version: str = "football-v2"
    computation_version: str = "metrics-v2"
    model_version: str | None = None
    team_scope: str = "team"
    player_scope: str | None = None
    match_scope: str | None = None
    time_window: str = "current"
    coverage_status: str = "unknown"
    dataset_revision: str | None = None
    coverage: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


DEFINITIONS: dict[str, MetricDefinition] = {
    "possession": MetricDefinition(
        metric_id="possession",
        label="Controlled possession share",
        unit="%",
        scope="team",
        event_inputs=["observed possession intervals"],
        formula="100 * own controlled seconds / controlled seconds of both teams",
        numerator_definition="own controlled seconds in the comparison window",
        denominator_definition="both teams' controlled seconds; dead-ball time excluded",
        capabilities=["event_data", "continuous_or_partial_with_caveat"],
        missing_policy="null / unobserved when the denominator is zero",
        model_status="deterministic",
        limitations=["Does not measure territory, intent or off-ball shape."],
    ),
    "shots": MetricDefinition(
        metric_id="shots",
        label="Shot attempts",
        unit="shots",
        scope="team",
        event_inputs=["Shot"],
        formula="count of shot events",
        capabilities=["event_data"],
        missing_policy="counts are observed; missing location does not remove the event",
    ),
    "entries": MetricDefinition(
        metric_id="entries",
        label="Attacking-third entries",
        unit="entries",
        scope="team",
        event_inputs=["Pass"],
        formula="first located pass per possession whose attack-relative x crosses 70m",
        capabilities=["located_events", "event_data"],
        missing_policy="null if no located pass exists; unlocated events are excluded, not centred",
        limitations=["Does not measure off-ball runs or progressive intent."],
    ),
    "high_recoveries": MetricDefinition(
        metric_id="high_recoveries",
        label="High recoveries",
        unit="recoveries",
        scope="team",
        event_inputs=["Ball Recovery", "Interception", "Tackle"],
        formula="count of located recoveries at attack-relative x >= 70m",
        capabilities=["located_events", "event_data"],
        missing_policy="null if no located recovery; no location is not a high recovery",
        limitations=["A recovery location is not proof of a pressing structure."],
    ),
    "transition_shots": MetricDefinition(
        metric_id="transition_shots",
        label="Recovery to shot <=10s",
        unit="shots",
        scope="team",
        event_inputs=["Ball Recovery", "Shot"],
        formula="count of shots <=10s after a recovery in the same possession without an intervening loss",
        capabilities=["event_data"],
        missing_policy="observed count; no inference when timestamps are absent",
        model_status="deterministic",
        limitations=["Temporal association only; not causal pressing evidence."],
    ),
    "goals": MetricDefinition(
        metric_id="goals",
        label="Recorded goals",
        unit="goals",
        scope="team",
        event_inputs=["Shot", "Own Goal"],
        formula="credited goals in the requested window; shootout goals excluded",
        capabilities=["event_data"],
        missing_policy="zero is a valid observed count; official final score is separate",
        limitations=["A partial prefix does not prove the final score."],
    ),
    "passes": MetricDefinition(
        metric_id="passes",
        label="Completed passes",
        unit="passes",
        scope="team",
        event_inputs=["Pass"],
        formula="count of pass events with outcome complete",
        capabilities=["event_data"],
        missing_policy="observed count",
    ),
    "progressive_passes": MetricDefinition(
        metric_id="progressive_passes",
        label="Progressive passes",
        unit="passes",
        scope="team",
        event_inputs=["Pass"],
        formula="located completed passes with >=12m forward gain or crossing 70m",
        capabilities=["located_events", "event_data"],
        missing_policy="null if no located passes exist",
    ),
    "carries": MetricDefinition(
        metric_id="carries",
        label="Carries",
        unit="carries",
        scope="team",
        event_inputs=["Carry"],
        formula="count of carry events",
        capabilities=["event_data"],
        missing_policy="observed count",
    ),
    "recoveries": MetricDefinition(
        metric_id="recoveries",
        label="Ball recoveries",
        unit="recoveries",
        scope="team",
        event_inputs=["Ball Recovery", "Interception", "Tackle"],
        formula="count of recorded recovery events",
        capabilities=["event_data"],
        missing_policy="observed count",
    ),
    "box_entries": MetricDefinition(
        metric_id="box_entries",
        label="Penalty-box entries",
        unit="entries",
        scope="team",
        event_inputs=["Pass"],
        formula="located passes ending inside the attacking penalty area",
        capabilities=["located_events", "event_data"],
        missing_policy="null if no located passes exist",
    ),
    "xg": MetricDefinition(
        metric_id="xg",
        label="Cumulative xG",
        unit="goals",
        scope="team",
        event_inputs=["Shot"],
        formula="requires a calibrated shot model; not available as a receipt in this build",
        capabilities=["calibrated_model"],
        missing_policy="not_available, never a fabricated zero",
        model_status="unavailable",
        limitations=["No trained/calibrated xG model receipt is present."],
    ),
    "oaai": MetricDefinition(
        metric_id="oaai",
        label="Observed Attacking Activity Index",
        unit="dimensionless",
        scope="team",
        event_inputs=["on-ball events"],
        formula="recorded weighted event contributions with causal exponential decay",
        capabilities=["event_data", "model_output"],
        missing_policy="model output only; unlocated events contribute without spatial terms",
        model_status="heuristic",
        limitations=["A model activity index, not psychological momentum or causality."],
    ),
}


def _window_bounds(as_of: int, window: MetricWindow) -> tuple[int, int]:
    if window == "match":
        return 0, as_of
    if window == "previous":
        return max(0, as_of - 360), max(0, as_of - 180)
    return max(0, as_of - 180), as_of


def _event_window(events: list[dict], as_of: int, window: MetricWindow) -> list[dict]:
    start, end = _window_bounds(as_of, window)
    return [e for e in events if start < float(e.get("t", 0)) <= end]


def _receipt_key(metric_id: str, team: str, window: MetricWindow) -> str:
    return f"{team}.{metric_id}.{window}"


class MetricsService:
    @classmethod
    def definitions(cls) -> list[MetricDefinition]:
        return list(DEFINITIONS.values())

    @classmethod
    def query(
        cls,
        snapshot: Snapshot,
        metric_id: str,
        team: str = "H",
        window: MetricWindow = "current",
        match_id: str | None = None,
    ) -> MetricValue:
        definition = DEFINITIONS.get(metric_id)
        if definition is None:
            raise KeyError("metric_not_registered")
        team = "N" if team == "N" else "H"
        data = snapshot.data
        events = data.get("events", [])
        coverage = data.get("coverage", {})
        receipts = metric_receipts({
            **data,
            "at": int(data.get("as_of", 0)),
            "events": events,
            "intervals": data.get("intervals", []),
            "score": data.get("score", {"H": 0, "N": 0}),
        })
        coverage_status = (
            "complete" if coverage.get("continuous") is True
            else "partial" if coverage.get("continuous") is False
            else "unknown"
        )
        base = {
            "metric_id": metric_id,
            "match_id": match_id or str(data.get("match_id") or ""),
            "snapshot_id": snapshot.id,
            "team": team,
            "window": window,
            "unit": definition.unit,
            "definition": definition.formula,
            "version": definition.version,
            "metric_version": definition.version,
            "computation_version": "metrics-v2",
            "model_version": (
                "oaai-1.0.0" if metric_id == "oaai"
                else None if definition.model_status != "unavailable"
                else "unavailable"
            ),
            "team_scope": team,
            "match_scope": match_id or str(data.get("match_id") or ""),
            "time_window": window,
            "coverage_status": coverage_status,
            "dataset_revision": data.get("dataset_revision") or data.get("data_version"),
            "coverage": coverage,
            "limitations": definition.limitations,
        }

        if definition.model_status == "unavailable":
            return MetricValue(
                value=None, status="not_calibrated", numerator=None, denominator=None,
                event_ids=[], source_events=[], **base,
            )

        if metric_id in ("possession", "shots", "entries", "high_recoveries", "transition_shots", "goals"):
            receipt = receipts.get(_receipt_key(metric_id, team, window))
            if receipt is None:
                return MetricValue(value=None, status="missing_input", event_ids=[], source_events=[], **base)
            value = receipt.get("value")
            status = receipt.get("status", "ok" if value is not None else "unobserved")
            return MetricValue(
                value=value,
                status=status,
                numerator=receipt.get("numerator"),
                denominator=receipt.get("denominator"),
                event_ids=list(receipt.get("event_ids", [])),
                source_events=list(receipt.get("event_ids", [])),
                details={
                    "receipt_id": receipt.get("id"),
                    "window_start": receipt.get("start"),
                    "window_end": receipt.get("end"),
                    "chains": receipt.get("chains", []),
                },
                **base,
            )

        as_of = int(data.get("as_of", 0))
        scoped = _event_window(events, as_of, window)
        team_events = [e for e in scoped if e.get("team") == team and e.get("kind") != "end"]
        located = [e for e in team_events if e.get("located")]
        if metric_id == "passes":
            selected = [e for e in team_events if e.get("kind") == "pass" and e.get("outcome") == "complete"]
            status = "ok"
        elif metric_id == "carries":
            selected = [e for e in team_events if e.get("kind") == "carry"]
            status = "ok"
        elif metric_id == "recoveries":
            selected = [e for e in team_events if e.get("kind") == "recovery"]
            status = "ok"
        elif metric_id == "progressive_passes":
            if not located:
                return MetricValue(value=None, status="unobserved", event_ids=[], **base)
            selected = []
            for e in located:
                if e.get("kind") != "pass" or e.get("outcome") != "complete":
                    continue
                ax_s = event_attacking_x(e, team, "start")
                ax_e = event_attacking_x(e, team, "end")
                if ax_s is not None and ax_e is not None and (ax_e - ax_s >= 12.0 or ax_s <= 70 < ax_e):
                    selected.append(e)
            status = "ok"
        elif metric_id == "box_entries":
            if not located:
                return MetricValue(value=None, status="unobserved", event_ids=[], **base)
            selected = []
            for e in located:
                if e.get("kind") != "pass" or e.get("outcome") != "complete" or not e.get("end"):
                    continue
                if event_attacking_x(e, team, "end") is not None and event_attacking_x(e, team, "end") >= 88.5:
                    ey = e["end"][1]
                    if ey is not None and 13.84 <= ey <= 54.16:
                        selected.append(e)
            status = "ok"
        elif metric_id == "oaai":
            from .oaai import compute_oaai, compute_oaai_contribution_ledger

            start, end = _window_bounds(as_of, window)
            if not team_events:
                return MetricValue(value=None, status="unobserved", event_ids=[], source_events=[], **base)
            dead_intervals = data.get("dead_intervals", [])
            oaai = compute_oaai(
                events,
                smoothing_mode="causal",
                t_end=end,
                dead_intervals=dead_intervals,
            )
            key = "home_smoothed" if team == "H" else "away_smoothed"
            points = [
                p for p in oaai.get("timeline", [])
                if start < float(p.get("t", 0.0)) <= end
            ]
            if not points:
                return MetricValue(value=None, status="unobserved", event_ids=[], source_events=[], **base)
            peak = max(points, key=lambda p: abs(float(p.get(key, 0.0))))
            peak_at = float(peak.get("t", 0.0))
            value = float(peak.get(key, 0.0))
            ledger = compute_oaai_contribution_ledger(
                events,
                at=peak_at,
                team=team,
                dead_intervals=dead_intervals,
                smoothing_mode="causal",
                limit=8,
            )
            event_ids = [
                row["event_id"] for row in ledger["contributions"]
                if row.get("team") == team
            ]
            return MetricValue(
                value=round(value, 4),
                status="ok",
                numerator=round(ledger["raw_team_intensity"], 4),
                denominator=None,
                event_ids=event_ids,
                source_events=event_ids,
                details={
                    "peak_at": round(peak_at, 2),
                    "value_basis": "smoothed_team_intensity",
                    "raw_team_intensity": ledger["raw_team_intensity"],
                    "raw_net_contribution": ledger["raw_net_contribution"],
                    "contribution_count": ledger["contribution_count"],
                    "half_life_seconds": ledger["half_life_seconds"],
                    "top_contributions": ledger["contributions"][:6],
                },
                **base,
            )
        else:
            return MetricValue(value=None, status="not_applicable", event_ids=[], source_events=[], **base)

        source_events = [str(e.get("id")) for e in selected if e.get("id")]
        return MetricValue(
            value=len(selected),
            status=status,
            numerator=len(selected),
            denominator=None,
            event_ids=source_events,
            source_events=source_events,
            **base,
        )
