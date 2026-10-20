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
from .football import CHAPTERS, PLAYERS, Snapshot, freeze, generate_match, metric_receipts, reduce_match

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
    speed: int = 6
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
    action: Literal["focus", "exit_focus", "play", "pause", "speed", "restart"]
    chapter: Literal["A", "B", "C"] | None = None
    speed: Literal[1, 6, 30] | None = None


class Engine:
    def __init__(self, runtime: Path, key: str | None):
        self.events = generate_match()
        self.sessions: dict[str, Session] = {}
        self.rates = RateLimits()
        self.ledger = BudgetLedger(runtime / "budget.sqlite3", int(os.getenv("MATCHLENS_MAX_REQUESTS", "32")), float(os.getenv("MATCHLENS_MAX_RESERVED_USD", "1")))
        self.runner = AgentRunner(key, self.ledger)
        self.slots = asyncio.Semaphore(2)
        self.runtime = runtime
        (runtime / "runs").mkdir(parents=True, exist_ok=True)

    def cleanup(self):
        for sid, s in list(self.sessions.items()):
            if time.monotonic()-s.touched > 1800:
                s.invalidate()
                del self.sessions[sid]

    def view(self, s: Session) -> dict:
        s.tick()
        state = reduce_match(self.events, s.at)
        snapshot = next((snap for snap in s.snapshots.values() if snap.data["as_of"] == s.at), None) if s.focus else None
        result = s.cache.get(snapshot.id) if snapshot else None
        if result:
            result = {**result, "reused": s.run_info is None or s.run_info.get("run_id") != result["run_id"]}
        accepted_history = [card for r in s.cache.values() if r["status"] == "completed" for card in r["accepted"]]
        return {"revision": s.revision, "epoch": s.epoch, "at": s.at, "paused": s.paused, "speed": s.speed,
                "focus": s.focus, "score": state["score"], "owner": state["owner"], "ball": state["ball"],
                "events": state["events"], "players": PLAYERS, "receipts": metric_receipts(state),
                "chapters": CHAPTERS, "snapshot_id": snapshot.id if snapshot else None,
                "analysis": s.run_info, "result": result, "history": accepted_history,
                "model_configured": bool(self.runner.key), "session_analyses_remaining": max(0, 8-s.analyses),
                "format_seconds": 720, "ended": state["ended"]}

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
            if epoch == s.epoch and s.focus:
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
        snap = freeze(eng.events, at)
        s.snapshots[snap.id] = snap
    elif command.action == "exit_focus":
        s.invalidate()
        s.focus, s.paused = None, s.at == 720
    elif command.action == "restart":
        s.invalidate()
        s.focus, s.at, s.paused = None, 0, True
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
    if not s.focus:
        raise HTTPException(409, "focus_moment_required")
    snap = next(v for v in s.snapshots.values() if v.data["as_of"] == s.at)
    cached = s.cache.get(snap.id)
    if s.task and not s.task.done() or cached and cached["status"] == "completed":
        return eng.view(s)
    eng.rates.check("analyse:"+s.id, 3)
    eng.rates.check("analyse-ip:"+s.ip, 6)
    eng.rates.check("analyse:global", 12)
    if s.analyses >= 8:
        raise HTTPException(429, "session_analysis_budget")
    s.analyses += 1
    run = Run("run-"+secrets.token_hex(8), snap)
    s.run_info = {"run_id": run.id, "status": "queued", "as_of": s.at, "epoch": s.epoch}
    s.revision += 1
    s.task = asyncio.create_task(eng.execute(s, snap, s.epoch, run))
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
