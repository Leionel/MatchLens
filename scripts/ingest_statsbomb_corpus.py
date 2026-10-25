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
import os
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


def _rel(path: Path) -> str:
    """Repository-relative POSIX path, stable across operating systems."""
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


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
            "dataset_path": _rel(dataset_path),
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
        "source_file": _rel(events_path),
        "source_sha256": _sha256(events_path),
        "lineups_file": _rel(lineups_path) if lineups_path.exists() else None,
        "lineups_sha256": _sha256(lineups_path) if lineups_path.exists() else None,
        "target_file": _rel(dataset_path),
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
        "dataset_path": _rel(dataset_path),
        "dataset_sha256": receipt["target_sha256"],
        "metadata": metadata,
        "receipt": receipt,
    }


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _manifest_entry(row: dict[str, Any], entry: dict[str, Any], corpus: dict[str, Any]) -> dict[str, Any]:
    return {
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
    }


def merge_manifest_entries(
    existing: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    corpus: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Merge freshly imported rows into the full manifest by match id.

    ``--match`` imports a subset; every other committed entry must survive.
    Sorting by id keeps repeated imports byte-stable.
    """
    merged = {str(match_id): dict(entry) for match_id, entry in existing.items()}
    by_id = {str(entry["match_id"]): entry for entry in entries}
    for row in results:
        entry = by_id.get(str(row["match_id"]))
        if entry is None:
            continue
        merged[str(row["match_id"])] = _manifest_entry(row, entry, corpus)
    return {match_id: merged[match_id] for match_id in sorted(merged)}


def _verify_manifest(*, require_all: bool = False) -> int:
    if not MANIFEST_PATH.exists():
        print(f"manifest not found: {MANIFEST_PATH}", file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
    missing: list[str] = []
    verified = 0
    for entry in manifest.get("matches", []):
        match_id = str(entry.get("match_id", "?"))
        rel = str(entry.get("dataset_path") or "")
        if not rel:
            failures.append(f"{match_id}: dataset_path missing")
            continue
        if "\\" in rel:
            failures.append(f"{match_id}: dataset_path uses a Windows separator: {rel!r}")
            continue
        parts = rel.split("/")
        if rel.startswith("/") or ".." in parts or (parts and ":" in parts[0]):
            failures.append(f"{match_id}: dataset_path escapes the repository: {rel!r}")
            continue
        path = ROOT / Path(*parts)
        if not path.exists():
            if require_all:
                failures.append(f"{match_id}: dataset not materialised: {rel}")
            else:
                missing.append(match_id)
            continue
        actual = _sha256(path)
        expected = entry.get("dataset_sha256")
        if not expected or actual != expected:
            failures.append(f"{match_id}: checksum mismatch expected={str(expected)[:16]} actual={actual[:16]}")
            continue
        metadata = entry.get("metadata") or {}
        if not metadata.get("home_provider_team_id") or not metadata.get("away_provider_team_id"):
            failures.append(f"{match_id}: provider team mapping incomplete")
        if not (entry.get("completeness") or {}).get("status"):
            failures.append(f"{match_id}: completeness report missing")
        verified += 1
    if failures:
        for row in failures:
            print(f"  FAILED {row}", file=sys.stderr)
        print(f"\n{len(failures)} manifest failure(s)", file=sys.stderr)
        return 1
    print(
        f"manifest verified: {verified} materialised matches have valid content hashes; "
        f"{len(missing)} catalogued match(es) are not installed in this checkout"
    )
    if missing and not require_all:
        print(f"  not installed: {', '.join(missing[:5])}" + (" ..." if len(missing) > 5 else ""))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--match", action="append", help="limit to specific match ids")
    parser.add_argument("--raw-dir", default=str(RAW_DIR))
    parser.add_argument("--dataset-dir", default=str(DATASET_DIR))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="verify installed datasets against the committed manifest without importing",
    )
    parser.add_argument(
        "--verify-all",
        action="store_true",
        help="like --verify, but fail if any catalogued match is not installed",
    )
    args = parser.parse_args()

    if args.verify or args.verify_all:
        return _verify_manifest(require_all=args.verify_all)

    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    entries = list(corpus["matches"])
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

    if failures and not results:
        print("every requested import failed; manifest was not modified", file=sys.stderr)
        return 1

    existing: dict[str, Any] = {}
    existing_generated_at = None
    previous_body: dict[str, Any] | None = None
    if MANIFEST_PATH.exists():
        try:
            previous = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            existing_generated_at = previous.get("generated_at")
            existing = {
                str(e.get("match_id")): e
                for e in previous.get("matches", [])
                if isinstance(e, dict) and e.get("match_id")
            }
            previous_body = {k: v for k, v in previous.items() if k != "generated_at"}
        except (OSError, ValueError) as exc:
            # A corrupt manifest must not be "repaired" by dropping every entry
            # that this invocation did not happen to import.
            print(f"manifest is unreadable; refusing to overwrite it: {exc}", file=sys.stderr)
            return 1

    merged = merge_manifest_entries(existing, results, entries, corpus)

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
        "matches": list(merged.values()),
    }
    new_body = {k: v for k, v in manifest.items() if k != "generated_at"}
    if previous_body == new_body and existing_generated_at:
        # A repeated import of unchanged content must not churn the manifest.
        manifest["generated_at"] = existing_generated_at
    _atomic_write(MANIFEST_PATH, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

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
        print(
            f"\n{len(failures)} match(es) failed; existing manifest entries were preserved",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
