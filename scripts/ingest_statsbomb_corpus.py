"""Materialise the curated StatsBomb corpus into ignored datasets + a manifest.

The provider agreement forbids redistributing the payloads, so this script
writes every imported match into ``data/datasets/`` (ignored by git) and emits
``data/source_manifest.json`` with the metadata, provenance and completeness
report that the catalog needs.

Usage:
  python scripts/ingest_statsbomb_corpus.py            # import every corpus match
  python scripts/ingest_statsbomb_corpus.py --match sb_8658
  python scripts/ingest_statsbomb_corpus.py --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from matchlens.adapters.statsbomb import StatsBombAdapter  # noqa: E402
from matchlens.completeness import (  # noqa: E402
    NOMINAL_PERIOD_SECONDS,
    expected_match_periods,
    nominal_match_seconds,
    verify_dataset_completeness,
)
from matchlens.provider_terms import (  # noqa: E402
    STATSBOMB_ATTRIBUTION_TEXT,
    STATSBOMB_LICENSE_REF,
    STATSBOMB_REDISTRIBUTION_RULES,
)
from matchlens.schema import DataCoverageLevel  # noqa: E402

CORPUS_PATH = ROOT / "data" / "corpus_statsbomb.json"
RAW_DIR = ROOT / "data" / "raw" / "statsbomb"
DATASET_DIR = ROOT / "data" / "datasets"
MANIFEST_PATH = ROOT / "data" / "source_manifest.json"
RECEIPT_DIR = ROOT / "evidence" / "imports"

# A regulation match is two 45-minute halves; the nominal duration of a match
# that went to extra time is longer. The expected duration is therefore derived
# from the periods the provider actually recorded.
NOMINAL_REGULATION_SECONDS = NOMINAL_PERIOD_SECONDS[1] + NOMINAL_PERIOD_SECONDS[2]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raw_path(raw_dir: Path, provider_match_id: int, kind: str) -> Path:
    return raw_dir / f"{kind}_{provider_match_id}.json"


def _score_reconciliation(events: list[Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Compare the provider index score with the goals recorded in the payload.

    The index score is the provider's own declaration; the event stream is the
    only evidence of what was actually recorded. The two are reported side by
    side instead of being merged, because a mismatch in the provider payload
    must not be presented as a verified score.
    """
    home_id = str(entry["home_provider_team_id"])
    away_id = str(entry["away_provider_team_id"])
    goals = {"home": 0, "away": 0}
    shootout_goals = {"home": 0, "away": 0}
    counted_own_goals: set[tuple[int, float]] = set()
    for event in events:
        outcome = str(event.outcome or "").lower()
        if outcome not in ("goal", "own_goal", "own_goal_for"):
            continue
        side = "home" if event.team_id == home_id else ("away" if event.team_id == away_id else None)
        if side is None:
            continue
        if outcome == "own_goal":
            side = "away" if side == "home" else "home"
        if outcome.startswith("own_goal"):
            # The provider records one own goal twice, once for each side.
            key = (int(event.period), round(float(event.clock_seconds), 3))
            if key in counted_own_goals:
                continue
            counted_own_goals.add(key)
        if int(event.period) >= 5:
            shootout_goals[side] += 1
        else:
            goals[side] += 1

    provider_home = int(entry["home_score"])
    provider_away = int(entry["away_score"])
    consistent = goals["home"] == provider_home and goals["away"] == provider_away
    return {
        "provider_score": f"{provider_home}-{provider_away}",
        "recorded_goals": f"{goals['home']}-{goals['away']}",
        "provider_home_score": provider_home,
        "provider_away_score": provider_away,
        "recorded_home_goals": goals["home"],
        "recorded_away_goals": goals["away"],
        "shootout_goals": shootout_goals,
        "consistent": consistent,
        "note": (
            "Provider index score and event-recorded goals agree."
            if consistent
            else "Provider index score and event-recorded goals disagree; the event "
            "stream is reported as observed and the index score stays the provider's "
            "declaration."
        ),
    }


def import_match(entry: dict[str, Any], *, raw_dir: Path, dataset_dir: Path, dry_run: bool) -> dict[str, Any]:
    provider_match_id = int(entry["provider_match_id"])
    match_id = str(entry["match_id"])
    events_path = _raw_path(raw_dir, provider_match_id, "events")
    lineups_path = _raw_path(raw_dir, provider_match_id, "lineups")

    if not events_path.exists():
        raise FileNotFoundError(
            f"{events_path} is missing; run scripts/fetch_statsbomb_open_data.py --corpus first"
        )

    payload = json.loads(events_path.read_text(encoding="utf-8"))
    raw_events = payload.get("events") if isinstance(payload, dict) else payload
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError(f"{events_path} contains no events")

    adapter = StatsBombAdapter(match_id=match_id)
    events = adapter.load_events(raw_events)

    known = {str(entry["home_provider_team_id"]), str(entry["away_provider_team_id"])}
    unmapped = sorted({e.team_id for e in events if e.team_id not in known})
    if unmapped:
        raise ValueError(f"{match_id}: unmapped provider teams {unmapped}")

    observed_end = max((e.clock_seconds for e in events), default=0.0)
    expected_periods = expected_match_periods(events)
    expected_duration = nominal_match_seconds(expected_periods)
    report = verify_dataset_completeness(
        events,
        raw_event_count=len(raw_events),
        expected_duration=expected_duration,
        source_declaration="statsbomb_open_data",
        declared_complete=True,
        conversion_drop_count=max(0, len(raw_events) - len(events)),
        drop_reasons=(["adapter_dropped_or_unsupported_events"] if len(raw_events) > len(events) else []),
        team_ids=sorted(known),
        expected_periods=expected_periods,
    )

    coverage = (
        DataCoverageLevel.C1_OPEN_EVENTS
        if report.status in ("COMPLETE_VERIFIED", "COMPLETE_CLAIMED_UNVERIFIED")
        else DataCoverageLevel.C1_PARTIAL
    )
    reconciliation = _score_reconciliation(events, entry)

    dataset_path = dataset_dir / f"{match_id}.json"
    metadata = {
        "match_id": match_id,
        "label": entry["label"],
        "competition": entry["competition"],
        "season": entry["season"],
        "match_date": entry["match_date"],
        "home_team": entry["home_team"],
        "away_team": entry["away_team"],
        "home_score": entry["home_score"],
        "away_score": entry["away_score"],
        "coverage_level": coverage.value,
        "data_provider": "statsbomb_open_data",
        "provenance_kind": "provider_payload",
        "provider_match_id": str(provider_match_id),
        "description": (
            f"StatsBomb Open Data: {len(raw_events)} provider events across "
            f"{len({e.period for e in events})} periods, observed through {observed_end:.0f}s "
            f"of a nominal {expected_duration:.0f}s match."
        ),
        "license_ref": STATSBOMB_LICENSE_REF,
        "attribution_text": STATSBOMB_ATTRIBUTION_TEXT,
        "events_count": len(raw_events),
        "format_seconds": expected_duration,
        "home_provider_team_id": entry["home_provider_team_id"],
        "away_provider_team_id": entry["away_provider_team_id"],
        "continuous_coverage": report.status == "COMPLETE_VERIFIED",
        "source_declared_complete": True,
        "completeness_status": report.status,
        "capabilities": ["schema_compatibility", "event_stream", "spatial_drilldown"],
        "official_score_note": (
            "Score read from the provider match index; penalties excluded from the "
            "regulation score."
        ),
        "score_reconciliation": reconciliation,
    }

    if dry_run:
        return {
            "match_id": match_id,
            "status": report.status,
            "events": len(events),
            "observed_end": round(observed_end, 1),
            "reordered_events": len(adapter.reordered_events),
            "dataset_path": str(dataset_path.relative_to(ROOT)),
            "score_reconciliation": reconciliation,
        }

    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text(
        json.dumps({"metadata": metadata, "events": raw_events}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    receipt = {
        "version": "statsbomb-corpus-import-v2",
        "imported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "match_id": match_id,
        "provider": "statsbomb_open_data",
        "provider_match_id": provider_match_id,
        "competition": entry["competition"],
        "season": entry["season"],
        "stage": entry.get("stage"),
        "match_date": entry["match_date"],
        "home_team": entry["home_team"],
        "away_team": entry["away_team"],
        "home_score": entry["home_score"],
        "away_score": entry["away_score"],
        "home_provider_team_id": entry["home_provider_team_id"],
        "away_provider_team_id": entry["away_provider_team_id"],
        "source_file": str(events_path.relative_to(ROOT)),
        "source_sha256": _sha256(events_path),
        "lineups_file": str(lineups_path.relative_to(ROOT)) if lineups_path.exists() else None,
        "lineups_sha256": _sha256(lineups_path) if lineups_path.exists() else None,
        "target_file": str(dataset_path.relative_to(ROOT)),
        "target_sha256": _sha256(dataset_path),
        "raw_event_count": len(raw_events),
        "normalized_event_count": len(events),
        "observed_end_seconds": round(observed_end, 3),
        "expected_duration_seconds": expected_duration,
        "reordered_events": adapter.reordered_events,
        "completeness_status": report.status,
        "completeness": report.model_dump(),
        "coverage_level": coverage.value,
        "score_reconciliation": reconciliation,
        "license_ref": STATSBOMB_LICENSE_REF,
        "attribution_text": STATSBOMB_ATTRIBUTION_TEXT,
    }
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    (RECEIPT_DIR / f"{match_id}.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return {
        "match_id": match_id,
        "status": report.status,
        "events": len(events),
        "raw_events": len(raw_events),
        "observed_end": round(observed_end, 1),
        "reordered_events": len(adapter.reordered_events),
        "dataset_path": str(dataset_path.relative_to(ROOT)),
        "dataset_sha256": receipt["target_sha256"],
        "metadata": metadata,
        "receipt": receipt,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--match", action="append", help="limit to specific match ids")
    parser.add_argument("--raw-dir", default=str(RAW_DIR))
    parser.add_argument("--dataset-dir", default=str(DATASET_DIR))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    entries = corpus["matches"]
    if args.match:
        wanted = set(args.match)
        entries = [e for e in entries if e["match_id"] in wanted]
        if not entries:
            parser.error(f"no corpus match matches {sorted(wanted)}")

    raw_dir = Path(args.raw_dir).resolve()
    dataset_dir = Path(args.dataset_dir).resolve()

    results = []
    failures = []
    for entry in entries:
        try:
            results.append(import_match(entry, raw_dir=raw_dir, dataset_dir=dataset_dir, dry_run=args.dry_run))
        except Exception as exc:
            failures.append({"match_id": entry["match_id"], "error": f"{type(exc).__name__}: {exc}"})
            print(f"  FAILED {entry['match_id']}: {type(exc).__name__}: {exc}", file=sys.stderr)

    if args.dry_run:
        for row in results:
            recon = row["score_reconciliation"]
            mark = "ok" if recon["consistent"] else "SCORE-MISMATCH"
            print(
                f"  {row['match_id']:>12}  {row['status']:<24} events={row['events']:>5} "
                f"end={row['observed_end']}s index={recon['provider_score']} "
                f"recorded={recon['recorded_goals']} {mark}"
            )
        print(f"\n{len(results)} ok, {len(failures)} failed")
        return 1 if failures else 0

    manifest = {
        "version": "matchlens-source-manifest-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider": {
            "name": "statsbomb_open_data",
            "repository": corpus["provider"]["repository"],
            "base_url": corpus["provider"]["base_url"],
        },
        "license_ref": STATSBOMB_LICENSE_REF,
        "attribution_text": STATSBOMB_ATTRIBUTION_TEXT,
        "redistribution_rules": list(STATSBOMB_REDISTRIBUTION_RULES),
        "payload_policy": (
            "Provider payloads are excluded from version control. Each entry below records "
            "metadata and provenance only; run scripts/ingest_statsbomb_corpus.py to "
            "materialise the dataset files under data/datasets/."
        ),
        "matches": [],
    }
    for row in results:
        entry = next(e for e in entries if e["match_id"] == row["match_id"])
        manifest["matches"].append({
            "match_id": row["match_id"],
            "dataset_path": row["dataset_path"],
            "dataset_sha256": row["dataset_sha256"],
            "stage": entry.get("stage"),
            # The completeness report lives here once. The catalog reads it back
            # into the match metadata, so the committed file never carries two
            # copies that could drift apart.
            "completeness": row["receipt"]["completeness"],
            "source": {
                "provider": "statsbomb_open_data",
                "competition_id": entry["competition_id"],
                "season_id": entry["season_id"],
                "match_id": entry["provider_match_id"],
                "events_url": f"{corpus['provider']['base_url']}/events/{entry['provider_match_id']}.json",
                "lineups_url": f"{corpus['provider']['base_url']}/lineups/{entry['provider_match_id']}.json",
                "source_sha256": row["receipt"]["source_sha256"],
            },
            "metadata": row["metadata"],
        })
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"manifest: {MANIFEST_PATH} ({len(manifest['matches'])} matches)")
    for row in results:
        recon = row["metadata"]["score_reconciliation"]
        mark = "ok" if recon["consistent"] else "SCORE-MISMATCH"
        print(
            f"  {row['match_id']:>12}  {row['status']:<24} events={row['events']:>5} "
            f"end={row['observed_end']}s index={recon['provider_score']} "
            f"recorded={recon['recorded_goals']} {mark}"
        )
    if failures:
        print(f"\n{len(failures)} match(es) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
