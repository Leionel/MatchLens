"""Refresh the curated StatsBomb corpus definition from the upstream match index.

The provider publishes a match index per competition and season. This script
reads those indexes and turns them into the corpus entries that
``scripts/fetch_statsbomb_open_data.py`` and ``scripts/ingest_statsbomb_corpus.py``
consume. Only metadata is written: the provider payloads themselves are never
copied into version control, in line with the StatsBomb Public Data User
Agreement.

Usage:
  python scripts/refresh_statsbomb_corpus.py --list
  python scripts/refresh_statsbomb_corpus.py --competition 223 --season 282
  python scripts/refresh_statsbomb_corpus.py --competition 43 --season 272 --apply

Environment:
  HTTPS_PROXY / HTTP_PROXY  optional outbound proxy, e.g. http://127.0.0.1:9674
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "data" / "corpus_statsbomb.json"
BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

# Upstream stage labels mapped onto the slug and the display wording the rest
# of the project already uses.
STAGE_SLUGS = {
    "group stage": "group_stage",
    "1st group stage": "group_stage",
    "2nd group stage": "group_stage",
    "round of 32": "round_of_32",
    "round of 16": "round_of_16",
    "quarter-finals": "quarter_final",
    "quarter-final": "quarter_final",
    "semi-finals": "semi_final",
    "semi-final": "semi_final",
    "3rd place final": "third_place",
    "3rd place": "third_place",
    "final": "final",
}

STAGE_LABELS = {
    "group_stage": "Group Stage",
    "round_of_32": "Round of 32",
    "round_of_16": "Round of 16",
    "quarter_final": "Quarter-Final",
    "semi_final": "Semi-Final",
    "third_place": "3rd Place",
    "final": "Final",
}


def _opener() -> urllib.request.OpenerDirector:
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _fetch_json(url: str) -> Any:
    with _opener().open(url, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _slug_stage(name: str | None) -> str | None:
    if not name:
        return None
    return STAGE_SLUGS.get(str(name).strip().lower(), str(name).strip().lower().replace(" ", "_"))


def _entry(match: dict[str, Any]) -> dict[str, Any]:
    competition = match.get("competition") or {}
    season = match.get("season") or {}
    home = match.get("home_team") or {}
    away = match.get("away_team") or {}
    stage = _slug_stage((match.get("competition_stage") or {}).get("name"))
    competition_name = str(competition.get("competition_name"))
    season_name = str(season.get("season_name"))
    home_team = str(home.get("home_team_name"))
    away_team = str(away.get("away_team_name"))
    home_score = match.get("home_score")
    away_score = match.get("away_score")
    stage_label = STAGE_LABELS.get(stage or "", "Group Stage")
    label = f"{competition_name} {season_name} {stage_label} - {home_team} {home_score}-{away_score} {away_team}"
    return {
        "match_id": f"sb_{match['match_id']}",
        "provider_match_id": int(match["match_id"]),
        "competition_id": int(competition["competition_id"]),
        "season_id": int(season["season_id"]),
        "competition": competition_name,
        "season": season_name,
        "stage": stage,
        "label": label,
        "match_date": match.get("match_date"),
        "kick_off": match.get("kick_off"),
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "home_provider_team_id": str(home.get("home_team_id")),
        "away_provider_team_id": str(away.get("away_team_id")),
        "home_team_gender": home.get("home_team_gender") or "male",
        "away_team_gender": away.get("away_team_gender") or "male",
    }


def _upstream_entries(competition_id: int, season_id: int) -> list[dict[str, Any]]:
    url = f"{BASE}/matches/{competition_id}/{season_id}.json"
    return [_entry(m) for m in _fetch_json(url)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--competition", type=int, action="append", help="upstream competition id")
    parser.add_argument("--season", type=int, action="append", help="upstream season id")
    parser.add_argument("--apply", action="store_true", help="write the corpus definition")
    parser.add_argument("--dry-run", action="store_true", help="show the diff without writing")
    args = parser.parse_args()

    if not args.competition or not args.season:
        parser.error("provide --competition and --season (both accept multiple values)")

    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    existing = {e["match_id"]: e for e in corpus["matches"]}
    added: list[dict[str, Any]] = []
    skipped: list[str] = []

    for competition_id, season_id in zip(args.competition, args.season):
        for entry in _upstream_entries(competition_id, season_id):
            if entry["match_id"] in existing:
                skipped.append(entry["match_id"])
                continue
            existing[entry["match_id"]] = entry
            added.append(entry)

    print(f"new entries: {len(added)}  already present: {len(skipped)}")
    for entry in added:
        print(f"  + {entry['match_id']:<14} {entry['competition']} {entry['season']} "
              f"{str(entry['stage']):<14} {entry['label']}")

    if not args.apply:
        print("\n(dry run: pass --apply to write data/corpus_statsbomb.json)")
        return 0

    corpus["matches"] = sorted(existing.values(), key=lambda e: (e["competition"], e["season"], e["match_date"] or "", e["match_id"]))
    CORPUS_PATH.write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\ncorpus: {CORPUS_PATH} ({len(corpus['matches'])} matches)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
