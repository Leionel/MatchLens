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

# Nominal playing time per period. A regulation match is two 45-minute
# halves; extra time adds two 15-minute periods; a shoot-out adds a final
# period. Provider clocks also carry stoppage time, so the observed span of a
# period routinely exceeds its nominal length and the verifier compares spans
# against these nominal values rather than against a single match total.
NOMINAL_PERIOD_SECONDS: dict[int, float] = {
    1: 2700.0,
    2: 2700.0,
    3: 900.0,
    4: 900.0,
    5: 600.0,
}

# Stoppage allowance granted to every period before the clock is considered
# out of bounds. The 2022 World Cup final ran 454 seconds of first-half
# stoppage time, so a tight bound would reject a genuine full match.
STOPPAGE_ALLOWANCE_SECONDS = 900.0

# A penalty shoot-out is a sequence of kicks, not a block of playing time.
# Its wall-clock length follows the number of kicks each side took, so the
# span of the shoot-out period says nothing about whether it was recorded in
# full. A shoot-out is therefore judged by recorded kicks per team.
PENALTY_SHOOTOUT_PERIOD = 5
PENALTY_SHOOTOUT_MIN_KICKS_PER_TEAM = 3


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


def _is_shot_event(event: Any) -> bool:
    """Whether the event is a shot, in either normalized or raw form."""
    value = _event_value(event, "action_type", "type", default="")
    if isinstance(value, dict):
        value = value.get("name", "")
    name = str(getattr(value, "value", value) or "").strip().lower()
    return name == "shot"


def _contiguous_prefix(periods: Sequence[int]) -> list[int]:
    """The periods a match must contain: 1..max, with no gaps.

    A provider that emitted period 3 without period 2 is reporting a corrupt
    payload rather than a match with a missing half, so the expected period
    set is derived from the observed maximum and checked for gaps. A penalty
    shoot-out is a separate phase that may follow the second half directly,
    so it is added to the match period without requiring extra time.
    """
    if not periods:
        return [1, 2]
    playing = sorted({int(p) for p in periods if int(p) < PENALTY_SHOOTOUT_PERIOD})
    expected = list(range(1, (max(playing) if playing else 2) + 1))
    if any(int(p) >= PENALTY_SHOOTOUT_PERIOD for p in periods):
        expected.append(PENALTY_SHOOTOUT_PERIOD)
    return expected


def _nominal_total(periods: Sequence[int]) -> float:
    return sum(NOMINAL_PERIOD_SECONDS.get(int(p), 2700.0) for p in periods)


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

    observed_period_values = [_event_period(event) for event in events]
    if expected_periods is None:
        expected_list = _contiguous_prefix(observed_period_values)
    else:
        expected_list = sorted(int(p) for p in expected_periods)

    nominal_total = _nominal_total(expected_list)
    clock_ceiling = nominal_total + STOPPAGE_ALLOWANCE_SECONDS * len(expected_list)

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
        if _event_clock(event) < 0 or (clock_ceiling and _event_clock(event) > clock_ceiling)
    ]
    allowed_teams = {str(team) for team in team_ids} if team_ids else {"H", "N"}
    unmapped_team = [
        _event_id(event) for event in events
        if not _event_team(event) or _event_team(event) not in allowed_teams
    ]
    periods = observed_period_values
    clocks = [_event_clock(event) for event in events]
    observed_start = min(clocks) if clocks else None
    observed_end = max(clocks) if clocks else None
    period_gaps = sorted(set(periods) - set(expected_list))

    check("events_present", count > 0, f"{count} normalized events")
    check("event_ids_present", all(ids), "every event has an ID")
    check("event_ids_unique", not duplicate_ids, f"duplicates={duplicate_ids[:5]}")
    check("clock_in_bounds", not invalid_clock, f"invalid={invalid_clock[:5]}")
    check("team_mapping_declared", not unmapped_team, f"unmapped={unmapped_team[:5]}")
    check("periods_present", not period_gaps, f"observed={sorted(set(periods))} expected={expected_list}")
    check("conversion_accounted", raw_count >= count and conversion_drop_count >= 0,
          f"raw={raw_count} normalized={count} drops={conversion_drop_count}")

    period_rows: list[dict[str, Any]] = []
    teams = [_event_team(event) for event in events]
    shots = [_is_shot_event(event) for event in events]
    for period in expected_list:
        nominal = NOMINAL_PERIOD_SECONDS.get(period, 2700.0)
        period_clocks = [clock for clock, p in zip(clocks, periods) if p == period]
        period_events = sum(1 for p in periods if p == period)
        is_shootout = period >= PENALTY_SHOOTOUT_PERIOD
        if period_clocks:
            p_start, p_end = min(period_clocks), max(period_clocks)
            span = max(0.0, p_end - p_start)
            coverage = min(1.0, span / max(1.0, nominal))
        else:
            p_start = p_end = None
            coverage = 0.0
        enough = period_events >= max(8, int(nominal / 120))
        kicks_by_team: dict[str, int] = {}
        shootout_ok = True
        if is_shootout:
            kicks_by_team = {
                team: count
                for team, count in Counter(
                    team for team, p, shot in zip(teams, periods, shots) if p == period and shot
                ).items()
            }
            shootout_teams = len({team for team, p in zip(teams, periods) if p == period})
            min_kicks = min(kicks_by_team.values()) if kicks_by_team else 0
            shootout_ok = (
                shootout_teams >= 2
                and len(kicks_by_team) >= 2
                and min_kicks >= PENALTY_SHOOTOUT_MIN_KICKS_PER_TEAM
            )
            # A shoot-out is measured in kicks, so the nominal playing-time
            # density rule does not apply to it; an incomplete shoot-out is a
            # missing segment rather than a sparse dataset.
            enough = True
        period_rows.append({
            "period": period,
            "expected_start": round(sum(NOMINAL_PERIOD_SECONDS.get(p, 2700.0) for p in expected_list if p < period), 2),
            "expected_end": round(sum(NOMINAL_PERIOD_SECONDS.get(p, 2700.0) for p in expected_list if p <= period), 2),
            "observed_start": round(p_start, 2) if p_start is not None else None,
            "observed_end": round(p_end, 2) if p_end is not None else None,
            "event_count": period_events,
            "coverage": round(coverage, 3),
            "event_density_ok": enough,
            "completeness_rule": "recorded_kicks" if is_shootout else "span_coverage",
            "shootout_kicks_by_team": kicks_by_team,
            "shootout_kicks_ok": shootout_ok,
        })
        if period_events == 0:
            missing.append(f"period {period} has no events")
        elif not is_shootout and coverage < 0.70:
            missing.append(f"period {period} observed span covers {coverage:.0%}")
        if is_shootout and not shootout_ok:
            missing.append(
                f"shoot-out recorded {min(kicks_by_team.values()) if kicks_by_team else 0} "
                f"kick(s) for the least-taken side, below {PENALTY_SHOOTOUT_MIN_KICKS_PER_TEAM}"
            )
        elif not is_shootout and not enough:
            missing.append(f"period {period} has only {period_events} events")

    check("period_event_density", all(row["event_density_ok"] for row in period_rows),
          "minimum per playing period=max(8, nominal_period/120); a shoot-out needs recorded kicks")
    check("period_span_coverage",
          all(row["coverage"] >= 0.70 for row in period_rows
              if row["completeness_rule"] == "span_coverage"),
          "minimum per-period span coverage=70%")
    check("shootout_kicks_recorded",
          all(row["shootout_kicks_ok"] for row in period_rows
              if row["completeness_rule"] == "recorded_kicks"),
          f"minimum kicks per team={PENALTY_SHOOTOUT_MIN_KICKS_PER_TEAM}")

    provider_consistency = not unmapped_team and not invalid_clock and not duplicate_ids
    sorted_clocks = [(p, clock) for p, clock in zip(periods, clocks)]
    monotonic = all(
        (p1, c1) <= (p2, c2)
        for (p1, c1), (p2, c2) in zip(sorted_clocks, sorted_clocks[1:])
    )
    check("clock_monotonic_by_period", monotonic, "event order is chronological by period")
    provider_consistency = provider_consistency and monotonic

    min_sparse = max(10, int(nominal_total / 60)) if nominal_total else 10
    severe_integrity = not all(
        item["passed"] for index, item in enumerate(integrity)
        if index in (0, 1, 2, 3, 4, 5, 6)
    )
    if synthetic:
        status: CompletenessStatus = "COMPLETE_VERIFIED"
        confidence = 1.0
        notes.append("Synthetic generator: complete by construction; not real-match evidence.")
    elif severe_integrity:
        status = "INVALID_CORRUPTED"
        confidence = 0.0
    elif count < min_sparse or any(not row["event_density_ok"] for row in period_rows):
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
    if duration and abs(duration - nominal_total) > 1:
        notes.append(
            f"declared duration {duration:.0f}s differs from the {nominal_total:.0f}s implied by "
            f"{len(expected_list)} period(s); the period structure was used for verification."
        )
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
        expected_duration=round(nominal_total, 2),
        observed_start=round(observed_start, 2) if observed_start is not None else None,
        observed_end=round(observed_end, 2) if observed_end is not None else None,
        known_missing_segments=missing,
        provider_consistency=provider_consistency,
        integrity_checks=integrity,
        confidence=round(confidence, 3),
        verified=status == "COMPLETE_VERIFIED",
        notes=notes,
    )
