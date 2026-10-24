"""Dataset completeness verification.

The final event timestamp is not evidence that a match is complete. This module
checks the source declaration, event conversion counts, period coverage,
provider consistency and integrity before a dataset may be treated as
``COMPLETE_VERIFIED``.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

CompletenessStatus = Literal[
    "COMPLETE_VERIFIED",
    "COMPLETE_CLAIMED_UNVERIFIED",
    "PARTIAL_OBSERVED",
    "SPARSE_SAMPLE_FIXTURE",
    "INVALID_CORRUPTED",
]


class DatasetCompleteness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CompletenessStatus
    synthetic: bool = False
    source_declaration: str = "unknown"
    raw_event_count: int = 0
    normalized_event_count: int = 0
    conversion_drop_count: int = 0
    drop_reasons: list[str] = Field(default_factory=list)
    observed_periods: list[int] = Field(default_factory=list)
    expected_periods: list[int] = Field(default_factory=list)
    coverage_by_period: list[dict[str, Any]] = Field(default_factory=list)
    expected_duration: float = 0.0
    observed_start: float | None = None
    observed_end: float | None = None
    known_missing_segments: list[str] = Field(default_factory=list)
    provider_consistency: bool = False
    integrity_checks: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    verified: bool = False
    notes: list[str] = Field(default_factory=list)

    @property
    def full_match_allowed(self) -> bool:
        return self.status == "COMPLETE_VERIFIED"


def _event_value(event: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(event, dict) and name in event:
            return event[name]
        if hasattr(event, name):
            return getattr(event, name)
    return default


def _event_clock(event: Any) -> float:
    value = _event_value(event, "clock_seconds", "clock", "t", default=0.0)
    return float(value or 0.0)


def _event_period(event: Any) -> int:
    value = _event_value(event, "period", default=1)
    return int(value or 1)


def _event_team(event: Any) -> str:
    return str(_event_value(event, "team_id", "team", default="") or "")


def _event_id(event: Any) -> str:
    return str(_event_value(event, "event_id", "id", default="") or "")


def verify_dataset_completeness(
    normalized_events: Sequence[Any],
    *,
    raw_event_count: int | None = None,
    expected_duration: float = 5400.0,
    source_declaration: str = "unknown",
    declared_complete: bool | None = None,
    synthetic: bool = False,
    conversion_drop_count: int = 0,
    drop_reasons: list[str] | None = None,
    expected_periods: Sequence[int] | None = None,
    team_ids: Sequence[str] | None = None,
) -> DatasetCompleteness:
    """Verify completeness from evidence, not from a final timestamp."""
    events = list(normalized_events)
    raw_count = int(raw_event_count if raw_event_count is not None else len(events))
    count = len(events)
    duration = float(expected_duration or 0.0)
    if expected_periods is None:
        expected_periods = (1, 2) if duration <= 5400 else (1, 2, 3, 4)
    expected_list = sorted(int(p) for p in expected_periods)

    integrity: list[dict[str, Any]] = []
    missing: list[str] = []
    notes: list[str] = []

    def check(name: str, passed: bool, detail: str = "") -> bool:
        integrity.append({"check": name, "passed": bool(passed), "detail": detail})
        return bool(passed)

    ids = [_event_id(event) for event in events]
    duplicate_ids = sorted(event_id for event_id, count in Counter(ids).items() if event_id and count > 1)
    invalid_clock = [
        _event_id(event) for event in events
        if _event_clock(event) < 0 or (duration and _event_clock(event) > duration + 120)
    ]
    allowed_teams = {str(team) for team in team_ids} if team_ids else {"H", "N"}
    unmapped_team = [
        _event_id(event) for event in events
        if not _event_team(event) or _event_team(event) not in allowed_teams
    ]
    periods = [_event_period(event) for event in events]
    clocks = [_event_clock(event) for event in events]
    observed_start = min(clocks) if clocks else None
    observed_end = max(clocks) if clocks else None

    check("events_present", count > 0, f"{count} normalized events")
    check("event_ids_present", all(ids), "every event has an ID")
    check("event_ids_unique", not duplicate_ids, f"duplicates={duplicate_ids[:5]}")
    check("clock_in_bounds", not invalid_clock, f"invalid={invalid_clock[:5]}")
    check("team_mapping_declared", not unmapped_team, f"unmapped={unmapped_team[:5]}")
    check("periods_present", all(period in periods for period in expected_list),
          f"observed={sorted(set(periods))}")
    check("conversion_accounted", raw_count >= count and conversion_drop_count >= 0,
          f"raw={raw_count} normalized={count} drops={conversion_drop_count}")

    period_rows: list[dict[str, Any]] = []
    period_count_min = max(8, int(duration / 120)) if duration else 8
    for period in expected_list:
        period_start = (period - 1) * duration / len(expected_list)
        period_end = period * duration / len(expected_list)
        period_clocks = [clock for clock, p in zip(clocks, periods) if p == period]
        period_events = sum(1 for p in periods if p == period)
        if period_clocks:
            p_start, p_end = min(period_clocks), max(period_clocks)
            span = max(0.0, p_end - p_start)
            coverage = min(1.0, span / max(1.0, period_end - period_start))
        else:
            p_start = p_end = None
            coverage = 0.0
        enough = period_events >= period_count_min
        period_rows.append({
            "period": period,
            "expected_start": round(period_start, 2),
            "expected_end": round(period_end, 2),
            "observed_start": round(p_start, 2) if p_start is not None else None,
            "observed_end": round(p_end, 2) if p_end is not None else None,
            "event_count": period_events,
            "coverage": round(coverage, 3),
            "event_density_ok": enough,
        })
        if period_events == 0:
            missing.append(f"period {period} has no events")
        elif coverage < 0.70:
            missing.append(f"period {period} observed span covers {coverage:.0%}")
        if not enough:
            missing.append(f"period {period} has only {period_events} events")

    check("period_event_density", all(row["event_density_ok"] for row in period_rows),
          f"minimum per period={period_count_min}")
    check("period_span_coverage", all(row["coverage"] >= 0.70 for row in period_rows),
          "minimum per-period span coverage=70%")

    provider_consistency = not unmapped_team and not invalid_clock and not duplicate_ids
    sorted_clocks = [(p, clock) for p, clock in zip(periods, clocks)]
    monotonic = all(
        (p1, c1) <= (p2, c2)
        for (p1, c1), (p2, c2) in zip(sorted_clocks, sorted_clocks[1:])
    )
    check("clock_monotonic_by_period", monotonic, "event order is chronological by period")
    provider_consistency = provider_consistency and monotonic

    min_sparse = max(10, int(duration / 60)) if duration else 10
    severe_integrity = not all(
        item["passed"] for index, item in enumerate(integrity)
        if index in (0, 1, 2, 3, 4, 6)
    )
    if synthetic:
        status: CompletenessStatus = "COMPLETE_VERIFIED"
        confidence = 1.0
        notes.append("Synthetic generator: complete by construction; not real-match evidence.")
    elif severe_integrity:
        status = "INVALID_CORRUPTED"
        confidence = 0.0
    elif count < min_sparse or any(row["event_count"] < period_count_min for row in period_rows):
        status = "SPARSE_SAMPLE_FIXTURE"
        confidence = min(0.35, count / max(1, min_sparse))
        notes.append("Event density is below the minimum for a match-level dataset.")
    elif missing:
        status = "PARTIAL_OBSERVED"
        confidence = 0.55
    elif declared_complete is True:
        status = "COMPLETE_VERIFIED"
        confidence = 1.0
    else:
        status = "COMPLETE_CLAIMED_UNVERIFIED"
        confidence = 0.75
        notes.append("Period checks pass, but no explicit complete-source declaration was supplied.")

    if synthetic:
        confidence = 1.0
    return DatasetCompleteness(
        status=status,
        synthetic=synthetic,
        source_declaration=source_declaration,
        raw_event_count=raw_count,
        normalized_event_count=count,
        conversion_drop_count=int(conversion_drop_count),
        drop_reasons=list(drop_reasons or []),
        observed_periods=sorted(set(periods)),
        expected_periods=expected_list,
        coverage_by_period=period_rows,
        expected_duration=duration,
        observed_start=round(observed_start, 2) if observed_start is not None else None,
        observed_end=round(observed_end, 2) if observed_end is not None else None,
        known_missing_segments=missing,
        provider_consistency=provider_consistency,
        integrity_checks=integrity,
        confidence=round(confidence, 3),
        verified=status == "COMPLETE_VERIFIED",
        notes=notes,
    )
