"""Football match clock semantics.

A provider clock is not a match length. StatsBomb timestamps are cumulative
match-elapsed values that keep running through stoppage time, and a shoot-out
is stamped at the end of the playing clock rather than being 10 minutes of
football. The model below keeps the distinctions explicit:

``nominal_duration``
    Playing time implied by the recorded periods (90 or 120 minutes).
``observed_end``
    Last recorded event clock.
``replayable_end``
    The last clock a replay/seek may address. It equals ``observed_end``:
    missing time is not invented, and recorded stoppage time is not truncated.
``stoppage_time``
    Recorded time beyond the nominal end of each *playing* period.
``shootout_clock``
    Recorded kick clocks, reported separately from playing time.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from .completeness import NOMINAL_PERIOD_SECONDS, PENALTY_SHOOTOUT_PERIOD

PERIOD_LABELS = {
    1: "first_half",
    2: "second_half",
    3: "extra_time_1",
    4: "extra_time_2",
    5: "shootout",
}


def _event_time(event: Any) -> float:
    value = getattr(event, "clock_seconds", None)
    if value is None and isinstance(event, dict):
        value = event.get("t", event.get("clock_seconds", 0.0))
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _event_period(event: Any) -> int:
    value = getattr(event, "period", None)
    if value is None and isinstance(event, dict):
        value = event.get("period", 1)
    try:
        return int(value or 1)
    except (TypeError, ValueError):
        return 1


def _event_team(event: Any) -> str:
    value = getattr(event, "team_id", None)
    if value is None and isinstance(event, dict):
        value = event.get("team", "")
    return str(value or "")


def _event_is_goal(event: Any) -> bool:
    value = getattr(event, "outcome", None)
    if value is None and isinstance(event, dict):
        value = event.get("outcome")
    return str(value or "").lower() in ("goal", "own_goal_for")


def build_match_clock(
    events: Sequence[Any],
    *,
    nominal_duration: float,
    synthetic: bool = False,
) -> dict[str, Any]:
    if not events:
        raise ValueError("match_clock_requires_events")

    by_period: dict[int, list[Any]] = {}
    for event in events:
        by_period.setdefault(_event_period(event), []).append(event)

    playing_periods = sorted(period for period in by_period if period < PENALTY_SHOOTOUT_PERIOD)
    nominal = float(nominal_duration or 0.0)
    if playing_periods and not synthetic:
        # The provider's declared format can include a 600-second shoot-out
        # allocation. Playing time ends at the last playing period.
        nominal = sum(
            NOMINAL_PERIOD_SECONDS.get(period, 2700.0)
            for period in range(1, max(playing_periods) + 1)
        )

    period_rows: list[dict[str, Any]] = []
    stoppage_total = 0.0
    shootout: dict[str, Any] | None = None

    playing_starts: dict[int, float] = {}
    if synthetic:
        # The 12-minute demonstration match is not two 45-minute halves; its
        # two periods are equal halves of the declared format.
        half = nominal / 2.0
        for period in (1, 2):
            playing_starts[period] = (period - 1) * half
    else:
        cursor = 0.0
        for period in range(1, max(playing_periods or [2]) + 1):
            playing_starts[period] = cursor
            cursor += NOMINAL_PERIOD_SECONDS.get(period, 2700.0)

    for period in sorted(by_period):
        period_events = by_period[period]
        clocks = [_event_time(event) for event in period_events]
        observed_start = min(clocks)
        observed_end = max(clocks)
        is_shootout = period >= PENALTY_SHOOTOUT_PERIOD
        if is_shootout:
            nominal_start = nominal_end = nominal
            stoppage = 0.0
            kicks_by_team = Counter(_event_team(event) for event in period_events)
            goals_by_team = Counter(
                _event_team(event) for event in period_events if _event_is_goal(event)
            )
            shootout = {
                "period": period,
                "start_clock": round(observed_start, 3),
                "end_clock": round(observed_end, 3),
                "kick_count": len(period_events),
                "kicks_by_team": dict(kicks_by_team),
                "goals_by_team": dict(goals_by_team),
                "clock_note": (
                    "A shoot-out is measured in recorded kicks, not playing time; "
                    "provider kick clocks are reported as observed."
                ),
            }
        else:
            nominal_start = playing_starts.get(period, 0.0)
            period_length = (
                nominal / 2.0
                if synthetic
                else NOMINAL_PERIOD_SECONDS.get(period, 2700.0)
            )
            nominal_end = nominal_start + period_length
            stoppage = 0.0 if synthetic else max(0.0, observed_end - nominal_end)
            stoppage_total += stoppage

        period_rows.append({
            "period": period,
            "label": PERIOD_LABELS.get(period, f"period_{period}"),
            "is_shootout": is_shootout,
            "nominal_start": round(nominal_start, 3),
            "nominal_end": round(nominal_end, 3),
            "observed_start": round(observed_start, 3),
            "observed_end": round(observed_end, 3),
            "stoppage_seconds": round(stoppage, 3),
            "event_count": len(period_events),
        })

    observed_end = max(_event_time(event) for event in events)
    replayable_end = max(0.0, observed_end)
    return {
        "clock_version": "match-clock-v2",
        "basis": "match_elapsed",
        "synthetic": synthetic,
        "nominal_duration": round(nominal, 3),
        "observed_end": round(observed_end, 3),
        "replayable_end": round(replayable_end, 3),
        "as_of": round(replayable_end, 3),
        "period": max(by_period),
        "periods": period_rows,
        "stoppage_time_seconds": round(stoppage_total, 3),
        "shootout_clock": shootout,
    }
