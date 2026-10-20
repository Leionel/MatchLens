"""Durable, conservative request reservation before network dispatch."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

REQUEST_RESERVATION_USD = 0.02
MAX_BODY_BYTES = 48_000
MAX_OUTPUT_TOKENS = 1024


class BudgetExceeded(RuntimeError):
    pass


class BudgetLedger:
    def __init__(self, path: Path, max_requests: int = 32, max_usd: float = 1.0):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self.max_requests, self.max_usd = max_requests, max_usd
        self.db.execute("CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY, run_id TEXT, role TEXT, at REAL, reserved REAL, status INTEGER, usage TEXT)")
        self.db.commit()

    def reserve(self, run_id: str, role: str) -> int:
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                n, dollars = self.db.execute("SELECT count(*), coalesce(sum(reserved),0) FROM requests").fetchone()
                if n >= self.max_requests or dollars+REQUEST_RESERVATION_USD > self.max_usd+1e-9:
                    raise BudgetExceeded("global_inference_budget_exhausted")
                cursor = self.db.execute("INSERT INTO requests(run_id,role,at,reserved) VALUES(?,?,?,?)", (run_id, role, time.time(), REQUEST_RESERVATION_USD))
                self.db.commit()
                return cursor.lastrowid
            except BaseException:
                self.db.rollback()
                raise

    def complete(self, request_id: int, status: int, usage: dict | None) -> None:
        with self.lock:
            self.db.execute("UPDATE requests SET status=?,usage=? WHERE id=?", (status, json.dumps(usage), request_id))
            self.db.commit()

    def has_runway(self, requests: int = 6) -> bool:
        with self.lock:
            count, reserved = self.db.execute("SELECT count(*),coalesce(sum(reserved),0) FROM requests").fetchone()
            return count + requests <= self.max_requests and reserved + requests * REQUEST_RESERVATION_USD <= self.max_usd + 1e-9

    def summary(self) -> dict:
        with self.lock:
            n, reserved = self.db.execute("SELECT count(*),coalesce(sum(reserved),0) FROM requests").fetchone()
            rows = self.db.execute("SELECT usage FROM requests WHERE usage IS NOT NULL").fetchall()
        total = {"prompt_tokens": 0, "completion_tokens": 0, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0}
        for row in rows:
            usage = json.loads(row[0]) or {}
            for key in total:
                total[key] += usage.get(key, 0)
        # Published peak Flash rates, checked 2026-10-19 PT; invoice may differ.
        estimate = (total["prompt_cache_miss_tokens"]*.30+total["prompt_cache_hit_tokens"]*.006+total["completion_tokens"]*1.20)/1_000_000
        return {"requests_reserved": n, "reserved_usd": round(reserved, 4), "max_requests": self.max_requests,
                "max_reserved_usd": self.max_usd, "usage": total, "known_usage_estimate_usd": round(estimate, 8)}

    def close(self) -> None:
        self.db.close()
