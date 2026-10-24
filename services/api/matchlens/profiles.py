"""Cross-match team & player profiles (Slice C-1).

Aggregates registry metrics over multiple real provider matches. Every numeric
value funnels through `MetricsService` — the same single formula used by charts,
the Ask layer and the agent tools — so a profile can never publish a number
that contradicts the per-match surfaces.

Honesty rules enforced here:
- Per-90 rates are only aggregated over matches whose coverage is verified
  continuous (COMPLETE_VERIFIED); partial fixtures keep raw totals but never
  enter a rate.
- Distributions are reported as raw per-match values (mean/median/min/max and
  the full list). No confidence interval, p-value or significance claim is
  produced: the sample is a convenience corpus, not a designed one.
- Style tags are descriptive labels derived from L1/L2 aggregates with their
  derivation rule attached. They are never causal claims and carry no league
  baseline (baseline comparison: Not Run).
- Synthetic scenarios are excluded by default; a profile only accepts
  `provenance_kind: provider_payload` matches and reports what it excluded.
"""
from __future__ import annotations

import dataclasses
import json
from collections import Counter
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .contracts import Snapshot
from .metrics import DEFINITIONS, MetricsService

PROFILE_VERSION = "profiles-v1"
COMPUTE_VERSION = "profiles-v1"

#: Team-scope metrics aggregated by the team profile. All of them exist in the
#: registry; `possession` is a share, the rest are counts.
TEAM_METRICS = (
    "possession",
    "shots",
    "entries",
    "high_recoveries",
    "transition_shots",
    "goals",
    "passes",
    "progressive_passes",
    "carries",
    "recoveries",
    "box_entries",
)

#: Player-scope metrics. Excluded on purpose: `possession`, `entries` and
#: `transition_shots` are defined over possession chains, and a player-filtered
#: event list would corrupt those chains into fabricated adjacency. Excluding a
#: metric is documented, never silently approximated.
PLAYER_METRICS = (
    "passes",
    "progressive_passes",
    "carries",
    "recoveries",
    "high_recoveries",
    "shots",
    "goals",
    "box_entries",
)

PLAYER_METRIC_EXCLUSIONS = {
    "possession": "share is defined over both teams' controlled seconds; not a player quantity",
    "entries": "count is defined per possession chain; a player-filtered stream would fabricate chains",
    "transition_shots": "the <=10s recovery link requires the unfiltered possession context",
}


class ProfileMatchMetricValue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric_id: str
    value: float | int | None
    status: str
    unit: str
    event_count: int = 0


class ProfileMatchRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_id: str
    label: str
    competition: str
    season: str
    match_date: Optional[str] = None
    side: str
    side_team_name: str
    opponent_name: str
    minutes_basis_seconds: float
    window_seconds: float = 0.0
    coverage_status: Optional[str] = None
    continuous_coverage: bool = False
    provenance_kind: str
    dataset_revision: Optional[str] = None
    included_in_rates: bool
    clock_bounded_at_duration: bool = False
    metrics: dict[str, ProfileMatchMetricValue] = Field(default_factory=dict)
    window_metrics: dict[str, ProfileMatchMetricValue] = Field(default_factory=dict)
    delta_xt_heuristic: Optional[float] = None


class ProfileMetricAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric_id: str
    label: str
    unit: str
    formula: str
    metric_version: str
    model_status: str
    model_version: Optional[str] = None
    absolute_total: float | int | None = None
    absolute_total_basis: dict[str, Any] = Field(default_factory=dict)
    sample_size: int = 0
    per_match_values: list[dict[str, Any]] = Field(default_factory=list)
    per_match_mean: Optional[float] = None
    per_match_median: Optional[float] = None
    per_match_min: Optional[float] = None
    per_match_max: Optional[float] = None
    per_90: Optional[float] = None
    per_90_basis: dict[str, Any] = Field(default_factory=dict)
    window_per_90: Optional[float] = None
    window_per_90_basis: dict[str, Any] = Field(default_factory=dict)
    rate_status: str = "withheld_no_complete_matches"
    notes: list[str] = Field(default_factory=list)


class StyleDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    label: str
    value: float
    unit: str
    formula: str
    per_match_values: list[float] = Field(default_factory=list)


class StyleTag(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tag: str
    rule: str
    basis_metric_ids: list[str]
    level: str = "descriptive_label_from_l1_l2_aggregates"


class TeamProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_kind: str = "team"
    team: dict[str, Any]
    scope: dict[str, Any]
    provenance_kinds: dict[str, int]
    matches: list[ProfileMatchRow]
    aggregates: dict[str, ProfileMetricAggregate]
    style_dimensions: list[StyleDimension] = Field(default_factory=list)
    style_tags: list[StyleTag] = Field(default_factory=list)
    window_alignment: Optional[dict[str, Any]] = None
    uncertainty_note: str
    limitations: list[str]


class PlayerProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_kind: str = "player"
    player: dict[str, Any]
    scope: dict[str, Any]
    provenance_kinds: dict[str, int]
    matches: list[ProfileMatchRow]
    aggregates: dict[str, ProfileMetricAggregate]
    minutes: dict[str, Any]
    window_alignment: Optional[dict[str, Any]] = None
    uncertainty_note: str
    limitations: list[str]


# ------------------------------------------------------------------ helpers


def _median(values: list[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return round(float(ordered[mid]), 4)
    return round((ordered[mid - 1] + ordered[mid]) / 2.0, 4)


def _round_or_none(value: Optional[float], digits: int = 4) -> Optional[float]:
    return None if value is None else round(float(value), digits)


def _delta_xt_for_state_events(
    events: list[dict],
    team: str,
    xt_model: Any,
) -> tuple[float, int]:
    """Sum of forward ΔxT over located completed passes and carries of one team.

    Mirrors the xT evaluation used by `oaai.compute_event_contribution`
    (attack-oriented coordinates via `_attack_x`, clamped at zero so backward
    actions never earn value). The grid is the uncalibrated heuristic surface;
    every surface that exposes this number labels it heuristic.
    """
    from .oaai import _attack_x

    total = 0.0
    count = 0
    for e in events:
        if e.get("team") != team or e.get("kind") not in ("pass", "carry"):
            continue
        if e.get("kind") == "pass" and e.get("outcome") not in (None, "complete"):
            continue
        start = e.get("start")
        end = e.get("end")
        if not start or not end:
            continue
        frame = "team_relative" if e.get("frame") == "team_relative" else "fixed"
        ax_s = _attack_x(team, float(start[0]), frame)
        ax_e = _attack_x(team, float(end[0]), frame)
        try:
            v_s = xt_model.value_at(ax_s, float(start[1]))
            v_e = xt_model.value_at(ax_e, float(end[1]))
        except Exception:
            continue
        total += max(0.0, v_e - v_s)
        count += 1
    return round(total, 4), count


def align_windows_by_period(
    snapshots_events: list[tuple[str, list[dict]]],
) -> dict[str, Any]:
    """Equal-length per-period windows shared by every match.

    Windows never merge periods: half-time, extra time and shootout breaks stay
    boundaries. A period participates only when every match observed events in
    it; the aligned window is the intersection of the observed spans, so it is
    identical in length across all matches.
    """
    per_period: dict[int, dict[str, list[float]]] = {}
    for _match_id, events in snapshots_events:
        seen: dict[int, list[float]] = {}
        for e in events:
            p = int(e.get("period") or 1)
            if p >= 5:  # shootout: not comparable football time
                continue
            seen.setdefault(p, []).append(float(e.get("t", 0.0)))
        for p, ts in seen.items():
            per_period.setdefault(p, {}).setdefault("starts", []).append(min(ts))
            per_period.setdefault(p, {}).setdefault("ends", []).append(max(ts))

    windows: list[dict[str, Any]] = []
    for p in sorted(per_period):
        entry = per_period[p]
        if len(entry["starts"]) != len(snapshots_events):
            continue
        start = max(entry["starts"])
        end = min(entry["ends"])
        if end <= start:
            continue
        windows.append({
            "period": p,
            "start_s": round(start, 1),
            "end_s": round(end, 1),
            "length_seconds": round(end - start, 1),
        })
    return {
        "method": "per-period intersection of observed event spans; periods are never merged",
        "matches": [m for m, _ in snapshots_events],
        "windows": windows,
        "aligned_seconds_total": round(sum(w["length_seconds"] for w in windows), 1),
        "exclusions": [
            "shootout periods excluded",
            "periods not observed in every match excluded",
        ],
    }


def _metric_aggregate(
    metric_id: str,
    rows: list[ProfileMatchRow],
    windowed: bool,
) -> ProfileMetricAggregate:
    definition = DEFINITIONS[metric_id]
    is_share = metric_id == "possession"

    values: list[float] = []
    per_match: list[dict[str, Any]] = []
    total = 0.0
    total_ok = 0
    basis_complete = 0
    basis_partial = 0
    share_values: list[float] = []
    rate_minutes = 0.0
    rate_total = 0.0

    for row in rows:
        mv = row.metrics.get(metric_id)
        if mv is None or mv.status != "ok" or mv.value is None:
            continue
        v = float(mv.value)
        values.append(v)
        total += v
        total_ok += 1
        rate_eligible = row.continuous_coverage and row.included_in_rates
        if rate_eligible:
            basis_complete += 1
            if is_share:
                share_values.append(v)
            else:
                rate_total += v
                rate_minutes += float(row.minutes_basis_seconds)
        else:
            basis_partial += 1
        per_match.append({
            "match_id": row.match_id,
            "match_date": row.match_date,
            "value": mv.value,
            "status": mv.status,
            "coverage_status": row.coverage_status,
            "included_in_rates": rate_eligible,
            "minutes_basis_seconds": row.minutes_basis_seconds,
        })

    if is_share:
        if share_values:
            aggregate_value: Optional[float] = round(sum(share_values) / len(share_values), 2)
            per_90_value = None
            per_90_basis: dict[str, Any] = {}
            rate_status = "comparable_mean_of_match_shares"
        else:
            aggregate_value = None
            per_90_value = None
            per_90_basis = {}
            rate_status = "withheld_no_complete_matches"
        notes = [
            "Possession is a share: the aggregate is the unweighted mean of per-match shares, never a summed percentage.",
        ]
    else:
        aggregate_value = round(total, 2) if total_ok else None
        if rate_minutes > 0:
            per_90_value = round(rate_total * 5400.0 / rate_minutes, 2)
            per_90_basis = {
                "total_value": round(rate_total, 2),
                "total_minutes_seconds": round(rate_minutes, 1),
                "matches_with_complete_coverage": basis_complete,
                "rate_definition": "sum(ok values of complete-coverage matches) / their minutes * 5400",
            }
            rate_status = "comparable"
        else:
            per_90_value = None
            per_90_basis = {}
            rate_status = "withheld_no_complete_matches"
        notes = []

    window_values: list[float] = []
    window_minutes = 0.0
    if windowed:
        for row in rows:
            if not (row.continuous_coverage and row.included_in_rates):
                continue
            mv = row.window_metrics.get(metric_id)
            if mv is None or mv.status != "ok" or mv.value is None:
                continue
            window_values.append(float(mv.value))
            window_minutes += float(row.window_seconds)
    if window_values and window_minutes > 0 and not is_share:
        window_per_90: Optional[float] = round(sum(window_values) * 5400.0 / window_minutes, 2)
        window_basis: dict[str, Any] = {
            "total_value": round(sum(window_values), 2),
            "total_window_seconds": round(window_minutes, 1),
            "matches": len(window_values),
            "rate_definition": "sum(aligned-window values) / sum(aligned window seconds) * 5400",
        }
    else:
        window_per_90 = None
        window_basis = {}

    return ProfileMetricAggregate(
        metric_id=metric_id,
        label=definition.label,
        unit=definition.unit,
        formula=definition.formula,
        metric_version=definition.version,
        model_status=definition.model_status,
        model_version="oaai-1.0.0" if metric_id == "oaai" else None,
        absolute_total=aggregate_value,
        absolute_total_basis={
            "matches_with_values": total_ok,
            "matches_complete_coverage": basis_complete,
            "matches_partial_coverage": basis_partial,
            "note": "raw totals include partial-coverage matches and are not per-90 comparable",
        },
        sample_size=len(values),
        per_match_values=per_match,
        per_match_mean=_round_or_none(sum(values) / len(values)) if values else None,
        per_match_median=_median(values),
        per_match_min=_round_or_none(min(values)) if values else None,
        per_match_max=_round_or_none(max(values)) if values else None,
        per_90=per_90_value,
        per_90_basis=per_90_basis,
        window_per_90=window_per_90,
        window_per_90_basis=window_basis,
        rate_status=rate_status,
        notes=notes + [
            "No confidence interval or p-value is computed; the per-match distribution is reported raw.",
        ],
    )


def _style_block(
    aggregates: dict[str, ProfileMetricAggregate],
    match_count: int,
) -> tuple[list[StyleDimension], list[StyleTag]]:
    dims: list[StyleDimension] = []
    tags: list[StyleTag] = []

    poss = aggregates.get("possession")
    if poss and poss.per_match_values:
        share_values = [float(v["value"]) for v in poss.per_match_values if v["value"] is not None]
        if share_values:
            dims.append(StyleDimension(
                key="possession_share",
                label="Mean possession share",
                value=round(sum(share_values) / len(share_values), 2),
                unit="%",
                formula="mean of per-match possession share",
                per_match_values=share_values,
            ))

    def per90(metric_id: str) -> Optional[float]:
        agg = aggregates.get(metric_id)
        return agg.per_90 if agg else None

    for key, label in (
        ("passes", "Passes per 90"),
        ("progressive_passes", "Progressive passes per 90"),
        ("high_recoveries", "High recoveries per 90"),
        ("transition_shots", "Recovery-to-shot per 90"),
        ("shots", "Shots per 90"),
        ("box_entries", "Penalty-box entries per 90"),
    ):
        v = per90(key)
        if v is not None:
            dims.append(StyleDimension(
                key=f"{key}_per_90",
                label=label,
                value=v,
                unit=DEFINITIONS[key].unit + "/90",
                formula=f"sum({key}) / minutes * 90 over complete-coverage matches",
                per_match_values=[
                    float(pv["value"]) for pv in aggregates[key].per_match_values if pv["value"] is not None
                ],
            ))

    passes90 = per90("passes")
    prog90 = per90("progressive_passes")
    shots_total = aggregates["shots"].absolute_total if "shots" in aggregates else None
    trans_total = aggregates["transition_shots"].absolute_total if "transition_shots" in aggregates else None
    if passes90:
        dims.append(StyleDimension(
            key="directness_index",
            label="Directness (progressive pass share)",
            value=round((prog90 or 0.0) / passes90, 4),
            unit="ratio",
            formula="progressive_passes_per_90 / passes_per_90",
        ))
    if shots_total:
        dims.append(StyleDimension(
            key="transition_shot_share",
            label="Share of shots preceded by a <=10s recovery",
            value=round(float(trans_total or 0.0) / float(shots_total), 4),
            unit="ratio",
            formula="transition_shots_total / shots_total",
        ))

    if match_count >= 2:
        poss_mean = next((d.value for d in dims if d.key == "possession_share"), None)
        directness = next((d.value for d in dims if d.key == "directness_index"), None)
        trans_share = next((d.value for d in dims if d.key == "transition_shot_share"), None)
        if poss_mean is not None:
            if poss_mean >= 55.0:
                tags.append(StyleTag(tag="possession_dominant", rule="mean possession share >= 55%", basis_metric_ids=["possession"]))
            elif poss_mean < 45.0:
                tags.append(StyleTag(tag="possession_deferred", rule="mean possession share < 45%", basis_metric_ids=["possession"]))
            else:
                tags.append(StyleTag(tag="possession_balanced", rule="45% <= mean possession share < 55%", basis_metric_ids=["possession"]))
        if trans_share is not None and trans_share >= 0.2:
            tags.append(StyleTag(
                tag="transition_reliant_shot_creation",
                rule=">= 20% of shots came <=10s after a recovery",
                basis_metric_ids=["transition_shots", "shots"],
            ))
        if directness is not None and directness >= 0.15:
            tags.append(StyleTag(
                tag="direct_progression",
                rule="progressive pass share of completed passes >= 15%",
                basis_metric_ids=["progressive_passes", "passes"],
            ))
        if not tags:
            tags.append(StyleTag(
                tag="no_style_threshold_met",
                rule="no dimension crossed a tag threshold in this sample",
                basis_metric_ids=[],
            ))
    return dims, tags


def _excluded_row(match_id: str, reason: str) -> dict[str, Any]:
    return {"match_id": match_id, "reason": reason}


def _match_window_metrics(
    snap: Snapshot,
    state: dict,
    metric_ids: tuple[str, ...],
    side: str,
    match_id: str,
) -> dict[str, ProfileMatchMetricValue]:
    """Full-match observations: one receipts pass, one batched evaluation.

    `metric_receipts_for_range` over (0, as_of] is exactly the formula the
    registry's match window uses; handing it to `query_range_many` only skips
    recomputing the same receipts per metric. Values are identical.
    """
    from .football import metric_receipts_for_range
    from .metrics import RANGE_WINDOW

    as_of = float(snap.data.get("as_of", 0.0))
    receipts = metric_receipts_for_range(state, 0.0, as_of, name=RANGE_WINDOW)
    values = MetricsService.query_range_many(
        snap, list(metric_ids), team=side,
        start_s=0.0, end_s=as_of, match_id=match_id,
        precomputed_receipts=receipts,
    )
    return {
        mv.metric_id: ProfileMatchMetricValue(
            metric_id=mv.metric_id,
            value=mv.value,
            status=mv.status,
            unit=mv.unit,
            event_count=len(mv.event_ids),
        )
        for mv in values
    }


def _aligned_window_metrics(
    snap: Snapshot,
    state: dict,
    metric_ids: tuple[str, ...],
    side: str,
    alignment: dict[str, Any],
    match_id: str,
) -> tuple[dict[str, ProfileMatchMetricValue], float]:
    """Sum registry range observations over the shared per-period windows.

    Each window gets one receipts pass; the batched evaluation reuses it.
    """
    from .football import metric_receipts_for_range
    from .metrics import RANGE_WINDOW

    out: dict[str, ProfileMatchMetricValue] = {}
    window_seconds = 0.0
    for w in alignment.get("windows", []):
        receipts = metric_receipts_for_range(
            state, float(w["start_s"]), float(w["end_s"]), name=RANGE_WINDOW,
        )
        for mv in MetricsService.query_range_many(
            snap, list(metric_ids), team=side,
            start_s=float(w["start_s"]), end_s=float(w["end_s"]),
            match_id=match_id, precomputed_receipts=receipts,
        ):
            if mv.status == "ok" and mv.value is not None:
                prev = out.get(mv.metric_id)
                out[mv.metric_id] = ProfileMatchMetricValue(
                    metric_id=mv.metric_id,
                    value=float(mv.value) + float(prev.value) if prev and prev.value is not None else mv.value,
                    status="ok",
                    unit=mv.unit,
                    event_count=(prev.event_count if prev else 0) + len(mv.event_ids),
                )
            elif mv.metric_id not in out:
                out[mv.metric_id] = ProfileMatchMetricValue(
                    metric_id=mv.metric_id, value=None, status=mv.status, unit=mv.unit,
                )
        window_seconds += float(w["length_seconds"])
    for metric_id in metric_ids:
        if metric_id not in out:
            out[metric_id] = ProfileMatchMetricValue(
                metric_id=metric_id, value=None, status="unobserved",
                unit=DEFINITIONS[metric_id].unit,
            )
    return out, round(window_seconds, 1)


# ------------------------------------------------------------------ team profile

#: Deterministic per-match metric rows, keyed by (match, side, dataset
#: revision, metric set, window mode). Registry metrics are pure functions of
#: the frozen snapshot, so a revision-keyed result cache cannot serve stale
#: numbers. Bounded LRU; cache state is reported, never assumed.
_ROW_METRICS_CACHE: dict[tuple[Any, ...], tuple[dict[str, ProfileMatchMetricValue], dict[str, ProfileMatchMetricValue], float, Optional[float]]] = {}
_ROW_METRICS_CACHE_MAX = 240
_ROW_METRICS_CACHE_STATS = {"hits": 0, "misses": 0}


def _cached_row_metrics(
    *,
    scope: str,
    match_id: str,
    side: str,
    dataset_revision: Optional[str],
    window: str,
    metric_ids: tuple[str, ...],
    snap: Snapshot,
    state: dict,
    alignment: Optional[dict[str, Any]],
    xt_model: Any = None,
    with_delta_xt: bool = False,
) -> tuple[dict[str, ProfileMatchMetricValue], dict[str, ProfileMatchMetricValue], float, Optional[float]]:
    key = (scope, match_id, side, dataset_revision or "", window, metric_ids)
    cached = _ROW_METRICS_CACHE.get(key)
    if cached is not None:
        _ROW_METRICS_CACHE_STATS["hits"] += 1
        return cached
    metrics = _match_window_metrics(snap, state, metric_ids, side, match_id)
    window_metrics: dict[str, ProfileMatchMetricValue] = {}
    window_seconds = 0.0
    if window == "aligned" and alignment:
        window_metrics, window_seconds = _aligned_window_metrics(
            snap, state, metric_ids, side, alignment, match_id,
        )
    delta_xt = (
        _delta_xt_for_state_events(snap.data.get("events", []), side, xt_model)[0]
        if with_delta_xt and xt_model is not None
        else None
    )
    result = (metrics, window_metrics, window_seconds, delta_xt)
    if len(_ROW_METRICS_CACHE) >= _ROW_METRICS_CACHE_MAX:
        _ROW_METRICS_CACHE.pop(next(iter(_ROW_METRICS_CACHE)))
    _ROW_METRICS_CACHE[key] = result
    _ROW_METRICS_CACHE_STATS["misses"] += 1
    return result


def build_team_profile(
    *,
    team: str,
    rows: list[dict[str, Any]],
    window: str = "match",
    xt_model: Any = None,
) -> TeamProfileResponse:
    """Aggregate one team across pre-resolved matches.

    Each `rows` entry carries the resolved match facts and the frozen
    full-match Snapshot (`snapshot`), plus the side ("H"/"N") the requested
    team played on and a precomputed `window_alignment` when `window="aligned"`.
    All metric values come from `MetricsService` — the registry formulas —
    never from a profile-local reimplementation.
    """
    match_rows: list[ProfileMatchRow] = []
    provenance: Counter[str] = Counter()
    excluded: list[dict[str, Any]] = []
    provider_ids: set[str] = set()

    for row in rows:
        snap: Snapshot = row["snapshot"]
        data = snap.data
        side = row["side"]
        provider_ids.update(str(x) for x in row.get("provider_team_ids", []) if x)
        if row.get("provenance_kind") != "provider_payload":
            excluded.append(_excluded_row(
                row["match_id"],
                f"provenance_kind={row.get('provenance_kind')}; only provider_payload matches enter profiles",
            ))
            continue
        provenance[row["provenance_kind"]] += 1
        continuous = bool(row.get("continuous_coverage"))
        events = data.get("events", [])

        metrics, window_metrics, window_seconds, delta_xt = _cached_row_metrics(
            scope="team",
            match_id=row["match_id"],
            side=side,
            dataset_revision=row.get("dataset_revision"),
            window=window,
            metric_ids=TEAM_METRICS,
            snap=snap,
            state=row["state"],
            alignment=row.get("window_alignment"),
            xt_model=xt_model,
            with_delta_xt=True,
        )

        match_rows.append(ProfileMatchRow(
            match_id=row["match_id"],
            label=row["label"],
            competition=row["competition"],
            season=row["season"],
            match_date=row.get("match_date"),
            side=side,
            side_team_name=row["side_team_name"],
            opponent_name=row["opponent_name"],
            minutes_basis_seconds=float(data.get("as_of", 0)),
            window_seconds=window_seconds,
            coverage_status=row.get("coverage_status"),
            continuous_coverage=continuous,
            provenance_kind=row["provenance_kind"],
            dataset_revision=row.get("dataset_revision"),
            included_in_rates=True,
            clock_bounded_at_duration=bool(row.get("clock_bounded")),
            metrics=metrics,
            window_metrics=window_metrics,
            delta_xt_heuristic=delta_xt,
        ))

    aggregates = {
        metric_id: _metric_aggregate(metric_id, match_rows, windowed=(window == "aligned"))
        for metric_id in TEAM_METRICS
    }

    alignment_out = None
    if window == "aligned":
        first_alignment = next((r.get("window_alignment") for r in rows if r.get("window_alignment")), None)
        if first_alignment is not None:
            alignment_out = {
                **first_alignment,
                "usage": "window_metrics per match are summed over the shared aligned period windows",
            }

    dims, tags = _style_block(aggregates, len(match_rows))

    limitations = [
        "Profile aggregates reuse the registry formulas via MetricsService; they add no new metric semantics.",
        "Per-90 rates use only matches with verified continuous coverage; partial matches keep raw totals only.",
        "No confidence interval, p-value or significance claim is produced. Style tags are descriptive L1/L2 labels, not causal claims.",
        "ΔxT uses the uncalibrated heuristic threat grid and is labelled heuristic.",
    ]
    if excluded:
        limitations.append(f"{len(excluded)} requested matches were excluded from the profile (see scope.excluded).")
    bounded = sum(1 for r in match_rows if r.clock_bounded_at_duration)
    if bounded:
        limitations.append(
            f"{bounded} match(es) ran beyond the nominal {int(match_rows[0].minutes_basis_seconds if match_rows else 0)}s "
            "duration bound (second-half stoppage and extra time). Snapshots freeze at the nominal duration "
            "(platform-wide snapshot semantics), so observed events beyond it are excluded and the per-90 "
            "denominator uses the bounded clock."
        )

    return TeamProfileResponse(
        team={
            "requested": team,
            "provider_team_ids": sorted(provider_ids),
        },
        scope={
            "requested_matches": len(rows),
            "included_matches": len(match_rows),
            "excluded": excluded,
            "window": window,
            "profile_version": PROFILE_VERSION,
            "computation_version": COMPUTE_VERSION,
            "row_metrics_cache": dict(_ROW_METRICS_CACHE_STATS),
        },
        provenance_kinds=dict(provenance),
        matches=match_rows,
        aggregates=aggregates,
        style_dimensions=dims,
        style_tags=tags,
        window_alignment=alignment_out,
        uncertainty_note=(
            "Only raw sample quantities are reported (per-match values, mean, median, min, max, sample size). "
            "No interval estimate or hypothesis test is attached; treat differences between teams as descriptive."
        ),
        limitations=limitations,
    )


# ------------------------------------------------------------------ player profile


def compute_player_minutes(
    events: list[Any],
    player_id: str,
    observed_end: float,
) -> dict[str, Any]:
    """Minutes denominator for one player in one match.

    Denominators are derived from provider substitution/lineup records, never
    invented:
    - starter with an exit record: 0 -> exit
    - starter without an exit record: 0 -> observed span (flagged as an
      assumption, exit events can be missing in old seasons)
    - substitute with an entry record: entry -> exit or observed span
    - no records at all: span between the player's first and last event
      (a lower bound, flagged `event_span_fallback`)
    """
    pid = str(player_id)
    is_starter = any(
        (e.lineup_role == "starter" and str(e.player_id or "") == pid)
        for e in events
    )
    off_t: Optional[float] = None
    on_t: Optional[float] = None
    for e in events:
        if str(e.substitution_off_player_id or "") == pid and e.clock_seconds is not None:
            off_t = float(e.clock_seconds) if off_t is None else min(off_t, float(e.clock_seconds))
        if str(e.substitution_on_player_id or "") == pid and e.clock_seconds is not None:
            on_t = float(e.clock_seconds) if on_t is None else min(on_t, float(e.clock_seconds))

    if is_starter:
        seconds = (off_t if off_t is not None else observed_end) - 0.0
        return {"seconds": round(max(0.0, seconds), 1), "method": "starter_assumed_full" if off_t is None else "substitution_derived", "exit_at": off_t}
    if on_t is not None:
        seconds = (off_t if off_t is not None else observed_end) - on_t
        return {"seconds": round(max(0.0, seconds), 1), "method": "substitution_derived", "entered_at": on_t, "exit_at": off_t}

    own = [float(e.clock_seconds) for e in events if str(e.player_id or "") == pid and e.clock_seconds is not None]
    if own:
        return {
            "seconds": round(max(0.0, max(own) - min(own)), 1),
            "method": "event_span_fallback",
            "first_event_at": min(own),
            "last_event_at": max(own),
        }
    return {"seconds": 0.0, "method": "no_records", "exit_at": None}


def _player_scoped_snapshot(snap: Snapshot, player_id: str, *, allow_actor_match: bool) -> tuple[Snapshot, str, int, Counter]:
    """Re-freeze the snapshot with only the player's on-ball events.

    The filtered snapshot goes through the same `MetricsService` formulas as
    the full match, so player metrics cannot drift from team metrics. Snapshot
    identity is preserved via `dataclasses.replace`; the id is untouched and
    the canonical content is the player-filtered event stream.
    """
    data = snap.data
    scoped: list[dict] = []
    name_variants: Counter[str] = Counter()
    for e in data.get("events", []):
        pid = str(e.get("player_id") or "")
        actor = str(e.get("actor") or "")
        if pid == str(player_id) or (allow_actor_match and actor == str(player_id)):
            scoped.append(e)
            if actor and actor != "Unknown":
                name_variants[actor] += 1
    filtered = {**data, "events": scoped}
    player_snap = dataclasses.replace(snap, canonical=json.dumps(filtered, ensure_ascii=False))
    return player_snap, (name_variants.most_common(1)[0][0] if name_variants else str(player_id)), len(scoped), name_variants


def build_player_profile(
    *,
    player_id: str,
    rows: list[dict[str, Any]],
    window: str = "match",
) -> PlayerProfileResponse:
    """Aggregate one player across pre-resolved provider matches.

    Each `rows` entry: match_id, label, competition, season, match_date,
    provenance_kind, coverage_status, continuous_coverage, dataset_revision,
    snapshot (full-match frozen Snapshot), side (the player's team "H"/"N"),
    side_team_name, opponent_name, minutes {seconds, method}, and a
    precomputed `window_alignment` when `window="aligned"`.
    """
    match_rows: list[ProfileMatchRow] = []
    provenance: Counter[str] = Counter()
    excluded: list[dict[str, Any]] = []
    name_variants: Counter[str] = Counter()
    minutes_methods: Counter[str] = Counter()

    for row in rows:
        snap: Snapshot = row["snapshot"]
        side = row["side"]
        if row.get("provenance_kind") != "provider_payload":
            excluded.append(_excluded_row(
                row["match_id"],
                f"provenance_kind={row.get('provenance_kind')}; player profiles cover provider payloads only",
            ))
            continue
        provenance[row["provenance_kind"]] += 1
        player_snap, player_name, event_count, variants = _player_scoped_snapshot(
            snap, player_id, allow_actor_match=bool(row.get("allow_actor_match"))
        )
        name_variants.update(variants)
        if event_count == 0:
            excluded.append(_excluded_row(row["match_id"], "player_has_no_events_in_this_match"))
            continue

        # Receipts must be computed from the player-filtered stream, so the
        # state handed to the receipts builder is re-scoped to the same events
        # as the player snapshot. possession/entries/transition_shots receipts
        # built from it are simply never read (not in PLAYER_METRICS).
        player_state = {**row["state"], "events": player_snap.data.get("events", [])}
        metrics, window_metrics, window_seconds, _ = _cached_row_metrics(
            scope=f"player:{player_id}",
            match_id=row["match_id"],
            side=side,
            dataset_revision=row.get("dataset_revision"),
            window=window,
            metric_ids=PLAYER_METRICS,
            snap=player_snap,
            state=player_state,
            alignment=row.get("window_alignment"),
        )

        minutes = row.get("minutes") or {}
        minutes_seconds = float(minutes.get("seconds") or 0.0)
        minutes_method = str(minutes.get("method") or "unknown")
        minutes_methods[minutes_method] += 1

        match_rows.append(ProfileMatchRow(
            match_id=row["match_id"],
            label=row["label"],
            competition=row["competition"],
            season=row["season"],
            match_date=row.get("match_date"),
            side=side,
            side_team_name=row["side_team_name"],
            opponent_name=row["opponent_name"],
            minutes_basis_seconds=minutes_seconds,
            window_seconds=window_seconds,
            coverage_status=row.get("coverage_status"),
            continuous_coverage=bool(row.get("continuous_coverage")),
            provenance_kind=row["provenance_kind"],
            dataset_revision=row.get("dataset_revision"),
            included_in_rates=minutes_seconds > 0,
            clock_bounded_at_duration=bool(row.get("clock_bounded")),
            metrics=metrics,
            window_metrics=window_metrics,
        ))

    aggregates = {
        metric_id: _metric_aggregate(metric_id, match_rows, windowed=(window == "aligned"))
        for metric_id in PLAYER_METRICS
    }

    alignment_out = None
    if window == "aligned":
        alignment_out = next((r.get("window_alignment") for r in rows if r.get("window_alignment")), None)

    minutes_total = sum(r.minutes_basis_seconds for r in match_rows)
    minutes_note: dict[str, Any] = {
        "total_seconds": round(minutes_total, 1),
        "total_minutes": round(minutes_total / 60.0, 1),
        "methods": dict(minutes_methods),
        "method_legend": {
            "substitution_derived": "entry/exit times read from provider substitution events",
            "starter_assumed_full": "listed starter with no exit record; assumed on pitch through the observed span",
            "event_span_fallback": "no substitution records; span between the player's first and last event (lower bound)",
        },
        "limitation": (
            "Player minutes are denominators, not observed metrics. Fallback methods are lower bounds "
            "and are counted per match so per-90 rates that lean on them are inspectable."
        ),
    }

    limitations = [
        "Player metrics reuse the registry formulas by re-freezing the match snapshot with only the player's events.",
        "possession / entries / transition_shots are excluded from the player scope because their definitions depend on unfiltered possession chains.",
        "No confidence interval or p-value is computed; differences across matches are reported as raw distributions.",
    ]
    if excluded:
        limitations.append(f"{len(excluded)} requested matches were excluded (see scope.excluded).")
    bounded = sum(1 for r in match_rows if r.clock_bounded_at_duration)
    if bounded:
        limitations.append(
            f"{bounded} match(es) ran beyond the nominal duration bound (second-half stoppage and extra "
            "time). Snapshots freeze at the nominal duration (platform-wide snapshot semantics), so "
            "observed events beyond it are excluded and the minutes denominator uses the bounded clock."
        )

    return PlayerProfileResponse(
        player={
            "requested_id": player_id,
            "name": name_variants.most_common(1)[0][0] if name_variants else None,
            "name_variants": dict(name_variants),
        },
        scope={
            "requested_matches": len(rows),
            "included_matches": len(match_rows),
            "excluded": excluded,
            "window": window,
            "profile_version": PROFILE_VERSION,
            "computation_version": COMPUTE_VERSION,
            "row_metrics_cache": dict(_ROW_METRICS_CACHE_STATS),
        },
        provenance_kinds=dict(provenance),
        matches=match_rows,
        aggregates=aggregates,
        minutes=minutes_note,
        window_alignment=alignment_out,
        uncertainty_note=(
            "Only raw sample quantities are reported (per-match values and summary statistics). "
            "No interval estimate or hypothesis test is attached."
        ),
        limitations=limitations,
    )


# ------------------------------------------------------------------ discovery


def discover_team_matches(team: str) -> dict[str, Any]:
    """Metadata-only index of the matches a team appears in across the catalog.

    No event payload is loaded: this is the cheap discovery step the UI calls
    before asking for a full profile. Matching is by exact team name or by
    provider team id; synthetic scenarios are listed but flagged.
    """
    from .catalog import MatchCatalog

    team_clean = team.strip()
    matches: list[dict[str, Any]] = []
    for meta in MatchCatalog.list_matches():
        side = None
        if meta.home_team == team_clean or meta.home_provider_team_id == team_clean:
            side = "home"
        elif meta.away_team == team_clean or meta.away_provider_team_id == team_clean:
            side = "away"
        if side is None:
            continue
        matches.append({
            "match_id": meta.match_id,
            "label": meta.label,
            "competition": meta.competition,
            "season": meta.season,
            "match_date": meta.match_date,
            "side": side,
            "opponent": meta.away_team if side == "home" else meta.home_team,
            "provenance_kind": meta.provenance_kind,
            "data_provider": meta.data_provider,
            "coverage_status": meta.completeness_status,
            "dataset_imported": meta.completeness_status != "DATASET_NOT_IMPORTED",
        })
    matches.sort(key=lambda m: (m["match_date"] or "", m["match_id"]))
    return {
        "team": team_clean,
        "match_count": len(matches),
        "provider_matches": sum(1 for m in matches if m["provenance_kind"] == "provider_payload"),
        "other_provenance": sum(1 for m in matches if m["provenance_kind"] != "provider_payload"),
        "matches": matches,
        "note": (
            "Discovery reads catalog metadata only. Profiles are computed exclusively over "
            "provenance_kind=provider_payload matches."
        ),
    }


_PLAYER_INDEX_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}


def discover_players(match_ids: list[str], *, limit: int = 200, team: str | None = None, q: str | None = None) -> dict[str, Any]:
    """Index players across the requested provider matches.

    Scans normalized events (served from the catalog's content-keyed cache on
    repeat calls) and reports, per player: display name, the matches they
    appear in and their event volume. Response states whether the scan was a
    cache hit so the cost is measurable, never assumed.
    """
    from .adapters.statsbomb import StatsBombAdapter  # noqa: F401  (import guard: catalog needs it anyway)
    from .catalog import MatchCatalog

    ids = sorted({m for m in match_ids if m})
    signature = (tuple(ids), limit, team or "", (q or "").lower())
    cached = _PLAYER_INDEX_CACHE.get(signature)
    if cached is not None:
        return {**cached, "cache": "hit"}

    players: dict[str, dict[str, Any]] = {}
    scanned: list[str] = []
    errors: list[dict[str, str]] = []
    events, load_status = MatchCatalog.load_multiple_matches_with_status(ids)
    for mid in ids:
        status = load_status.get(mid, {})
        if status.get("status") != "ok":
            errors.append({"match_id": mid, "status": status.get("status", "unknown")})
            continue
        meta = MatchCatalog.get_match(mid)
        scanned.append(mid)
        team_names = {"H": meta.home_team if meta else "H", "N": meta.away_team if meta else "N"}
        for e in events.get(mid, []):
            pid = e.player_id
            if not pid:
                continue
            row = players.setdefault(str(pid), {
                "player_id": str(pid),
                "names": Counter(),
                "teams": Counter(),
                "match_ids": [],
                "event_count": 0,
            })
            if e.player_name:
                row["names"][e.player_name] += 1
            row["teams"][team_names.get(e.team_id, e.team_id)] += 1
            row["match_ids"].append(mid)
            row["event_count"] += 1

    rows = []
    q_clean = (q or "").strip().lower()
    for row in players.values():
        if team and team not in row["teams"]:
            continue
        entry = {
            "player_id": row["player_id"],
            "name": row["names"].most_common(1)[0][0] if row["names"] else row["player_id"],
            "teams": [t for t, _ in row["teams"].most_common()],
            "match_count": len(set(row["match_ids"])),
            "match_ids": sorted(set(row["match_ids"])),
            "event_count": row["event_count"],
        }
        if q_clean and q_clean not in entry["name"].lower():
            continue
        rows.append(entry)
    rows.sort(key=lambda r: (-r["event_count"], r["player_id"]))
    result = {
        "players": rows[:limit],
        "total_players": len(rows),
        "scanned_matches": scanned,
        "match_errors": errors,
        "cache": "miss",
        "note": "Counts come from provider event payloads; no metric is computed here.",
    }
    _PLAYER_INDEX_CACHE[signature] = result
    return result
