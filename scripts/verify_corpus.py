"""Verify the complete curated corpus from a clean materialisation.

This is the full-corpus counterpart of the minimum one-match CI integration.
It never fabricates data: a catalogued match without its payload, a checksum
mismatch, a broken completeness report or an unverified analysis state fails
the run.

The 80-match set is a curated functional-acceptance sample (a high-scoring,
competition-balanced selection), not an unbiased population of football
matches. The printed note keeps that selection boundary visible.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from matchlens.catalog import MatchCatalog  # noqa: E402


def main() -> int:
    corpus = json.loads((ROOT / "data" / "corpus_statsbomb.json").read_text(encoding="utf-8"))
    expected = {str(entry["match_id"]) for entry in corpus["matches"]}

    listed = {meta.match_id: meta for meta in MatchCatalog.list_matches()}
    provider = {
        match_id: meta
        for match_id, meta in listed.items()
        if meta.provenance_kind == "provider_payload"
    }
    missing_catalog = sorted(expected - set(provider))
    failures: list[str] = []
    if missing_catalog:
        failures.append(f"catalog missing {len(missing_catalog)} corpus matches: {missing_catalog[:5]}")

    competition_counts: Counter[str] = Counter()
    season_counts: Counter[str] = Counter()
    completeness_counts: Counter[str] = Counter()
    total_events = 0
    total_observed = 0.0
    for match_id in sorted(expected & set(provider)):
        meta = provider[match_id]
        competition_counts[meta.competition] += 1
        season_counts[f"{meta.competition} {meta.season}"] += 1
        completeness_counts[str(meta.completeness_status)] += 1
        if meta.availability_status != "ANALYSIS_READY":
            failures.append(
                f"{match_id}: availability={meta.availability_status} reason={meta.availability_reason}"
            )
            continue
        ok, reason = MatchCatalog.verify_analysis_ready(match_id)
        if not ok:
            failures.append(f"{match_id}: live verification failed: {reason}")
            continue
        try:
            ctx = MatchCatalog.get_match_context(match_id)
        except Exception as exc:  # noqa: BLE001 - the report needs the real reason
            failures.append(f"{match_id}: context failed: {type(exc).__name__}: {exc}")
            continue
        if ctx.event_count <= 0:
            failures.append(f"{match_id}: zero normalized events")
        if ctx.completeness_status not in (
            "COMPLETE_VERIFIED",
            "COMPLETE_CLAIMED_UNVERIFIED",
            "PARTIAL_OBSERVED",
            "SPARSE_SAMPLE_FIXTURE",
        ):
            failures.append(f"{match_id}: completeness={ctx.completeness_status}")
        total_events += ctx.event_count
        total_observed += float(ctx.observed_end or 0)

    print(
        f"corpus: expected={len(expected)} catalogued={len(provider)} "
        f"verified={len(expected) - len(failures)} events={total_events}"
    )
    print("competitions:", dict(sorted(competition_counts.items(), key=lambda kv: (-kv[1], kv[0]))))
    print("completeness:", dict(completeness_counts))
    print(f"mean observed end: {total_observed / max(1, len(expected)):.1f}s")
    print(
        "selection note: this 80-match corpus is a curated functional-acceptance sample "
        "(competition-balanced, high-scoring bias possible); cross-match rates describe "
        "this sample, never an unbiased football population."
    )
    if failures:
        for row in failures[:40]:
            print(f"  FAILED {row}", file=sys.stderr)
        print(f"\n{len(failures)} corpus failure(s)", file=sys.stderr)
        return 1
    print("all corpus matches are analysis-ready and content-verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
