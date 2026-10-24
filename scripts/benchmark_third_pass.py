"""Third-pass runtime benchmark on real and synthetic-scale event streams.

Usage: services/api/.venv/Scripts/python.exe scripts/benchmark_third_pass.py

The 12-event fixture is real StatsBomb sample data. Larger streams are a
volume stress generator built by replicating synthetic events at the same
match clock; they measure reducer/metric complexity, not football realism.
"""
from __future__ import annotations

import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from matchlens.catalog import MatchCatalog  # noqa: E402
from matchlens.evidence import build_evidence_graph  # noqa: E402
from matchlens.football import (  # noqa: E402
    build_player_spotlight,
    build_sequences,
    build_tactical_explorer,
    freeze,
    generate_match,
    metric_receipts,
    reduce_match,
)
from matchlens.oaai import compute_oaai  # noqa: E402
from matchlens.registry import ClaimRegistry  # noqa: E402


def scaled_events(scale: int) -> list[dict]:
    base = reduce_match(generate_match(), 720)["events"]
    out: list[dict] = []
    for rep in range(scale):
        for event in base:
            clone = dict(event)
            clone["id"] = f"{event['id']}-r{rep:02d}"
            clone["seq"] = len(out) + 1
            clone["t"] = round(float(event["t"]) + rep * 0.001, 3)
            clone["possession_id"] = int(event["possession_id"]) + rep * 1000
            out.append(clone)
    out.sort(key=lambda e: (e["t"], e["id"]))
    return out


def timed(fn, repeats: int = 3) -> tuple[dict, object]:
    samples = []
    result = None
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn()
        samples.append((time.perf_counter() - start) * 1000)
    return {
        "median_ms": round(statistics.median(samples), 2),
        "min_ms": round(min(samples), 2),
        "max_ms": round(max(samples), 2),
        "samples": len(samples),
    }, result


def measure_stream(name: str, events: list[dict], *, real: bool) -> dict:
    state_holder = {}

    def reduce_once():
        state = reduce_match(
            events,
            at=720,
            max_duration=720,
            is_synthetic=False,
            coordinate_frame="fixed",
            continuous_coverage=True,
        )
        state_holder["state"] = state
        return state

    reduce_timing, _ = timed(reduce_once)
    state = state_holder["state"]
    rows = {
        "stream": name,
        "real_data": real,
        "event_count": len(events),
        "reduce": reduce_timing,
        "sequences": timed(lambda: build_sequences(state))[0],
        "tactical_explorer": timed(lambda: build_tactical_explorer(state, "H"))[0],
        "player_spotlight": timed(lambda: build_player_spotlight(state))[0],
        "metric_receipts": timed(lambda: metric_receipts(state))[0],
        "oaai_720s": timed(lambda: compute_oaai(state["events"], smoothing_mode="causal"))[0],
    }
    return rows


def main() -> int:
    bench = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "notes": [
            "12-event stream is the bundled StatsBomb sample (real data, partial coverage).",
            "Scaled streams replicate synthetic events at identical timestamps (volume stress, not football realism).",
            "Medians over three runs; no warm-up exclusions.",
        ],
        "streams": [],
    }

    sample = MatchCatalog.load_normalized_events("sb_wc2022_final")
    sample_dicts = [
        {
            "id": e.event_id,
            "t": e.clock_seconds,
            "kind": e.action_type.value.lower(),
            "team": e.team_id,
            "actor": e.player_name or "unknown",
            "actor_name": e.player_name,
            "start": [e.x, e.y] if e.x is not None and e.y is not None else None,
            "end": [e.end_x, e.end_y] if e.end_x is not None and e.end_y is not None else None,
            "outcome": e.outcome or "complete",
            "located": e.x is not None and e.y is not None,
            "coordinate_frame": "team_relative",
            "possession_id": e.possession_id,
        }
        for e in sample
    ]
    bench["streams"].append(measure_stream("sb_wc2022_sample_12", sample_dicts, real=True))

    for scale in (1, 8, 28):
        events = scaled_events(scale)
        bench["streams"].append(measure_stream(f"synthetic_volume_x{scale}", events, real=False))

    # Evidence graph + snapshot on the largest volume stream.
    events = scaled_events(28)
    tracemalloc.start()
    snap_timing, snap = timed(lambda: freeze(
        events,
        720,
        match_id="bench_volume",
        scenario="historical",
        format_seconds=720,
        coordinate_frame="fixed",
        continuous_coverage=True,
    ), repeats=1)
    registry = ClaimRegistry()
    registry.verify_and_register(snap, "bench_volume", "goal_sequence", "H")
    graph_timing, graph = timed(lambda: build_evidence_graph(
        match_id="bench_volume",
        match_context=MatchContextStub(),
        snapshot=snap,
        registry=registry,
    ), repeats=1)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    bench["largest_stream_snapshot"] = {
        "event_count": len(events),
        "snapshot_bytes": len(snap.canonical.encode("utf-8")),
        "freeze": snap_timing,
        "evidence_graph": graph_timing,
        "graph_nodes": graph["nodes_count"],
        "graph_edges": graph["edges_count"],
        "peak_memory_mb": round(peak / 1024 / 1024, 2),
    }

    print(json.dumps(bench, indent=2))
    out = ROOT / "evidence" / "third_pass" / "runtime_benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bench, indent=2), encoding="utf-8")
    return 0


class MatchContextStub:
    home_team_name = "Harbor FC"
    away_team_name = "Northbridge United"
    provider = "synthetic_volume"
    data_coverage = "C0"
    mode = "synthetic_replay"
    data_version = "bench"
    official_home_score = 1
    official_away_score = 0


if __name__ == "__main__":
    raise SystemExit(main())
