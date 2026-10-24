"""Explicit full-match import with provenance checks.

No network download is hidden here. The operator must supply a licensed
StatsBomb JSON payload and the explicit provider team IDs; the importer
validates, writes the raw payload plus metadata, and emits a provenance receipt.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .adapters.statsbomb import StatsBombAdapter
from .schema import DataCoverageLevel

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data" / "matches"
DEFAULT_RECEIPT_DIR = Path(__file__).resolve().parents[3] / "evidence" / "imports"


class ImportError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_match(
    *,
    source_path: Path | str,
    match_id: str,
    data_dir: Path | str = DEFAULT_DATA_DIR,
    receipt_dir: Path | str = DEFAULT_RECEIPT_DIR,
    home_team: str,
    away_team: str,
    home_provider_team_id: str,
    away_provider_team_id: str,
    competition: str,
    season: str,
    match_date: str | None = None,
    home_score: int | None = None,
    away_score: int | None = None,
    license_ref: str,
    format_seconds: int = 5400,
    force: bool = False,
) -> dict[str, Any]:
    source = Path(source_path)
    if not source.exists():
        raise ImportError("source_not_found")
    if not license_ref.strip():
        raise ImportError("license_required")
    if home_provider_team_id == away_provider_team_id:
        raise ImportError("provider_team_ids_must_differ")

    payload = json.loads(source.read_text(encoding="utf-8"))
    raw_events = payload.get("events") if isinstance(payload, dict) else payload
    if not isinstance(raw_events, list) or not raw_events:
        raise ImportError("events_must_be_non_empty_list")

    adapter = StatsBombAdapter(match_id=match_id)
    events = adapter.load_events(raw_events)
    known = {home_provider_team_id, away_provider_team_id}
    unmapped = sorted({e.team_id for e in events if e.team_id not in known})
    if unmapped:
        raise ImportError(f"unmapped_provider_teams:{','.join(unmapped)}")

    observed_end = max((e.clock_seconds for e in events), default=0.0)
    coverage = (
        DataCoverageLevel.C1_OPEN_EVENTS
        if observed_end >= format_seconds - 60
        else DataCoverageLevel.C1_PARTIAL
    )
    target = Path(data_dir) / f"{match_id}.json"
    if target.exists() and not force:
        raise ImportError("target_exists_use_force")

    metadata = {
        "match_id": match_id,
        "label": f"{home_team} vs {away_team}",
        "competition": competition,
        "season": season,
        "match_date": match_date,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "coverage_level": coverage.value,
        "data_provider": "statsbomb_open_data",
        "description": (
            f"Imported StatsBomb payload: {len(raw_events)} events, observed through "
            f"{observed_end:.0f}s of {format_seconds}s."
        ),
        "license_ref": license_ref,
        "attribution_text": "Data provided by StatsBomb Open Data (https://github.com/statsbomb/open-data)",
        "events_count": len(raw_events),
        "format_seconds": format_seconds,
        "home_provider_team_id": str(home_provider_team_id),
        "away_provider_team_id": str(away_provider_team_id),
        "continuous_coverage": coverage is DataCoverageLevel.C1_OPEN_EVENTS,
        "capabilities": [
            "schema_compatibility",
            "event_stream",
            "spatial_drilldown",
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"metadata": metadata, "events": raw_events}, ensure_ascii=False, indent=2), encoding="utf-8")

    receipt = {
        "version": "statsbomb-import-v1",
        "imported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "match_id": match_id,
        "source_file": str(source),
        "source_sha256": _sha256_file(source),
        "target_file": str(target),
        "target_sha256": _sha256_file(target),
        "license_ref": license_ref,
        "event_count": len(raw_events),
        "observed_end": observed_end,
        "format_seconds": format_seconds,
        "coverage_level": coverage.value,
        "home_provider_team_id": str(home_provider_team_id),
        "away_provider_team_id": str(away_provider_team_id),
        "home_team": home_team,
        "away_team": away_team,
    }
    receipt_path = Path(receipt_dir) / f"{match_id}.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return receipt
