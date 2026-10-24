"""Import a licensed StatsBomb event payload into the match catalog.

Example:
  python scripts/import_statsbomb_match.py --source final.json \
    --match-id sb_wc2022_final_full --home-team Argentina --away-team France \
    --home-provider-team-id 779 --away-provider-team-id 771 \
    --competition "FIFA World Cup" --season 2022 --license "StatsBomb Open Data CC BY-NC-SA 4.0"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from matchlens.ingest import ImportError, import_match  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--home-team", required=True)
    parser.add_argument("--away-team", required=True)
    parser.add_argument("--home-provider-team-id", required=True)
    parser.add_argument("--away-provider-team-id", required=True)
    parser.add_argument("--competition", required=True)
    parser.add_argument("--season", required=True)
    parser.add_argument("--match-date")
    parser.add_argument("--home-score", type=int)
    parser.add_argument("--away-score", type=int)
    parser.add_argument("--license", required=True)
    parser.add_argument("--format-seconds", type=int, default=5400)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        receipt = import_match(
            source_path=args.source,
            match_id=args.match_id,
            home_team=args.home_team,
            away_team=args.away_team,
            home_provider_team_id=args.home_provider_team_id,
            away_provider_team_id=args.away_provider_team_id,
            competition=args.competition,
            season=args.season,
            match_date=args.match_date,
            home_score=args.home_score,
            away_score=args.away_score,
            license_ref=args.license,
            format_seconds=args.format_seconds,
            force=args.force,
        )
    except ImportError as exc:
        print(f"Import rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
