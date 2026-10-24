"""Football Analytics Registry.

One definition and one execution path for every metric used by charts, Ask,
Agent tools, cross-match comparisons and story claims. A metric never becomes
numeric zero merely because its denominator or location is unobserved.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .football import Snapshot, event_attacking_x, metric_receipts, metric_receipts_for_range

MetricWindow = Literal["previous", "current", "match"]
MetricStatus = Literal["ok", "unobserved", "not_applicable", "missing_input", "not_calibrated", "not_available"]

# Window label used for arbitrary [start, end] second ranges. The registry keeps
# the discrete window labels untouched so existing callers are unaffected.
RANGE_WINDOW = "range"

# Metrics whose observation is produced by the football receipt layer
# (`football.metric_receipts`) rather than by the generic event scan.
RECEIPT_METRICS = (
    "possession",
    "shots",
    "entries",
    "high_recoveries",
    "transition_shots",
    "goals",
)


@lru_cache(maxsize=2)
def canonical_xt_model(resolution: str = "16x12"):
    """The single calibrated xT grid used by every OAAI computation.

    The registry, the chart endpoints and the contribution ledger must all use
    the same grid, otherwise the same activity index would be published with
    different numbers. The grid is immutable, so it is loaded once.
    """
    from .models.xt import ExpectedThreatModel

    return ExpectedThreatModel.load_default(resolution)


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


def _event_window(events: list[dict], start: float, end: float) -> list[dict]:
    """Events of the half-open interval (start, end]."""
    return [e for e in events if start < float(e.get("t", 0)) <= end]


def _receipt_key(metric_id: str, team: str, window: str) -> str:
    return f"{team}.{metric_id}.{window}"


# ==============================================================================
# Shared OAAI observation (registry <-> chart)
# ==============================================================================

def canonical_oaai_timeline(
    events: list[dict],
    *,
    t_end: float | None = None,
    dead_intervals: list[dict] | None = None,
    xt_model: Any = None,
) -> list[dict]:
    """The one causal OAAI timeline behind the registry and the chart.

    Both surfaces read the same timeline, so the same window yields the same
    peak. Layer A (event contributions) and Layer B (causal aggregation) are
    executed exactly once per call.
    """
    from .oaai import compute_oaai

    oaai = compute_oaai(
        events,
        smoothing_mode="causal",
        t_end=t_end,
        dead_intervals=dead_intervals or [],
        xt_model=xt_model if xt_model is not None else canonical_xt_model(),
    )
    return list(oaai.get("timeline", []))


def oaai_window_observation(
    timeline: list[dict],
    *,
    events: list[dict],
    team: str,
    start: float,
    end: float,
    dead_intervals: list[dict] | None = None,
    xt_model: Any = None,
) -> dict[str, Any]:
    """Registry observation of `oaai` for one team inside (start, end].

    The peak selection and the contribution ledger are shared with the chart
    endpoint, so the registry and the chart publish the same value and the
    same event ids for the same window. An unobserved window stays `None`;
    it never collapses to zero.
    """
    from .oaai import compute_oaai_contribution_ledger, oaai_window_peak

    team = "N" if team == "N" else "H"
    scoped = [
        e for e in (events or [])
        if start < float(e.get("t", 0)) <= end
        and e.get("team") == team
        and e.get("kind") != "end"
    ]
    empty = {
        "status": "unobserved",
        "value": None,
        "peak_at": None,
        "event_ids": [],
        "value_basis": "smoothed_team_intensity",
        "raw_team_intensity": None,
        "raw_net_contribution": None,
        "contribution_count": 0,
        "half_life_seconds": None,
        "top_contributions": [],
    }
    if not scoped:
        return dict(empty)
    peak = oaai_window_peak(timeline, team, start, end)
    if peak is None:
        return dict(empty)
    peak_at = float(peak["peak_at"])
    ledger = compute_oaai_contribution_ledger(
        events,
        at=peak_at,
        team=team,
        dead_intervals=dead_intervals or [],
        xt_model=xt_model if xt_model is not None else canonical_xt_model(),
        smoothing_mode="causal",
        limit=8,
        timeline=timeline,
    )
    event_ids = [
        row["event_id"] for row in ledger["contributions"]
        if row.get("team") == team
    ]
    return {
        "status": "ok",
        "value": round(float(peak["value"]), 4),
        "peak_at": round(peak_at, 2),
        "event_ids": event_ids,
        "value_basis": "smoothed_team_intensity",
        "raw_team_intensity": ledger["raw_team_intensity"],
        "raw_net_contribution": ledger["raw_net_contribution"],
        "contribution_count": ledger["contribution_count"],
        "half_life_seconds": ledger["half_life_seconds"],
        "top_contributions": ledger["contributions"][:6],
    }


def registry_oaai_comparison(
    snapshot: Snapshot,
    timeline: list[dict],
    *,
    teams: tuple[str, ...] = ("H", "N"),
    windows: tuple[str, ...] = ("previous", "current", "match"),
    registry_comparable: bool = True,
    reason: str | None = None,
    chart_smoothing_mode: str = "causal",
    data: dict | None = None,
) -> dict[str, Any]:
    """Consistency statement between a chart OAAI timeline and the registry.

    The observations are produced with the registry's own peak rule and
    contribution ledger, so the chart can state - instead of imply - whether
    it publishes the same number as `MetricsService.query(...)`.
    """
    data = data if data is not None else snapshot.data
    as_of = int(data.get("as_of", 0))
    events = data.get("events", [])
    dead_intervals = data.get("dead_intervals", [])
    coverage = data.get("coverage", {})
    coverage_status = (
        "complete" if coverage.get("continuous") is True
        else "partial" if coverage.get("continuous") is False
        else "unknown"
    )
    dataset_revision = data.get("dataset_revision") or data.get("data_version")
    observations: dict[str, dict[str, Any]] = {}
    for team in teams:
        team_observations: dict[str, Any] = {}
        for window in windows:
            start, end = _window_bounds(as_of, window)
            obs = oaai_window_observation(
                timeline,
                events=events,
                team=team,
                start=start,
                end=end,
                dead_intervals=dead_intervals,
                xt_model=canonical_xt_model(),
            )
            team_observations[window] = {
                "metric_id": "oaai",
                "team": team,
                "window": window,
                "window_start_s": start,
                "window_end_s": end,
                "value": obs["value"],
                "status": obs["status"],
                "unit": "dimensionless",
                "peak_at": obs["peak_at"],
                "value_basis": obs["value_basis"],
                "event_ids": obs["event_ids"],
                "event_count": len(obs["event_ids"]),
                "metric_version": "football-v2",
                "computation_version": "metrics-v2",
                "model_version": "oaai-1.0.0",
                "coverage_status": coverage_status,
                "dataset_revision": dataset_revision,
                "snapshot_id": snapshot.id,
            }
        observations[team] = team_observations
    return {
        "metric_id": "oaai",
        "registry_comparable": registry_comparable,
        "reason": reason,
        "chart_smoothing_mode": chart_smoothing_mode,
        "registry_smoothing_mode": "causal",
        "snapshot_id": snapshot.id,
        "snapshot_as_of": as_of,
        "value_basis": "smoothed_team_intensity",
        "observations": observations,
        "disclaimer": (
            "Registry 观测与图表使用同一因果 OAAI 时间线与同一峰值规则；"
            "双方数值口径一致时不重复计算。"
        ),
    }


def registry_recoveries_comparison(
    snapshot: Snapshot,
    *,
    window_seconds: float = 6.0,
    focus_team: str = "H",
    teams: tuple[str, ...] = ("H", "N"),
    data: dict | None = None,
) -> dict[str, Any]:
    """Consistency statement between the BL-03 quick-recovery chart and the registry.

    The chart counts possessions regained within `window_seconds` of a
    possession loss - a regain by a pass or a shot counts as well. The
    registry publishes `recoveries` (count of recorded recovery events) and
    `high_recoveries` (located recoveries in the attacking third). These are
    different metrics, so the chart is explicitly reported as *not*
    comparable and the registry's own numbers are published beside it
    instead of a fabricated match.
    """
    data = data if data is not None else snapshot.data
    as_of = int(data.get("as_of", 0))
    observations: dict[str, Any] = {}
    for team in teams:
        team_observations: dict[str, Any] = {}
        for metric_id in ("recoveries", "high_recoveries"):
            value = MetricsService.query_range(
                snapshot,
                metric_id,
                team=team,
                start_s=0,
                end_s=as_of,
            )
            team_observations[metric_id] = {
                "metric_id": metric_id,
                "team": team,
                "window": RANGE_WINDOW,
                "window_start_s": 0,
                "window_end_s": as_of,
                "value": value.value,
                "status": value.status,
                "unit": value.unit,
                "definition": value.definition,
                "event_count": len(value.event_ids),
                "event_ids": value.event_ids,
                "metric_version": value.metric_version,
                "computation_version": value.computation_version,
                "coverage_status": value.coverage_status,
                "dataset_revision": value.dataset_revision,
                "snapshot_id": value.snapshot_id,
            }
        observations[team] = team_observations
    return {
        "metric_id": "quick_recoveries",
        "registry_comparable": False,
        "reason": (
            "quick_recovery_window_is_not_a_registry_metric: "
            f"the chart counts possessions regained within {window_seconds}s of a "
            "possession loss (a pass or a shot also counts as a regain), while the "
            "registry publishes 'recoveries' (recorded recovery events) and "
            "'high_recoveries' (located recoveries in the attacking third)"
        ),
        "chart_metric": {
            "metric_id": "quick_recoveries",
            "window_seconds": window_seconds,
            "focus_team": focus_team,
            "interval": "observed prefix (0, as_of]",
        },
        "registry_smoothing_mode": None,
        "snapshot_id": snapshot.id,
        "snapshot_as_of": as_of,
        "observations": observations,
        "disclaimer": (
            "图表与 Registry 使用不同口径，不做等值声明；仅并列展示 Registry 观测供参考。"
        ),
    }


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
        """Observation for one of the three discrete registry windows."""
        definition = DEFINITIONS.get(metric_id)
        if definition is None:
            raise KeyError("metric_not_registered")
        data = snapshot.data
        as_of = int(data.get("as_of", 0))
        start, end = _window_bounds(as_of, window)
        return cls._evaluate(
            data,
            snapshot.id,
            metric_id,
            team=team,
            window_label=window,
            start=start,
            end=end,
            match_id=match_id,
        )

    @classmethod
    def query_range(
        cls,
        snapshot: Snapshot,
        metric_id: str,
        team: str = "H",
        start_s: float = 0.0,
        end_s: float | None = None,
        match_id: str | None = None,
    ) -> MetricValue:
        """Observation for an arbitrary [start_s, end_s] second range.

        The range flavour runs through exactly the same computation as the
        discrete windows (`_evaluate`), so a metric never has two formulas.
        An illegal range (end <= start, negative start, or a bound beyond the
        frozen snapshot) is reported as `not_applicable` with a null value
        instead of a fabricated number; an observed-but-empty range stays
        `unobserved` with a null value and never collapses to zero.
        """
        definition = DEFINITIONS.get(metric_id)
        if definition is None:
            raise KeyError("metric_not_registered")
        data = snapshot.data
        start, end, reason = cls._resolve_range(data, start_s, end_s)
        if reason is not None:
            return cls._invalid_range(
                data, snapshot.id, metric_id, team, start, end,
                match_id=match_id,
                reason=reason,
            )
        return cls._evaluate(
            data,
            snapshot.id,
            metric_id,
            team=team,
            window_label=RANGE_WINDOW,
            start=start,
            end=end,
            match_id=match_id,
        )

    @classmethod
    def query_range_many(
        cls,
        snapshot: Snapshot,
        metric_ids: list[str],
        team: str = "H",
        start_s: float = 0.0,
        end_s: float | None = None,
        match_id: str | None = None,
    ) -> list[MetricValue]:
        """Several range observations for one team and one interval.

        The frozen snapshot is parsed once; every metric still goes through the
        single `_evaluate` implementation, so batching cannot change a value.
        """
        data = snapshot.data
        start, end, reason = cls._resolve_range(data, start_s, end_s)
        results: list[MetricValue] = []
        for metric_id in metric_ids:
            if metric_id not in DEFINITIONS:
                raise KeyError("metric_not_registered")
            if reason is not None:
                results.append(
                    cls._invalid_range(
                        data, snapshot.id, metric_id, team, start, end,
                        match_id=match_id,
                        reason=reason,
                    )
                )
                continue
            results.append(
                cls._evaluate(
                    data,
                    snapshot.id,
                    metric_id,
                    team=team,
                    window_label=RANGE_WINDOW,
                    start=start,
                    end=end,
                    match_id=match_id,
                )
            )
        return results

    # ------------------------------------------------------------------ internals
    @classmethod
    def _resolve_range(
        cls,
        data: dict,
        start_s: float,
        end_s: float | None,
    ) -> tuple[float, float, str | None]:
        """Resolve a requested range into (start, end, rejection reason)."""
        as_of = int(data.get("as_of", 0))
        start = float(start_s)
        end = float(as_of if end_s is None else end_s)
        if start < 0:
            return start, end, "range_start_before_match_clock"
        if end <= start:
            return start, end, "range_end_not_after_start"
        if end > as_of:
            return start, end, "range_beyond_snapshot_as_of"
        return start, end, None

    @classmethod
    def _invalid_range(
        cls,
        data: dict,
        snapshot_id: str,
        metric_id: str,
        team: str,
        start: float,
        end: float,
        *,
        match_id: str | None,
        reason: str,
    ) -> MetricValue:
        definition = DEFINITIONS[metric_id]
        team = "N" if team == "N" else "H"
        coverage = data.get("coverage", {})
        coverage_status = (
            "complete" if coverage.get("continuous") is True
            else "partial" if coverage.get("continuous") is False
            else "unknown"
        )
        return MetricValue(
            metric_id=metric_id,
            match_id=match_id or str(data.get("match_id") or ""),
            snapshot_id=snapshot_id,
            team=team,
            window=RANGE_WINDOW,
            value=None,
            status="not_applicable",
            unit=definition.unit,
            numerator=None,
            denominator=None,
            event_ids=[],
            source_events=[],
            definition=definition.formula,
            version=definition.version,
            metric_version=definition.version,
            computation_version="metrics-v2",
            model_version=(
                "oaai-1.0.0" if metric_id == "oaai"
                else None if definition.model_status != "unavailable"
                else "unavailable"
            ),
            team_scope=team,
            match_scope=match_id or str(data.get("match_id") or ""),
            time_window=RANGE_WINDOW,
            coverage_status=coverage_status,
            dataset_revision=data.get("dataset_revision") or data.get("data_version"),
            coverage=coverage,
            limitations=definition.limitations,
            details={
                "reason": reason,
                "requested_start": start,
                "requested_end": end,
                "snapshot_as_of": int(data.get("as_of", 0)),
                "window_start": start,
                "window_end": end,
            },
        )

    @classmethod
    def _evaluate(
        cls,
        data: dict,
        snapshot_id: str,
        metric_id: str,
        *,
        team: str,
        window_label: str,
        start: float,
        end: float,
        match_id: str | None = None,
    ) -> MetricValue:
        """The one and only metric computation.

        `query()` and `query_range()` both funnel through this method, so the
        formula of a metric exists exactly once in the registry.
        """
        definition = DEFINITIONS.get(metric_id)
        if definition is None:
            raise KeyError("metric_not_registered")
        team = "N" if team == "N" else "H"
        events = data.get("events", [])
        coverage = data.get("coverage", {})
        as_of = int(data.get("as_of", 0))
        state = {
            **data,
            "at": as_of,
            "events": events,
            "intervals": data.get("intervals", []),
            "score": data.get("score", {"H": 0, "N": 0}),
        }
        coverage_status = (
            "complete" if coverage.get("continuous") is True
            else "partial" if coverage.get("continuous") is False
            else "unknown"
        )
        base = {
            "metric_id": metric_id,
            "match_id": match_id or str(data.get("match_id") or ""),
            "snapshot_id": snapshot_id,
            "team": team,
            "window": window_label,
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
            "time_window": window_label,
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

        if metric_id in RECEIPT_METRICS:
            # One formula for every window flavour, including the match-wide
            # window and any explicit range.
            receipts = metric_receipts_for_range(state, start, end, name=window_label)
            receipt = receipts.get(_receipt_key(metric_id, team, window_label))
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

        scoped = _event_window(events, start, end)
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
            from .oaai import compute_oaai

            dead_intervals = data.get("dead_intervals", [])
            xt_model = canonical_xt_model()
            oaai = compute_oaai(
                events,
                smoothing_mode="causal",
                t_end=end,
                dead_intervals=dead_intervals,
                xt_model=xt_model,
            )
            obs = oaai_window_observation(
                oaai.get("timeline", []),
                events=events,
                team=team,
                start=start,
                end=end,
                dead_intervals=dead_intervals,
                xt_model=xt_model,
            )
            if obs["status"] != "ok":
                return MetricValue(value=None, status="unobserved", event_ids=[], source_events=[], **base)
            event_ids = list(obs["event_ids"])
            return MetricValue(
                value=obs["value"],
                status="ok",
                numerator=round(float(obs["raw_team_intensity"]), 4),
                denominator=None,
                event_ids=event_ids,
                source_events=event_ids,
                details={
                    "peak_at": obs["peak_at"],
                    "value_basis": obs["value_basis"],
                    "raw_team_intensity": obs["raw_team_intensity"],
                    "raw_net_contribution": obs["raw_net_contribution"],
                    "contribution_count": obs["contribution_count"],
                    "half_life_seconds": obs["half_life_seconds"],
                    "window_start": start,
                    "window_end": end,
                    "top_contributions": obs["top_contributions"],
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
            details={
                "window_start": start,
                "window_end": end,
            },
            **base,
        )
