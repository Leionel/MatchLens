"""Exercise the actual HTTP product; preserve real evidence without credentials."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--out", type=Path, default=Path("evidence/r0.1/live-http.json"))
    parser.add_argument("--chapters", default="A,B,C")
    args = parser.parse_args()
    report = {"origin": "live_http_product", "cases": []}
    with httpx.Client(base_url=args.base, trust_env=False, timeout=35) as client:
        health = client.get("/api/health").json()
        if not health["model_configured"]:
            raise SystemExit("Model is not configured; no live claim recorded.")
        client.post("/api/sessions").raise_for_status()
        for chapter in args.chapters.split(","):
            focus = client.post("/api/control", json={"action": "focus", "chapter": chapter})
            focus.raise_for_status()
            snap_id = focus.json()["snapshot_id"]
            started = time.perf_counter()
            client.post("/api/analyse", json={}).raise_for_status()
            while time.perf_counter()-started < 35:
                state = client.get("/api/state").json()
                if state["result"] is not None:
                    break
                time.sleep(.25)
            result = state["result"]
            evidence = client.get("/api/evidence/"+snap_id).json()
            item = {"chapter": chapter, "wall_ms": round((time.perf_counter()-started)*1000), "result": result, "evidence": evidence}
            report["cases"].append(item)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"chapter": chapter, "status": result["status"] if result else "poll_timeout",
                              "accepted": len(result["accepted"]) if result else 0,
                              "duration_ms": result.get("duration_ms") if result else None,
                              "requests": result.get("requests") if result else None}), flush=True)
    if not all(c["result"] and c["result"]["status"] == "completed" and c["result"]["accepted"] for c in report["cases"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
