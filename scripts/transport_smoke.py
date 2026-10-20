"""Local HTTP/SSE/replay smoke. No inference requests are made."""
import json
import time
from pathlib import Path

import httpx


def main():
    timings, replay = [], []
    with httpx.Client(base_url="http://127.0.0.1:8000", trust_env=False, timeout=5) as client:
        client.post("/api/sessions", json={}).raise_for_status()
        for i in range(30):
            start = time.perf_counter()
            response = client.post("/api/control", json={"action": "focus", "chapter": "A" if i % 2 == 0 else "B"})
            response.raise_for_status()
            timings.append((time.perf_counter()-start)*1000)
        for speed in (1, 6, 30):
            client.post("/api/control", json={"action": "restart"}).raise_for_status()
            client.post("/api/control", json={"action": "speed", "speed": speed}).raise_for_status()
            client.post("/api/control", json={"action": "play"}).raise_for_status()
            start = time.perf_counter()
            time.sleep(1.05)
            state = client.get("/api/state").json()
            elapsed = time.perf_counter()-start
            assert abs(state["at"]-int(elapsed*speed)) <= 1
            replay.append({"speed": speed, "elapsed_seconds": round(elapsed, 3), "match_seconds": state["at"]})
        focus = client.post("/api/control", json={"action": "focus", "chapter": "C"}).json()
        assert focus["at"] == 720 and focus["score"] == {"H": 1, "N": 0}
        received = []
        for _ in range(2):
            with client.stream("GET", "/api/stream") as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        state = json.loads(line[6:])
                        received.append({"epoch": state["epoch"], "revision": state["revision"], "at": state["at"]})
                        break
        assert received[0] == received[1]
        report = {"scope": "localhost HTTP, not public ingress or browser paint", "model_requests": 0,
                  "control_rtt_ms": {"n": len(timings), "median": round(sorted(timings)[14], 2), "p95_nearest_rank": round(sorted(timings)[28], 2), "all": [round(t, 2) for t in timings]},
                  "replay": replay, "sse_initial_and_reconnect": received, "final_score": focus["score"]}
        Path("evidence/r0.1/transport.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k:v for k,v in report.items() if k != "control_rtt_ms"}))
        print(json.dumps({k:v for k,v in report["control_rtt_ms"].items() if k != "all"}))


if __name__ == "__main__":
    main()
