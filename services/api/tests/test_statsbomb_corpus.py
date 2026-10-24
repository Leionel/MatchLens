"""Acceptance for the curated StatsBomb Open Data corpus.

Three layers of evidence, each with a different failure mode:

1. The corpus declaration itself (always runs): every curated match must be a
   real upstream match with an explicit provider team mapping, and the licence
   strings must match the provider agreement actually in force.
2. The upstream season index (runs when ``data/raw/`` holds the indexes): the
   curated competition/season/team/score metadata must match the provider's
   own index, so a hand-edited corpus cannot drift away from the source.
3. The imported dataset (runs when ``data/datasets/`` holds the payloads): the
   normalized stream must reproduce the declared score, keep every coordinate
   inside the pitch, carry contiguous periods, and contain no synthetic event.

Layer 3 is skipped - never silently passed - when the payloads are absent,
because the provider agreement keeps them out of version control.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from matchlens.catalog import MatchCatalog
from matchlens.completeness import NOMINAL_PERIOD_SECONDS
from matchlens.provider_terms import (
    STATSBOMB_ATTRIBUTION_TEXT,
    STATSBOMB_LICENSE_REF,
    STATSBOMB_REDISTRIBUTION_RULES,
)
from matchlens.schema import DataCoverageLevel

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_PATH = REPO_ROOT / "data" / "corpus_statsbomb.json"
RAW_DIR = REPO_ROOT / "data" / "raw" / "statsbomb"
DATASET_DIR = REPO_ROOT / "data" / "datasets"
MANIFEST_PATH = REPO_ROOT / "data" / "source_manifest.json"
RECEIPT_DIR = REPO_ROOT / "evidence" / "imports"

REQUIRED_ENTRY_FIELDS = (
    "match_id",
    "provider_match_id",
    "competition_id",
    "season_id",
    "competition",
    "season",
    "stage",
    "label",
    "match_date",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "home_provider_team_id",
    "away_provider_team_id",
)


@pytest.fixture(scope="module")
def corpus() -> dict:
    if not CORPUS_PATH.exists():
        pytest.skip("corpus declaration is not present")
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def entries(corpus: dict) -> list[dict]:
    return list(corpus.get("matches") or [])


def _season_index(competition_id: int, season_id: int) -> list[dict] | None:
    path = RAW_DIR / f"matches_{competition_id}_{season_id}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return payload if isinstance(payload, list) else None


# --------------------------------------------------------------------- corpus
def test_corpus_declares_provider_and_version(corpus: dict):
    assert corpus["version"] == "matchlens-statsbomb-corpus-v1"
    provider = corpus["provider"]
    assert provider["name"] == "statsbomb_open_data"
    assert provider["repository"].startswith("https://github.com/statsbomb/open-data")
    assert provider["base_url"].startswith("https://")


def test_corpus_entries_are_complete_and_self_consistent(entries: list[dict]):
    assert len(entries) >= 10, "a curated corpus of this size is expected to be useful"
    seen_ids: set[str] = set()
    seen_provider_ids: set[int] = set()
    for entry in entries:
        for field in REQUIRED_ENTRY_FIELDS:
            assert field in entry, f"{entry.get('match_id')} is missing {field}"
        assert entry["match_id"] == f"sb_{entry['provider_match_id']}"
        assert entry["match_id"] not in seen_ids
        assert entry["provider_match_id"] not in seen_provider_ids
        seen_ids.add(entry["match_id"])
        seen_provider_ids.add(entry["provider_match_id"])
        assert entry["home_provider_team_id"] != entry["away_provider_team_id"]
        assert str(entry["home_provider_team_id"]).isnumeric()
        assert str(entry["away_provider_team_id"]).isnumeric()
        assert isinstance(entry["home_score"], int) and entry["home_score"] >= 0
        assert isinstance(entry["away_score"], int) and entry["away_score"] >= 0
        assert entry["home_team"] != entry["away_team"]


def test_corpus_covers_several_tournaments_with_repeated_teams(entries: list[dict]):
    tournaments = {(entry["competition_id"], entry["season_id"]) for entry in entries}
    assert len(tournaments) >= 3, "cross-era comparison needs several tournaments"
    competitions = {entry["competition_id"] for entry in entries}
    assert len(competitions) >= 2, "cross-competition comparison needs several competitions"
    teams: dict[str, int] = {}
    for entry in entries:
        teams[entry["home_team"]] = teams.get(entry["home_team"], 0) + 1
        teams[entry["away_team"]] = teams.get(entry["away_team"], 0) + 1
    repeated = [team for team, count in teams.items() if count >= 3]
    assert repeated, "no team appears often enough to build a cross-match profile"


def test_corpus_does_not_claim_licences_the_provider_does_not_grant(corpus: dict):
    """The provider agreement is a custom licence, not CC BY-NC-SA."""
    serialized = json.dumps(corpus, ensure_ascii=False).lower()
    assert "cc by" not in serialized
    assert "cc-by" not in serialized
    assert "public domain" not in serialized
    assert "mit license" not in serialized


# ------------------------------------------------------------------- licensing
def test_provider_terms_match_the_agreement_in_force():
    assert "StatsBomb Public Data User Agreement" in STATSBOMB_LICENSE_REF
    assert "8 September 2023" in STATSBOMB_LICENSE_REF
    assert "CC BY" not in STATSBOMB_LICENSE_REF
    assert "StatsBomb" in STATSBOMB_ATTRIBUTION_TEXT
    assert "logo" in STATSBOMB_ATTRIBUTION_TEXT.lower()
    assert STATSBOMB_REDISTRIBUTION_RULES
    joined = " ".join(STATSBOMB_REDISTRIBUTION_RULES).lower()
    assert "distribut" in joined
    assert "third party" in joined
    assert "1.4" in joined, "the attribution duty (clause 1.4) must be recorded"


def test_no_module_still_claims_cc_by_nc_sa():
    """Every module that names the provider must name the same licence."""
    offenders: list[str] = []
    for path in (REPO_ROOT / "services" / "api" / "matchlens").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "CC BY" in text and "provider_terms" not in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"stale licence strings: {offenders}"


def test_no_bundled_fixture_claims_to_be_a_full_provider_payload():
    """A bundled fixture is an excerpt. It must say so and use the real licence."""
    fixture_dir = REPO_ROOT / "services" / "api" / "matchlens" / "data" / "matches"
    if not fixture_dir.exists():
        pytest.skip("no bundled fixtures")
    for path in sorted(fixture_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta = payload["metadata"]
        assert meta["license_ref"] == STATSBOMB_LICENSE_REF, (
            f"{path.name} cites a licence the provider does not grant"
        )
        assert meta.get("attribution_text") == STATSBOMB_ATTRIBUTION_TEXT
        assert meta["provenance_kind"] in ("provider_schema_excerpt", "synthetic"), (
            f"{path.name} does not declare how its events were obtained"
        )
        assert meta["continuous_coverage"] is False
        assert meta["coverage_level"] != "C1_OPEN_EVENTS", (
            f"{path.name} is an excerpt and must not claim full open-event coverage"
        )


def test_catalog_exposes_the_provenance_of_every_match():
    for meta in MatchCatalog.list_matches():
        assert meta.provenance_kind in ("synthetic", "provider_payload", "provider_schema_excerpt")
        if meta.data_provider == "synthetic":
            assert meta.provenance_kind == "synthetic"
        if meta.provenance_kind == "provider_payload":
            assert meta.coverage_level == DataCoverageLevel.C1_OPEN_EVENTS


# -------------------------------------------------------------- upstream index
def test_curated_metadata_matches_the_provider_season_index(entries: list[dict]):
    """The corpus may not drift away from the provider's own index."""
    checked = 0
    for entry in entries:
        index = _season_index(entry["competition_id"], entry["season_id"])
        if index is None:
            continue
        by_id = {str(m["match_id"]): m for m in index}
        upstream = by_id.get(str(entry["provider_match_id"]))
        assert upstream is not None, f"{entry['match_id']} is not in the upstream season index"
        assert upstream["home_team"]["home_team_name"] == entry["home_team"]
        assert upstream["away_team"]["away_team_name"] == entry["away_team"]
        assert str(upstream["home_team"]["home_team_id"]) == str(entry["home_provider_team_id"])
        assert str(upstream["away_team"]["away_team_id"]) == str(entry["away_provider_team_id"])
        assert upstream["home_score"] == entry["home_score"]
        assert upstream["away_score"] == entry["away_score"]
        assert upstream["match_date"] == entry["match_date"]
        checked += 1
    if checked == 0:
        pytest.skip("no upstream season index is present locally")


# ------------------------------------------------------------- imported corpus
def _imported_match_ids(entries: list[dict]) -> list[str]:
    available = []
    for entry in entries:
        if (DATASET_DIR / f"{entry['match_id']}.json").exists():
            available.append(entry["match_id"])
    return available


def test_imported_corpus_is_available_through_the_catalog(entries: list[dict]):
    imported = _imported_match_ids(entries)
    if not imported:
        pytest.skip("no imported corpus dataset is present locally")
    catalog = {m.match_id: m for m in MatchCatalog.list_matches()}
    for match_id in imported:
        assert match_id in catalog, f"{match_id} is imported but not listed by the catalog"
        meta = catalog[match_id]
        assert meta.data_provider == "statsbomb_open_data"
        assert meta.coverage_level == DataCoverageLevel.C1_OPEN_EVENTS


def _credited_goals(events) -> dict[str, int]:
    """Goals credited per side, with the provider's own-goal pair counted once.

    A provider records one own goal twice: once for the beneficiary and once
    for the conceding side. Both events carry the same clock, so the goal is
    counted once and credited to the beneficiary.
    """
    goals = {"H": 0, "N": 0}
    counted_own_goals: set[tuple[int, float]] = set()
    for event in events:
        outcome = str(event.outcome or "").lower()
        if outcome not in ("goal", "own_goal", "own_goal_for"):
            continue
        if event.team_id not in goals:
            continue
        if int(event.period) >= 5:
            continue  # shoot-out kicks are not part of the match score
        if outcome.startswith("own_goal"):
            key = (int(event.period), round(float(event.clock_seconds), 3))
            if key in counted_own_goals:
                continue
            counted_own_goals.add(key)
        side = event.team_id
        if outcome == "own_goal":
            side = "N" if side == "H" else "H"
        goals[side] += 1
    return goals


def test_imported_match_reproduces_the_declared_score(entries: list[dict]):
    imported = _imported_match_ids(entries)
    if not imported:
        pytest.skip("no imported corpus dataset is present locally")
    by_id = {entry["match_id"]: entry for entry in entries}
    for match_id in imported:
        entry = by_id[match_id]
        events = MatchCatalog.load_normalized_events(match_id)
        assert events, f"{match_id} produced no events"
        goals = _credited_goals(events)
        assert goals["H"] == entry["home_score"], f"{match_id} home score mismatch"
        assert goals["N"] == entry["away_score"], f"{match_id} away score mismatch"


def test_imported_match_keeps_every_coordinate_inside_the_pitch(entries: list[dict]):
    imported = _imported_match_ids(entries)
    if not imported:
        pytest.skip("no imported corpus dataset is present locally")
    for match_id in imported:
        events = MatchCatalog.load_normalized_events(match_id)
        for event in events:
            if event.x is not None:
                assert 0.0 <= event.x <= 105.0, f"{match_id}:{event.event_id} x={event.x}"
            if event.y is not None:
                assert 0.0 <= event.y <= 68.0, f"{match_id}:{event.event_id} y={event.y}"
            if event.end_x is not None:
                assert 0.0 <= event.end_x <= 105.0
            if event.end_y is not None:
                assert 0.0 <= event.end_y <= 68.0


def test_imported_match_has_contiguous_periods_and_a_full_clock(entries: list[dict]):
    imported = _imported_match_ids(entries)
    if not imported:
        pytest.skip("no imported corpus dataset is present locally")
    for match_id in imported:
        events = MatchCatalog.load_normalized_events(match_id)
        periods = sorted({e.period for e in events})
        assert periods == list(range(1, max(periods) + 1)), f"{match_id} has a period gap: {periods}"
        nominal = sum(NOMINAL_PERIOD_SECONDS.get(p, 2700.0) for p in periods)
        observed_end = max(e.clock_seconds for e in events)
        assert observed_end >= nominal * 0.9, f"{match_id} clock stops at {observed_end}s of {nominal}s"


def test_imported_match_contains_no_synthetic_event(entries: list[dict]):
    """A provider match must never carry synthetic generator identifiers."""
    imported = _imported_match_ids(entries)
    if not imported:
        pytest.skip("no imported corpus dataset is present locally")
    for match_id in imported:
        events = MatchCatalog.load_normalized_events(match_id)
        for event in events:
            assert event.source.provider == "statsbomb_open_data"
            assert not event.event_id.startswith("syn_")
            assert event.team_id in ("H", "N")
            assert event.clock_basis in ("period_elapsed", "match_elapsed")


def test_imported_match_reports_a_verified_completeness(entries: list[dict]):
    imported = _imported_match_ids(entries)
    if not imported:
        pytest.skip("no imported corpus dataset is present locally")
    for match_id in imported:
        report = MatchCatalog.completeness_report(match_id)
        assert report.status in ("COMPLETE_VERIFIED", "COMPLETE_CLAIMED_UNVERIFIED"), (
            f"{match_id} is {report.status}: {report.known_missing_segments}"
        )
        assert report.provider_consistency is True, f"{match_id} provider consistency failed"
        assert report.raw_event_count >= report.normalized_event_count


def test_imported_match_carries_lineups_and_player_identity(entries: list[dict]):
    imported = _imported_match_ids(entries)
    if not imported:
        pytest.skip("no imported corpus dataset is present locally")
    for match_id in imported:
        events = MatchCatalog.load_normalized_events(match_id)
        players = {e.player_id for e in events if e.player_id}
        assert len(players) >= 20, f"{match_id} only identifies {len(players)} players"
        named = {e.player_name for e in events if e.player_name}
        assert len(named) >= 20, f"{match_id} only names {len(named)} players"


# ------------------------------------------------------------------- manifest
def test_source_manifest_records_provenance_without_payloads(entries: list[dict]):
    if not MANIFEST_PATH.exists():
        pytest.skip("no source manifest is present")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["version"] == "matchlens-source-manifest-v1"
    assert manifest["provider"]["name"] == "statsbomb_open_data"
    assert manifest["license_ref"] == STATSBOMB_LICENSE_REF
    assert manifest["redistribution_rules"]
    manifest_ids = {m["match_id"] for m in manifest["matches"]}
    assert manifest_ids, "the manifest declares no matches"
    assert manifest_ids <= {entry["match_id"] for entry in entries}
    for match in manifest["matches"]:
        assert match["dataset_sha256"]
        assert len(match["dataset_sha256"]) == 64
        source = match["source"]
        assert source["provider"] == "statsbomb_open_data"
        assert source["events_url"].startswith("https://")
        assert source["source_sha256"]
        assert match["completeness"]["status"]


def test_manifest_carries_no_provider_payload():
    """The manifest is committed, so it must not embed provider event data."""
    if not MANIFEST_PATH.exists():
        pytest.skip("no source manifest is present")
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    manifest = json.loads(text)
    assert "events" not in manifest
    for match in manifest["matches"]:
        assert "events" not in match
        assert "raw_events" not in match


def test_import_receipts_record_the_conversion_accounting(entries: list[dict]):
    imported = _imported_match_ids(entries)
    if not imported:
        pytest.skip("no imported corpus dataset is present locally")
    for match_id in imported:
        receipt_path = RECEIPT_DIR / f"{match_id}.json"
        if not receipt_path.exists():
            continue
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["provider"] == "statsbomb_open_data"
        assert receipt["raw_event_count"] >= receipt["normalized_event_count"]
        assert receipt["source_sha256"] and receipt["target_sha256"]
        assert receipt["completeness_status"] in (
            "COMPLETE_VERIFIED",
            "COMPLETE_CLAIMED_UNVERIFIED",
        )
        assert receipt["license_ref"] == STATSBOMB_LICENSE_REF
