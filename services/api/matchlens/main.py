from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import math
import os
import secrets
import time
from collections import OrderedDict, defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger("matchlens.main")

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from typing import Callable, Literal

from .agents import AgentRunner, Run, PROMPT_VERSION
from .auth import Principal, SESSION_COOKIE, optional_principal
from .budget import BudgetLedger
from .runstore import TERMINAL_STATES
from .contracts import (
    ChallengeRequest,
    ClaimDraft,
    VerifierDecision,
    ask_the_match,
    evaluate_hypotheses,
    publication_gate,
    resolve_challenge,
)
from .football import (
    CHAPTERS,
    PLAYERS,
    SCENARIOS,
    Snapshot,
    both_team_receipts,
    build_player_spotlight,
    build_sequences,
    build_tactical_explorer,
    detect_moments,
    freeze,
    generate_match,
    metric_receipts,
    reduce_match,
)
from .oaai import compute_oaai, smooth_oaai_timeline, chart_oaai_payload, OAAIConfig
from .gate import publication_gate_2_0
from .metrics import (
    MetricsService,
    canonical_oaai_timeline,
    canonical_xt_model,
    registry_oaai_comparison,
    registry_recoveries_comparison,
)
from .models.xt import ExpectedThreatModel
from .score import verify_score
from .provider_projection import (
    bounded_state_events,
    is_protected_provider,
    public_event_summary,
    publication_notice,
    strip_sequence_event_detail,
)
from .exploration import (
    analyze_quick_recoveries,
    analyze_action_density_differential,
    analyze_attacking_channels,
    build_spatial_sequence_drilldown,
    locate_highlights,
)

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
COOKIE = SESSION_COOKIE


class RateLimits:
    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str, limit: int, window: int = 60):
        now = time.monotonic()
        hits = self.hits[key]
        while hits and hits[0] <= now-window:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(429, "rate_limit_exceeded", headers={"Retry-After": str(window)})
        hits.append(now)
        # Bound unauthenticated limiter memory, including rotating source addresses.
        if len(self.hits) > 2048:
            self.hits = defaultdict(deque, {k: v for k, v in self.hits.items() if v and v[-1] > now-window})


@dataclass
class Session:
    id: str
    ip: str
    at: int = 0
    paused: bool = True
    speed: int = 30
    epoch: int = 0
    revision: int = 0
    focus: str | None = None
    #: Last replayable clock (includes recorded stoppage time).
    format_seconds: int = 720
    #: Nominal playing time; never used to clamp a replay.
    nominal_seconds: int = 720
    match_id: str = "syn_default"
    touched: float = field(default_factory=time.monotonic)
    anchor_time: float = field(default_factory=time.monotonic)
    anchor_at: int = 0
    snapshots: dict[str, Snapshot] = field(default_factory=dict)
    snapshots_by_as_of: dict[int, Snapshot] = field(default_factory=dict)
    cache: dict[str, dict] = field(default_factory=dict)
    state_key: tuple | None = None
    state_value: dict | None = None
    run_info: dict | None = None
    task: asyncio.Task | None = None
    analyses: int = 0
    moments: dict[str, dict] = field(default_factory=dict)
    observed_at: int = -1
    attempted: set[str] = field(default_factory=set)
    attempts: dict[str, int] = field(default_factory=dict)
    last_auto_at: int = -30
    auto_started: int = 0
    scenario: str = "default"
    seed: int = 17
    focus_team: Literal["H", "N"] = "H"
    revisions: list[dict] = field(default_factory=list)
    moments_scan_truncated: bool = False

    def tick(self):
        if not self.paused:
            at = min(self.format_seconds, self.anchor_at+int((time.monotonic()-self.anchor_time)*self.speed))
            if at != self.at:
                self.at = at
                self.revision += 1
            if at >= self.format_seconds:
                self.at = self.format_seconds
                self.paused = True

    def invalidate(self):
        self.epoch += 1
        self.revision += 1
        if self.task and not self.task.done():
            self.task.cancel()
        self.run_info = None


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal[
        "focus", "focus_moment", "exit_focus", "play", "pause", "speed", "restart",
        "set_scenario", "set_team", "seek", "set_match"
    ]
    chapter: Literal["A", "B", "C"] | None = None
    moment_id: str | None = None
    speed: Literal[1, 6, 30] | None = None
    scenario: str | None = None
    team: Literal["H", "N"] | None = None
    at: int | None = None
    match_id: str | None = None


def freeze_with_context(
    events,
    ctx,
    at: int,
    *,
    seed: int = 17,
    scenario: str = "historical",
    match_id: str | None = None,
):
    """Single entry point for snapshot creation, bound to MatchContext."""
    bounded = max(0, min(int(at), int(math.ceil(ctx.replayable_end))))
    is_syn = ctx.mode == "synthetic_replay"
    official = (
        {"H": int(ctx.official_home_score), "N": int(ctx.official_away_score)}
        if not is_syn and ctx.official_home_score is not None and ctx.official_away_score is not None
        else None
    )
    legacy = is_syn and scenario == "default" and seed == 17 and match_id is None
    return freeze(
        events,
        bounded,
        seed=seed,
        match_id=None if legacy else (match_id or ctx.match_id),
        scenario=scenario if is_syn else "historical",
        data_version=ctx.data_version,
        clock_basis=ctx.match_clock_basis,
        teams={"H": ctx.home_team_name, "N": ctx.away_team_name},
        format_seconds=ctx.duration,
        team_map=(
            {ctx.home_provider_team_id: "H", ctx.away_provider_team_id: "N"}
            if ctx.home_provider_team_id and ctx.away_provider_team_id
            else None
        ),
        coordinate_frame=ctx.coordinate_frame,
        continuous_coverage=ctx.continuous_coverage,
        official_score=official,
        limitations=[ctx.partial_notice] if ctx.partial_notice else None,
        dataset_revision=ctx.dataset_revision or ctx.data_version,
        completeness=ctx.completeness,
        replayable_end=ctx.replayable_end,
    )


def freeze_match_snapshot(eng: "Engine", match_id: str, at: int) -> tuple[Snapshot, dict]:
    """Freeze a match API request with the same event identity as a session.

    Delegates to the engine's bounded LRU. The cache key is content-addressed
    (dataset revision + clock/metric versions), so a changed payload or clock
    model can never serve a stale snapshot.
    """
    return eng.frozen(match_id, at)


def _freeze_match_snapshot_uncached(eng: "Engine", match_id: str, at: int) -> tuple[Snapshot, dict]:
    from .catalog import MatchCatalog

    ctx = eng.match_context(match_id)
    bounded = max(0, min(int(at), int(math.ceil(ctx.replayable_end))))
    if match_id.startswith("syn_"):
        scenario = match_id.replace("syn_", "", 1)
        events = eng.events_for_match(match_id, scenario=scenario)
        legacy = match_id == "syn_default" and scenario == "default"
        snap = freeze(
            events,
            bounded,
            seed=17,
            match_id=None if legacy else match_id,
            scenario=scenario,
            data_version=ctx.data_version,
            clock_basis=ctx.match_clock_basis,
            teams={"H": ctx.home_team_name, "N": ctx.away_team_name},
            format_seconds=ctx.duration,
            team_map=None,
            coordinate_frame=ctx.coordinate_frame,
            continuous_coverage=ctx.continuous_coverage,
            dataset_revision=ctx.dataset_revision or ctx.data_version,
            completeness=ctx.completeness,
            replayable_end=ctx.replayable_end,
        )
    else:
        events = eng.events_for_match(match_id)
        snap = freeze_with_context(events, ctx, bounded, match_id=match_id, scenario="historical")
    state = reduce_match(
        events,
        bounded,
        max_duration=int(math.ceil(ctx.replayable_end)),
        nominal_duration=ctx.duration,
        is_synthetic=match_id.startswith("syn_"),
        team_names={"H": ctx.home_team_name, "N": ctx.away_team_name},
        team_map=(
            {ctx.home_provider_team_id: "H", ctx.away_provider_team_id: "N"}
            if ctx.home_provider_team_id and ctx.away_provider_team_id
            else None
        ),
        coordinate_frame=ctx.coordinate_frame,
        continuous_coverage=ctx.continuous_coverage,
        official_score=(
            {"H": int(ctx.official_home_score), "N": int(ctx.official_away_score)}
            if ctx.mode != "synthetic_replay"
            and ctx.official_home_score is not None
            and ctx.official_away_score is not None
            else None
        ),
    )
    return snap, state


class Engine:
    def __init__(self, runtime: Path, key: str | None):
        self.events = generate_match()
        self.scenario_events = {("default", 17): self.events}
        self.real_events: dict[str, list] = {}
        self.context_cache: dict[str, object] = {}
        self.exploration_cache: dict[tuple, dict] = {}
        self.story_cache: dict[tuple, object] = {}
        from .broadcast import BroadcastStore
        self.broadcast = BroadcastStore(runtime / "broadcast.json")
        self.xt_model = ExpectedThreatModel.load_default("16x12")
        self.sessions: dict[str, Session] = {}
        self.rates = RateLimits()
        self.ledger = BudgetLedger(runtime / "budget.sqlite3", int(os.getenv("MATCHLENS_MAX_REQUESTS", "32")), float(os.getenv("MATCHLENS_MAX_RESERVED_USD", "1.0")))
        self.runner = AgentRunner(key, self.ledger)
        from .registry import ClaimRegistry
        from .investigation import InvestigationStore
        from .runstore import AgentRunStore
        self.registry = ClaimRegistry(runtime / "claims.json")
        self.investigations = InvestigationStore(runtime / "investigations.json")
        self.agent_runs = AgentRunStore(runtime / "agent_runs.json")
        self.auto_enabled = os.getenv("MATCHLENS_AUTO_ANALYSE", "0") == "1"
        self.auto_limit = min(2, max(0, int(os.getenv("MATCHLENS_AUTO_RUNS_PER_SESSION", "2"))))
        self.admissions: set[str] = set()
        self.slots = asyncio.Semaphore(2)
        self.runtime = runtime
        (runtime / "runs").mkdir(parents=True, exist_ok=True)
        # Bounded caches. Keys always include the dataset revision and the
        # clock/metric versions; a bounded LRU is the only eviction policy, so
        # a changed payload cannot be served from a warm entry.
        self.snapshot_cache: OrderedDict[tuple, tuple[Snapshot, dict]] = OrderedDict()
        self.snapshot_cache_max_entries = 6
        self.snapshot_cache_max_bytes = 64 * 1024 * 1024
        self.snapshot_cache_bytes = 0
        self.oaai_cache: OrderedDict[tuple, dict] = OrderedDict()
        self.oaai_cache_max_entries = 32
        # Featured-investigation responses are pure catalog+OAAI derivations, so
        # they are memoised per catalog signature for the process lifetime.
        self.featured_cache: OrderedDict[str, dict] = OrderedDict()
        self.featured_cache_max_entries = 4
        self.cache_stats = {
            "snapshot_hits": 0,
            "snapshot_misses": 0,
            "snapshot_evictions": 0,
            "oaai_hits": 0,
            "oaai_misses": 0,
            "oaai_evictions": 0,
        }
        self.saved_runs: dict[str, dict] = {}
        self.saved_snapshots: dict[str, Snapshot] = {}
        # Live investigation requests, keyed by owner + client request key. The
        # event is checked before each model dispatch and races the in-flight
        # provider call, so a cancel cannot start the next paid stage.
        self.investigation_requests: dict[str, asyncio.Event] = {}
        self.investigation_request_runs: dict[str, str] = {}
        # A cancel can arrive a few milliseconds before the POST registers its
        # request. Keep a short-lived tombstone so the run starts cancelled.
        self.investigation_cancel_tombstones: dict[str, float] = {}
        for p in sorted((runtime / "runs").glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                snap_id = data.get("snapshot_id")
                res = data.get("result")
                if snap_id and res and res.get("status") == "completed" and res.get("accepted"):
                    evidence_match = data["evidence"].get("match_id") or "syn_default"
                    try:
                        evidence_ctx = self.match_context(
                            evidence_match if evidence_match.startswith("sb_") else "syn_default"
                        )
                    except (FileNotFoundError, ValueError):
                        evidence_ctx = None
                    snap = freeze(
                        self.events,
                        data["evidence"]["as_of"],
                        dataset_revision=data["evidence"].get("dataset_revision"),
                        completeness=evidence_ctx.completeness if evidence_ctx else None,
                    )
                    # A historical receipt must match this match prefix byte for
                    # byte and pass today's gate. Never relabel an old hash.
                    if snap.id != snap_id or snap.data != data["evidence"]:
                        continue
                    checked = publication_gate(ClaimDraft.model_validate(data["draft"]), VerifierDecision.model_validate(data["review"]), snap, data["audit"])
                    if not checked["accepted"]:
                        continue
                    for card in checked["accepted"]:
                        card.update(historical=True, source_run_id=data.get("run_id", p.stem))
                        self.registry.register_verified_claim(
                            "syn_default",
                            snap_id,
                            card,
                            source_run=str(data.get("run_id", p.stem)),
                            gate_status="approved",
                            gate_version="publication_gate-v1",
                        )
                    self.saved_runs[snap_id] = {**res, **checked, "reused": True, "snapshot_id": snap_id, "as_of": snap.data["as_of"],
                                               "audit": data["audit"], "requests": data["requests"], "run_id": data.get("run_id", p.stem)}
                    self.saved_snapshots[snap_id] = snap
                    # Dual-track mapping for evidence-v2 snapshot id
                    try:
                        v2_snap = freeze(
                            self.events,
                            data["evidence"]["as_of"],
                            seed=17,
                            match_id="syn_default",
                            scenario="default",
                            completeness=self.match_context("syn_default").completeness,
                        )
                        self.saved_runs[v2_snap.id] = {**self.saved_runs[snap_id], "snapshot_id": v2_snap.id}
                        self.saved_snapshots[v2_snap.id] = v2_snap
                    except Exception:
                        pass
            except Exception:
                pass

    @staticmethod
    def _investigation_request_key(owner_id: str, request_key: str) -> str:
        return f"{owner_id}:{request_key}"

    def begin_investigation_request(self, owner_id: str, request_key: str) -> asyncio.Event:
        key = self._investigation_request_key(owner_id, request_key)
        event = self.investigation_requests.get(key)
        if event is None:
            event = asyncio.Event()
            self.investigation_requests[key] = event
        if self.investigation_cancel_tombstones.pop(key, None) is not None:
            event.set()
        return event

    def bind_investigation_run(self, owner_id: str, request_key: str, run_id: str) -> None:
        self.investigation_request_runs[self._investigation_request_key(owner_id, request_key)] = run_id

    def cancel_investigation_request(self, owner_id: str, request_key: str) -> dict[str, object]:
        key = self._investigation_request_key(owner_id, request_key)
        event = self.investigation_requests.get(key)
        active = event is not None
        if event is not None:
            event.set()
        else:
            self.investigation_cancel_tombstones[key] = time.monotonic()
        now = time.monotonic()
        expired = [k for k, ts in self.investigation_cancel_tombstones.items() if now - ts > 120]
        for expired_key in expired:
            self.investigation_cancel_tombstones.pop(expired_key, None)
        return {"active": active, "run_id": self.investigation_request_runs.get(key)}

    def end_investigation_request(self, owner_id: str, request_key: str) -> None:
        key = self._investigation_request_key(owner_id, request_key)
        self.investigation_requests.pop(key, None)
        self.investigation_request_runs.pop(key, None)

    def events_for(self, s: Session):
        if not s.match_id.startswith("syn_"):
            if s.match_id not in self.real_events:
                from .catalog import MatchCatalog
                self.real_events[s.match_id] = MatchCatalog.load_normalized_events(s.match_id)
            return self.real_events[s.match_id]
        key = (s.scenario, s.seed)
        if key not in self.scenario_events:
            self.scenario_events[key] = generate_match(seed=s.seed, scenario=s.scenario)
        return self.scenario_events[key]

    def events_for_match(self, match_id: str, scenario: str | None = None, seed: int = 17):
        """Use the same event representation as a session for synthetic fixtures."""
        if match_id.startswith("syn_"):
            scenario = scenario or match_id.replace("syn_", "", 1)
            key = (scenario, seed)
            if key not in self.scenario_events:
                self.scenario_events[key] = generate_match(seed=seed, scenario=scenario)
            return self.scenario_events[key]
        if match_id not in self.real_events:
            from .catalog import MatchCatalog
            self.real_events[match_id] = MatchCatalog.load_normalized_events(match_id)
        return self.real_events[match_id]

    def match_context(self, match_id: str):
        from .catalog import MatchCatalog

        version = MatchCatalog.data_version(match_id)
        key = f"{match_id}@{version}"
        if key not in self.context_cache:
            self.context_cache[key] = MatchCatalog.get_match_context(match_id)
        return self.context_cache[key]

    def _snapshot_key(self, match_id: str, at: int) -> tuple:
        ctx = self.match_context(match_id)
        return (
            match_id,
            ctx.dataset_revision or ctx.data_version,
            ctx.clock_version,
            ctx.metric_version,
            int(at),
        )

    def frozen(self, match_id: str, at: int) -> tuple[Snapshot, dict]:
        ctx = self.match_context(match_id)
        bounded = max(0, min(int(at), int(math.ceil(ctx.replayable_end))))
        key = self._snapshot_key(match_id, bounded)
        cached = self.snapshot_cache.get(key)
        if cached is not None:
            self.snapshot_cache.move_to_end(key)
            self.cache_stats["snapshot_hits"] += 1
            return cached
        self.cache_stats["snapshot_misses"] += 1
        result = _freeze_match_snapshot_uncached(self, match_id, bounded)
        snap, state = result
        estimate = max(1, len(snap.canonical)) * 3
        while self.snapshot_cache and (
            len(self.snapshot_cache) >= self.snapshot_cache_max_entries
            or self.snapshot_cache_bytes + estimate > self.snapshot_cache_max_bytes
        ):
            _, (old_snap, _old_state) = self.snapshot_cache.popitem(last=False)
            self.snapshot_cache_bytes -= max(1, len(old_snap.canonical)) * 3
            self.cache_stats["snapshot_evictions"] += 1
        self.snapshot_cache[key] = result
        self.snapshot_cache_bytes += estimate
        return result

    def oaai_for(
        self,
        match_id: str,
        events: list,
        at: float,
        *,
        smoothing_mode: Literal["causal", "bilateral"] = "causal",
        xt_model: Any = None,
        dead_intervals: list[dict] | None = None,
        include_raw: bool = False,
    ) -> dict:
        ctx = self.match_context(match_id)
        dead_intervals = dead_intervals or []
        dead_signature = hashlib.sha256(
            json.dumps(dead_intervals, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
        key = (
            match_id,
            ctx.dataset_revision or ctx.data_version,
            ctx.clock_version,
            round(float(at), 3),
            smoothing_mode,
            len(events),
            dead_signature,
            include_raw,
            getattr(xt_model, "model_version", "none") if xt_model is not None else "none",
        )
        cached = self.oaai_cache.get(key)
        if cached is not None:
            self.oaai_cache.move_to_end(key)
            self.cache_stats["oaai_hits"] += 1
            return dict(cached)
        self.cache_stats["oaai_misses"] += 1
        result = compute_oaai(
            events,
            smoothing_mode=smoothing_mode,
            t_end=int(at),
            dead_intervals=dead_intervals,
            xt_model=xt_model,
            include_raw=include_raw,
        )
        while len(self.oaai_cache) >= self.oaai_cache_max_entries:
            self.oaai_cache.popitem(last=False)
            self.cache_stats["oaai_evictions"] += 1
        self.oaai_cache[key] = result
        return dict(result)

    def reduce_state(self, s: Session, at: int | None = None):
        ctx = self.match_context(s.match_id)
        target = s.at if at is None else at
        key = (
            s.match_id,
            ctx.data_version,
            ctx.clock_version,
            int(target),
            s.scenario,
            s.seed,
            ctx.coordinate_frame,
        )
        if at is None and s.state_key == key and s.state_value is not None:
            return s.state_value
        state = reduce_match(
            self.events_for(s),
            target,
            max_duration=int(math.ceil(ctx.replayable_end)),
            nominal_duration=ctx.duration,
            is_synthetic=ctx.mode == "synthetic_replay",
            team_names={"H": ctx.home_team_name, "N": ctx.away_team_name},
            team_map=(
                {ctx.home_provider_team_id: "H", ctx.away_provider_team_id: "N"}
                if ctx.home_provider_team_id and ctx.away_provider_team_id
                else None
            ),
            coordinate_frame=ctx.coordinate_frame,
            continuous_coverage=ctx.continuous_coverage,
            official_score=(
                {"H": int(ctx.official_home_score), "N": int(ctx.official_away_score)}
                if ctx.mode != "synthetic_replay"
                and ctx.official_home_score is not None
                and ctx.official_away_score is not None
                else None
            ),
        )
        if at is None:
            s.state_key = key
            s.state_value = state
        return state

    def snapshot_for(self, s: Session, at: int):
        ctx = self.match_context(s.match_id)
        legacy_default = (
            s.match_id.startswith("syn_") and s.scenario == "default" and s.seed == 17
        )
        return freeze_with_context(
            self.events_for(s),
            ctx,
            at,
            seed=s.seed,
            scenario=s.scenario,
            match_id=None if legacy_default else s.match_id,
        )

    def snapshot_at(self, s: Session, at: int) -> Snapshot:
        """Frozen snapshot of the session at a given clock, cached per session.

        The registry observations attached to the chart data must refer to the
        very same frozen snapshot the rest of the session publishes, otherwise
        the chart and the registry would compare different clocks.
        """
        snap = s.snapshots_by_as_of.get(at)
        if snap is None:
            snap = self.snapshot_for(s, at)
            s.snapshots_by_as_of[at] = snap
            s.snapshots.setdefault(snap.id, snap)
        return snap

    def cleanup(self):
        for sid, s in list(self.sessions.items()):
            if time.monotonic()-s.touched > 1800:
                s.invalidate()
                del self.sessions[sid]

    def view(self, s: Session) -> dict:
        s.tick()
        active_events = self.events_for(s)
        is_syn = s.match_id.startswith("syn_")
        match_ctx = self.match_context(s.match_id)
        state = self.reduce_state(s)
        # Scan newly crossed event boundaries so 30x playback cannot skip a
        # detector condition. On large historical feeds the scan is bounded:
        # structural events and an even sample are prioritised, and truncation
        # is reported rather than hidden.
        crossed = sorted({
            getattr(e, "t", getattr(e, "clock_seconds", 0))
            for e in active_events
            if s.observed_at < getattr(e, "t", getattr(e, "clock_seconds", 0)) <= s.at
        })
        if len(crossed) > 240:
            structural = [
                getattr(e, "t", getattr(e, "clock_seconds", 0))
                for e in active_events
                if s.observed_at < getattr(e, "t", getattr(e, "clock_seconds", 0)) <= s.at
                and str(e.get("kind") if isinstance(e, dict) else getattr(e, "kind", "")) in ("shot", "recovery")
            ][:120]
            step = max(1, len(crossed) // 120)
            sampled = crossed[::step][:120]
            times = sorted(set(structural) | set(sampled) | ({s.at} if s.at > s.observed_at else set()))
            s.moments_scan_truncated = True
        else:
            times = sorted(set(crossed) | ({s.at} if s.at > s.observed_at else set()))
        is_default_fixture = s.scenario == "default" and s.seed == 17 and is_syn

        for at in times:
            for moment in detect_moments(self.reduce_state(s, at)):
                if moment["id"] not in s.moments:
                    s.moments[moment["id"]] = moment
                    snap = self.snapshot_for(s, moment["at"])
                    s.snapshots[snap.id] = snap
        s.observed_at = max(s.observed_at, s.at)
        moments = sorted((m for m in s.moments.values() if m["at"] <= s.at), key=lambda m: m["at"])
        active = min(moments, key=lambda m: (m["priority"], -m["at"])) if moments else None
        if s.focus in ("A", "B", "C"):
            active = None
        elif s.focus in s.moments:
            active = s.moments[s.focus]
        elif s.run_info:
            active = next((m for m in moments if m["at"] == s.run_info.get("as_of")), active)
        if self.auto_enabled and not s.focus and (not s.paused or state["ended"]):
            self.schedule_auto(s, moments)

        # Snapshot resolution
        if s.focus:
            snapshot = next((snap for snap in s.snapshots.values() if snap.data["as_of"] == s.at), None)
            if not snapshot:
                snapshot = self.snapshot_for(s, s.at)
                s.snapshots[snapshot.id] = snapshot
        elif s.run_info and s.run_info.get("as_of", int(math.ceil(match_ctx.replayable_end)) + 1) <= s.at:
            snapshot = next((snap for snap in s.snapshots.values() if snap.data["as_of"] == s.run_info["as_of"]), None)
        elif s.paused and any(snap.data["as_of"] == s.at for snap in s.snapshots.values()):
            snapshot = next(snap for snap in s.snapshots.values() if snap.data["as_of"] == s.at)
        elif active:
            snapshot = next((snap for snap in s.snapshots.values() if snap.data["as_of"] == active["at"]), None)
            if not snapshot:
                snapshot = self.snapshot_for(s, active["at"])
                s.snapshots[snapshot.id] = snapshot
        else:
            snapshot = None

        # Result resolution: if actively analysing, result is None until finished
        is_default_fixture = s.scenario == "default" and s.seed == 17 and is_syn
        pending = s.run_info is not None and s.run_info.get("status") in ("queued", "analysing", "verifying")
        if pending:
            result = None
        else:
            result = s.cache.get(snapshot.id) if snapshot else None
            if not result and is_default_fixture and snapshot and snapshot.id in self.saved_runs:
                result = self.saved_runs[snapshot.id]
            if result and "reused" not in result:
                result = {**result, "reused": s.run_info is None or s.run_info.get("run_id") != result.get("run_id")}

        # History resolution
        all_accepted = {}
        if is_default_fixture:
            for snap_id, r in self.saved_runs.items():
                for card in r.get("accepted", []):
                    all_accepted[f"{card['snapshot_id']}-{card['claim_id']}"] = card
        for r in s.cache.values():
            if r.get("status") == "completed":
                for card in r.get("accepted", []):
                    all_accepted[f"{card['snapshot_id']}-{card['claim_id']}"] = card
        accepted_history = [card for card in all_accepted.values() if card.get("as_of", 0) <= s.at]
        if is_default_fixture:
            for card in accepted_history:
                snap_id = card.get("snapshot_id")
                if snap_id in self.saved_snapshots:
                    s.snapshots[snap_id] = self.saved_snapshots[snap_id]

        teams = {"H": match_ctx.home_team_name, "N": match_ctx.away_team_name}
        if is_syn:
            players = PLAYERS
        else:
            # Roster identity comes from the full source, not only the prefix
            # observed so far; a kick-off state still knows who may appear.
            players = {
                team: sorted({
                    str(getattr(e, "player_name", None) or getattr(e, "player_id", ""))
                    for e in active_events
                    if getattr(e, "team_id", "") == team
                    and (getattr(e, "player_name", None) or getattr(e, "player_id", None))
                })
                for team in ("H", "N")
            }
        # Always the score observed up to the requested timestamp. The official
        # final score is exposed separately and is never projected backwards.
        score = state["score"]

        cache_key = (
            s.match_id,
            match_ctx.data_version,
            s.scenario,
            s.seed,
            s.at,
            s.focus_team,
            state["coverage"]["event_count"],
        )
        if cache_key in self.exploration_cache:
            exp_data = self.exploration_cache[cache_key]
        else:
            sequences = build_sequences(state)
            tactical = build_tactical_explorer(state, s.focus_team)
            # The chart timeline and the registry observations must describe the
            # same frozen clock, so the timeline runs to the snapshot's as_of and
            # the registry peak is read from that very timeline.
            chart_snapshot = self.snapshot_at(s, s.at)
            chart_data = chart_snapshot.data
            oaai_data = self.oaai_for(
                s.match_id,
                state["events"],
                int(chart_data.get("as_of", s.at)),
                smoothing_mode="causal",
                dead_intervals=state.get("dead_intervals", []),
                xt_model=canonical_xt_model(),
            )
            oaai_data["registry_comparison"] = registry_oaai_comparison(
                chart_snapshot,
                oaai_data.get("timeline", []),
                registry_comparable=True,
                reason=None,
                chart_smoothing_mode="causal",
                data=chart_data,
            )
            quick_rec = analyze_quick_recoveries(state["events"], window_seconds=6.0, target_team=s.focus_team)
            density_diff = analyze_action_density_differential(state["events"])
            channels = analyze_attacking_channels(
                state["events"],
                sequences=sequences,
                team=s.focus_team,
                team_name=match_ctx.home_team_name if s.focus_team == "H" else match_ctx.away_team_name,
                coordinate_frame=state.get("coordinate_frame", "fixed"),
            )
            drilldown = build_spatial_sequence_drilldown(sequences, tactical.get("zone_cells"))
            highlights = locate_highlights(
                state["events"],
                sequences,
                oaai_data=oaai_data,
                team_names={"H": match_ctx.home_team_name, "N": match_ctx.away_team_name},
            )
            exp_data = {
                "sequences": sequences,
                "tactical": tactical,
                # The chart receives a size-bounded copy of the timeline. The
                # registry comparison above was computed on the full
                # resolution timeline and is carried over unchanged.
                "oaai": chart_oaai_payload(oaai_data),
                "quick_recoveries": quick_rec,
                "density_differential": density_diff,
                "attacking_channels": channels,
                "spatial_drilldown": drilldown,
                "highlights": highlights,
                "player_spotlight": build_player_spotlight(state),
            }
            if len(self.exploration_cache) > 100:
                self.exploration_cache.clear()
            self.exploration_cache[cache_key] = exp_data

        # Provider payloads are protected data. The public cockpit receives a
        # bounded replay window and coordinate-free sequence steps, while the
        # charts, metrics and evidence references remain complete. The full
        # machine-readable event stream stays behind the producer boundary.
        public_events = state["events"]
        public_sequences = exp_data["sequences"]
        provider_boundary = None
        if is_protected_provider(match_ctx.provenance_kind):
            public_events, window = bounded_state_events(
                state["events"], at=s.at, total_events=len(active_events)
            )
            public_sequences = strip_sequence_event_detail(exp_data["sequences"], at=s.at)
            provider_boundary = {
                **publication_notice(match_id=s.match_id, tier="public_analysis_projection"),
                "state_window": window,
                "full_event_endpoint": f"/api/matches/{s.match_id}/events",
                "full_event_access": "producer_or_internal_data_access",
            }

        return {
            "revision": s.revision, "epoch": s.epoch, "at": s.at, "paused": s.paused, "speed": s.speed,
            "scenario": s.scenario, "scenarios": list(SCENARIOS.values()), "focus_team": s.focus_team,
            "focus": s.focus, "score": score, "score_basis": state["score_basis"],
            "official_score": (
                {"H": match_ctx.official_home_score, "N": match_ctx.official_away_score}
                if not is_syn and match_ctx.official_home_score is not None else None
            ),
            "coverage": state["coverage"],
            "owner": state["owner"], "ball": state["ball"],
            "events": public_events, "players": players, "receipts": both_team_receipts(state),
            "teams": teams, "match_context": match_ctx.model_dump(),
            "sequences": public_sequences, "tactical": exp_data["tactical"],
            "player_spotlight": exp_data["player_spotlight"],
            "oaai": exp_data["oaai"], "quick_recoveries": exp_data["quick_recoveries"],
            "density_differential": exp_data["density_differential"], "attacking_channels": exp_data["attacking_channels"],
            "spatial_drilldown": exp_data["spatial_drilldown"], "highlights": exp_data["highlights"],
            "provider_data_boundary": provider_boundary,
            "chapters": CHAPTERS, "moments": moments, "active_moment": active,
            "moments_scan_truncated": s.moments_scan_truncated,
            "snapshot_id": snapshot.id if snapshot else None,
            "snapshot_as_of": snapshot.data["as_of"] if snapshot else None,
            "analysis_receipts": snapshot.data["receipts"] if snapshot else None,
            "analysis": s.run_info, "result": result, "history": accepted_history,
            "revisions": s.revisions,
            "hypotheses_matrix": evaluate_hypotheses(snapshot, s.focus_team).model_dump() if snapshot else None,
            "model_configured": bool(self.runner.key), "session_analyses_remaining": max(0, 8-s.analyses),
            "auto_status": "disabled" if not self.auto_enabled else "model_unavailable" if not self.runner.key else "budget_limited" if not self.can_admit() else "session_limited" if s.auto_started >= self.auto_limit else "enabled",
            "format_seconds": s.format_seconds,
            "nominal_duration": s.nominal_seconds,
            "match_id": s.match_id,
            "ended": state["ended"],
        }

    def ensure_snapshot_claims(self, match_id: str, snap: Snapshot) -> None:
        """Execute the deterministic gate for the standard assertions.

        Rejected candidates are registered too; a claim existing in the registry
        never implies it was approved.
        """
        from .registry import ClaimRegistry  # noqa: F401

        for assertion in (
            "goal_sequence",
            "possession_without_penetration",
            "attacking_threat_increased",
            "recoveries_followed_by_shots",
        ):
            for team in ("H", "N"):
                self.registry.verify_and_register(
                    snap,
                    match_id,
                    assertion,
                    team,
                    source_run="deterministic_gate",
                )

    def get_registered_claims(self, s: Session, snap: Snapshot) -> set[str]:
        """Claim IDs with an actual persisted gate verdict for this snapshot."""
        self.ensure_snapshot_claims(s.match_id, snap)
        return {r.claim_id for r in self.registry.records_for(s.match_id, snap.id)}

    def can_admit(self) -> bool:
        # Conservative whole-workflow runway; dispatches still reserve durably
        # before HTTP. The application deliberately runs one worker/replica.
        return self.ledger.has_runway(6 * (len(self.admissions) + 1))

    def start_analysis(self, s: Session, snap: Snapshot, trigger: str) -> bool:
        if s.task and not s.task.done() or s.analyses >= 8 or not self.can_admit():
            return False
        if snap.id in s.attempted and (trigger == "automatic" or s.attempts.get(snap.id, 0) >= 2):
            return False
        for key, cap in (("analyse:"+s.id, 3), ("analyse-ip:"+s.ip, 6), ("analyse:global", 12)):
            self.rates.check(key, cap)
        run = Run(
            "run-"+secrets.token_hex(8),
            snap,
            match_id=s.match_id,
            dataset_revision=str(snap.data.get("dataset_revision") or snap.data.get("data_version") or ""),
            epoch=s.epoch,
        )
        run.audit.append({
            "type": "trigger", "source": trigger, "as_of": snap.data["as_of"],
            "match_id": run.match_id, "dataset_revision": run.dataset_revision, "epoch": run.epoch,
        })
        s.attempted.add(snap.id)
        s.attempts[snap.id] = s.attempts.get(snap.id, 0) + 1
        s.analyses += 1
        self.admissions.add(run.id)
        s.run_info = {"run_id": run.id, "status": "queued", "as_of": snap.data["as_of"], "epoch": s.epoch}
        s.revision += 1
        # A lifecycle record exists only when a model run is actually possible;
        # deterministic fallbacks are not agent runs.
        if self.runner.key:
            self.agent_runs.create(
                run_id=run.id,
                trigger=trigger,  # type: ignore[arg-type]
                match_id=run.match_id,
                snapshot_id=snap.id,
                model="deepseek-flash",
                prompt_version=PROMPT_VERSION,
                dataset_revision=run.dataset_revision,
                epoch=s.epoch,
                audit=run.audit,
                owner_session_id=s.id,
            )
        s.task = asyncio.create_task(self.execute(s, snap, s.epoch, run))

        def close_lifecycle(task: asyncio.Task):
            self.admissions.discard(run.id)
            # A task that never reached execute's result mapping (cancelled
            # before the first step, or crashed) must not leave an ambiguous
            # non-terminal record behind.
            record = self.agent_runs.get(run.id) if self.runner.key else None
            if record is None or record.state in TERMINAL_STATES:
                return
            if task.cancelled():
                self.agent_runs.cancel(run.id, reason="cancelled before completion")
            elif task.exception() is not None:
                self.agent_runs.finish(run.id, state="FAILED", reason="run_task_crashed",
                                       error="run_task_crashed", audit_entries=record.audit)
            else:
                self.agent_runs.cancel(run.id, reason="run task ended without terminal transition")

        # Cancellation can happen before the coroutine reaches its finally.
        s.task.add_done_callback(close_lifecycle)
        return True

    def schedule_auto(self, s: Session, moments: list[dict]):
        if not self.runner.key or s.auto_started >= self.auto_limit or s.task and not s.task.done() or s.at-s.last_auto_at < 30:
            return
        # Four detector types bound the queue; old-epoch tasks cannot commit.
        for moment in sorted(moments, key=lambda m: (m["priority"], -m["at"])):
            snap = next(v for v in s.snapshots.values() if v.data["as_of"] == moment["at"])
            if snap.id in s.attempted:
                continue
            try:
                asyncio.get_running_loop()
                if self.start_analysis(s, snap, "automatic"):
                    s.last_auto_at = s.at
                    s.auto_started += 1
            except (RuntimeError, HTTPException):
                pass
            break

    async def execute(self, s: Session, snapshot: Snapshot, epoch: int, run: Run):
        result = None
        def lifecycle_record():
            return self.agent_runs.get(run.id) if self.runner.key else None

        def finish_lifecycle(state, reason, **kwargs):
            record = lifecycle_record()
            if record is not None and record.state not in TERMINAL_STATES:
                self.agent_runs.finish(run.id, state=state, reason=reason, **kwargs)

        async def progress(status: str):
            if epoch != s.epoch:
                raise asyncio.CancelledError()
            s.run_info = {"run_id": run.id, "status": status, "as_of": snapshot.data["as_of"], "epoch": epoch}
            s.revision += 1
            if not lifecycle_record():
                return
            record = self.agent_runs.get(run.id)
            if status == "analysing":
                self.agent_runs.attach(run.id, run.audit, run.requests)
                self.agent_runs.transition(run.id, "ANALYSING", "analyst stage dispatch")
            elif status == "verifying" and record is not None:
                if record.state == "ANALYSING":
                    self.agent_runs.transition(run.id, "HANDOFF", "analyst draft handed to verifier")
                self.agent_runs.attach(run.id, run.audit, run.requests)
                self.agent_runs.transition(run.id, "VERIFYING", "verifier stage dispatch")
        try:
            # Queue time is bounded separately from model time.
            async with asyncio.timeout(5):
                await self.slots.acquire()
            try:
                result = await self.runner.analyse(run, progress)
            finally:
                self.slots.release()
            result.update(run_id=run.id, snapshot_id=snapshot.id, as_of=snapshot.data["as_of"],
                          audit=run.audit, requests=run.requests)
            # A run is committed only under its frozen identity. The registry
            # write must never read a match_id that the session changed while
            # the model was running, and a stale run only leaves audit evidence.
            snapshot_match = str(snapshot.data.get("match_id") or "")
            legacy_default = run.match_id == "syn_default" and snapshot_match.startswith("harbor-northbridge-")
            identity_ok = (
                epoch == s.epoch
                and run.match_id == s.match_id
                and (snapshot_match == run.match_id or legacy_default)
                and snapshot.data.get("as_of", 0) <= s.at
            )
            if identity_ok:
                for card in result.get("accepted", []):
                    self.registry.register_verified_claim(
                        run.match_id,
                        snapshot.id,
                        card,
                        source_run=run.id,
                        gate_status="approved",
                        gate_version="publication_gate-v1",
                        dataset_revision=run.dataset_revision,
                    )
                s.cache[snapshot.id] = result
                s.run_info = {"run_id": run.id, "status": result["status"], "as_of": result["as_of"], "epoch": epoch}
                s.revision += 1
                if result.get("status") == "completed":
                    if lifecycle_record():
                        # A completed run reached the gate even if its role
                        # stages never emitted verifying progress; walk the
                        # bounded path instead of jumping across the machine.
                        record = self.agent_runs.get(run.id)
                        walk = {
                            "QUEUED": ["ANALYSING", "HANDOFF", "VERIFYING"],
                            "ANALYSING": ["HANDOFF", "VERIFYING"],
                            "TOOL_WAIT": ["ANALYSING", "HANDOFF", "VERIFYING"],
                            "HANDOFF": ["VERIFYING"],
                        }
                        for target in walk.get(record.state, []):
                            self.agent_runs.transition(run.id, target, "run completed; bounded lifecycle walk")
                        self.agent_runs.attach(run.id, run.audit, run.requests)
                        self.agent_runs.transition(run.id, "GATED", "publication gate executed")
                        if result.get("accepted"):
                            self.agent_runs.finish(run.id, state="PUBLISHED", reason="accepted cards registered",
                                                   origin=result.get("origin"), accepted_count=len(result.get("accepted", [])),
                                                   rejected_count=len(result.get("rejected", [])),
                                                   audit_entries=run.audit, requests=run.requests)
                        else:
                            self.agent_runs.finish(run.id, state="WITHHELD", reason="gate withheld every draft claim",
                                                   origin=result.get("origin"), accepted_count=0,
                                                   rejected_count=len(result.get("rejected", [])),
                                                   audit_entries=run.audit, requests=run.requests)
                else:
                    finish_lifecycle("FAILED", str(result.get("error") or "analysis_failed"),
                                     error=str(result.get("error") or "analysis_failed"),
                                     origin=result.get("origin"), audit_entries=run.audit, requests=run.requests)
            else:
                run.audit.append({
                    "type": "superseded",
                    "bound_epoch": epoch,
                    "current_epoch": s.epoch,
                    "bound_match_id": run.match_id,
                    "current_match_id": s.match_id,
                    "snapshot_match_id": snapshot_match,
                    "reason": "identity_or_clock_mismatch",
                })
                finish_lifecycle("CANCELLED", "superseded_identity_mismatch",
                                 origin=result.get("origin") if result else None,
                                 audit_entries=run.audit, requests=run.requests)
        except asyncio.CancelledError:
            run.audit.append({"type": "superseded", "bound_epoch": epoch, "current_epoch": s.epoch})
            finish_lifecycle("CANCELLED", "superseded by session epoch change",
                             audit_entries=run.audit, requests=run.requests)
        except TimeoutError:
            result = {"status": "fallback", "origin": "deterministic", "error": "analysis_queue_busy", "accepted": [], "rejected": [],
                      "run_id": run.id, "snapshot_id": snapshot.id, "as_of": snapshot.data["as_of"], "audit": run.audit, "requests": run.requests}
            finish_lifecycle("FAILED", "analysis_queue_busy", error="analysis_queue_busy",
                             origin="deterministic", audit_entries=run.audit, requests=run.requests)
            if epoch == s.epoch:
                s.cache[snapshot.id] = result
                s.run_info = {"status": "fallback", "run_id": run.id, "as_of": result["as_of"], "epoch": epoch}
                s.revision += 1
        finally:
            self.admissions.discard(run.id)
            record = {"run_id": run.id, "snapshot_id": snapshot.id, "evidence": snapshot.data,
                      "prompt_version": PROMPT_VERSION,
                      "bound_epoch": epoch, "current_epoch": s.epoch, "draft": run.draft, "review": run.review,
                      "result": result, "audit": run.audit, "requests": run.requests, "raw_outputs": run.raw_outputs}
            (self.runtime / "runs" / f"{run.id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = Engine(Path(os.getenv("MATCHLENS_RUNTIME_DIR", ROOT / ".runtime")), os.getenv("DEEPSEEK_API_KEY"))
    app.state.engine = engine
    try:
        yield
    finally:
        tasks = [s.task for s in engine.sessions.values() if s.task and not s.task.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        engine.ledger.close()


app = FastAPI(title="MatchLens AI", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def boundaries(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        if int(request.headers.get("content-length", "0")) > 4096:
            return Response("Request too large", status_code=413)
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return Response("Origin rejected", status_code=403)
            # SameSite=Strict already blocks the cookie, but a non-browser
            # client can present a forged Origin. Reject the browser's own
            # cross-site signal as a second, independent check.
            if request.headers.get("sec-fetch-site") == "cross-site":
                return Response("Cross-site request rejected", status_code=403)
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - started) * 1000:.1f}"
    return response


def engine(request: Request) -> Engine:
    return request.app.state.engine


def public_rate(request: Request, bucket: str, limit: int) -> None:
    """Anonymous research endpoints share a per-source quota."""
    eng = engine(request)
    ip = hashlib.sha256((request.client.host if request.client else "unknown").encode()).hexdigest()[:20]
    eng.rates.check(f"{bucket}:{ip}", limit)


def session(request: Request) -> Session:
    eng = engine(request)
    eng.cleanup()
    s = eng.sessions.get(request.cookies.get(COOKIE, ""))
    if not s:
        raise HTTPException(401, "session_expired")
    s.touched = time.monotonic()
    return s


def optional_session(request: Request) -> Session | None:
    """A live server-side session, or None. Never trusts an arbitrary cookie."""
    eng = engine(request)
    eng.cleanup()
    s = eng.sessions.get(request.cookies.get(COOKIE, ""))
    if s:
        s.touched = time.monotonic()
    return s


def private_access(
    request: Request,
    owner_session_id: str | None,
    *,
    allowed_by_producer: bool = True,
) -> Principal | None:
    """Authorise a private draft/run by server-side owner, not by ID alone.

    Producers/admins are a separate, independently verified role. A record
    without an owner is legacy data from before ownership tracking and is
    fail-closed: only an editorial principal may read it.

    Non-owners receive 404 rather than 403 so an ID probe cannot distinguish
    "exists but is private" from "does not exist".
    """
    principal = optional_principal(request)
    if principal is not None and principal.can_edit_content and allowed_by_producer:
        return principal
    live = optional_session(request)
    if (
        live is not None
        and owner_session_id
        and hmac.compare_digest(str(live.id), str(owner_session_id))
    ):
        return principal
    raise HTTPException(404, "record_not_found")


def is_producer(request: Request) -> bool:
    principal = optional_principal(request)
    return bool(principal and principal.can_edit_content)


def private_plan_payload(plan) -> dict:
    """Never return the server session credential used as the owner key."""
    return plan.model_dump(exclude={"owner_session_id"})


def private_run_payload(record) -> dict:
    return record.model_dump(exclude={"owner_session_id"})


@app.get("/api/health")
async def health(request: Request):
    from .catalog import MatchCatalog

    eng = engine(request)
    return {
        "ok": True,
        "model_configured": bool(eng.runner.key),
        "format": "12-minute synthetic match",
        "manifest_rejections": MatchCatalog.manifest_rejections(),
        "cache": {
            **eng.cache_stats,
            "snapshot_entries": len(eng.snapshot_cache),
            "snapshot_bytes_estimate": eng.snapshot_cache_bytes,
            "oaai_entries": len(eng.oaai_cache),
        },
    }


@app.post("/api/sessions")
async def create_session(request: Request, response: Response):
    eng = engine(request)
    eng.cleanup()
    existing = eng.sessions.get(request.cookies.get(COOKIE, ""))
    if existing:
        existing.touched = time.monotonic()
        return eng.view(existing)
    ip = hashlib.sha256((request.client.host if request.client else "unknown").encode()).hexdigest()[:20]
    eng.rates.check("create:"+ip, 10)
    eng.rates.check("create:global", 30)
    if len(eng.sessions) >= 8:
        raise HTTPException(503, "session_capacity")
    s = Session(id=secrets.token_urlsafe(24), ip=ip)
    eng.sessions[s.id] = s
    response.set_cookie(
        COOKIE,
        s.id,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
        max_age=1800,
    )
    return eng.view(s)


@app.get("/api/state")
async def state(request: Request):
    return engine(request).view(session(request))


@app.post("/api/control")
async def control(command: Control, request: Request):
    s, eng = session(request), engine(request)
    # Replay operations (seek/play/pause) are cheap session-scoped actions a
    # live viewer issues continuously; the budget is per session, and sessions
    # are capped server-side, so this stays a DoS non-vector.
    eng.rates.check("control:"+s.id, 240)
    s.tick()
    if command.action == "focus":
        if not command.chapter:
            raise HTTPException(422, "chapter_required")
        at = next(c["at"] for c in CHAPTERS if c["id"] == command.chapter)
        if s.focus != command.chapter:
            s.invalidate()
        s.at, s.paused, s.focus = at, True, command.chapter
        snap = eng.snapshot_for(s, at)
        s.snapshots[snap.id] = snap
    elif command.action == "focus_moment":
        moment = s.moments.get(command.moment_id)
        if not moment or moment["at"] > s.at:
            raise HTTPException(409, "moment_not_yet_detected")
        s.invalidate()
        s.at, s.paused, s.focus = moment["at"], True, moment["id"]
    elif command.action == "exit_focus":
        s.invalidate()
        s.focus, s.paused = None, s.at >= s.format_seconds
    elif command.action == "seek":
        if command.at is None:
            raise HTTPException(422, "at_required")
        target_at = max(0, min(s.format_seconds, int(command.at)))
        s.invalidate()
        s.at = target_at
        s.paused = True
        s.focus = None
        s.anchor_at = target_at
        s.anchor_time = time.monotonic()
        snap = eng.snapshot_for(s, target_at)
        s.snapshots[snap.id] = snap
    elif command.action == "set_match":
        if not command.match_id:
            raise HTTPException(422, "match_id_required")
        from .catalog import MatchCatalog
        meta = MatchCatalog.get_match(command.match_id)
        if not meta:
            raise HTTPException(404, f"match_not_found: {command.match_id}")
        if not meta.analysis_ready:
            raise HTTPException(
                409,
                {
                    "code": "match_not_analysis_ready",
                    "match_id": command.match_id,
                    "status": meta.availability_status,
                    "reason": meta.availability_reason,
                    "install_hint": meta.install_hint,
                },
            )
        ready, reason = MatchCatalog.verify_analysis_ready(command.match_id)
        if not ready:
            raise HTTPException(
                409,
                {"code": "match_not_analysis_ready", "match_id": command.match_id, "reason": reason},
            )
        s.invalidate()
        s.match_id = command.match_id
        if command.match_id.startswith("syn_"):
            sc_key = command.match_id.replace("syn_", "", 1)
            if sc_key in SCENARIOS:
                s.scenario = sc_key
        match_ctx = MatchCatalog.get_match_context(s.match_id)
        s.format_seconds = int(math.ceil(match_ctx.replayable_end))
        s.nominal_seconds = match_ctx.duration
        s.focus, s.at, s.paused = None, 0, True
        s.cache.clear()
        s.revisions.clear()
        s.moments.clear()
        s.snapshots.clear()
        s.attempted.clear()
        s.attempts.clear()
        s.observed_at = -1
        s.state_key = None
        s.state_value = None
        s.run_info = None
        if s.task and not s.task.done():
            s.task.cancel()
            s.task = None
    elif command.action == "restart":
        s.invalidate()
        s.focus, s.at, s.paused = None, 0, True
        s.moments.clear()
        s.observed_at = -1
    elif command.action == "set_scenario":
        if not command.scenario or command.scenario not in SCENARIOS:
            raise HTTPException(422, "invalid_scenario")
        s.invalidate()
        s.scenario = command.scenario
        s.match_id = f"syn_{command.scenario}"
        s.format_seconds = 720
        s.nominal_seconds = 720
        s.focus, s.at, s.paused = None, 0, True
        s.cache.clear()
        s.revisions.clear()
        s.moments.clear()
        s.snapshots.clear()
        s.observed_at = -1
        s.state_key = None
        s.state_value = None
    elif command.action == "set_team":
        if command.team not in ("H", "N"):
            raise HTTPException(422, "invalid_team")
        s.focus_team = command.team
    elif command.action == "play":
        if s.focus:
            raise HTTPException(409, "exit_focus_before_play")
        s.paused = s.at >= s.format_seconds
    elif command.action == "pause":
        s.paused = True
    elif command.action == "speed":
        if command.speed is None:
            raise HTTPException(422, "speed_required")
        s.speed = command.speed
    s.anchor_at, s.anchor_time = s.at, time.monotonic()
    s.revision += 1
    return eng.view(s)


@app.post("/api/analyse", status_code=202)
async def analyse(request: Request):
    s, eng = session(request), engine(request)
    view = eng.view(s)
    snap = s.snapshots.get(view["snapshot_id"])
    if not snap:
        raise HTTPException(409, "no_detected_moment")
    cached = s.cache.get(snap.id)
    if s.task and not s.task.done() or cached and cached["status"] == "completed":
        return eng.view(s)
    if not eng.start_analysis(s, snap, "manual"):
        raise HTTPException(429, "workflow_budget_or_duplicate")
    return eng.view(s)


@app.get("/api/evidence/{snapshot_id}")
async def evidence(snapshot_id: str, request: Request):
    s = session(request)
    snap = s.snapshots.get(snapshot_id)
    if not snap:
        raise HTTPException(404, "snapshot_not_in_session")
    eng = engine(request)
    ctx = eng.match_context(s.match_id)
    if is_protected_provider(ctx.provenance_kind):
        principal = optional_principal(request)
        if not (principal and principal.can_edit_content):
            data = snap.data
            public_events, window = bounded_state_events(
                data.get("events", []),
                at=int(data.get("as_of", 0)),
                total_events=len(data.get("events", [])),
            )
            return {
                **data,
                "snapshot_id": snap.id,
                "events": public_events,
                "total_event_count": len(data.get("events", [])),
                "provider_data_boundary": {
                    **publication_notice(
                        match_id=s.match_id, tier="public_analysis_projection"
                    ),
                    "state_window": window,
                },
            }
    return {"snapshot_id": snap.id, **snap.data}


@app.get("/api/stream")
async def stream(request: Request):
    s, eng = session(request), engine(request)
    # SSE connects are charged per session. The budget must absorb a normal
    # browsing pattern (navigating workspaces reopens the stream) plus the
    # client's reconnect-with-backoff: a burst of reconnects must drain
    # instead of wedging the session in a 429 loop.
    eng.rates.check("stream:"+s.id, 60)
    # One stream per session; a reconnect replaces the previous stream.
    token = secrets.token_hex(8)
    s.stream_token = token
    async def updates():
        previous, last_send = -1, time.monotonic()
        while not await request.is_disconnected() and eng.sessions.get(s.id) is s and getattr(s, "stream_token", None) == token:
            s.tick()
            if s.revision != previous:
                previous = s.revision
                s.touched = time.monotonic()
                yield "event: state\ndata: "+json.dumps(eng.view(s), separators=(",", ":"))+"\n\n"
                last_send = time.monotonic()
            elif time.monotonic()-last_send > 10:
                yield ": keepalive\n\n"
                last_send = time.monotonic()
            await asyncio.sleep(.3)
    return StreamingResponse(updates(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


@app.get("/api/challengeable-claims")
async def challengeable_claims(request: Request, snapshot_id: str):
    """Registered claims of the session snapshot that a user can challenge.

    The deterministic gate executes on demand, so the registry holds a real
    verdict for every standard assertion of this snapshot even when no paid
    deliberation has run. Listing those ids is what lets the UI challenge a
    registered claim instead of a placeholder the server would reject.
    """
    s, eng = session(request), engine(request)
    snap = s.snapshots.get(snapshot_id) or eng.saved_snapshots.get(snapshot_id)
    if snap is None:
        raise HTTPException(404, "snapshot_not_found")
    eng.get_registered_claims(s, snap)
    records = eng.registry.records_for(s.match_id, snapshot_id)
    return {
        "match_id": s.match_id,
        "snapshot_id": snapshot_id,
        "claims": [
            {
                "claim_id": r.claim_id,
                "assertion": r.assertion,
                "gate_status": r.gate_status,
                "claim_level": r.claim_level,
                "lifecycle_status": r.lifecycle_status,
                "editorial_status": r.editorial_status,
                "statement": r.statement,
            }
            for r in sorted(records, key=lambda r: (r.gate_status != "approved", r.claim_id))
        ],
    }


def _challenge_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _challenge_revision(record, revision_id: str) -> dict:
    result = record.result
    return {
        "revision_id": revision_id,
        "snapshot_id": record.snapshot_id,
        "at": result.get("snapshot_as_of") or result.get("at"),
        "claim_id": record.claim_id,
        "challenge_type": record.challenge_type,
        "outcome": result.get("outcome"),
        "summary": result.get("resolution_summary"),
        "counterevidence_checked": result.get("counterevidence_checked", []),
        "idempotency_key": record.idempotency_key,
        "request_hash": record.request_hash,
        "timestamp": record.created_at,
        "restored_from_registry": True,
    }


@app.post("/api/challenge")
async def challenge(body: ChallengeRequest, request: Request):
    s, eng = session(request), engine(request)
    eng.rates.check("challenge:" + s.id, 60)
    payload = body.model_dump(mode="json", exclude={"idempotency_key"})
    request_hash = _challenge_hash(payload)

    if body.idempotency_key:
        existing_key = eng.registry.find_idempotency_key(
            body.idempotency_key, owner_id=s.id, match_id=s.match_id
        )
        if existing_key:
            if existing_key.request_hash != request_hash:
                raise HTTPException(409, "idempotency_key_conflict")
            revision = _challenge_revision(existing_key, f"rev-restored-{request_hash[:8]}")
            return {
                "result": existing_key.result,
                "revisions": s.revisions or [revision],
                "state": eng.view(s),
                "reused": True,
            }

    session_duplicate = next(
        (r for r in s.revisions if r.get("request_hash") == request_hash),
        None,
    )
    if session_duplicate:
        return {
            "result": session_duplicate["result"],
            "revisions": s.revisions,
            "state": eng.view(s),
            "reused": True,
        }

    snap = s.snapshots.get(body.snapshot_id)
    if not snap:
        snap = eng.saved_snapshots.get(body.snapshot_id)
    if not snap:
        # A process restart discards in-memory snapshots. Rebuild only the
        # frozen prefix named by a registered claim, never an arbitrary clock.
        hint = next(
            (
                record for record in eng.registry.records.values()
                if record.match_id == s.match_id
                and record.snapshot_id == body.snapshot_id
                and record.claim_id == body.claim_id
            ),
            None,
        )
        if hint is not None:
            from .catalog import MatchCatalog

            try:
                ctx = MatchCatalog.get_match_context(s.match_id)
                events = (
                    eng.events_for(s)
                    if s.match_id.startswith("syn_")
                    else MatchCatalog.load_normalized_events(s.match_id)
                )
                legacy_default = (
                    s.match_id == "syn_default" and s.scenario == "default" and s.seed == 17
                )
                snap = freeze_with_context(
                    events, ctx, hint.as_of,
                    seed=s.seed,
                    scenario=s.scenario,
                    match_id=None if legacy_default else s.match_id,
                )
                if snap.id == body.snapshot_id:
                    eng.saved_snapshots[snap.id] = snap
                else:
                    snap = None
            except (FileNotFoundError, ValueError):
                snap = None
    if not snap:
        raise HTTPException(404, "snapshot_not_found")

    snapshot_match = snap.data.get("match_id")
    if snapshot_match and snapshot_match != s.match_id and not (
        s.match_id == "syn_default" and str(snapshot_match).startswith("harbor-northbridge-")
    ):
        raise HTTPException(409, "snapshot_match_mismatch")
    # Keep the frozen evidence available for a replay in another process/session.
    eng.saved_snapshots[snap.id] = snap

    # A claim must have a persisted gate verdict; hypotheses are not claims.
    valid_claims = eng.get_registered_claims(s, snap)
    if body.claim_id not in valid_claims:
        raise HTTPException(404, f"claim_not_found: {body.claim_id}")

    record = eng.registry.get(s.match_id, snap.id, body.claim_id)
    result = resolve_challenge(
        snap,
        body,
        claim_meta=(
            {
                "assertion": record.assertion,
                "gate_status": record.gate_status,
                "claim_level": record.claim_level,
            }
            if record else None
        ),
    )
    result_payload = result.model_dump()
    result_payload["snapshot_as_of"] = snap.data["as_of"]

    revised_card = result.revised_card
    revised_gate_status: str | None = None
    revised_gate_violations: list[str] = []
    if result.outcome == "narrowed" and record is not None:
        if revised_card is None:
            revised_card = {
                "claim_id": record.claim_id,
                "claim_level": 2,
                "text": f"Observed local association only: {result.resolution_summary}",
                "evidence_scope": {
                    "metric_ids": [r for r in result.counterevidence_checked if r in snap.data.get("receipts", {})],
                    "event_ids": [],
                },
                "assumptions": ["Frozen snapshot only; no causal identification."],
                "counterevidence": [],
                "verification_method": "Recomputed receipts after challenge.",
            }
        verdict = publication_gate_2_0(
            revised_card,
            snap.data.get("events", []),
            catalog_metric_ids=set(snap.data.get("receipts", {})),
        )
        revised_gate_status = verdict.status
        revised_gate_violations = list(verdict.rule_violations)
        result_payload["revised_gate"] = {
            "status": verdict.status,
            "violations": revised_gate_violations,
            "claim_level": revised_card.get("claim_level"),
        }

    revision = eng.registry.apply_challenge_revision(
        record,
        outcome=result.outcome,
        rationale=result.resolution_summary,
        challenge_request_hash=request_hash,
        actor="challenge_review",
        revised_card=revised_card,
        gate_status=revised_gate_status,
        gate_violations=revised_gate_violations,
    ) if record else None
    if revision is not None:
        result_payload["revision_id"] = revision.revision_id
        result_payload["revision_version"] = revision.version
        result_payload["lifecycle_status"] = revision.status
    rev_entry = {
        "revision_id": f"rev-{len(s.revisions) + 1:03d}",
        "snapshot_id": snap.id,
        "at": snap.data["as_of"],
        "claim_id": body.claim_id,
        "challenge_type": body.challenge_type,
        "outcome": result.outcome,
        "summary": result.resolution_summary,
        "counterevidence_checked": result.counterevidence_checked,
        "idempotency_key": body.idempotency_key,
        "request_hash": request_hash,
        "result": result_payload,
        "timestamp": time.time(),
    }
    s.revisions.append(rev_entry)
    s.revision += 1
    eng.registry.remember_challenge(
        request_payload=payload,
        idempotency_key=body.idempotency_key,
        owner_id=s.id,
        match_id=s.match_id,
        snapshot_id=snap.id,
        claim_id=body.claim_id,
        challenge_type=body.challenge_type,
        result=result_payload,
    )
    return {
        "result": result_payload,
        "revisions": s.revisions,
        "state": eng.view(s),
        "reused": False,
    }


class AskQuery(BaseModel):
    intent_id: str
    team: Literal["H", "N"] | None = None


@app.post("/api/ask")
async def ask(body: AskQuery, request: Request):
    s, eng = session(request), engine(request)
    eng.rates.check("ask:" + s.id, 60)
    view = eng.view(s)
    snap_id = view["snapshot_id"]
    snap = s.snapshots.get(snap_id) if snap_id else None
    if not snap:
        snap = eng.snapshot_for(s, s.at)
        s.snapshots[snap.id] = snap
    team = body.team or s.focus_team
    ans = ask_the_match(snap, body.intent_id, team=team)
    return ans


class ExplainQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chart_type: Literal[
        "oaai_momentum",
        "density_differential",
        "passing_network",
        "attacking_channels",
        "spatial_drilldown",
        "xt_surface",
        "shot_location",
        "cross_match_diff",
    ]
    team: Literal["H", "N"] | None = None
    zone_id: str | None = None
    player_id: str | None = None
    sequence_id: str | None = None
    point_timestamp: float | None = None
    pass_edge: tuple[str, str] | None = None
    xt_cell: tuple[int, int] | None = None
    # Slice C explain targets: a single shot position/event and a two-match
    # diff of one registry metric. Additive; existing fields unchanged.
    shot_location: tuple[float, float] | None = None
    shot_event_id: str | None = Field(default=None, max_length=80)
    metric_id: str | None = Field(default=None, max_length=64)
    compare_match_id: str | None = Field(default=None, max_length=80)
    compare_label: str | None = Field(default=None, max_length=160)


def _match_target(eng: "Engine", match_id: str) -> int:
    """Full-match freeze target: same rule the metric endpoints use."""
    ctx = eng.match_context(match_id)
    return int(ctx.duration) if match_id.startswith("syn_") else int(math.ceil(ctx.replayable_end))


@app.post("/api/explain")
async def explain(body: ExplainQuery, request: Request):
    from .explain import explain_chart
    s, eng = session(request), engine(request)
    eng.rates.check("explain:" + s.id, 60)
    view = eng.view(s)
    snap_id = view["snapshot_id"]
    snap = s.snapshots.get(snap_id) if snap_id else None
    if not snap:
        snap = eng.snapshot_for(s, s.at)
        s.snapshots[snap.id] = snap
    team = body.team or s.focus_team
    compare_snapshot = None
    if body.chart_type == "cross_match_diff":
        if not body.compare_match_id:
            raise HTTPException(400, "compare_match_id_required")
        try:
            compare_snapshot, _state = freeze_match_snapshot(
                eng, body.compare_match_id, _match_target(eng, body.compare_match_id)
            )
        except FileNotFoundError:
            raise HTTPException(404, f"match_not_found: {body.compare_match_id}")
        eng.saved_snapshots[compare_snapshot.id] = compare_snapshot
    return explain_chart(
        snapshot=snap,
        chart_type=body.chart_type,
        team=team,
        zone_id=body.zone_id,
        player_id=body.player_id,
        sequence_id=body.sequence_id,
        point_timestamp=body.point_timestamp,
        pass_edge=body.pass_edge,
        xt_cell=body.xt_cell,
        shot_location=body.shot_location,
        shot_event_id=body.shot_event_id,
        metric_id=body.metric_id,
        compare_snapshot=compare_snapshot,
        compare_label=body.compare_label,
    ).model_dump()


@app.get("/api/matches")
async def list_matches(request: Request):
    from .catalog import MatchCatalog
    return {"matches": [m.model_dump() for m in MatchCatalog.list_matches()]}


@app.get("/api/metrics")
async def list_metrics(request: Request):
    from .metrics import MetricsService

    public_rate(request, "metrics", 120)
    return {"metric_version": "football-v2", "metrics": [m.model_dump() for m in MetricsService.definitions()]}


@app.get("/api/metrics/{metric_id}")
async def query_metric(
    metric_id: str,
    request: Request,
    match_id: str = "syn_default",
    at: int | None = None,
    team: str = "H",
    window: Literal["previous", "current", "match"] = "current",
):
    from .catalog import MatchCatalog
    from .metrics import MetricsService

    public_rate(request, "metrics", 120)
    if team not in ("H", "N"):
        raise HTTPException(400, "invalid_team")
    try:
        ctx = MatchCatalog.get_match_context(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")
    if at is not None and (at < 0 or at > int(math.ceil(ctx.replayable_end))):
        raise HTTPException(422, "at_outside_match_context")
    target = int(at) if at is not None else (
        ctx.duration if match_id.startswith("syn_") else int(math.ceil(ctx.replayable_end))
    )
    snap, _state = freeze_match_snapshot(engine(request), match_id, target)
    try:
        metric = MetricsService.query(snap, metric_id, team=team, window=window, match_id=match_id)
    except KeyError:
        raise HTTPException(404, "metric_not_registered")
    return metric.model_dump()


@app.get("/api/oaai/ledger")
async def get_oaai_ledger(
    request: Request,
    match_id: str = "syn_default",
    at: int | None = None,
    team: Literal["H", "N"] = "H",
    smoothing_mode: Literal["causal", "bilateral"] = "causal",
    limit: int = 8,
):
    from .catalog import MatchCatalog
    from .oaai import compute_oaai_contribution_ledger

    public_rate(request, "oaai_ledger", 60)
    if limit < 1 or limit > 20:
        raise HTTPException(422, "limit_out_of_bounds")
    try:
        ctx = MatchCatalog.get_match_context(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")
    if at is not None and (at < 0 or at > int(math.ceil(ctx.replayable_end))):
        raise HTTPException(422, "at_outside_match_context")
    target = int(at) if at is not None else (
        ctx.duration if match_id.startswith("syn_") else int(math.ceil(ctx.replayable_end))
    )
    eng = engine(request)
    _snap, state = freeze_match_snapshot(eng, match_id, target)
    ledger = compute_oaai_contribution_ledger(
        state.get("events", []),
        at=target,
        team=team,
        dead_intervals=state.get("dead_intervals", []),
        xt_model=eng.xt_model,
        smoothing_mode=smoothing_mode,
        limit=limit,
    )
    ledger.update(
        match_id=match_id,
        snapshot_as_of=target,
        dataset_revision=ctx.dataset_revision or ctx.data_version,
        coverage=state.get("coverage", {}),
        completeness_status=ctx.completeness_status,
    )
    return ledger


@app.get("/api/matches/compare")
async def compare_matches(
    request: Request,
    match_ids: str = "syn_default,sb_wc2022_final",
):
    public_rate(request, "compare", 30)
    from .catalog import MatchCatalog
    ids = [m.strip() for m in match_ids.split(",") if m.strip()]
    if not ids:
        raise HTTPException(400, "match_ids_required")

    matches_meta = []
    for mid in ids:
        m = MatchCatalog.get_match(mid)
        if not m:
            raise HTTPException(404, f"match_not_found: {mid}")
        ctx = MatchCatalog.get_match_context(mid)
        matches_meta.append({
            "metadata": m.model_dump(),
            "context": ctx.model_dump(),
        })

    summary = MatchCatalog.get_batch_summary(ids)
    return {
        "compared_matches": ids,
        "matches": matches_meta,
        "batch_summary": summary,
    }


@app.get("/api/featured")
async def featured_investigation(request: Request):
    """Deterministic first-visit recommendation for the Match Hub.

    Selection algorithm, fully disclosed and model-free:
    1. candidates = catalog matches with local data that are analysis ready;
    2. rank provider payloads above synthetic fixtures, then by recorded
       event count descending;
    3. walk the ranking and take the first match whose OAAI change points
       include one inside the replayable clock; feature its strongest such
       change point (largest |amplitude|);
    4. every narrative string is assembled from recorded values (team names,
       the amplitude, contributor actions). Nothing here is a model output and
       no claim is registered by this endpoint.
    """
    # The response is memoised per catalog signature, so a browsed hub costs
    # the server nothing after the first hit; the per-source budget covers a
    # user (and an E2E suite) paging through workspaces, not a scraper.
    public_rate(request, "featured", 120)
    from .catalog import MatchCatalog

    eng = engine(request)
    matches = MatchCatalog.list_matches()
    candidates = [
        m
        for m in matches
        if m.analysis_ready is not False and m.dataset_installed is not False
    ]
    signature = hashlib.sha256(
        json.dumps(
            sorted(
                (m.match_id, m.provenance_kind or "synthetic", m.events_count or 0)
                for m in candidates
            ),
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:32]
    cached = eng.featured_cache.get(signature)
    if cached is not None:
        eng.featured_cache.move_to_end(signature)
        return dict(cached)

    provenance_rank = {"provider_payload": 0, "provider_schema_excerpt": 1, "synthetic": 2}
    ranked = sorted(
        candidates,
        key=lambda m: (
            provenance_rank.get(m.provenance_kind or "synthetic", 2),
            -(m.events_count or 0),
        ),
    )

    featured: dict | None = None
    fallback_reason = "no analysis-ready match with an in-clock OAAI change point"
    considered = 0
    for meta in ranked:
        considered += 1
        mid = meta.match_id
        try:
            ctx = MatchCatalog.get_match_context(mid)
            events = MatchCatalog.load_normalized_events(mid)
            if mid.startswith("syn_"):
                events = generate_match(scenario=mid.replace("syn_", "", 1))
            replayable = int(math.ceil(ctx.replayable_end))
            result = compute_oaai(
                events,
                smoothing_mode="causal",
                t_end=replayable,
                xt_model=canonical_xt_model(),
            )
            points = [
                cp
                for cp in result.get("change_points", [])
                if 0 < float(cp.get("at") or 0) <= replayable
            ]
            if not points:
                fallback_reason = f"{mid}: no OAAI change point inside the replayable clock"
                continue
            ranked_points = sorted(
                points,
                key=lambda cp: abs(float(cp.get("oaai_amplitude") or 0)),
                reverse=True,
            )
            # Moments with a recorded shot among their contributors are the
            # ones a deterministic investigation can usually support with a
            # window comparison; prefer them, but never invent one.
            strongest = next(
                (
                    cp
                    for cp in ranked_points
                    if any(c.get("kind") == "shot" for c in (cp.get("top_contributors") or []))
                ),
                ranked_points[0],
            )
            shot_backed = any(c.get("kind") == "shot" for c in (strongest.get("top_contributors") or []))
            contributors = [
                c
                for c in (strongest.get("top_contributors") or [])
                if c.get("event_id")
            ]
            lead = strongest.get("leading_team")
            team_name = ctx.away_team_name if lead == "N" else ctx.home_team_name
            if lead not in ("H", "N"):
                fallback_reason = f"{mid}: strongest change point has no leading team"
                continue
            at = float(strongest.get("at") or 0)
            amplitude = float(strongest.get("oaai_amplitude") or 0)
            minute = max(1, int(at // 60) + 1)
            surged = "surge" in str(strongest.get("change_type") or "")
            home = meta.home_team
            away = meta.away_team
            lead_name = team_name or (home if lead == "H" else away)
            featured = {
                "match_id": mid,
                "label": meta.label,
                "competition": meta.competition,
                "season": meta.season,
                "stage": meta.stage,
                "match_date": meta.match_date,
                "home_team": home,
                "away_team": away,
                "home_score": meta.home_score,
                "away_score": meta.away_score,
                "provenance_kind": meta.provenance_kind or "synthetic",
                "data_provider": meta.data_provider,
                "attribution_text": meta.attribution_text,
                "replayable_end": replayable,
                "moment": {
                    "change_point_id": strongest.get("change_point_id"),
                    "at": at,
                    "minute": minute,
                    "leading_team": lead,
                    "team_name": lead_name,
                    "oaai_amplitude": amplitude,
                    "change_type": strongest.get("change_type"),
                    "claim_level": strongest.get("claim_level", 2),
                    "shot_backed": shot_backed,
                    "disclaimer": strongest.get("disclaimer"),
                },
                "what_changed": (
                    f"{lead_name}'s recorded attacking activity surged "
                    f"(smoothed OAAI {amplitude:+.2f}; formula attribution, not causation)."
                    if surged
                    else (
                        f"{lead_name} took the recorded activity advantage in this spell "
                        f"(smoothed OAAI {amplitude:+.2f}; formula attribution, not causation)."
                    )
                ),
                "why_investigate": (
                    f"Strongest recorded swing on this match's activity curve inside the replayable clock, "
                    f"backed by {len(contributors)} supporting recorded event(s)"
                    + (f" including a recorded {next(c['kind'] for c in contributors if c.get('kind') == 'shot')}" if shot_backed else "")
                    + "."
                ),
                "question": (
                    f"What produced {lead_name}'s attacking activity change around {minute}'?"
                ),
                "supporting_events": [
                    {
                        "event_id": c.get("event_id"),
                        "t": c.get("t"),
                        "minute": max(1, int(float(c.get("t") or 0) // 60) + 1),
                        "team": c.get("team"),
                        "actor": c.get("actor"),
                        "kind": c.get("kind"),
                        "outcome": c.get("outcome"),
                        "explanation": c.get("explanation"),
                    }
                    for c in contributors[:3]
                ],
                "source": (
                    "MatchLens deterministic OAAI change points over the installed, "
                    "analysis-ready match ranked first by provenance and recorded event count; "
                    "no model was called and no claim was registered."
                ),
            }
            break
        except FileNotFoundError:
            fallback_reason = f"{mid}: dataset not locally installed"
            continue
        except Exception as exc:  # noqa: BLE001 - one bad dataset must not 500 the hub
            logger.warning("featured candidate %s failed: %s", mid, exc)
            fallback_reason = f"{mid}: {type(exc).__name__}"
            continue

    response = {
        "featured": featured,
        "fallback": featured is None,
        "fallback_reason": fallback_reason if featured is None else None,
        "candidates_considered": considered,
        "algorithm": (
            "strongest |OAAI amplitude| change point within the replayable clock on the "
            "analysis-ready match ranked by provider provenance then recorded event count; "
            "shot-backed change points are preferred because a window comparison can "
            "support them; deterministic, no model called"
        ),
    }
    eng.featured_cache[signature] = response
    while len(eng.featured_cache) > eng.featured_cache_max_entries:
        eng.featured_cache.popitem(last=False)
    return response


# ---------------------------------------------------------------------------
# Slice C: cross-match profiles (team / player). All computation lives in
# matchlens.profiles; these routes only resolve catalog facts and freeze
# snapshots through the same path as /api/metrics.
# ---------------------------------------------------------------------------

@app.get("/api/profiles/teams")
async def profile_team_index(request: Request):
    from .catalog import MatchCatalog

    public_rate(request, "profiles", 60)
    index: dict[str, dict] = {}
    for meta in MatchCatalog.list_matches():
        for side, name, pid in (
            ("home", meta.home_team, meta.home_provider_team_id),
            ("away", meta.away_team, meta.away_provider_team_id),
        ):
            row = index.setdefault(name, {"team": name, "provider_team_ids": set(), "match_count": 0, "provider_match_count": 0, "synthetic_match_count": 0, "competitions": set()})
            if pid:
                row["provider_team_ids"].add(str(pid))
            row["match_count"] += 1
            if meta.provenance_kind == "provider_payload":
                row["provider_match_count"] += 1
            elif meta.provenance_kind == "synthetic":
                row["synthetic_match_count"] += 1
            row["competitions"].add(f"{meta.competition} {meta.season}")
    teams = [
        {
            "team": row["team"],
            "provider_team_ids": sorted(row["provider_team_ids"]),
            "match_count": row["match_count"],
            "provider_match_count": row["provider_match_count"],
            "synthetic_match_count": row["synthetic_match_count"],
            "competitions": sorted(row["competitions"]),
        }
        for row in index.values()
    ]
    teams.sort(key=lambda r: (-r["provider_match_count"], r["team"]))
    return {"teams": teams}


@app.get("/api/profiles/team-discovery")
async def profile_team_discovery(request: Request, team: str):
    from .profiles import discover_team_matches

    public_rate(request, "profiles", 60)
    if not team.strip():
        raise HTTPException(400, "team_required")
    return discover_team_matches(team)


_PROFILE_SNAPSHOT_CACHE: dict[tuple[str, int, str | None], tuple[Snapshot, dict]] = {}
_PROFILE_SNAPSHOT_CACHE_MAX = 24
_PROFILE_SNAPSHOT_CACHE_STATS = {"hits": 0, "misses": 0}


def _resolve_profile_snapshot(eng: "Engine", match_id: str, ctx) -> tuple[Snapshot, dict]:
    """Freeze a full-match snapshot at the same target the metric endpoints use.

    Snapshots frozen at the observed end are deterministic for a dataset
    revision, so a small LRU keeps repeat profile requests from re-running the
    full reduction. The cache is keyed by (match, target, dataset revision).
    """
    target = int(ctx.duration) if match_id.startswith("syn_") else int(math.ceil(ctx.replayable_end))
    key = (match_id, target, ctx.dataset_revision or ctx.data_version)
    cached = _PROFILE_SNAPSHOT_CACHE.get(key)
    if cached is not None:
        _PROFILE_SNAPSHOT_CACHE_STATS["hits"] += 1
        return cached
    snap, state = freeze_match_snapshot(eng, match_id, target)
    if len(_PROFILE_SNAPSHOT_CACHE) >= _PROFILE_SNAPSHOT_CACHE_MAX:
        _PROFILE_SNAPSHOT_CACHE.pop(next(iter(_PROFILE_SNAPSHOT_CACHE)))
    _PROFILE_SNAPSHOT_CACHE[key] = (snap, state)
    _PROFILE_SNAPSHOT_CACHE_STATS["misses"] += 1
    return snap, state


@app.get("/api/profiles/team")
async def profile_team(
    request: Request,
    team: str,
    match_ids: str | None = None,
    window: Literal["match", "aligned"] = "match",
):
    from .catalog import MatchCatalog
    from .profiles import align_windows_by_period, build_team_profile

    public_rate(request, "profiles", 30)
    team = team.strip()
    if not team:
        raise HTTPException(400, "team_required")
    eng = engine(request)
    if match_ids:
        ids = [m.strip() for m in match_ids.split(",") if m.strip()]
    else:
        ids = _discover_team_ids(team)
    if not ids:
        raise HTTPException(404, "no_matches_for_team")
    if len(ids) > 40:
        raise HTTPException(422, "too_many_matches_max_40")

    rows: list[dict] = []
    snap_events: list[tuple[str, list[dict]]] = []
    for mid in ids:
        meta = MatchCatalog.get_match(mid)
        if meta is None:
            raise HTTPException(404, f"match_not_found: {mid}")
        if meta.home_team == team or meta.home_provider_team_id == team:
            side, opponent = "H", meta.away_team
        elif meta.away_team == team or meta.away_provider_team_id == team:
            side, opponent = "N", meta.home_team
        else:
            raise HTTPException(422, f"team_not_in_match: {mid}")
        try:
            ctx = MatchCatalog.get_match_context(mid)
            snap, state = _resolve_profile_snapshot(eng, mid, ctx)
        except FileNotFoundError:
            raise HTTPException(404, f"match_dataset_not_imported: {mid}")
        rows.append({
            "match_id": mid,
            "label": meta.label,
            "competition": meta.competition,
            "season": meta.season,
            "match_date": meta.match_date,
            "side": side,
            "side_team_name": meta.home_team if side == "H" else meta.away_team,
            "opponent_name": opponent,
            "provider_team_ids": [meta.home_provider_team_id if side == "H" else meta.away_provider_team_id],
            "provenance_kind": meta.provenance_kind,
            "coverage_status": ctx.completeness_status,
            "continuous_coverage": ctx.continuous_coverage,
            "dataset_revision": ctx.dataset_revision or ctx.data_version,
            "snapshot": snap,
            "state": state,
            "clock_bounded": False,
            "nominal_duration": ctx.duration,
            "replayable_end": ctx.replayable_end,
            "stoppage_seconds": ctx.stoppage_time,
        })
        snap_events.append((mid, snap.data.get("events", [])))

    if window == "aligned":
        if len(rows) < 2:
            raise HTTPException(422, "aligned_window_requires_two_matches")
        alignment = align_windows_by_period(snap_events)
        for row in rows:
            row["window_alignment"] = alignment

    result = build_team_profile(
        team=team,
        rows=rows,
        window=window,
        xt_model=eng.xt_model,
    ).model_dump()
    result["scope"]["snapshot_cache"] = dict(_PROFILE_SNAPSHOT_CACHE_STATS)
    return result


def _discover_team_ids(team: str) -> list[str]:
    from .profiles import discover_team_matches

    discovery = discover_team_matches(team)
    return [
        m["match_id"] for m in discovery["matches"]
        if m["provenance_kind"] == "provider_payload"
        and m.get("analysis_ready", m.get("dataset_imported", False))
    ]


@app.get("/api/profiles/players")
async def profile_player_index(
    request: Request,
    match_ids: str | None = None,
    team: str | None = None,
    q: str | None = None,
    limit: int = 200,
):
    from .profiles import discover_players

    public_rate(request, "profiles", 30)
    if limit < 1 or limit > 1000:
        raise HTTPException(422, "limit_out_of_bounds")
    if match_ids:
        ids = [m.strip() for m in match_ids.split(",") if m.strip()]
    else:
        from .catalog import MatchCatalog

        ids = [
            m.match_id for m in MatchCatalog.list_matches()
            if m.provenance_kind == "provider_payload" and m.analysis_ready
        ]
    return discover_players(ids, limit=limit, team=team, q=q)


@app.get("/api/profiles/player")
async def profile_player(
    request: Request,
    player_id: str,
    match_ids: str,
    window: Literal["match", "aligned"] = "match",
):
    from .catalog import MatchCatalog
    from .profiles import align_windows_by_period, build_player_profile, compute_player_minutes

    public_rate(request, "profiles", 30)
    player_id = player_id.strip()
    ids = [m.strip() for m in match_ids.split(",") if m.strip()]
    if not player_id or not ids:
        raise HTTPException(400, "player_id_and_match_ids_required")
    if len(ids) > 40:
        raise HTTPException(422, "too_many_matches_max_40")
    eng = engine(request)

    rows: list[dict] = []
    snap_events: list[tuple[str, list[dict]]] = []
    for mid in ids:
        meta = MatchCatalog.get_match(mid)
        if meta is None:
            raise HTTPException(404, f"match_not_found: {mid}")
        try:
            ctx = MatchCatalog.get_match_context(mid)
            snap, state = _resolve_profile_snapshot(eng, mid, ctx)
        except FileNotFoundError:
            raise HTTPException(404, f"match_dataset_not_imported: {mid}")
        normalized = MatchCatalog.load_normalized_events(mid)
        own = [e for e in normalized if str(e.player_id or "") == player_id]
        if not own:
            raise HTTPException(422, f"player_not_in_match: {mid}")
        side_counts: dict[str, int] = {}
        for e in own:
            side_counts[e.team_id] = side_counts.get(e.team_id, 0) + 1
        side = max(side_counts, key=lambda t: side_counts[t])
        minutes = compute_player_minutes(normalized, player_id, float(ctx.observed_end))
        rows.append({
            "match_id": mid,
            "label": meta.label,
            "competition": meta.competition,
            "season": meta.season,
            "match_date": meta.match_date,
            "side": side,
            "side_team_name": meta.home_team if side == "H" else meta.away_team,
            "opponent_name": meta.away_team if side == "H" else meta.home_team,
            "provenance_kind": meta.provenance_kind,
            "coverage_status": ctx.completeness_status,
            "continuous_coverage": ctx.continuous_coverage,
            "dataset_revision": ctx.dataset_revision or ctx.data_version,
            "snapshot": snap,
            "state": state,
            "minutes": minutes,
            "clock_bounded": False,
            "nominal_duration": ctx.duration,
            "replayable_end": ctx.replayable_end,
            "stoppage_seconds": ctx.stoppage_time,
        })
        snap_events.append((mid, snap.data.get("events", [])))

    if window == "aligned":
        if len(rows) < 2:
            raise HTTPException(422, "aligned_window_requires_two_matches")
        alignment = align_windows_by_period(snap_events)
        for row in rows:
            row["window_alignment"] = alignment

    result = build_player_profile(
        player_id=player_id,
        rows=rows,
        window=window,
    ).model_dump()
    result["scope"]["snapshot_cache"] = dict(_PROFILE_SNAPSHOT_CACHE_STATS)
    return result


@app.get("/api/matches/{match_id}")
async def get_match_detail(match_id: str, request: Request):
    from .catalog import MatchCatalog
    meta = MatchCatalog.get_match(match_id)
    if not meta:
        raise HTTPException(404, "match_not_found")
    return {"match": meta.model_dump()}


@app.get("/api/matches/{match_id}/detail")
async def get_match_full_detail(match_id: str, request: Request):
    """Complete Match Detail: overview, lineups, shots, stats, tactics, insights."""
    from .catalog import MatchCatalog
    from .matchdetail import build_match_detail

    public_rate(request, "match_detail", 20)
    meta = MatchCatalog.get_match(match_id)
    if meta is None:
        raise HTTPException(404, "match_not_found")
    if not meta.analysis_ready:
        raise HTTPException(
            409,
            {
                "code": "match_not_analysis_ready",
                "match_id": match_id,
                "status": meta.availability_status,
                "reason": meta.availability_reason,
                "install_hint": meta.install_hint,
            },
        )
    eng = engine(request)
    live = optional_session(request)
    principal = optional_principal(request)
    try:
        return build_match_detail(
            eng,
            match_id,
            _resolve_profile_snapshot,
            owner_session_id=live.id if live else None,
            include_all_investigations=bool(principal and principal.can_edit_content),
        )
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/matches/{match_id}/completeness")
async def get_match_completeness(match_id: str, request: Request):
    from .catalog import MatchCatalog

    public_rate(request, "completeness", 120)
    try:
        ctx = MatchCatalog.get_match_context(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")
    return {
        "match_id": match_id,
        "dataset_revision": ctx.dataset_revision or ctx.data_version,
        "coverage_level": ctx.data_coverage,
        "continuous_coverage": ctx.continuous_coverage,
        "coverage_verified": ctx.coverage_verified,
        "completeness": ctx.completeness,
    }


@app.get("/api/matches/{match_id}/score")
async def get_match_score(match_id: str, request: Request):
    """Independent provider-vs-event score verification (aggregate only)."""
    from .catalog import MatchCatalog

    public_rate(request, "score", 120)
    meta = MatchCatalog.get_match(match_id)
    if meta is None:
        raise HTTPException(404, "match_not_found")
    if not meta.analysis_ready:
        raise HTTPException(
            409,
            {
                "code": "match_not_analysis_ready",
                "match_id": match_id,
                "status": meta.availability_status,
                "reason": meta.availability_reason,
            },
        )
    try:
        events = MatchCatalog.load_normalized_events(match_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(409, f"dataset_unavailable: {exc}")
    result = verify_score(events, meta)
    result["coverage"] = {
        "completeness_status": meta.completeness_status,
        "continuous_coverage": meta.continuous_coverage,
        "dataset_revision": MatchCatalog.data_version(match_id),
    }
    return result


@app.get("/api/matches/{match_id}/events")
async def get_match_events(match_id: str, request: Request):
    """Public analytics projection; full provider stream needs internal access.

    The anonymous response is aggregate plus a bounded structural evidence
    sample. It intentionally ignores ``limit``/``offset`` so pagination cannot
    turn this endpoint into a full payload export. Producer/admin credentials
    are checked independently and receive the complete normalized stream.
    """
    from .catalog import MatchCatalog

    meta = MatchCatalog.get_match(match_id)
    if meta is None:
        raise HTTPException(404, "match_not_found")
    try:
        events = MatchCatalog.load_normalized_events(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")

    principal = optional_principal(request)
    internal_access = bool(principal and principal.can_edit_content)
    if is_protected_provider(meta.provenance_kind) and not internal_access:
        public_rate(request, "match_events_public", 30)
        return public_event_summary(
            [event.model_dump(mode="json") for event in events],
            match_id=match_id,
        )

    tier = (
        "internal_event_access"
        if is_protected_provider(meta.provenance_kind)
        else "authored_excerpt"
        if meta.provenance_kind == "provider_schema_excerpt"
        else "owned_synthetic"
    )
    return {
        "match_id": match_id,
        "count": len(events),
        "access_tier": tier,
        "license_ref": meta.license_ref,
        "attribution_text": meta.attribution_text,
        "events": [e.model_dump() for e in events],
    }


@app.get("/api/models/xt")
async def get_xt_model_info(resolution: str = "16x12"):
    from .models.xt import ExpectedThreatModel
    if resolution not in ("16x12", "12x8"):
        raise HTTPException(400, "invalid_resolution")
    model = ExpectedThreatModel.load_default(resolution)
    return model.metadata


@app.get("/api/models/governance")
async def get_model_governance():
    """xG/xT model governance (Slice C-3).

    One place that states where each model comes from, how (if at all) it is
    trained, how to evaluate it, what it may and may not be used for, and
    which surfaces must label its output as heuristic. Statements here are
    binding for every chart, tool and profile that exposes the models.
    """
    from .metrics import DEFINITIONS
    from .models.xt import ExpectedThreatModel

    xt = ExpectedThreatModel.load_default("16x12")
    meta = xt.metadata
    return {
        "governance_version": "model-governance-v1",
        "models": {
            "xt": {
                "model_id": "matchlens_xt_grid",
                "model_version": meta.get("model_version"),
                "model_type": meta.get("model_type"),
                "calibration_status": meta.get("calibration_status"),
                "source": (
                    "Analytical spatial prior following the Karun Singh (2019) formulation; "
                    "generated by MatchLens analytical curves, not fitted to match outcomes."
                ),
                "training_protocol": {
                    "fitted": False,
                    "training_corpus": meta.get("training_corpus"),
                    "path_a": "Static precomputed grid shipped with the package (line production).",
                    "path_b": (
                        "Empirical fitting via ExpectedThreatFitter (Laplacian smoothing + empirical-Bayes "
                        "shrinkage) is available for research on sufficient samples and must never silently "
                        "replace the shipped grid."
                    ),
                    "monotonicity": "Axial grid values must increase from own goal toward the attacking goal.",
                },
                "evaluation_interface": {
                    "model_info": "/api/models/xt?resolution=16x12|12x8",
                    "fitted_vs_baseline": "/api/models/xt/compare?match_id=...&resolution=16x12",
                },
                "permitted_uses": [
                    "ΔxT for successful ball-retaining progression actions (completed passes, carries) only.",
                    "Spatial threat context for OAAI event weights and shot-position explanations.",
                ],
                "forbidden_uses": [
                    "ΔxT as a generic value measure for tackles, saves, fouls or defensive actions.",
                    "Presenting xT as shot quality (that is xG's role) or as possession probability.",
                    "Claiming empirical calibration without the Path B protocol and a declared corpus.",
                ],
                "labelling": "Every surface exposing xT must label it as a heuristic, uncalibrated spatial prior.",
                "consumers": ["oaai weights", "xt_surface chart", "shot_location explain", "what-if sandbox", "profiles delta_xt_heuristic"],
            },
            "pre_shot_xg": {
                "model_id": "matchlens_pre_shot_xg",
                "model_type": "geometric_heuristic",
                "source": "Goal-mouth distance and visible-angle geometry evaluated before any outcome is known.",
                "training_protocol": {
                    "fitted": False,
                    "outcome_leakage": "Strictly forbidden; outcome has zero effect on pre_shot_xg.",
                },
                "evaluation_interface": {
                    "explanation": "/api/explain chart_type=shot_location returns the heuristic figure with its formula",
                },
                "permitted_uses": ["Relative pre-shot danger context inside OAAI shot weights and shot explanations."],
                "forbidden_uses": [
                    "Publishing it as a calibrated xG model output.",
                    "Using post-shot outcomes to adjust the figure.",
                ],
                "labelling": "Must be labelled 'geometric heuristic, not calibrated'.",
                "consumers": ["oaai shot weights", "shot_location explain"],
            },
            "registry_xg": {
                "model_id": "xg",
                "metric_status": DEFINITIONS["xg"].model_status,
                "statement": (
                    "No calibrated xG model receipt exists in this build; the registry metric 'xg' stays "
                    "not_calibrated and never collapses to a fabricated zero."
                ),
            },
            "oaai": {
                "model_id": "oaai",
                "model_version": "oaai-1.0.0",
                "model_status": DEFINITIONS["oaai"].model_status,
                "smoothing": "Causal one-sided exponential decay; dead-ball intervals frozen via dead_intervals only.",
                "statement": (
                    "OAAI is MatchLens' own observed attacking activity index. It is not a reconstruction, "
                    "reverse-engineering or equivalent of any commercial product metric (including Sofascore "
                    "Attack Momentum), and must never be presented as one."
                ),
                "labelling": "Heuristic model output; a momentum proxy, not psychological momentum or causality.",
                "consumers": ["oaai_momentum chart", "registry metric 'oaai'", "investigation ledger"],
            },
        },
        "inference_levels": {
            "rule": (
                "Model outputs are Level 2 metric attributions (algebraic contributions), never Level 4 causal "
                "claims. Off-ball shape and pressing intent remain not_inferable without optical tracking."
            ),
            "sufficiency_advisor": "/api/sufficiency/{match_id}",
        },
    }


@app.get("/api/models/xt/compare")
async def get_xt_model_comparison(request: Request, resolution: str = "16x12", match_id: str = "sb_wc2022_final"):
    public_rate(request, "xt_compare", 20)
    from .models.xt import ExpectedThreatModel, compare_xt_grids, fit_xt_model
    from .catalog import MatchCatalog
    try:
        events = MatchCatalog.load_normalized_events(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")

    nx, ny = (16, 12) if resolution == "16x12" else (12, 8)
    baseline = ExpectedThreatModel.load_default(resolution)
    fitted = fit_xt_model(events, nx=nx, ny=ny)
    comparison = compare_xt_grids(fitted, baseline)
    return {
        "resolution": resolution,
        "match_id": match_id,
        "comparison": comparison,
    }


@app.get("/api/exploration/recoveries")
async def get_exploration_recoveries(request: Request, window_seconds: float = 6.0):
    s, eng = session(request), engine(request)
    state = eng.reduce_state(s)
    ctx = eng.match_context(s.match_id)
    result = analyze_quick_recoveries(
        state["events"],
        window_seconds=window_seconds,
        target_team=s.focus_team,
        team_names={"H": ctx.home_team_name, "N": ctx.away_team_name},
    )
    result.update(match_id=s.match_id, epoch=s.epoch, at=s.at, dataset_revision=ctx.dataset_revision)
    result["registry_comparison"] = registry_recoveries_comparison(
        eng.snapshot_at(s, s.at),
        window_seconds=window_seconds,
        focus_team=s.focus_team,
    )
    return result


@app.get("/api/exploration/oaai")
async def get_exploration_oaai(request: Request, smoothing_mode: Literal["causal", "bilateral"] = "causal"):
    s, eng = session(request), engine(request)
    state = eng.reduce_state(s)
    # Only explicit dead-ball intervals may freeze decay; possession intervals
    # are controlled play and must never be passed here.
    ctx = eng.match_context(s.match_id)
    chart_snapshot = eng.snapshot_at(s, s.at)
    chart_data = chart_snapshot.data
    as_of = int(chart_data.get("as_of", s.at))
    result = eng.oaai_for(
        s.match_id,
        state["events"],
        as_of,
        smoothing_mode=smoothing_mode,
        dead_intervals=state.get("dead_intervals", []),
        xt_model=canonical_xt_model(),
        include_raw=True,
    )
    # The registry publishes the causal (single-sided) smoothing. A bilateral
    # chart therefore shows a different curve and is reported as not
    # comparable instead of pretending to be the same number.
    if smoothing_mode == "causal":
        registry_timeline = result.get("timeline", [])
        registry_comparable = True
        reason = None
    else:
        registry_timeline = smooth_oaai_timeline(result.get("timeline_raw", []), mode="causal")
        registry_comparable = False
        reason = "smoothing_mode_bilateral_not_registry_canonical"
    result.update(match_id=s.match_id, epoch=s.epoch, at=s.at, dataset_revision=ctx.dataset_revision)
    result["registry_comparison"] = registry_oaai_comparison(
        chart_snapshot,
        registry_timeline,
        registry_comparable=registry_comparable,
        reason=reason,
        chart_smoothing_mode=smoothing_mode,
        data=chart_data,
    )
    # The unsmoothed timeline only exists to derive the registry's causal
    # curve. It is not part of the chart contract and doubles the response.
    result.pop("timeline_raw", None)
    return chart_oaai_payload(result)


@app.get("/api/matches/{match_id}/exploration")
async def get_match_exploration(
    request: Request,
    match_id: str,
    smoothing_mode: Literal["causal", "bilateral"] = "causal",
    window_seconds: float = 6.0,
    include_event_detail: bool = False,
):
    public_rate(request, "exploration", 30)
    from .catalog import MatchCatalog

    meta = MatchCatalog.get_match(match_id)
    if meta is None:
        raise HTTPException(404, "match_not_found")
    principal = optional_principal(request)
    internal_access = bool(principal and principal.can_edit_content)
    if include_event_detail and is_protected_provider(meta.provenance_kind) and not internal_access:
        raise HTTPException(403, "provider_event_detail_requires_data_access")
    try:
        events = MatchCatalog.load_normalized_events(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")

    ctx = MatchCatalog.get_match_context(match_id)
    oaai_res = compute_oaai(events, smoothing_mode=smoothing_mode)
    recoveries_res = analyze_quick_recoveries(
        events,
        window_seconds=window_seconds,
        team_names={"H": ctx.home_team_name, "N": ctx.away_team_name},
    )
    diff_res = analyze_action_density_differential(events)
    channels_h = analyze_attacking_channels(
        events, team="H", team_name=ctx.home_team_name, coordinate_frame=ctx.coordinate_frame
    )
    channels_n = analyze_attacking_channels(
        events, team="N", team_name=ctx.away_team_name, coordinate_frame=ctx.coordinate_frame
    )

    # Extract rich sequences, tactical zones, drilldown, and highlights for both synthetic and real matches
    meta = MatchCatalog.get_match_meta(match_id)
    at = int(ctx.duration) if match_id.startswith("syn_") else int(math.ceil(ctx.replayable_end))
    raw_events = (
        generate_match(scenario=match_id.replace("syn_", "", 1))
        if match_id.startswith("syn_")
        else events
    )
    state = reduce_match(
        raw_events,
        at=at,
        max_duration=int(math.ceil(ctx.replayable_end)),
        nominal_duration=ctx.duration,
        is_synthetic=match_id.startswith("syn_"),
        team_names={"H": ctx.home_team_name, "N": ctx.away_team_name},
        team_map=(
            {ctx.home_provider_team_id: "H", ctx.away_provider_team_id: "N"}
            if ctx.home_provider_team_id and ctx.away_provider_team_id
            else None
        ),
        coordinate_frame=ctx.coordinate_frame,
        continuous_coverage=ctx.continuous_coverage,
        official_score=(
            {"H": int(ctx.official_home_score), "N": int(ctx.official_away_score)}
            if ctx.official_home_score is not None and ctx.official_away_score is not None
            else None
        ),
    )

    sequences = build_sequences(state)
    tactical = build_tactical_explorer(state, "H")
    drilldown = build_spatial_sequence_drilldown(sequences, tactical.get("zone_cells"))
    highlights = locate_highlights(
        raw_events,
        sequences,
        oaai_data=oaai_res,
        team_names={"H": ctx.home_team_name, "N": ctx.away_team_name},
    )

    protected = is_protected_provider(meta.provenance_kind) and not internal_access
    if protected:
        sequences = strip_sequence_event_detail(
            sequences,
            at=float(ctx.observed_end or 0.0),
        )
    return {
        "match_id": match_id,
        "oaai": oaai_res,
        "quick_recoveries": recoveries_res,
        "density_differential": diff_res,
        "attacking_channels": {"H": channels_h, "N": channels_n},
        "sequences": sequences,
        "spatial_drilldown": drilldown,
        "highlights": highlights,
        "provider_data_boundary": (
            publication_notice(match_id=match_id, tier="public_analysis_projection")
            if protected
            else None
        ),
    }


@app.get("/api/xt/grid")
async def get_xt_grid(resolution: Literal["16x12", "12x8"] = "16x12"):
    from .models.xt import ExpectedThreatModel
    model = ExpectedThreatModel.load_default(resolution)
    return {
        "model_name": model.model_name,
        "model_version": model.model_version,
        "grid_resolution": {"nx": model.nx, "ny": model.ny},
        "values": model.values,
        "pitch_length": model.pitch_length,
        "pitch_width": model.pitch_width,
        "metadata": model.metadata,
    }


class InvestigationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_id: str
    at: int | None = None
    team: Literal["H", "N"] = "H"
    focus_type: Literal[
        "moment", "oaai_point", "event", "metric", "sequence", "player", "zone", "chart",
        "shot_location", "cross_match_diff",
    ] = "moment"
    focus_id: str | None = Field(default=None, max_length=160)
    question: str = Field(default="", max_length=500)
    compare_match_ids: list[str] = Field(default_factory=list, max_length=3)
    # "maf_agent" dispatches the real Analyst → Verifier model pair under the
    # frozen budget; any failure degrades to the deterministic planner and is
    # reported honestly through agent_status/agent_error.
    execution_mode: Literal["deterministic_planner", "maf_agent"] = "deterministic_planner"
    # Client-scoped handle for live cancellation. It is scoped to the server
    # session and carries no capability on its own.
    request_key: str | None = Field(default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


async def run_investigation_plan(
    eng: "Engine",
    body: InvestigationBody,
    snap: Snapshot,
    state: dict,
    owner_session_id: str,
    *,
    cancel_event: asyncio.Event | None = None,
    on_run_created: Callable[[str], None] | None = None,
):
    """Produce an InvestigationPlan in the requested execution mode.

    maf_agent requires a configured model and budget runway; otherwise — and on
    any agent failure — the deterministic planner produces the structurally
    identical plan and the degradation is recorded on it.
    """
    from .investigation import (
        AgentInvestigationError,
        InvestigationCancelled,
        InvestigationPlanner,
        run_maf_investigation,
    )

    if cancel_event is not None and cancel_event.is_set():
        raise InvestigationCancelled(None)

    def deterministic() -> "object":
        return InvestigationPlanner.run(
            match_id=body.match_id,
            snapshot=snap,
            state=state,
            team=body.team,
            focus_type=body.focus_type,
            focus_id=body.focus_id,
            question=body.question,
            compare_match_ids=body.compare_match_ids,
            xt_model=eng.xt_model,
            owner_session_id=owner_session_id,
        )

    if body.execution_mode != "maf_agent":
        return deterministic()
    if not eng.runner.key:
        plan = deterministic()
        plan.agent_error = "model_not_configured"
        plan.unresolved.append(
            "Real-agent execution was requested but no model provider is configured; "
            "the deterministic planner produced this plan."
        )
        return plan
    if not eng.ledger.has_runway(6):
        plan = deterministic()
        plan.agent_error = "agent_budget_no_runway"
        plan.unresolved.append(
            "Real-agent execution was requested but the inference budget has no runway; "
            "the deterministic planner produced this plan."
        )
        return plan
    try:
        return await run_maf_investigation(
            runner=eng.runner,
            run_store=eng.agent_runs,
            match_id=body.match_id,
            snapshot=snap,
            state=state,
            team=body.team,
            focus_type=body.focus_type,
            focus_id=body.focus_id,
            question=body.question,
            compare_match_ids=body.compare_match_ids,
            xt_model=eng.xt_model,
            owner_session_id=owner_session_id,
            cancel_event=cancel_event,
            on_run_created=on_run_created,
        )
    except asyncio.CancelledError:
        raise
    except AgentInvestigationError as exc:
        plan = deterministic()
        plan.agent_status = "failed"
        plan.agent_run_id = exc.run_id
        plan.agent_error = exc.code
        record = eng.agent_runs.get(exc.run_id)
        if record is not None:
            plan.agent_run = {
                "run_id": record.run_id,
                "state": record.state,
                "state_history": record.state_history,
                "requests": record.requests,
                "model": record.model,
                "prompt_version": record.prompt_version,
                "accepted_count": record.accepted_count,
                "rejected_count": record.rejected_count,
                "error": record.error,
            }
        plan.unresolved.append(
            f"Real-agent execution failed ({exc.code}); the deterministic planner produced this "
            "plan and the agent run audit is preserved."
        )
        return plan


@app.post("/api/investigate")
async def investigate(body: InvestigationBody, request: Request):
    from .catalog import MatchCatalog

    public_rate(request, "investigate", 30)
    # The owner is the server-side session, never a client-supplied field.
    owner = session(request)
    try:
        ctx = MatchCatalog.get_match_context(body.match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")
    eng = engine(request)
    events = eng.events_for_match(body.match_id)
    if body.at is not None and (body.at < 0 or body.at > int(math.ceil(ctx.replayable_end))):
        raise HTTPException(422, "at_outside_match_context")
    at = int(body.at) if body.at is not None else (
        ctx.duration if body.match_id.startswith("syn_") else int(math.ceil(ctx.replayable_end))
    )

    # Freeze the investigation at the selected football moment, not merely at
    # the session clock. This keeps current-window metrics and the focus aligned.
    if body.focus_type in ("event", "sequence", "moment", "oaai_point", "shot_location"):
        pre_state = reduce_match(
            events,
            at,
            max_duration=int(math.ceil(ctx.replayable_end)),
            nominal_duration=ctx.duration,
            is_synthetic=body.match_id.startswith("syn_"),
            team_names={"H": ctx.home_team_name, "N": ctx.away_team_name},
            team_map=(
                {ctx.home_provider_team_id: "H", ctx.away_provider_team_id: "N"}
                if ctx.home_provider_team_id and ctx.away_provider_team_id
                else None
            ),
            coordinate_frame=ctx.coordinate_frame,
            continuous_coverage=ctx.continuous_coverage,
        )
        if body.focus_type == "event" and body.focus_id:
            event = next((e for e in pre_state.get("events", []) if str(e.get("id")) == body.focus_id), None)
            if event is not None:
                at = int(float(event.get("t", at)))
        elif body.focus_type == "shot_location" and (body.focus_id or "").startswith("evt:"):
            # A shot pinned by event id freezes the investigation at the shot.
            # Coordinates-only foci keep the requested moment; the planner
            # resolves the nearest recorded shot itself.
            event = next(
                (e for e in pre_state.get("events", []) if str(e.get("id")) == body.focus_id[4:]),
                None,
            )
            if event is not None:
                at = int(float(event.get("t", at)))
        elif body.focus_type == "sequence" and body.focus_id:
            sequence = next(
                (s for s in build_sequences(pre_state) if s.get("sequence_id") == body.focus_id),
                None,
            )
            if sequence is not None:
                at = int(float(sequence.get("end_t", at)))
        else:
            # The OAAI pipeline is expensive on a full provider payload, so it
            # only runs when the caller did not pin the moment itself.
            if body.at is None:
                oaai = compute_oaai(
                    pre_state.get("events", []),
                    t_end=at,
                    dead_intervals=pre_state.get("dead_intervals", []),
                    xt_model=eng.xt_model,
                )
                points = oaai.get("change_points", [])
                point = None
                if body.focus_id:
                    point = next((p for p in points if p.get("change_point_id") == body.focus_id), None)
                elif points:
                    point = max(points, key=lambda p: float(p.get("at", 0.0)))
                if point is not None:
                    at = int(float(point.get("at", at)))

    snap, state = freeze_match_snapshot(eng, body.match_id, at)
    eng.saved_snapshots[snap.id] = snap
    if body.execution_mode == "maf_agent":
        # A real agent run dispatches paid model requests; rate it separately
        # from deterministic reads, on top of the durable budget ledger.
        public_rate(request, "investigate-agent", 6)
    from .investigation import InvestigationCancelled

    request_key = body.request_key
    cancel_event = eng.begin_investigation_request(owner.id, request_key) if request_key else None
    try:
        plan = await run_investigation_plan(
            eng,
            body,
            snap,
            state,
            owner.id,
            cancel_event=cancel_event,
            on_run_created=(
                (lambda run_id: eng.bind_investigation_run(owner.id, request_key, run_id))
                if request_key
                else None
            ),
        )
        plan.owner_session_id = owner.id
        eng.investigations.save(plan)
        return private_plan_payload(plan)
    except InvestigationCancelled as exc:
        record = eng.agent_runs.get(exc.run_id) if exc.run_id else None
        return JSONResponse(
            status_code=409,
            content={
                "detail": "investigation_cancelled",
                "cancelled": True,
                "request_key": request_key,
                "run_id": exc.run_id,
                "state": record.state if record is not None else "CANCELLED",
                "state_history": record.state_history if record is not None else [],
            },
        )
    finally:
        if request_key:
            eng.end_investigation_request(owner.id, request_key)


@app.post("/api/investigation-requests/{request_key}/cancel")
async def cancel_live_investigation(request_key: str, request: Request):
    """Cancel a live investigation request owned by this server session.

    The request key is client-generated and only meaningful inside the session;
    it grants no access by itself. Cancellation is cooperative on the server:
    the model dispatch races the cancel event and the run record closes as
    CANCELLED. A cancel that arrives just before registration is remembered.
    """
    public_rate(request, "investigate-cancel", 60)
    if not (8 <= len(request_key) <= 64) or not request_key.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(422, "invalid_request_key")
    owner = session(request)
    eng = engine(request)
    result = eng.cancel_investigation_request(owner.id, request_key)
    return {
        "request_key": request_key,
        "state": "cancel_requested",
        "active": result["active"],
        "run_id": result["run_id"],
    }


@app.get("/api/investigations")
async def list_investigations(request: Request, match_id: str | None = None, limit: int = 50):
    """Saved investigation summaries, scoped to the server-side owner.

    A producer token is a separate role and may list the full store; an
    anonymous browser only ever sees its own session's records. Legacy records
    have no owner and are visible only to that producer role.
    """
    public_rate(request, "investigations", 60)
    if limit < 1 or limit > 200:
        raise HTTPException(422, "limit_out_of_bounds")
    eng = engine(request)
    live = optional_session(request)
    principal = optional_principal(request)
    allow_all = bool(principal and principal.can_edit_content)
    if live is None and not allow_all:
        raise HTTPException(401, "session_expired")
    plans = eng.investigations.list_for(
        owner_session_id=live.id if live else None,
        allow_all=allow_all,
        match_id=match_id,
        limit=limit,
    )
    return {
        "match_id": match_id,
        "count": len(plans),
        "scope": "producer_all" if allow_all else "session_owner",
        "investigations": [
            {
                "investigation_id": p.investigation_id,
                "match_id": p.match_id,
                "snapshot_id": p.snapshot_id,
                "state": p.state,
                "focus_type": p.focus_type,
                "focus_id": p.focus_id,
                "team": p.team,
                "as_of": p.as_of,
                "question": p.question,
                "intent": p.intent,
                "execution_mode": p.execution_mode,
                "agent_status": p.agent_status,
                "gate_status": p.gate_preview.status,
                "gate_assertion": p.gate_preview.assertion,
                "finding_count": len(p.findings),
                "dataset_revision": p.dataset_revision,
                "legacy_unowned": p.owner_session_id is None,
            }
            for p in plans
        ],
    }


@app.get("/api/investigations/{investigation_id}")
async def get_investigation(investigation_id: str, request: Request):
    eng = engine(request)
    plan = eng.investigations.get(investigation_id)
    if plan is None:
        raise HTTPException(404, "investigation_not_found")
    private_access(request, plan.owner_session_id)
    return private_plan_payload(plan)


@app.post("/api/investigations/{investigation_id}/cancel")
async def cancel_investigation(investigation_id: str, request: Request):
    eng = engine(request)
    plan = eng.investigations.get(investigation_id)
    if plan is None:
        raise HTTPException(404, "investigation_not_found")
    private_access(request, plan.owner_session_id)
    try:
        plan = eng.investigations.cancel(investigation_id)
    except KeyError:
        raise HTTPException(404, "investigation_not_found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return private_plan_payload(plan)


@app.post("/api/investigations/{investigation_id}/promote")
async def promote_investigation(investigation_id: str, request: Request):
    from .catalog import MatchCatalog

    eng = engine(request)
    plan = eng.investigations.get(investigation_id)
    if plan is None:
        raise HTTPException(404, "investigation_not_found")
    # Promotion writes a public claim; it still requires ownership of the
    # private draft (or the independent producer role).
    private_access(request, plan.owner_session_id)
    if plan.gate_preview.assertion == "none" or plan.gate_preview.status != "approved":
        raise HTTPException(409, "investigation_not_gate_approved")
    if plan.state not in ("APPROVED", "QUALIFIED"):
        raise HTTPException(409, f"investigation_state_{plan.state.lower()}")

    snap = eng.saved_snapshots.get(plan.snapshot_id)
    if snap is None:
        try:
            snap, _state = freeze_match_snapshot(eng, plan.match_id, plan.as_of)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "snapshot_not_found")
    snap_revision = snap.data.get("dataset_revision") or snap.data.get("data_version")
    if plan.dataset_revision and snap_revision and plan.dataset_revision != snap_revision:
        raise HTTPException(409, "dataset_revision_changed")

    record = eng.registry.verify_and_register(
        snap,
        plan.match_id,
        plan.gate_preview.assertion,
        subject_team=plan.team,  # type: ignore[arg-type]
        source_run=plan.investigation_id,
    )
    plan.gate_preview.persisted = record.gate_status == "approved"
    if plan.agent_run_id:
        agent_record = eng.agent_runs.get(plan.agent_run_id)
        if agent_record is not None and agent_record.state == "GATED" and plan.gate_preview.persisted:
            eng.agent_runs.transition(plan.agent_run_id, "PUBLISHED", "claim promoted to registry by user")
    eng.investigations.save(plan)
    return {
        "claim": record.model_dump(),
        "investigation_id": plan.investigation_id,
        "gate_status": record.gate_status,
        "current_revision_id": record.current_revision_id,
    }


@app.get("/api/agent-runs")
async def list_agent_runs(request: Request, limit: int = 50, state: str | None = None):
    """Persisted agent-run lifecycle records, scoped to the owner.

    The budget summary is deployment-wide operational information, so it is
    returned only to a producer/admin; an anonymous session receives its own
    runs and no global spend figure.
    """
    eng = engine(request)
    live = optional_session(request)
    principal = optional_principal(request)
    allow_all = bool(principal and principal.can_edit_content)
    if live is None and not allow_all:
        raise HTTPException(401, "session_expired")
    records = eng.agent_runs.list_for(
        live.id if live else None,
        allow_all=allow_all,
        limit=min(max(limit, 1), 200),
        state=state,
    )
    payload: dict[str, object] = {
        "runs": [private_run_payload(record) for record in records],
        "scope": "producer_all" if allow_all else "session_owner",
    }
    if allow_all:
        payload["budget"] = eng.ledger.summary()
    return payload


@app.get("/api/agent-runs/{run_id}")
async def get_agent_run(run_id: str, request: Request):
    record = engine(request).agent_runs.get(run_id)
    if record is None:
        raise HTTPException(404, "agent_run_not_found")
    private_access(request, record.owner_session_id)
    return private_run_payload(record)


@app.post("/api/agent-runs/{run_id}/cancel")
async def cancel_agent_run(run_id: str, request: Request):
    """Close a non-terminal run record as CANCELLED.

    Live session runs are cancelled through the session epoch (which cancels
    the task and records CANCELLED); this endpoint closes records left
    non-terminal by a restart or a lost dispatch so no run stays ambiguous.
    """
    eng = engine(request)
    record = eng.agent_runs.get(run_id)
    if record is None:
        raise HTTPException(404, "agent_run_not_found")
    private_access(request, record.owner_session_id)
    try:
        record = eng.agent_runs.cancel(run_id)
    except KeyError:
        raise HTTPException(404, "agent_run_not_found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return private_run_payload(record)


@app.get("/api/matches/{match_id}/story")
async def get_match_story(
    match_id: str,
    request: Request,
    perspective: Literal["coach", "media", "fan"] = "media",
    as_of: int | None = None,
    mode: Literal["live", "recap"] = "recap",
):
    from .catalog import MatchCatalog
    from .stories import MatchStoryEngine

    public_rate(request, "story", 30)
    eng = engine(request)
    try:
        ctx = MatchCatalog.get_match_context(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")

    if as_of is not None and (as_of < 0 or as_of > int(math.ceil(ctx.replayable_end))):
        raise HTTPException(422, "as_of_outside_match_context")
    if mode == "live":
        at = int(as_of) if as_of is not None else int(math.ceil(ctx.replayable_end))
    else:
        at = int(as_of) if as_of is not None else (
            ctx.duration if match_id.startswith("syn_") else int(math.ceil(ctx.replayable_end))
        )
    at = max(0, min(at, int(math.ceil(ctx.replayable_end))))
    snap, state = freeze_match_snapshot(eng, match_id, at)
    eng.saved_snapshots[snap.id] = snap
    eng.ensure_snapshot_claims(match_id, snap)
    records = eng.registry.records_for(match_id, snap.id)
    approval_signature = hashlib.sha256(json.dumps([
        (r.claim_id, r.gate_status, r.editorial_status, r.lifecycle_status, r.editorial_version, r.revision_count)
        for r in sorted(records, key=lambda x: x.claim_id)
    ], sort_keys=True).encode()).hexdigest()[:16]
    cache_key = (match_id, snap.id, perspective, ctx.dataset_revision or ctx.data_version, approval_signature, mode)
    if cache_key in eng.story_cache:
        return eng.story_cache[cache_key]
    story = MatchStoryEngine.generate_story(
        match_id,
        state["events"],
        eng.registry,
        snap.id,
        perspective,
        coverage=state["coverage"],
        dataset_revision=ctx.dataset_revision or ctx.data_version,
        snapshot=snap,
    ).model_dump()
    story.update(dataset_revision=ctx.dataset_revision or ctx.data_version, as_of=at, mode=mode)
    if len(eng.story_cache) > 128:
        eng.story_cache.clear()
    eng.story_cache[cache_key] = story
    return story


class EditorialDecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_id: str
    snapshot_id: str
    claim_id: str
    decision: Literal["approved", "rejected"] = "approved"
    note: str | None = None


@app.post("/api/story/editorial-approval")
async def editorial_approval(body: EditorialDecisionBody, request: Request):
    from .auth import require_content_editor

    principal = require_content_editor(request)
    eng = engine(request)
    try:
        record = eng.registry.editorial_decision(
            body.match_id,
            body.snapshot_id,
            body.claim_id,
            approver=principal.subject,
            role=principal.role,
            decision=body.decision,
            note=body.note,
        )
    except KeyError:
        raise HTTPException(404, "claim_not_registered")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return private_run_payload(record)


@app.get("/api/claims/history")
async def claim_history(
    request: Request,
    match_id: str,
    snapshot_id: str,
    claim_id: str,
):
    from .auth import require_content_editor

    require_content_editor(request)
    eng = engine(request)
    record = eng.registry.get(match_id, snapshot_id, claim_id)
    if record is None:
        raise HTTPException(404, "claim_not_registered")
    revisions = eng.registry.revision_history(match_id, snapshot_id, claim_id)
    return {
        "claim": record.model_dump(),
        "revisions": [
            {
                **r.model_dump(),
                "is_current": r.revision_id == record.current_revision_id,
            }
            for r in revisions
        ],
        "supersessions": [e.model_dump() for e in eng.registry.supersessions_for(match_id, snapshot_id, claim_id)],
        "editorial_history": record.editorial_history,
        "validity": eng.registry.claim_validity(record, require_editorial=False),
    }


class RundownBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_id: str
    snapshot_id: str
    claim_ids: list[str] = Field(min_length=1, max_length=20)


class ExportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_id: str
    snapshot_id: str
    perspective: Literal["coach", "media", "fan"] = "media"
    export_format: Literal["json", "svg", "markdown"] = "json"


@app.get("/api/broadcast/queue")
async def broadcast_queue(request: Request, match_id: str, snapshot_id: str):
    from .broadcast import public_claim_projection

    public_rate(request, "broadcast", 60)
    eng = engine(request)
    records = eng.registry.records_for(match_id, snapshot_id)
    return {
        "match_id": match_id,
        "snapshot_id": snapshot_id,
        "projection": "public",
        "records": [
            public_claim_projection(r)
            for r in sorted(records, key=lambda r: (r.as_of, r.claim_id))
        ],
        "broadcastable_count": sum(1 for r in records if r.broadcastable),
    }


@app.get("/api/broadcast/queue/producer")
async def broadcast_queue_producer(request: Request, match_id: str, snapshot_id: str):
    from .auth import require_content_editor
    from .broadcast import producer_claim_projection

    principal = require_content_editor(request)
    eng = engine(request)
    records = eng.registry.records_for(match_id, snapshot_id)
    return {
        "match_id": match_id,
        "snapshot_id": snapshot_id,
        "projection": "producer",
        "principal": principal.subject,
        "records": [
            producer_claim_projection(r)
            for r in sorted(records, key=lambda r: (r.as_of, r.claim_id))
        ],
        "broadcastable_count": sum(1 for r in records if r.broadcastable),
    }


@app.post("/api/broadcast/rundown")
async def broadcast_rundown(body: RundownBody, request: Request):
    from .auth import require_content_editor

    principal = require_content_editor(request)
    eng = engine(request)
    snap = eng.saved_snapshots.get(body.snapshot_id)
    if snap is None:
        raise HTTPException(404, "snapshot_not_found")
    ctx = eng.match_context(body.match_id)
    records = eng.registry.records_for(body.match_id, body.snapshot_id)
    try:
        rundown = eng.broadcast.build(
            match_id=body.match_id,
            snapshot_id=body.snapshot_id,
            claims=records,
            claim_ids=body.claim_ids,
            dataset_revision=ctx.dataset_revision or ctx.data_version,
            actor=principal.subject,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return rundown.model_dump()


@app.get("/api/broadcast/rundown")
async def get_broadcast_rundown(request: Request, match_id: str, snapshot_id: str):
    from .broadcast import RundownValidation

    eng = engine(request)
    rundown = eng.broadcast.get(match_id, snapshot_id)
    if rundown is None:
        raise HTTPException(404, "rundown_not_found")
    snap = eng.saved_snapshots.get(snapshot_id)
    if snap is None:
        from .catalog import MatchCatalog

        try:
            ctx = MatchCatalog.get_match_context(match_id)
            target = rundown.as_of if rundown.as_of is not None else int(math.ceil(ctx.replayable_end))
            snap, _state = freeze_match_snapshot(eng, match_id, target)
            eng.saved_snapshots[snap.id] = snap
        except (FileNotFoundError, ValueError):
            snap = None
    dataset_revision = (
        (snap.data.get("dataset_revision") or snap.data.get("data_version"))
        if snap else rundown.dataset_revision
    )
    records = eng.registry.records_for(match_id, snapshot_id)
    if snap is None:
        validation = RundownValidation(
            valid=False,
            items=[],
            stale_items=[item.claim_id for item in rundown.items],
            dataset_revision=dataset_revision,
        )
    else:
        validation = eng.broadcast.validate(
            rundown, claims=records, dataset_revision=dataset_revision, require_editorial=True
        )
    return {
        **rundown.model_dump(),
        "valid": validation.valid,
        "stale_items": validation.stale_items,
        "validation": validation.model_dump(),
        "items": [item.model_dump() for item in validation.items],
    }


@app.get("/api/broadcast/manifests")
async def broadcast_manifest_history(request: Request, match_id: str, snapshot_id: str):
    """Bounded export-manifest history for one snapshot (producer scope)."""
    from .auth import require_content_editor

    principal = require_content_editor(request)
    eng = engine(request)
    history = eng.broadcast.manifest_history(match_id, snapshot_id)
    return {
        "match_id": match_id,
        "snapshot_id": snapshot_id,
        "projection": "producer",
        "principal": principal.subject,
        "count": len(history),
        "manifests": [m.model_dump() for m in history],
    }


@app.post("/api/broadcast/export")
async def broadcast_export(body: ExportBody, request: Request):
    from .auth import require_content_editor
    from .stories import MatchStoryEngine, StoryExportEngine

    principal = require_content_editor(request)
    eng = engine(request)
    snap = eng.saved_snapshots.get(body.snapshot_id)
    if snap is None:
        raise HTTPException(404, "snapshot_not_found")
    dataset_revision = snap.data.get("dataset_revision") or snap.data.get("data_version")
    records = eng.registry.records_for(body.match_id, body.snapshot_id)
    approved = [
        r for r in records
        if r.broadcastable
        and eng.registry.claim_validity(
            r, dataset_revision=dataset_revision, require_editorial=True
        )["valid"]
    ]
    if not approved:
        raise HTTPException(409, "no_broadcastable_claims")

    rundown = eng.broadcast.get(body.match_id, body.snapshot_id)
    if rundown is None:
        try:
            rundown = eng.broadcast.build(
                match_id=body.match_id,
                snapshot_id=body.snapshot_id,
                claims=records,
                claim_ids=[r.claim_id for r in approved],
                dataset_revision=dataset_revision,
                actor=principal.subject,
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc))
    validation = eng.broadcast.validate(
        rundown, claims=records, dataset_revision=dataset_revision, require_editorial=True
    )
    if not validation.valid:
        raise HTTPException(409, {
            "code": "rundown_contains_stale_claims",
            "stale_items": validation.stale_items,
        })

    story = MatchStoryEngine.generate_story(
        body.match_id,
        snap.data.get("events", []),
        eng.registry,
        body.snapshot_id,
        body.perspective,
        coverage=snap.data.get("coverage", {}),
        dataset_revision=dataset_revision,
        claim_ids=[item.claim_id for item in rundown.items],
        snapshot=snap,
    )
    if story.approval_status != "approved_for_broadcast":
        raise HTTPException(409, "story_not_broadcastable")
    package = StoryExportEngine.export_story_package(story, body.export_format)
    manifest = eng.broadcast.manifest(
        rundown=rundown,
        validation=validation,
        claims=records,
        dataset_revision=dataset_revision,
        actor=principal.subject,
        package_payload=package.payload,
    )
    eng.broadcast.record_manifest(manifest)
    valid_claim_ids = [item.claim_id for item in validation.items if item.valid]
    approved_by = sorted({
        r.editorial_approver for r in approved
        if r.claim_id in set(valid_claim_ids) and r.editorial_approver
    })
    return {
        **package.model_dump(),
        "match_id": body.match_id,
        "snapshot_id": body.snapshot_id,
        "dataset_revision": dataset_revision,
        "approved_by": approved_by,
        "claim_ids": valid_claim_ids,
        "manifest": manifest.model_dump(),
    }


@app.get("/api/matches/{match_id}/perspectives")
async def get_match_perspectives(
    match_id: str,
    perspective: Literal["coach", "media", "fan"] = "media",
):
    from .stories import PerspectiveManager
    return PerspectiveManager.get_perspective_view(perspective, match_id)


@app.get("/api/matches/{match_id}/attribution")
async def get_match_attribution(
    match_id: str,
    request: Request,
    window_start: float = 0.0,
    window_end: float = 1200.0,
    team: str = "H",
):
    if window_start < 0 or window_end <= window_start or window_end - window_start > 5400:
        raise HTTPException(400, "invalid_window_bounds")
    if team not in ("H", "N"):
        raise HTTPException(400, "invalid_team")

    from .catalog import MatchCatalog
    from .attribution import EventAttributionSpecialist
    try:
        events = MatchCatalog.load_normalized_events(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")

    decomp = EventAttributionSpecialist.temporal_window_decomposition(
        events, window_start_s=window_start, window_end_s=window_end, team=team
    )
    alt = EventAttributionSpecialist.alternative_hypothesis_assessment(
        events, primary_hypothesis=decomp.summary, window_start_s=window_start, window_end_s=window_end, team=team
    )
    return {
        "match_id": match_id,
        "window_decomposition": decomp,
        "alternative_hypotheses": alt,
    }


@app.get("/api/matches/{match_id}/validation")
async def get_match_validation(
    match_id: str,
    request: Request,
    iterations: int = 50,
):
    public_rate(request, "validation", 10)
    if iterations <= 0 or iterations > 200:
        raise HTTPException(400, "iterations_out_of_bounds")

    from .catalog import MatchCatalog
    from .validation import ScientificValidationEngine
    try:
        events = MatchCatalog.load_normalized_events(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")

    return ScientificValidationEngine.run_bootstrap_validation(match_id, events, iterations=iterations)


@app.post("/api/matches/{match_id}/whatif")
async def post_match_whatif(
    match_id: str,
    req: dict,
):
    from .catalog import MatchCatalog
    from .validation import WhatIfSimulationEngine, WhatIfScenarioRequest
    try:
        events = MatchCatalog.load_normalized_events(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")

    request_obj = WhatIfScenarioRequest.model_validate(req)
    return WhatIfSimulationEngine.simulate(events, request_obj)


@app.get("/api/benchmark/agents")
async def get_agent_benchmark(request: Request, match_id: str = "syn_default"):
    public_rate(request, "benchmark", 10)
    from .attribution import run_agent_benchmark_harness
    return run_agent_benchmark_harness(match_id=match_id)


@app.get("/api/attribution/window")
async def get_attribution_window(
    request: Request,
    match_id: str = "syn_default",
    window_start: float = 0.0,
    window_end: float = 600.0,
    team: str = "H",
    top_k: int = 5,
):
    if window_start < 0 or window_end <= window_start or window_end - window_start > 5400:
        raise HTTPException(400, "invalid_window_bounds")
    if top_k <= 0 or top_k > 50:
        raise HTTPException(400, "invalid_top_k")
    if team not in ("H", "N"):
        raise HTTPException(400, "invalid_team")

    from .catalog import MatchCatalog
    from .attribution import EventAttributionSpecialist
    try:
        events = MatchCatalog.load_normalized_events(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")
    return EventAttributionSpecialist.temporal_window_decomposition(
        events, window_start=window_start, window_end=window_end, team=team, top_k=top_k, match_id=match_id
    )


@app.get("/api/attribution/chain")
async def get_attribution_chain(
    request: Request,
    match_id: str = "syn_default",
    target_event_id: str = "",
    lookback_seconds: float = 30.0,
):
    if lookback_seconds <= 0 or lookback_seconds > 300:
        raise HTTPException(400, "invalid_lookback")

    from .catalog import MatchCatalog
    from .attribution import EventAttributionSpecialist
    try:
        events = MatchCatalog.load_normalized_events(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")
    if not target_event_id and events:
        target_event_id = events[-1].event_id
    return EventAttributionSpecialist.causal_chain_query(
        events, target_event_id=target_event_id, lookback_seconds=lookback_seconds
    )


@app.get("/api/attribution/alternatives")
async def get_attribution_alternatives(
    request: Request,
    match_id: str = "syn_default",
    window_start: float = 0.0,
    window_end: float = 600.0,
    team: str = "H",
    primary_hypothesis: str = "High pressing forced turnover and chance",
):
    if window_start < 0 or window_end <= window_start or window_end - window_start > 5400:
        raise HTTPException(400, "invalid_window_bounds")
    if team not in ("H", "N"):
        raise HTTPException(400, "invalid_team")

    from .catalog import MatchCatalog
    from .attribution import EventAttributionSpecialist
    try:
        events = MatchCatalog.load_normalized_events(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")
    return EventAttributionSpecialist.alternative_hypothesis_assessment(
        events, primary_hypothesis=primary_hypothesis, window_start=window_start, window_end=window_end, team=team
    )


@app.get("/api/sufficiency/{match_id}")
async def get_data_sufficiency(
    match_id: str,
    request: Request,
    coverage_level: str = "C0",
):
    from .catalog import MatchCatalog
    from .sufficiency import assess_data_sufficiency
    try:
        events = MatchCatalog.load_normalized_events(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")
    return assess_data_sufficiency(events, coverage_level=coverage_level)


@app.get("/api/benchmark/abc")
async def get_benchmark_abc(
    request: Request,
    match_id: str = "syn_default",
):
    public_rate(request, "benchmark", 10)
    from .benchmark import run_agent_benchmark_harness
    return run_agent_benchmark_harness(match_id=match_id)


@app.get("/api/benchmark/agent-contract")
async def get_benchmark_agent_contract(request: Request):
    """Recorded-replay contract benchmark for the agentic publication path.

    Replays genuine recorded model outputs through the real validation and
    gate code; live comparison arms are reported as Not Run until an
    authorized paid budget exists.
    """
    public_rate(request, "benchmark", 10)
    from .benchmark import run_agent_contract_benchmark
    return run_agent_contract_benchmark()


@app.get("/api/matches/{match_id}/evidence-graph")
async def get_match_evidence_graph(
    match_id: str,
    request: Request,
    at: float | None = None,
    team: str = "H",
):
    from .catalog import MatchCatalog
    from .evidence import build_evidence_graph

    public_rate(request, "evidence_graph", 30)
    eng = engine(request)
    try:
        ctx = MatchCatalog.get_match_context(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")

    if at is not None and (at < 0 or at > int(math.ceil(ctx.replayable_end))):
        raise HTTPException(422, "at_outside_match_context")
    at_time = int(
        at if at is not None
        else (ctx.duration if match_id.startswith("syn_") else int(math.ceil(ctx.replayable_end)))
    )
    snap, _state = freeze_match_snapshot(eng, match_id, at_time)
    eng.saved_snapshots[snap.id] = snap
    eng.ensure_snapshot_claims(match_id, snap)
    meta = MatchCatalog.get_match(match_id)
    principal = optional_principal(request)
    include_coordinates = not (
        meta is not None
        and is_protected_provider(meta.provenance_kind)
        and not (principal and principal.can_edit_content)
    )
    return build_evidence_graph(
        match_id=match_id,
        match_context=ctx,
        snapshot=snap,
        registry=eng.registry,
        team=team,
        include_coordinates=include_coordinates,
    )


@app.get("/api/{path:path}", operation_id="missing_api_get")
@app.post("/api/{path:path}", operation_id="missing_api_post")
@app.put("/api/{path:path}", operation_id="missing_api_put")
@app.delete("/api/{path:path}", operation_id="missing_api_delete")
async def missing_api(path: str):
    raise HTTPException(404, "api_not_found")


web = ROOT / "apps" / "web" / "out"
if web.exists():
    app.mount("/", StaticFiles(directory=web, html=True), name="web")
else:
    @app.get("/")
    async def build_notice():
        return {"message": "Build apps/web first, then restart FastAPI. See README.md", "api": "/api/health"}
