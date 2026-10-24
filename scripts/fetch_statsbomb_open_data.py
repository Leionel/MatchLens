"""Repeatable fetch of StatsBomb Open Data with a source manifest.

The raw provider payloads are large and are therefore NOT committed. This
script downloads them into an ignored directory and writes a manifest that
records, for every file, the upstream URL, its SHA-256, the retrieval time
and the licence/attribution terms that govern redistribution.

Usage:
  python scripts/fetch_statsbomb_open_data.py --preset wc2022_final
  python scripts/fetch_statsbomb_open_data.py --competition 43 --season 106 \
      --match-ids 3869685,3869519

Environment:
  HTTPS_PROXY / HTTP_PROXY  optional outbound proxy, e.g. http://127.0.0.1:9674
  MATCHLENS_SB_RAW_DIR      override the ignored raw directory
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = Path(os.environ.get("MATCHLENS_SB_RAW_DIR", ROOT / "data" / "raw" / "statsbomb"))

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
REPO_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master"

# Attribution and redistribution terms as published by the provider. The
# upstream LICENSE.pdf is a custom "StatsBomb Public Data User Agreement", not
# a Creative Commons licence: it forbids redistributing the data itself while
# permitting published analysis with attribution.
LICENSE_REF = (
    "StatsBomb Public Data User Agreement (Standard Terms, last updated 8 September 2023) "
    "- https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf"
)
ATTRIBUTION_TEXT = (
    "Data provided by StatsBomb. Publications of analysis derived from this data must state "
    "the data source as StatsBomb and display the StatsBomb logo from their Media Pack "
    "(https://statsbomb.com/media-pack/)."
)
REDISTRIBUTION_RULES = [
    "Clause 1.2.1 forbids editing, distorting, distributing, reproducing, selling or "
    "otherwise providing the data to any external or third party.",
    "Clause 7 reserves all rights in the data to StatsBomb and forbids modifying, "
    "translating, transferring, distributing, licensing or selling it.",
    "Clause 1.2.2 forbids commercial exploitation of the data or of derived analysis.",
    "Clause 1.4 requires any publication of analysis to credit StatsBomb and display the "
    "StatsBomb brand logo.",
    "This repository therefore stores only locally imported match payloads for research "
    "use and never republishes the upstream collection.",
]
CORPUS_PATH = ROOT / "data" / "corpus_statsbomb.json"

# Presets are complete historical matches with period 1-2 coverage.
PRESETS: dict[str, dict[str, Any]] = {
    "wc2022_final": {
        "competition_id": 43,
        "season_id": 106,
        "match_ids": [3869685],
        "label": "FIFA World Cup 2022 Final - Argentina vs France",
    },
    "wc2022_semifinal": {
        "competition_id": 43,
        "season_id": 106,
        "match_ids": [3869519],
        "label": "FIFA World Cup 2022 Semi-Final - Argentina vs Croatia",
    },
    "wc2022_quarterfinal": {
        "competition_id": 43,
        "season_id": 106,
        "match_ids": [3869354],
        "label": "FIFA World Cup 2022 Quarter-Final - England vs France",
    },
}


def _proxy_opener() -> urllib.request.OpenerDirector:
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if proxy:
        handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    else:
        handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(handler)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, target: Path, retries: int = 3) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    opener = _proxy_opener()
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            started = time.perf_counter()
            with opener.open(url, timeout=180) as response:
                payload = response.read()
            target.write_bytes(payload)
            return {
                "url": url,
                "path": str(target.relative_to(ROOT)) if target.is_relative_to(ROOT) else str(target),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "duration_ms": round((time.perf_counter() - started) * 1000),
                "attempts": attempt,
            }
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
    return {"url": url, "path": str(target), "error": last_error, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def _fetch_many(urls: dict[str, Path], label: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for key, target in urls.items():
        if target.exists() and target.stat().st_size > 0:
            entry = {
                "url": f"{BASE}/{key}",
                "path": str(target.relative_to(ROOT)) if target.is_relative_to(ROOT) else str(target),
                "bytes": target.stat().st_size,
                "sha256": _sha256(target),
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "duration_ms": 0,
                "attempts": 0,
                "reused": True,
            }
            entry["dataset"] = label
            entry["relative_path"] = str(target)
            entries.append(entry)
            continue
        print(f"  fetching {label}/{key} ...", flush=True)
        entry = _download(f"{BASE}/{key}", target)
        entry["dataset"] = label
        entry["relative_path"] = str(target)
        entries.append(entry)
        if "error" in entry:
            print(f"    FAILED: {entry['error']}", file=sys.stderr)
        else:
            print(f"    ok {entry['bytes']} bytes sha256={entry['sha256'][:16]}...", flush=True)
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preset", action="append", choices=sorted(PRESETS), help="named match preset")
    parser.add_argument("--corpus", action="store_true", help="fetch every match in data/corpus_statsbomb.json")
    parser.add_argument("--competition", type=int, help="competition id")
    parser.add_argument("--season", type=int, help="season id")
    parser.add_argument("--match-ids", help="comma separated match ids")
    parser.add_argument("--with-360", action="store_true", help="also fetch StatsBomb 360 files")
    parser.add_argument("--out", default=str(RAW_DIR), help="raw output directory")
    args = parser.parse_args()

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[dict[str, Any]] = []
    for preset in args.preset or []:
        jobs.append(PRESETS[preset])
    if args.corpus:
        if not CORPUS_PATH.exists():
            parser.error(f"corpus definition not found: {CORPUS_PATH}")
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        by_season: dict[tuple[int, int], list[int]] = {}
        for entry in corpus["matches"]:
            key = (int(entry["competition_id"]), int(entry["season_id"]))
            by_season.setdefault(key, []).append(int(entry["provider_match_id"]))
        for (competition_id, season_id), match_ids in sorted(by_season.items()):
            jobs.append({
                "competition_id": competition_id,
                "season_id": season_id,
                "match_ids": match_ids,
                "label": f"corpus-competition-{competition_id}-season-{season_id}",
            })
    if args.competition is not None and args.season is not None and args.match_ids:
        jobs.append({
            "competition_id": args.competition,
            "season_id": args.season,
            "match_ids": [int(m) for m in args.match_ids.split(",") if m.strip()],
            "label": f"competition-{args.competition}-season-{args.season}",
        })
    if not jobs:
        parser.error("provide --preset and/or --corpus and/or --competition/--season/--match-ids")

    manifest_path = out_dir / "MANIFEST.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError:
            manifest = {}
    manifest.setdefault("version", "statsbomb-source-manifest-v1")
    manifest["license_ref"] = LICENSE_REF
    manifest["attribution_text"] = ATTRIBUTION_TEXT
    manifest["redistribution_rules"] = REDISTRIBUTION_RULES
    manifest["upstream_repository"] = "https://github.com/statsbomb/open-data"
    previous = manifest.get("files", [])
    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in previous:
        url = str(entry.get("url") or "")
        if url and url not in seen:
            seen.add(url)
            files.append(entry)

    for job in jobs:
        competition_id = job["competition_id"]
        season_id = job["season_id"]
        print(f"== {job['label']} ==")
        urls: dict[str, Path] = {
            f"matches/{competition_id}/{season_id}.json": out_dir / f"matches_{competition_id}_{season_id}.json",
        }
        files.extend(_fetch_many(urls, job["label"]))
        for match_id in job["match_ids"]:
            urls = {
                f"events/{match_id}.json": out_dir / f"events_{match_id}.json",
                f"lineups/{match_id}.json": out_dir / f"lineups_{match_id}.json",
            }
            if args.with_360:
                urls[f"three-sixty/{match_id}.json"] = out_dir / f"three-sixty_{match_id}.json"
            files.extend(_fetch_many(urls, job["label"]))

    manifest["files"] = files
    manifest["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # A re-fetch replaces the earlier record for the same URL, so a file that
    # failed earlier and succeeded now is not still reported as failed.
    latest: dict[str, dict[str, Any]] = {}
    for entry in files:
        url = str(entry.get("url") or "")
        if url:
            latest[url] = entry
    resolved = list(latest.values())
    manifest["files"] = resolved
    manifest["failed_files"] = [f["url"] for f in resolved if "error" in f]
    manifest["total_bytes"] = sum(int(f.get("bytes") or 0) for f in resolved)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nmanifest: {manifest_path}")
    if manifest["failed_files"]:
        print(f"{len(manifest['failed_files'])} file(s) failed", file=sys.stderr)
        return 1
    print(f"{len(resolved)} file(s) fetched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
