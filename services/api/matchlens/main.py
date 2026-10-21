from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from typing import Literal

from .agents import AgentRunner, Run, PROMPT_VERSION
from .budget import BudgetLedger
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

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
COOKIE = "matchlens_session"


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
    touched: float = field(default_factory=time.monotonic)
    anchor_time: float = field(default_factory=time.monotonic)
    anchor_at: int = 0
    snapshots: dict[str, Snapshot] = field(default_factory=dict)
    cache: dict[str, dict] = field(default_factory=dict)
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

    def tick(self):
        if not self.paused:
            at = min(720, self.anchor_at+int((time.monotonic()-self.anchor_time)*self.speed))
            if at != self.at:
                self.at = at
                self.revision += 1
            if at == 720:
                self.paused = True

    def invalidate(self):
        self.epoch += 1
        self.revision += 1
        if self.task and not self.task.done():
            self.task.cancel()
        self.run_info = None


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["focus", "focus_moment", "exit_focus", "play", "pause", "speed", "restart", "set_scenario", "set_team"]
    chapter: Literal["A", "B", "C"] | None = None
    moment_id: str | None = None
    speed: Literal[1, 6, 30] | None = None
    scenario: str | None = None
    team: Literal["H", "N"] | None = None


class Engine:
    def __init__(self, runtime: Path, key: str | None):
        self.events = generate_match()
        self.scenario_events = {("default", 17): self.events}
        self.sessions: dict[str, Session] = {}
        self.rates = RateLimits()
        self.ledger = BudgetLedger(runtime / "budget.sqlite3", int(os.getenv("MATCHLENS_MAX_REQUESTS", "32")), float(os.getenv("MATCHLENS_MAX_RESERVED_USD", "1.0")))
        self.runner = AgentRunner(key, self.ledger)
        self.auto_enabled = os.getenv("MATCHLENS_AUTO_ANALYSE", "0") == "1"
        self.auto_limit = min(2, max(0, int(os.getenv("MATCHLENS_AUTO_RUNS_PER_SESSION", "2"))))
        self.admissions: set[str] = set()
        self.slots = asyncio.Semaphore(2)
        self.runtime = runtime
        (runtime / "runs").mkdir(parents=True, exist_ok=True)
        self.saved_runs: dict[str, dict] = {}
        self.saved_snapshots: dict[str, Snapshot] = {}
        for p in sorted((runtime / "runs").glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                snap_id = data.get("snapshot_id")
                res = data.get("result")
                if snap_id and res and res.get("status") == "completed" and res.get("accepted"):
                    snap = freeze(self.events, data["evidence"]["as_of"])
                    # A historical receipt must match this match prefix byte for
                    # byte and pass today's gate. Never relabel an old hash.
                    if snap.id != snap_id or snap.data != data["evidence"]:
                        continue
                    checked = publication_gate(ClaimDraft.model_validate(data["draft"]), VerifierDecision.model_validate(data["review"]), snap, data["audit"])
                    if not checked["accepted"]:
                        continue
                    for card in checked["accepted"]:
                        card.update(historical=True, source_run_id=data.get("run_id", p.stem))
                    self.saved_runs[snap_id] = {**res, **checked, "reused": True, "snapshot_id": snap_id, "as_of": snap.data["as_of"],
                                               "audit": data["audit"], "requests": data["requests"], "run_id": data.get("run_id", p.stem)}
                    self.saved_snapshots[snap_id] = snap
            except Exception:
                pass

    def events_for(self, s: Session):
        key = (s.scenario, s.seed)
        if key not in self.scenario_events:
            self.scenario_events[key] = generate_match(seed=s.seed, scenario=s.scenario)
        return self.scenario_events[key]

    def cleanup(self):
        for sid, s in list(self.sessions.items()):
            if time.monotonic()-s.touched > 1800:
                s.invalidate()
                del self.sessions[sid]

    def view(self, s: Session) -> dict:
        s.tick()
        active_events = self.events_for(s)
        state = reduce_match(active_events, s.at)
        # Scan newly crossed event boundaries so 30x playback cannot skip a
        # transient detector condition. Each type is latched once per session.
        times = sorted({e.t for e in active_events if s.observed_at < e.t <= s.at} | ({s.at} if s.at > s.observed_at else set()))
        for at in times:
            for moment in detect_moments(reduce_match(active_events, at)):
                if moment["id"] not in s.moments:
                    s.moments[moment["id"]] = moment
                    snap = freeze(active_events, moment["at"], seed=s.seed)
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
                snapshot = freeze(active_events, s.at, seed=s.seed)
                s.snapshots[snapshot.id] = snapshot
        elif s.run_info and s.run_info.get("as_of", 721) <= s.at:
            snapshot = next((snap for snap in s.snapshots.values() if snap.data["as_of"] == s.run_info["as_of"]), None)
        elif active:
            snapshot = next((snap for snap in s.snapshots.values() if snap.data["as_of"] == active["at"]), None)
            if not snapshot:
                snapshot = freeze(active_events, active["at"], seed=s.seed)
                s.snapshots[snapshot.id] = snapshot
        else:
            snapshot = None

        # Result resolution: if actively analysing, result is None until finished
        is_default_fixture = s.scenario == "default" and s.seed == 17
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

        return {"revision": s.revision, "epoch": s.epoch, "at": s.at, "paused": s.paused, "speed": s.speed,
                "scenario": s.scenario, "scenarios": list(SCENARIOS.values()), "focus_team": s.focus_team,
                "focus": s.focus, "score": state["score"], "owner": state["owner"], "ball": state["ball"],
                "events": state["events"], "players": PLAYERS, "receipts": both_team_receipts(state),
                "sequences": build_sequences(state), "tactical": build_tactical_explorer(state, s.focus_team),
                "player_spotlight": build_player_spotlight(state),
                "chapters": CHAPTERS, "moments": moments, "active_moment": active,
                "snapshot_id": snapshot.id if snapshot else None,
                "snapshot_as_of": snapshot.data["as_of"] if snapshot else None,
                "analysis_receipts": snapshot.data["receipts"] if snapshot else None,
                "analysis": s.run_info, "result": result, "history": accepted_history,
                "revisions": s.revisions,
                "hypotheses_matrix": evaluate_hypotheses(snapshot, s.focus_team).model_dump() if snapshot else None,
                "model_configured": bool(self.runner.key), "session_analyses_remaining": max(0, 8-s.analyses),
                "auto_status": "disabled" if not self.auto_enabled else "model_unavailable" if not self.runner.key else "budget_limited" if not self.can_admit() else "session_limited" if s.auto_started >= self.auto_limit else "enabled",
                "format_seconds": 720, "ended": state["ended"]}

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
        run = Run("run-"+secrets.token_hex(8), snap)
        run.audit.append({"type": "trigger", "source": trigger, "as_of": snap.data["as_of"]})
        s.attempted.add(snap.id)
        s.attempts[snap.id] = s.attempts.get(snap.id, 0) + 1
        s.analyses += 1
        self.admissions.add(run.id)
        s.run_info = {"run_id": run.id, "status": "queued", "as_of": snap.data["as_of"], "epoch": s.epoch}
        s.revision += 1
        s.task = asyncio.create_task(self.execute(s, snap, s.epoch, run))
        # Cancellation can happen before the coroutine reaches its finally.
        s.task.add_done_callback(lambda _: self.admissions.discard(run.id))
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
        async def progress(status: str):
            if epoch != s.epoch:
                raise asyncio.CancelledError()
            s.run_info = {"run_id": run.id, "status": status, "as_of": snapshot.data["as_of"], "epoch": epoch}
            s.revision += 1
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
            if epoch == s.epoch and snapshot.data["as_of"] <= s.at:
                s.cache[snapshot.id] = result
                s.run_info = {"run_id": run.id, "status": result["status"], "as_of": result["as_of"], "epoch": epoch}
                s.revision += 1
            else:
                run.audit.append({"type": "superseded", "bound_epoch": epoch, "current_epoch": s.epoch})
        except asyncio.CancelledError:
            run.audit.append({"type": "superseded", "bound_epoch": epoch, "current_epoch": s.epoch})
        except TimeoutError:
            result = {"status": "fallback", "origin": "deterministic", "error": "analysis_queue_busy", "accepted": [], "rejected": [],
                      "run_id": run.id, "snapshot_id": snapshot.id, "as_of": snapshot.data["as_of"], "audit": run.audit, "requests": run.requests}
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
        if request.method == "POST":
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return Response("Origin rejected", status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def engine(request: Request) -> Engine:
    return request.app.state.engine


def session(request: Request) -> Session:
    eng = engine(request)
    eng.cleanup()
    s = eng.sessions.get(request.cookies.get(COOKIE, ""))
    if not s:
        raise HTTPException(401, "session_expired")
    s.touched = time.monotonic()
    return s


@app.get("/api/health")
async def health(request: Request):
    return {"ok": True, "model_configured": bool(engine(request).runner.key), "format": "12-minute synthetic match"}


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
    response.set_cookie(COOKIE, s.id, httponly=True, secure=request.url.scheme == "https", samesite="strict", max_age=1800)
    return eng.view(s)


@app.get("/api/state")
async def state(request: Request):
    return engine(request).view(session(request))


@app.post("/api/control")
async def control(command: Control, request: Request):
    s, eng = session(request), engine(request)
    eng.rates.check("control:"+s.id, 90)
    s.tick()
    if command.action == "focus":
        if not command.chapter:
            raise HTTPException(422, "chapter_required")
        at = next(c["at"] for c in CHAPTERS if c["id"] == command.chapter)
        if s.focus != command.chapter:
            s.invalidate()
        s.at, s.paused, s.focus = at, True, command.chapter
        snap = freeze(eng.events_for(s), at, seed=s.seed)
        s.snapshots[snap.id] = snap
    elif command.action == "focus_moment":
        moment = s.moments.get(command.moment_id)
        if not moment or moment["at"] > s.at:
            raise HTTPException(409, "moment_not_yet_detected")
        s.invalidate()
        s.at, s.paused, s.focus = moment["at"], True, moment["id"]
    elif command.action == "exit_focus":
        s.invalidate()
        s.focus, s.paused = None, s.at == 720
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
        s.focus, s.at, s.paused = None, 0, True
        s.moments.clear()
        s.snapshots.clear()
        s.observed_at = -1
    elif command.action == "set_team":
        if command.team not in ("H", "N"):
            raise HTTPException(422, "invalid_team")
        s.focus_team = command.team
    elif command.action == "play":
        if s.focus:
            raise HTTPException(409, "exit_focus_before_play")
        s.paused = s.at == 720
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
    snap = session(request).snapshots.get(snapshot_id)
    if not snap:
        raise HTTPException(404, "snapshot_not_in_session")
    return {"snapshot_id": snap.id, **snap.data}


@app.get("/api/stream")
async def stream(request: Request):
    s, eng = session(request), engine(request)
    eng.rates.check("stream:"+s.id, 20)
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


@app.post("/api/challenge")
async def challenge(body: ChallengeRequest, request: Request):
    s, eng = session(request), engine(request)
    eng.rates.check("challenge:" + s.id, 60)
    snap = s.snapshots.get(body.snapshot_id)
    if not snap:
        snap = eng.saved_snapshots.get(body.snapshot_id)
    if not snap:
        snap = freeze(eng.events_for(s), s.at, seed=s.seed)
        s.snapshots[snap.id] = snap

    result = resolve_challenge(snap, body)
    rev_entry = {
        "revision_id": f"rev-{len(s.revisions) + 1:03d}",
        "at": snap.data["as_of"],
        "claim_id": body.claim_id,
        "challenge_type": body.challenge_type,
        "outcome": result.outcome,
        "summary": result.resolution_summary,
        "counterevidence_checked": result.counterevidence_checked,
        "timestamp": time.time(),
    }
    s.revisions.append(rev_entry)
    s.revision += 1
    return {
        "result": result.model_dump(),
        "revisions": s.revisions,
        "state": eng.view(s),
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
        snap = freeze(eng.events_for(s), s.at, seed=s.seed)
        s.snapshots[snap.id] = snap
    team = body.team or s.focus_team
    ans = ask_the_match(snap, body.intent_id, team=team)
    return ans


@app.get("/api/matches")
async def list_matches(request: Request):
    from .catalog import MatchCatalog
    return {"matches": [m.model_dump() for m in MatchCatalog.list_matches()]}


@app.get("/api/matches/{match_id}")
async def get_match_detail(match_id: str, request: Request):
    from .catalog import MatchCatalog
    meta = MatchCatalog.get_match(match_id)
    if not meta:
        raise HTTPException(404, "match_not_found")
    return {"match": meta.model_dump()}


@app.get("/api/matches/{match_id}/events")
async def get_match_events(match_id: str, request: Request):
    from .catalog import MatchCatalog
    try:
        events = MatchCatalog.load_normalized_events(match_id)
    except FileNotFoundError:
        raise HTTPException(404, "match_not_found")
    return {
        "match_id": match_id,
        "count": len(events),
        "events": [e.model_dump() for e in events],
    }


@app.get("/api/models/xt")
async def get_xt_model_info(resolution: str = "16x12"):
    from .models.xt import ExpectedThreatModel
    if resolution not in ("16x12", "12x8"):
        raise HTTPException(400, "invalid_resolution")
    model = ExpectedThreatModel.load_default(resolution)
    return model.metadata


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def missing_api(path: str):
    raise HTTPException(404, "api_not_found")


web = ROOT / "apps" / "web" / "out"
if web.exists():
    app.mount("/", StaticFiles(directory=web, html=True), name="web")
else:
    @app.get("/")
    async def build_notice():
        return {"message": "Build apps/web first, then restart FastAPI. See README.md", "api": "/api/health"}
