# Slice A — Real corpus, match library and full-match momentum: Results (2026-10-24)

Scope: Prompt 2 §2 (complete historical matches, end to end) plus the two product
asks — a match library selected by competition and season instead of a flat grid,
and a momentum chart that is not limited to the 12-minute synthetic fixture.
Every statement below separates **executed and verified**, **executed but not
measured**, and **open**.

## 1. Executed and verified

### 1.1 Curated provider corpus — 80 complete matches

The corpus definition is produced by a committed rule, not by hand:
`scripts/select_statsbomb_corpus.py` reads the provider match indexes cached by
`scripts/fetch_statsbomb_open_data.py` and writes `data/corpus_statsbomb.json`.

| Tournament | Matches | Selection |
| --- | --- | --- |
| FIFA World Cup 2018 / 2022 | 16 + 16 | every match from the quarter-final up, plus the four highest-scoring round-of-16 and four group-stage matches each |
| UEFA Euro 2020 / 2024 | 15 + 15 | same rule |
| Copa America 2024 | 8 | knockouts from the quarter-final only |
| Champions League 2009/10 – 2018/19 | 10 | every final the provider publishes |

15 competition-seasons, 3 confederations, 2010-2024. All 80 imported as
`COMPLETE_VERIFIED`; `evidence/imports/` holds exactly one receipt per match (the
46 receipts of matches no longer in the corpus were deleted, so the repository does
not claim 126 imports); `data/source_manifest.json` carries 80 entries and the
catalog serves 87 (`80 provider_payload + 6 synthetic + 1 provider_schema_excerpt`,
86 `COMPLETE_VERIFIED` and the one `SPARSE_SAMPLE_FIXTURE`).

Each receipt reconciles the provider's index score against the goals counted from
that match's own event stream (`score_reconciliation.consistent = true`), and every
match passes the period, identity, clock, density and span-coverage checks.

Licence posture, unchanged and enforced: payloads are fetched by script into the
git-ignored `data/raw` and `data/datasets` directories and are never committed; only
metadata, receipts and the manifest are; the provider's attribution text travels in
each receipt.

Recorded limitation: competition 16 publishes **one match per season** (the final)
and publishes nothing for 2019/2020 – 2023/2024, so "Champions League from the
quarter-finals onwards" is not obtainable from this source. The finals of every
published season from 2009/2010 were taken instead, which is what the corpus
rationale states.

### 1.2 Match library replaces the flat grid

`MatchHubWorkspace.tsx` (one flat grid of every match) is deleted. The library is
`MatchLibraryWorkspace` + `MatchLibraryBrowser` + `MatchLibraryDetail` +
`matchLibrary.ts`: a competition column, a season strip with per-season counts,
round groups that fold, a provenance badge per row (Provider data / Sample excerpt /
Synthetic), and a detail panel with overview, coverage and source tabs. The former
Match Hub's 833-line detail surface (`MatchDetailPanel`: team and player profiles,
cross-match compare) is re-hosted in the library's deep panel rather than dropped.

Real-browser acceptance at 1440, 820 and 412 px: no console errors, no horizontal
overflow. The season strip initially stretched the page (scrollWidth 1741 in a
1440 viewport); the cause was the library list's implicit `auto` grid column, fixed
by bounding it (`grid-template-columns: minmax(0, 1fr)` in `apps/web/app/globals.css`)
and letting the strip scroll inside its own column.

### 1.3 Momentum chart over a complete real match

Verified on `sb_3795221` (UEFA Euro 2020 semi-final, England 2-1 Denmark, four
periods, 4 691 provider events): period bands, change points with rug marks, and a
peak-preserving sampling budget (602 of 3 601 samples kept) so a full match renders
without hiding a spike.

The blocking defect was computational, not visual. The dead-time freeze subtracted
the stoppage between each event and each sample by scanning the whole interval list,
which is `samples x events x intervals`. `oaai.py` now merges and prefix-sums the
intervals once (`_DeadTimeIndex`, a bisect per query):

| Measured on `sb_3795221` at 120:00 | Before | After |
| --- | --- | --- |
| `POST /api/control seek` | 166s (at 131:11, clamped) | 9.0s |
| `GET /api/exploration/oaai` | 225.8s | 6.8s |
| `compute_oaai` for the same window | 152.6s | 13.0s |

The published numbers did not move: the frozen dead seconds are identical to the
previous scan (max |old − new| = 0.0s over sampled windows), because the reducer's
dead intervals are disjoint and merging them cannot change the measure.

### 1.4 Browser suite and CI

Playwright drives the served static export against a throwaway backend that is
structurally unable to spend model budget (`DEEPSEEK_API_KEY: ""`), so every agent
path in the suite asserts the honest deterministic fallback (`execution_mode =
deterministic_planner`, `agent_status = not_run`).

The suite asserts the real match on provider facts only: provenance separation,
library narrowing by competition and season with the "N of M" count, the detail
coverage and source tabs, identity through match centre and tactical lab
(`provider = statsbomb_open_data`, `official_score = {H:2, N:1}`), registry
observations bound to provider event ids, and the deep-link restore.

Extra-time semantics are now asserted rather than assumed: the anchor match must
report `duration = 7200`, `period = 4`, `match_clock_basis = match_elapsed` and
`observed_end > duration`, and a read that asks for a clock past the nominal end is
refused with `at_outside_match_context` instead of answering about another match.
The clock itself clamps a seek to the nominal end, which is covered in the backend
suite (`test_seek_clamps_to_match_context_duration`); the browser layer deliberately
does not repeat it, because proving it there means freezing a full provider match.
The synthetic constants (720s, two periods) are used only for synthetic fixtures.

Suite cost, measured: 19 tests in 1.4 minutes, serial by design (`workers: 1`) because
the claim registry and the broadcast store are persisted runtime state shared by one
backend — a withdrawal in one worker invalidates the approval chain another test
asserts on. The remaining real-match tests are the expensive and the valuable ones:
the deterministic investigation over 4 691 provider events (20.4s) and the deep-link
restore that rebuilds the session and its snapshot (10.2s).

## 2. Executed but not measured

- The library's provenance and coverage labels are rendered from the manifest and
  receipts; no separate visual baseline set is committed, so drift is caught by the
  Playwright assertions, not by screenshot diffing.
- The chart sampling and the dead-time index have no dedicated load-time budget in
  CI; the timings above are local single-run measurements on this machine (16 GB,
  shared with the dev server), not a CI-tracked metric.

## 3. Open items, with evidence

- **Stoppage tail beyond the nominal clock.** The replay clock is the nominal match
  clock, so `seek` clamps at `expected_duration` (7200s = 120:00) while this match
  records through 7871.78s: 516 events (11%) sit past the reachable end, including
  the final whistle. The boundary is asserted in the suite and documented in
  architecture §6.2 rather than hidden. Reaching the tail means separating the
  reducer's `max_duration` from the snapshot's `format_seconds`, which changes the
  published clock semantics that B-01/P0-B fixed — deliberately out of scope here.
- **First-snapshot cost.** Freezing a full provider match still takes 5-34s for the
  first snapshot at a new clock (the snapshot embeds every recorded event, which is
  what makes its hash addressable).
- **Cross-era performance receipts are stale.** `SLICE_C_RESULTS.md` measured profile
  and index timings against the previous 71-match corpus; the corpus is now 80
  matches, so those numbers need re-measurement before they are quoted again.
- **No independent score oracle.** Provider index against event stream agrees; that
  is one source checked against itself. A second results source is not wired.
- **Calibration.** xG remains a heuristic (`not_calibrated`), xT a static grid; the
  corpus now makes a fitted version possible, which is a research item (B-06/B-07),
  not a slice deliverable.
