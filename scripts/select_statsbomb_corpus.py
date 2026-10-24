"""Select the curated StatsBomb corpus definition from the upstream match indexes.

The provider publishes one match index per competition and season. The indexes
are downloaded by ``scripts/fetch_statsbomb_open_data.py`` into the ignored
cache directory; this script turns them into ``data/corpus_statsbomb.json``,
which is the single definition the fetch and ingest steps consume.

Selection rule:
  * knockout rounds from the quarter-final onwards are taken in full;
  * a fixed number of round-of-16 and group-stage matches is taken by
    combined goals, descending, earliest match date first.

Usage:
  python scripts/select_statsbomb_corpus.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "statsbomb"
OUT = ROOT / "data" / "corpus_statsbomb.json"

SLUGS = {
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
STAGE_LABEL = {
    "final": "Final",
    "third_place": "3rd Place",
    "semi_final": "Semi-Final",
    "quarter_final": "Quarter-Final",
    "round_of_32": "Round of 32",
    "round_of_16": "Round of 16",
    "group_stage": "Group Stage",
}

# (competition_id, season_id, rounds from the quarter-final onwards, r16 count, group count)
TOURNAMENTS = [
    (43, 3, True, 4, 4),      # FIFA World Cup 2018
    (43, 106, True, 4, 4),    # FIFA World Cup 2022
    (55, 43, True, 4, 4),     # UEFA Euro 2020
    (55, 282, True, 4, 4),    # UEFA Euro 2024
    (223, 282, True, 0, 0),   # Copa America 2024: knockouts only
    # Champions League: the provider publishes the final of each season and
    # nothing else, so every published final from 2009/2010 onwards is taken.
    (16, 21, True, 0, 0),     # 2009/2010
    (16, 22, True, 0, 0),     # 2010/2011
    (16, 23, True, 0, 0),     # 2011/2012
    (16, 24, True, 0, 0),     # 2012/2013
    (16, 25, True, 0, 0),     # 2013/2014
    (16, 26, True, 0, 0),     # 2014/2015
    (16, 27, True, 0, 0),     # 2015/2016
    (16, 2, True, 0, 0),      # 2016/2017
    (16, 1, True, 0, 0),      # 2017/2018
    (16, 4, True, 0, 0),      # 2018/2019
]
KNOCKOUT_STAGES = ("quarter_final", "semi_final", "third_place", "final")


def entry(match: dict) -> dict:
    competition = match["competition"]
    season = match["season"]
    home = match["home_team"]
    away = match["away_team"]
    stage = SLUGS[(match.get("competition_stage") or {}).get("name", "").strip().lower()]
    competition_name = str(competition["competition_name"])
    season_name = str(season["season_name"])
    home_name = str(home["home_team_name"])
    away_name = str(away["away_team_name"])
    return {
        "match_id": f"sb_{match['match_id']}",
        "provider_match_id": int(match["match_id"]),
        "competition_id": int(competition["competition_id"]),
        "season_id": int(season["season_id"]),
        "competition": competition_name,
        "season": season_name,
        "stage": stage,
        "label": (
            f"{competition_name} {season_name} {STAGE_LABEL[stage]} - "
            f"{home_name} {match['home_score']}-{match['away_score']} {away_name}"
        ),
        "match_date": match["match_date"],
        "kick_off": match.get("kick_off"),
        "home_team": home_name,
        "away_team": away_name,
        "home_score": match["home_score"],
        "away_score": match["away_score"],
        "home_provider_team_id": str(home["home_team_id"]),
        "away_provider_team_id": str(away["away_team_id"]),
        "home_team_gender": home.get("home_team_gender") or "male",
        "away_team_gender": away.get("away_team_gender") or "male",
    }


def main() -> int:
    selected: list[dict] = []
    for competition_id, season_id, with_knockouts, r16_count, group_count in TOURNAMENTS:
        rows = json.loads((RAW / f"matches_{competition_id}_{season_id}.json").read_text(encoding="utf-8"))
        buckets: dict[str, list[dict]] = {}
        for row in rows:
            stage = SLUGS[(row.get("competition_stage") or {}).get("name", "").strip().lower()]
            buckets.setdefault(stage, []).append(row)

        picks: list[dict] = []
        if with_knockouts:
            for stage in KNOCKOUT_STAGES:
                picks.extend(buckets.get(stage, []))
        for stage, count in (("round_of_16", r16_count), ("group_stage", group_count)):
            pool = sorted(
                buckets.get(stage, []),
                key=lambda m: (-(m["home_score"] + m["away_score"]), m["match_date"]),
            )
            picks.extend(pool[:count])

        picks.sort(key=lambda m: (m["match_date"], m["match_id"]))
        for row in picks:
            selected.append(entry(row))
        print(f"{competition_id}/{season_id}: {len(picks)} matches")

    selected.sort(key=lambda e: (e["competition"], e["season"], e["match_date"] or "", e["match_id"]))

    payload = {
        "version": "matchlens-statsbomb-corpus-v1",
        "provider": {
            "name": "statsbomb_open_data",
            "repository": "https://github.com/statsbomb/open-data",
            "base_url": "https://raw.githubusercontent.com/statsbomb/open-data/master/data",
        },
        "selection_rationale": (
            "Five modern international tournaments plus every Champions League final the "
            "provider publishes from 2009/2010 onwards. Every match from the quarter-final "
            "onwards is taken in full; the round-of-16 and group-stage samples are taken by "
            "combined goals, descending, earliest match date first, so the selection is "
            "reproducible and biased towards matches with the most attacking activity, which "
            "is what the activity index measures. Copa America 2024 is limited to the "
            "knockout rounds. The Champions League contributes the final of each published "
            "season because the provider publishes nothing else for that competition; the "
            "seasons 2019/2020 to 2023/2024 are not published at all. World Cups of 1958 to "
            "1990 were imported earlier and are left out of the curated set for now; their "
            "payloads stay on disk and the corpus definition is the single place where they "
            "would be restored."
        ),
        "matches": selected,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} with {len(selected)} matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
