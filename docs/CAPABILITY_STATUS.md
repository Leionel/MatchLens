# MatchLens Capability Status (single current matrix)

**Updated**: 2026-10-25 (Prompt 2.1 remediation)
**Code baseline**: `1af5fc6` + Prompt 2.1 remediation
**Planning authority**: `PRODUCT_UPGRADE_ROADMAP.md` (work items `A-01`…`F-08`)
**Architecture contract**: `NEXT_GENERATION_ARCHITECTURE.md`
**Rule**: code + an executed test/receipt is the status source. A checked box in a
plan, a passing schema test alone, or an API returning 200 is not completion.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| **Implemented & Verified** | Code exists and an executed automated test covers the stated scope. |
| **Implemented but Partial** | Code exists but a named capability, path or test is missing. |
| **Known Defect** | Code exists but a confirmed correctness/security defect is open. |
| **Planned** | Designed in the roadmap, not implemented. |
| **Research Required** | Needs a calibrated model, experiment, expert review or user study. |
| **External Dependency** | Blocked on licensed data, account provider, budget or deployment decision. |
| **Not Run** | Harness/code exists but no execution receipt exists. |

Last executed verification at this baseline (2026-10-25): **backend suite 346
passed** (`services/api/.venv/Scripts/python.exe -m pytest services/api/tests/ -q`);
**web typecheck and production build 0 errors**; **Playwright 37 passed / 1
skipped locally** (the skip is the catalogued-but-not-installed case). The R6.1
browser suite adds OAAI sign semantics, model-run status, cross-match clock
alignment, server-confirmed cancellation, mobile section tabs and the phone
tools menu. axe-core WCAG AA remains clean in light and dark themes on Match
Detail, Tactical Explorer and Intelligence Studio. R6/R6.1 screenshots are captured at 1440, 1024,
768, 412, 390 and 360 px and uploaded with the Playwright artifacts. The real-match CI job also runs
`scripts/benchmark_real_match.py` (cold snapshot <8s, warm seek <1s, OAAI cold
<5s) and the provider publication boundary tests. The manual full-corpus CI run
`40158510985` verified **80/80 analysis-ready matches, 302,638 events, all
COMPLETE_VERIFIED**, with 29 corpus tests passed; all five jobs were green.
Measured on that Linux runner: snapshot cold 252ms / warm 4ms, seek cold 111ms /
warm 4ms, OAAI cold 142ms / warm 2ms, Match Detail 621ms.

---

## 1. Capability matrix

`Track` maps each capability to the dependency-driven workstream in the V2
roadmap; it is not a phase claim.

| ID | Capability | Track | Status | Backend / entry | Frontend | Evidence | Current gap / next |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAP-01 | Possession state machine | B | Implemented & Verified | `football.reduce_match` | Match Center | 15 semantics tests | none for on-ball events |
| CAP-02 | Historical clock, periods, extra time, shootout | B | Implemented & Verified | `clock.build_match_clock` + reducer + API bounds | header/scoreboard/detail | `test_clock_semantics.py` + real-match integration | nominal/observed/replayable are distinct; 516 events after 7200s are replayable on `sb_3795221` |
| CAP-03 | As-of score vs official final | B | Implemented & Verified | reducer/state | Evidence Rail | runtime tests | none |
| CAP-04 | Coverage as Unknown, not zero | B | Implemented & Verified | `completeness.py` + coverage object | Evidence Rail/hub/story | fifth-pass tests | none |
| CAP-05 | Content-addressed DatasetRevision | A | Implemented & Verified | `catalog.content_revision_from_events` | rail version | revision tests | migrate pre-revision runs |
| CAP-06 | Licensed StatsBomb import | B | Implemented & Verified | `ingest.py` + completeness verifier + receipt + manifest merge | hub label | `test_data_contract.py`, `test_statsbomb_corpus.py` | payloads stay git-ignored; partial import preserves the catalog; paths are POSIX and hashes verified |
| CAP-07 | Real 2022 final full analysis | B | Implemented & Verified | `sb_3869685` in the ingested corpus | hub + match centre | `test_imported_match_reproduces_the_declared_score` | metrics are heuristic (CAP-09/CAP-10 still open) |
| CAP-08 | Metrics Registry | A | Implemented & Verified | `metrics.py` team×window receipts | charts, Ask, Investigation, Story | fifth-pass metric tests | story phase chapters still count events directly (`B-04`) |
| CAP-09 | Calibrated xG model | B | Research Required | `models/xg.py` heuristic | reports `not_calibrated` | metric tests | calibration remains outstanding |
| CAP-10 | xT grid/fitting | B | Implemented but Partial | `models/xt.py` | Validation Lab | existing tests | static grid; not fitted on complete data |
| CAP-11 | OAAI | B | Implemented & Verified | `oaai.py` + `compute_oaai_contribution_ledger` | OAAI timeline/investigation | ledger recompute tests | heuristic activity index, not momentum or causality |
| CAP-12 | Deterministic Investigation Plan | C | Implemented & Verified | `investigation.py` typed intents | Investigation panel | fifth-pass intent tests | agent-planned routing (`C-06`) not built |
| CAP-13 | Football tool registry for agents | C | Implemented & Verified | `tools.py` allow-list, budgets, receipts | tool receipt list | investigation tests | no cross-request tool cache |
| CAP-14 | Two-agent MAF workflow | C | Implemented but Partial | `agents.py` `Analyst → Verifier` | Story Workbench | CI contract tests | no live model run receipts at this baseline |
| CAP-15 | Third Specialist Agent | C | Planned | — | — | architecture §9.2 | must prove value over deterministic tools |
| CAP-16 | Claim Registry + Gate verdicts | A | Implemented & Verified | `registry.py`, `gate.py` | claim list | trust tests | free-form claim coverage still limited |
| CAP-17 | Claim Revision lifecycle | A | Implemented & Verified | append-only payloads + `SupersessionEvent` | history API + revision timeline | `test_claim_revision_history_is_append_only` | none |
| CAP-18 | Server-side editorial identity | A | Implemented & Verified | `auth.py` | producer token field | auth tests | token roles only; no accounts/SSO |
| CAP-19 | Broadcast queue/rundown/export | E | Implemented & Verified | `broadcast.py` + API + manifest | Producer workspace | fifth-pass rundown/export tests + 409 acceptance | re-review lifecycle (`E-06`) not built |
| CAP-20 | Story as-of / live vs recap | E | Implemented & Verified | story endpoint + cache | Story tab | story boundary test | live pacing is pause-based |
| CAP-21 | Evidence Graph | A | Implemented & Verified | `evidence.py` | inspector/evidence | graph tests + publication boundary tests | event node cap 400; anonymous provider nodes omit pitch coordinates |
| CAP-22 | Cross-match coverage comparison | B | Implemented but Partial | `catalog.get_batch_summary` | Validation Lab | crossmatch tests | stable player/team ID registry incomplete |
| CAP-23 | Explain any chart | D | Implemented & Verified | `explain.py` + ledger | chart click → investigation | fifth-pass ledger tests | none for the OAAI path |
| CAP-24 | What-if sandbox | B | Implemented but Partial | `whatif.py` | Validation Lab | existing tests | research identification not implemented |
| CAP-25 | Stale-run isolation | A | Implemented & Verified | `Run` identity + epoch | — | fourth-pass test | — |
| CAP-26 | Async UI response guards | D | Implemented & Verified | exploration responses | page handlers | Playwright suite in CI (`browser-e2e` job) | — |
| CAP-27 | Match Hub / discover / search | D | Implemented & Verified (R6.1) | `/api/matches` + availability contract | Single header search; query chip and clear; advanced filters collapsed; analysis-ready recommendations first; catalogued matches remain browsable | Playwright library/R6 tests + screenshots | no head-to-head filter yet |
| CAP-28 | URL deep links / refresh restore | D | Implemented & Verified (R6) | — | `page.tsx` URL state | deep-link, popstate-without-push, seek and zero-clock tests | investigation id not yet in the URL |
| CAP-29 | Multi-user drafts/isolation | E | Implemented & Verified (anonymous sessions); accounts External Dependency | session-owned investigations/runs + producer role | — | `test_authorization.py` + Playwright security spec | no SSO/account provider; legacy ownerless records are producer-only |
| CAP-30 | Live multi-agent ablation | F | Not Run | deterministic harness only | — | provenance audit | paid budget + frozen samples required |
| CAP-31 | Real browser/screenshot QA | F | Implemented but Partial (R6.1) | served static export | Playwright + axe-core | 37 passed / 1 skipped locally; screenshots at 1440/1024/768/412/390/360, including each phone section; CI uploads traces and report | no committed visual-diff baselines |
| CAP-32 | Mobile/tablet device QA | D | Implemented & Verified (R6.1) | — | Pixel 7 + iPad Mini + 360/390 viewport captures; phone section tabs, compact tools menu, key-event shortlist | responsive overflow/axe checks on detail, tactical and studio; R6 tab/menu interaction tests | real device and screen reader |
| CAP-33 | Dataset Completeness Verification | A | Implemented & Verified | `completeness.py` (5 states) | ingest receipt, hub, rail, investigation | fifth-pass completeness tests | provider-side declarations trusted only when supplied |
| CAP-34 | Public/Producer broadcast projections | E | Implemented & Verified | `public_claim_projection` / `producer_claim_projection` | Producer workspace | projection test | producer UI is token-based, not account-based |
| CAP-35 | Read-time rundown validity | A | Implemented & Verified | GET rundown revalidation + export 409 | Producer workspace notice | stale-rundown test + live withdrawal acceptance | — |
| CAP-36 | Immutable revision payload | A | Implemented & Verified | `registry._append_revision` | history API | immutability test + live `rev-001` narrowed | none |
| CAP-42 | Legacy registry migration (v1 → v2) | A | Implemented & Verified | `registry._load_legacy` + byte-identical backup | claim list / history API | `test_registry_migration.py` (12 cases) | derived revision 1 is a reconstruction, not a historical review |
| CAP-37 | Question-aware investigation intent | C | Implemented & Verified | `classify_intent` + `UNKNOWN → FAILED` | Investigation panel | intent/invalid-focus tests | metric focus routes at 0.6 confidence, no dedicated EXPLAIN_METRIC intent |
| CAP-38 | Chart→Investigation handoff | C | Implemented & Verified | `InvestigationSeed` + `oaai_point` focus | OAAI timeline drawer | live CP-01 acceptance at `at=54` | none |
| CAP-39 | OAAI contribution ledger | B | Implemented & Verified | `compute_oaai_contribution_ledger` | investigation + `/api/oaai/ledger` | reconciliation test | top-N list plus explicit unlisted remainder |
| CAP-40 | Investigation state machine | C | Implemented & Verified | bounded transitions + persisted store + cancel | state chip/history | fifth-pass state tests | no retry backoff on tool failure |
| CAP-41 | Agent run lifecycle persistence | C | Implemented & Verified (R6.1) | persisted `AgentRunStore` + live request cancellation | investigation cancellation status | `test_slice_b_agentic.py` + R6 browser test | no retry/backoff |
| CAP-43 | Provider corpus curation | B | Implemented & Verified | corpus + selection/refresh scripts + `scripts/verify_corpus.py` | library filters + sample-bias note | 80 matches, all analysis-ready and content-verified | curated functional-acceptance sample; never presented as an unbiased football population |
| CAP-44 | Score and identity cross-verification | B | Implemented & Verified | `/api/matches/{id}/score` (`score.verify_score`) + provider index | detail score verification | real-match test (2-1, own goal counted once) | second source is still the provider index; no independent results oracle |
| CAP-45 | Full-match momentum chart | D | Implemented & Verified | OAAI effective-time recurrence + peak-preserving chart payload | `OAAITimeline` period bands, change points, rug marks | exact oracle test; real match 15s → ~0.3s cold / <10ms warm; Playwright stoppage seek | heuristic activity index, not momentum/causality |

| CAP-46 | Data availability contract | A | Implemented & Verified | `availability.py` + catalog | availability badge, disabled action, install hint | `test_data_contract.py` (catalogued/materialized/tampered) | content hash is re-checked on load; listing uses the import receipt |
| CAP-47 | Provider publication boundary | A | Implemented & Verified | `provider_projection.py` + token-gated full events | public window / protected raw | `test_provider_publication.py` + Playwright security spec | producer token is an operator credential, not an account system |
| CAP-48 | Session-owned private drafts | A | Implemented & Verified | `InvestigationPlan.owner_session_id`, `AgentRunStore` scoping | owner-only lists/actions | `test_authorization.py` (cross-session 404, legacy fail-closed) | anonymous demo isolation only |
| CAP-49 | Real-match performance gate | B | Implemented & Verified | OAAI recurrence + bounded snapshot/OAAI LRUs | loading states | `scripts/benchmark_real_match.py` in CI; numeric invariants | single-worker in-memory caches, no distributed cache |

| CAP-50 | R6 product information architecture | D | Implemented & Verified | static export + existing APIs | Match Hub, Match Detail, Tactical Explorer, Intelligence Studio; Professional tools menu; contextual replay/evidence | `r6.spec.ts`, responsive/a11y, screenshots | producer/research remain token-based tools |
| CAP-51 | Interaction correctness (Space/history/seek/clock) | D | Implemented & Verified | page state layer | replay draft-on-release, one-seek guard, popstate without push, zero-clock guard, match-scoped async results | R6 Playwright interaction suite | no distributed session store |
| CAP-52 | R6.1 semantic and cancellation correctness | D | Implemented & Verified | owner-scoped live-cancel endpoint + cooperative MAF cancellation + agent-run reads | signed OAAI wording with neutral team choice; model availability/current source/latest run split; cross-match clock verify-or-block; server-confirmed cancel; phone tools and section tabs | 3 new backend tests, 7 new R6 browser tests, axe/overflow suite | deterministic cancellation is exercised without a paid model request |

---

## 2. Fifteen-risk audit against code

Verdicts are recorded at the `3746fee`/`ee388ed` baseline with the artifact that
closed each item.

| # | Defect | Risk (user list) | Verdict | Closing evidence |
| --- | --- | --- | --- | --- |
| 1 | DEF-02 | OAAI ignores Team/Window | **Fixed** | team-scoped window query + `test_oaai_metric_respects_team_and_window_and_ledger_recomputes` |
| 2 | DEF-01 | Goals ignores Window | **Fixed** | `_receipt_key` per team/window + `test_goals_metric_respects_team_and_window` |
| 3 | DEF-03 | Ingest completeness by end time only | **Fixed** | `verify_dataset_completeness` + `test_import_does_not_mark_end_time_as_complete` |
| 4 | DEF-04 | Revision append mutates prior revision | **Fixed** | append-only payloads + `SupersessionEvent`; `test_claim_revision_history_is_append_only` |
| 5 | DEF-05 | Narrowed claim reuses statement/scope | **Fixed** | `_revised_observational_card` new statement/scope, gate re-run; live `rev-001` NARROWED |
| 6 | DEF-06 | Investigation question only affects ID | **Fixed** | `classify_intent` selects metrics, tools and gate preview; intent tests |
| 7 | DEF-07 | Invalid focus degrades to generic plan | **Fixed** | `ToolError` paths end in `FAILED` with `unresolved` reasons |
| 8 | DEF-08 | Moment ID vs Sequence ID conflated | **Fixed** | typed `scope` per focus type |
| 9 | DEF-09 | Broadcast queue leaks internal approval data | **Fixed** | public vs producer projections; producer queue requires a token |
| 10 | DEF-10 | Old rundown remains valid after withdrawal | **Fixed** | read-time revalidation + `409 rundown_contains_stale_claims`; UI re-reads after decisions |
| 11 | DEF-11 | MetricsService vs chart calculation divergence | **Partially Fixed** | chart/quick stats read registry receipts; story phase chapters still count events directly |
| 12 | DEF-12 | Story/Export dataset revision and claim state | **Fixed** | `claim_validity` compares dataset revision, pointer, payload and hash at read time |
| 13 | DEF-13 | Investigation UI requires manual IDs | **Fixed** | peak click seeds the investigation; no typed ID needed for the journey |
| 14 | DEF-14 | Third Agent is concept only | **Open by design** | two-agent workflow plus deterministic tools remains the contract |
| 15 | DEF-15 | Real match data is still partial | **Fixed** | 80 provider matches ingested (`COMPLETE_VERIFIED`); the 12-event fixture stays labelled `SPARSE_SAMPLE_FIXTURE` |

---

## 3. Track status (V2)

| Track | Current state | Blocking gap | Next gate |
| --- | --- | --- | --- |
| A — Trust, Identity & Runtime | Metrics, completeness, revisions, validity, projections, idempotency ownership and legacy registry migration closed | none open in this track | agent run persistence (`C-09`) |
| B — Football Data & Analytics | Ledger, receipts and verified coverage; 80 provider matches across 15 competition-seasons (2010-2024) imported and verified | story phase counts; independent score oracle; calibrated xG/xT | B-04, B-06, B-07 |
| C — Agentic Investigation | Typed intent, tool registry, state machine, ledger, promotion, challenge | agent-planned routing; live model receipts | C-06, F-01 |
| D — Football Product Experience | Match library (competition/season pages, provenance, detail panel), producer workspace, deep links, chart handoff, responsive collapse | real device + screen-reader pass; screenshot baselines | D-07 |
| E — Broadcast & Content Production | Producer loop with manifest provenance and read-time validity | accounts/SSO; re-review lifecycle | E-05, E-06 |
| F — Scientific Evaluation & Operations | Backend suite + Playwright browser suite + axe-core a11y in CI | live ablation, real-match performance, user outcomes | F-01, F-04, F-07 |

---

## 4. Release reading

- The local demo is a **real-data, heuristic-metric** build. The corpus is real
  provider payloads (StatsBomb Open Data) and the completeness verifier passes on
  every imported match, but xG/xT are still heuristic and no calibrated model may
  be claimed.
- Synthetic fixtures are `COMPLETE_VERIFIED` by construction and labelled
  synthetic; that is not evidence about real matches.
- The vertical loop is closed and demonstrated in-product: chart peak → ledger →
  investigation → gate → claim → challenge → revision → producer approval →
  rundown → export → manifest, with withdrawal invalidating published content.
- Unproven and unchanged: calibrated xG (`not_calibrated`) and xT fitting, the
  live multi-agent advantage, third-specialist value, and any user-outcome claim.
- Outstanding before a public claim: an independent (non-provider) score oracle,
  screenshot baselines, real-device and screen-reader QA, and live model run
  receipts under an authorized budget.
- The provider agreement forbids redistribution of the payloads themselves. Only
  metadata, receipts and the source manifest are committed; the datasets live in
  git-ignored directories and are fetched by a repeatable script.

---

## 5. Claim registry persistence contract (`claim-registry-v2`)

**File layout.** The on-disk payload is
`{version:"claim-registry-v2", saved_at, claims[], challenges[], revisions[], supersessions[]}`.
A legacy `claim-registry-v1` payload (no `revisions` / `supersessions` keys) is
migrated on load by `services/api/matchlens/registry.py::ClaimRegistry._load_legacy`.

| Situation | Behaviour |
| --- | --- |
| Source file is `claim-registry-v2` | Read as is. No backup, no derived revision, no write. |
| Source file is legacy (or has no `version`) | The file is copied **byte for byte** to `<name>.v1.bak-<YYYYmmddTHHMMSSZ>.json` next to it, then migrated **in memory**. The original file keeps its bytes until an explicit `_save()`. |
| The same legacy file is loaded again | The existing backup with identical content is reused: no second backup, no duplicated revisions, identical derived revision ids. |
| Legacy file carries real revision payloads | That history is kept verbatim; only a missing/unresolvable current pointer is repaired or cleared. A claim with no revision payload stays invalid (`missing_revision_payload`). |
| Legacy claim has no revision history | One **derived** revision is created (`version=1`, `parent_revision_id=None`, `outcome=maintained` for an approved gate verdict and `rejected` otherwise, `status=current`/`disputed`), the record pointer is set to it and `revision_count` becomes 1. |
| Backup cannot be written | The legacy file is **never** overwritten: the migrated state is written to `<name>.v2-unbacked.json`, `persistence_errors` records the blocked write, and `load_errors` records `legacy_backup_failed`. The registry is not emptied. |
| Payload is not valid JSON / not an object | The registry stays **empty**, `load_errors` is non-empty and nothing is approved. The file is left untouched. |
| A single entry fails validation | That entry is skipped and reported; the rest of the payload is still loaded. A broken revision never becomes the current revision, and a claim whose only revision is broken is not broadcastable. |

**Honest limits of the derivation.** A legacy file recorded no review event for
its claims, so the derived "revision 1" is a *reconstruction* of the gate
verdict already stored on the record — not a historical fact. Every derived
revision is marked as such (`created_by="legacy_migration"`,
`review_result.derived_revision=true`, and a rationale that states that no
historical revision payload existed). A legacy `lifecycle_status` other than
`current` (for example `withdrawn`) is preserved, never overwritten.
`ClaimRegistry.load_errors` / `persistence_errors` expose every anomaly; a
non-empty `load_errors` never means "approved".
