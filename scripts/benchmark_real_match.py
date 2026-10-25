"""Real-match performance gate.

The old per-sample OAAI fold rescanned every causal event at every two-second
sample (about 15s for the 4,691-event reference match). This script measures the
current cold/warm paths on a materialised match and refuses a regression.

Thresholds are deliberately generous for shared CI runners while still far
below the pre-optimisation baseline.
"""
from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from matchlens.catalog import MatchCatalog  # noqa: E402
from matchlens.main import Engine, freeze_match_snapshot  # noqa: E402
from matchlens.matchdetail import build_match_detail  # noqa: E402

MATCH_ID = "sb_3795221"
THRESHOLDS_MS = {
    "snapshot_cold": 8000,
    "snapshot_warm": 2000,
    "seek_cold": 8000,
    "seek_warm": 1000,
    "oaai_cold": 5000,
    "oaai_warm": 1000,
    "detail": 8000,
}


def _timed(fn, repeats: int = 1) -> tuple[float, object]:
    values = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = fn()
        values.append((time.perf_counter() - started) * 1000)
    return round(statistics.median(values), 1), result


def main() -> int:
    meta = MatchCatalog.get_match(MATCH_ID)
    if meta is None or not meta.analysis_ready:
        print(f"{MATCH_ID} is not materialised; run the one-match import first", file=sys.stderr)
        return 2

    engine = Engine(Path(tempfile.mkdtemp()), None)
    ctx = engine.match_context(MATCH_ID)
    full_clock = int(ctx.replayable_end) + 1

    measurements: dict[str, float] = {}
    measurements["snapshot_cold"], (snap, state) = _timed(
        lambda: freeze_match_snapshot(engine, MATCH_ID, 7200)
    )
    measurements["snapshot_warm"], _ = _timed(
        lambda: freeze_match_snapshot(engine, MATCH_ID, 7200), repeats=3
    )
    measurements["seek_cold"], _ = _timed(
        lambda: freeze_match_snapshot(engine, MATCH_ID, 3600)
    )
    measurements["seek_warm"], _ = _timed(
        lambda: freeze_match_snapshot(engine, MATCH_ID, 3600), repeats=3
    )
    measurements["oaai_cold"], oaai = _timed(
        lambda: engine.oaai_for(
            MATCH_ID,
            state["events"],
            7200,
            dead_intervals=state["dead_intervals"],
            xt_model=engine.xt_model,
        )
    )
    measurements["oaai_warm"], _ = _timed(
        lambda: engine.oaai_for(
            MATCH_ID,
            state["events"],
            7200,
            dead_intervals=state["dead_intervals"],
            xt_model=engine.xt_model,
        ),
        repeats=3,
    )
    measurements["detail"], detail = _timed(
        lambda: build_match_detail(
            engine,
            MATCH_ID,
            lambda eng, match_id, context: eng.frozen(match_id, int(context.replayable_end) + 1),
        )
    )

    full, _ = freeze_match_snapshot(engine, MATCH_ID, full_clock)
    numeric = {
        "snapshot_events_at_nominal": len(snap.data["events"]),
        "snapshot_events_at_replayable_end": len(full.data["events"]),
        "total_events": len(state["events"]),
        "score": full.data["score"],
        "official_score": full.data["official_score"],
        "oaai_timeline_points": len(oaai.get("timeline", [])),
        "oaai_change_points": len(oaai.get("change_points", [])),
        "detail_shots": detail["shots"]["count"],
        "cache": engine.cache_stats,
    }
    failures = [
        f"{name}={value}ms > {THRESHOLDS_MS[name]}ms"
        for name, value in measurements.items()
        if value > THRESHOLDS_MS[name]
    ]
    if len(full.data["events"]) != 4691 or len(snap.data["events"]) >= len(full.data["events"]):
        failures.append("replayable clock no longer exposes the stoppage events")
    if full.data["score"] != {"H": 2, "N": 1}:
        failures.append(f"score regression: {full.data['score']}")
    if len(oaai.get("timeline", [])) < 3500:
        failures.append("OAAI timeline was downsampled or truncated")

    print(json.dumps({"measurements_ms": measurements, "numeric": numeric}, indent=2))
    if failures:
        for failure in failures:
            print(f"FAILED {failure}", file=sys.stderr)
        return 1
    print("performance gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
