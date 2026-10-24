# MatchLens Capability Status (single current matrix)

**Updated**: 2026-10-24
**Code baseline**: `3746fee` (backend), `ee388ed` (web), `.gitignore` `91b6fee`
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

Last executed verification at this baseline: **218 backend tests passed**
(`services/api/.venv/Scripts/python.exe -m pytest services/api/tests/ -q`);
**web typecheck and production build 0 errors**. In-app browser acceptance ran the
full journey (chart peak → ledger → investigation → gate → claim → challenge →
revision) and the producer path (queue → approve → order → validate → export →
manifest) against the served build, and refused export with
`409 rundown_contains_stale_claims` after a withdrawal.

---

## 1. Capability matrix

`Track` maps each capability to the dependency-driven workstream in the V2
roadmap; it is not a phase claim.

| ID | Capability | Track | Status | Backend / entry | Frontend | Evidence | Current gap / next |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAP-01 | Possession state machine | B | Implemented & Verified | `football.reduce_match` | Match Center | 15 semantics tests | none for on-ball events |
| CAP-02 | Historical clock, periods, extra time, shootout | B | Implemented & Verified | reducer + StatsBomb adapter | header/scoreboard | semantics/runtime tests | full real file absent |
| CAP-03 | As-of score vs official final | B | Implemented & Verified | reducer/state | Evidence Rail | runtime tests | none |
| CAP-04 | Coverage as Unknown, not zero | B | Implemented & Verified | `completeness.py` + coverage object | Evidence Rail/hub/story | fifth-pass tests | none |
| CAP-05 | Content-addressed DatasetRevision | A | Implemented & Verified | `catalog.content_revision_from_events` | rail version | revision tests | migrate pre-revision runs |
| CAP-06 | Licensed StatsBomb import | B | Implemented but Partial | `ingest.py` + completeness verifier + receipt | hub label | `test_import_does_not_mark_end_time_as_complete` | no licensed full match supplied |
| CAP-07 | Real 2022 final full analysis | B | External Dependency | loader ready | hub labels it `SPARSE_SAMPLE_FIXTURE` | provenance audit | 4,354-event file absent; cannot claim |
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
| CAP-21 | Evidence Graph | A | Implemented & Verified | `evidence.py` | inspector/evidence | graph tests | event node cap 400 |
| CAP-22 | Cross-match coverage comparison | B | Implemented but Partial | `catalog.get_batch_summary` | Validation Lab | crossmatch tests | stable player/team ID registry incomplete |
| CAP-23 | Explain any chart | D | Implemented & Verified | `explain.py` + ledger | chart click → investigation | fifth-pass ledger tests | none for the OAAI path |
| CAP-24 | What-if sandbox | B | Implemented but Partial | `whatif.py` | Validation Lab | existing tests | research identification not implemented |
| CAP-25 | Stale-run isolation | A | Implemented & Verified | `Run` identity + epoch | — | fourth-pass test | — |
| CAP-26 | Async UI response guards | D | Implemented but Partial | exploration responses | page handlers | typecheck + in-app checks | no automated browser E2E suite in CI |
| CAP-27 | Match Hub / discover / search | D | Implemented & Verified | `/api/matches` | `MatchHubWorkspace` | in-app acceptance (7 matches, correct labels) | no competition/date filters beyond text search |
| CAP-28 | URL deep links / refresh restore | D | Implemented & Verified | — | `page.tsx` URL state | in-app restore + back/forward | investigation id not yet in the URL |
| CAP-29 | Multi-user drafts/isolation | E | External Dependency | token roles only | — | product gap | account provider decision |
| CAP-30 | Live multi-agent ablation | F | Not Run | deterministic harness only | — | provenance audit | paid budget + frozen samples required |
| CAP-31 | Real browser/screenshot QA | F | Implemented but Partial | served static build | in-app DOM acceptance | journey + producer logs above | no screenshot baselines; no CI browser job |
| CAP-32 | Mobile/tablet device QA | D | Implemented but Partial | — | 390px and 820px viewport probes | zero page overflow across six workspaces | real device, screen reader, touch feel |
| CAP-33 | Dataset Completeness Verification | A | Implemented & Verified | `completeness.py` (5 states) | ingest receipt, hub, rail, investigation | fifth-pass completeness tests | provider-side declarations trusted only when supplied |
| CAP-34 | Public/Producer broadcast projections | E | Implemented & Verified | `public_claim_projection` / `producer_claim_projection` | Producer workspace | projection test | producer UI is token-based, not account-based |
| CAP-35 | Read-time rundown validity | A | Implemented & Verified | GET rundown revalidation + export 409 | Producer workspace notice | stale-rundown test + live withdrawal acceptance | — |
| CAP-36 | Immutable revision payload | A | Implemented & Verified | `registry._append_revision` | history API | immutability test + live `rev-001` narrowed | pre-v2 registry records need migration review |
| CAP-37 | Question-aware investigation intent | C | Implemented & Verified | `classify_intent` + `UNKNOWN → FAILED` | Investigation panel | intent/invalid-focus tests | metric focus routes at 0.6 confidence, no dedicated EXPLAIN_METRIC intent |
| CAP-38 | Chart→Investigation handoff | C | Implemented & Verified | `InvestigationSeed` + `oaai_point` focus | OAAI timeline drawer | live CP-01 acceptance at `at=54` | none |
| CAP-39 | OAAI contribution ledger | B | Implemented & Verified | `compute_oaai_contribution_ledger` | investigation + `/api/oaai/ledger` | reconciliation test | top-N list plus explicit unlisted remainder |
| CAP-40 | Investigation state machine | C | Implemented & Verified | bounded transitions + persisted store + cancel | state chip/history | fifth-pass state tests | no retry backoff on tool failure |
| CAP-41 | Agent run lifecycle persistence | C | Implemented but Partial | `agents.py` Run identity/audit | — | stale-run tests | no persisted state machine; roadmap `C-09` |

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
| 15 | DEF-15 | Real match data is still partial | **Open (external)** | 12-event fixture is now labelled `SPARSE_SAMPLE_FIXTURE` everywhere instead of complete |

---

## 3. Track status (V2)

| Track | Current state | Blocking gap | Next gate |
| --- | --- | --- | --- |
| A — Trust, Identity & Runtime | Metrics, completeness, revisions, validity, projections and idempotency ownership closed | pre-v2 registry migration review | B-04 residual and CI browser job |
| B — Football Data & Analytics | Ledger, receipts and verified coverage; import labels sparse fixtures honestly | complete licensed match; story phase counts | B-01, B-04 |
| C — Agentic Investigation | Typed intent, tool registry, state machine, ledger, promotion, challenge | agent-planned routing; live model receipts | C-06, F-01 |
| D — Football Product Experience | Hub, producer workspace, deep links, chart handoff, responsive collapse | real device + screen-reader pass; screenshot baselines | D-07 |
| E — Broadcast & Content Production | Producer loop with manifest provenance and read-time validity | accounts/SSO; re-review lifecycle | E-05, E-06 |
| F — Scientific Evaluation & Operations | 218 deterministic tests + in-app acceptance | live ablation, real-match performance, user outcomes | F-01, F-04, F-07 |

---

## 4. Release reading

- The local demo is a **partial-data, heuristic-metric** build. It must not be
  presented as a full-real-match or calibrated-model product; the hub, rail and
  completeness endpoint now say so explicitly.
- Synthetic fixtures are `COMPLETE_VERIFIED` by construction and labelled
  synthetic; that is not evidence about real matches.
- The vertical loop is closed and demonstrated in-product: chart peak → ledger →
  investigation → gate → claim → challenge → revision → producer approval →
  rundown → export → manifest, with withdrawal invalidating published content.
- Unproven and unchanged: calibrated xG (`not_calibrated`) and xT fitting, the
  live multi-agent advantage, third-specialist value, and any user-outcome claim.
- Outstanding before a public claim: a complete licensed match, a CI browser job
  with screenshot baselines, real-device and screen-reader QA, and live model run
  receipts under an authorized budget.
