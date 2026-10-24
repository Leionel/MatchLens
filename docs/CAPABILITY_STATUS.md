# MatchLens Capability Status (single current matrix)

**Updated**: 2026-10-23
**Code baseline**: `9abe7e3`
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

Last executed verification at this baseline: **209 backend tests passed**;
**web typecheck and production build 0 errors**; GitHub Actions runs
`40063289541` and `40063335191` succeeded. Documentation-only changes after that
run do not alter code status.

---

## 1. Capability matrix

`Track` maps each capability to the dependency-driven workstream in the V2
roadmap; it is not a phase claim.

| ID | Capability | Track | Status | Backend / entry | Frontend | Evidence | Current gap / next |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAP-01 | Possession state machine | B | Implemented & Verified | `football.reduce_match` | Match Center | 15 semantics tests | none for on-ball events |
| CAP-02 | Historical clock, periods, extra time, shootout | B | Implemented & Verified | reducer + StatsBomb adapter | header/scoreboard | semantics/runtime tests | full real file absent |
| CAP-03 | As-of score vs official final | B | Implemented & Verified | reducer/state | Evidence Rail | runtime tests | none |
| CAP-04 | Coverage as Unknown, not zero | B | Implemented & Verified | coverage object | Evidence Rail/story | partial-coverage tests | complete-coverage assertion unverified |
| CAP-05 | Content-addressed DatasetRevision | A | Implemented & Verified | `catalog.content_revision_from_events` | rail version | revision tests | migrate pre-revision runs |
| CAP-06 | Licensed StatsBomb import | B | Implemented but Partial | `ingest.py`, import script | none | import test | no licensed full match supplied |
| CAP-07 | Real 2022 final full analysis | B | External Dependency | loader ready | UI ready | provenance audit | 4,354-event file absent; cannot claim |
| CAP-08 | Metrics Registry | A | Known Defect | `metrics.py` | API only | metrics tests | `DEF-01`/`DEF-02` window semantics; `DEF-11` chart divergence |
| CAP-09 | Calibrated xG model | B | Research Required | `models/xg.py` heuristic | shows n/a | provenance audit | remains `not_available` until calibration |
| CAP-10 | xT grid/fitting | B | Implemented but Partial | `models/xt.py` | Validation Lab | existing tests | static grid; not fitted on complete data |
| CAP-11 | OAAI | B | Implemented but Partial | `oaai.py` | OAAI timeline | arithmetic tests | heuristic activity index, not momentum/causality; no contribution ledger |
| CAP-12 | Deterministic Investigation Plan | C | Implemented but Partial | `investigation.py` | Investigation tab | fourth-pass tests | question does not change plan (`DEF-06`); fixed metric panel |
| CAP-13 | Football tool registry for agents | C | Implemented but Partial | `agents.py` tools | agent workbench | contract tests | tools embedded, no unified registry/budgets |
| CAP-14 | Two-agent MAF workflow | C | Implemented but Partial | `agents.py` `Analyst → Verifier` | Story Workbench | CI contract tests | no live model run receipts at this baseline |
| CAP-15 | Third Specialist Agent | C | Planned | — | — | architecture §9.2 | must prove value over deterministic tools |
| CAP-16 | Claim Registry + Gate verdicts | A | Implemented & Verified | `registry.py`, `gate.py` | claim list | trust tests | free-form claim coverage still limited |
| CAP-17 | Claim Revision lifecycle | A | Known Defect | `registry.py` | history API | history test | `DEF-04` prior status mutation; `DEF-05` narrowed payload reuse |
| CAP-18 | Server-side editorial identity | A | Implemented & Verified | `auth.py` | producer token field | auth tests | token roles only; no accounts/SSO |
| CAP-19 | Broadcast queue/rundown/export | E | Implemented but Partial | `broadcast.py` + API | approve/reject, export gate | broadcast test | `DEF-09` queue leakage; `DEF-10` stale rundown read; no visual workspace |
| CAP-20 | Story as-of / live vs recap | E | Implemented & Verified | story endpoint + cache | Story tab | story boundary test | live pacing is pause-based |
| CAP-21 | Evidence Graph | A | Implemented & Verified | `evidence.py` | inspector/evidence | graph tests | event node cap 400 |
| CAP-22 | Cross-match coverage comparison | B | Implemented but Partial | `catalog.get_batch_summary` | Validation Lab | crossmatch tests | stable player/team ID registry incomplete |
| CAP-23 | Explain any chart | D | Implemented but Partial | `explain.py` | chart click | existing tests | no full OAAI contribution ledger; handoff is manual (`DEF-13`) |
| CAP-24 | What-if sandbox | B | Implemented but Partial | `whatif.py` | Validation Lab | existing tests | research identification not implemented |
| CAP-25 | Stale-run isolation | A | Implemented & Verified | `Run` identity + epoch | — | fourth-pass test | — |
| CAP-26 | Async UI response guards | D | Implemented but Partial | exploration responses | page handlers | typecheck + code | no browser E2E for every race |
| CAP-27 | Match Hub / discover / search | D | Planned | catalog list | no hub page | product gap | new IA (roadmap `D-01`) |
| CAP-28 | URL deep links / refresh restore | D | Planned | — | — | product gap | roadmap `D-03` |
| CAP-29 | Multi-user drafts/isolation | E | External Dependency | token roles only | — | product gap | account provider decision |
| CAP-30 | Live multi-agent ablation | F | Not Run | deterministic harness only | — | provenance audit | paid budget + frozen samples required |
| CAP-31 | Real browser/screenshot QA | F | Implemented but Partial | — | — | fourth-pass results | in-app viewport unavailable; screenshots absent |
| CAP-32 | Mobile/tablet device QA | D | Not Run | — | responsive CSS | product gap | real device + accessibility pass |
| CAP-33 | Dataset Completeness Verification | A | Known Defect | `ingest.py` L69-73 | none | `DEF-03` | end time treated as sufficient; no period coverage receipt |
| CAP-34 | Public/Producer broadcast projections | E | Planned | `main.py` queue | producer token field | `DEF-09` | public queue returns full `ClaimRecord` |
| CAP-35 | Read-time rundown validity | A | Implemented but Partial | `broadcast.py`, `main.py` | rundown view absent | `DEF-10` | build-time checks only; GET returns stored items |
| CAP-36 | Immutable revision payload | A | Known Defect | `registry.py` | history API | `DEF-04`/`DEF-05` | new statement/scope + supersession event required |
| CAP-37 | Question-aware investigation intent | C | Planned | `investigation.py` | Investigation panel | `DEF-06`/`DEF-07` | typed intent and `UNKNOWN` rejection |
| CAP-38 | Chart→Investigation handoff | C | Planned | investigation API | manual focus inputs | `DEF-13` | one-click selection contract |
| CAP-39 | OAAI contribution ledger | B | Planned | `oaai.py` | Explain panel | architecture §7.3 | recomputable event contributions |
| CAP-40 | Investigation state machine | C | Planned | — | — | architecture §8.3 | bounded retries, budgets, cancellation |
| CAP-41 | Agent run lifecycle persistence | C | Implemented but Partial | `agents.py` Run identity/audit | — | stale-run tests | no persisted state machine; roadmap `C-09` |

---

## 2. Fifteen-risk audit against code

Statuses use the requested labels: **Confirmed**, **Partially Fixed**,
**Already Fixed**, **Requires Verification**.

| # | Defect | Risk (user list) | Verdict | Code location | Finding |
| --- | --- | --- | --- | --- | --- |
| 1 | DEF-02 | OAAI ignores Team/Window | **Confirmed** | `services/api/matchlens/metrics.py` OAAI branch L321-328 | Computes the full timeline and selects the global absolute peak; no team sign or requested window. |
| 2 | DEF-01 | Goals ignores Window | **Confirmed** | `metrics.py::_receipt_key` L218-220; query L270 | Returns `goals.match` for every window request, then labels it current/previous. |
| 3 | DEF-03 | Ingest completeness by end time only | **Confirmed** | `services/api/matchlens/ingest.py` L69-73 | `observed_end >= format_seconds - 60` is treated as `C1_OPEN_EVENTS`; sparse start/end events pass. |
| 4 | DEF-04 | Revision append mutates prior revision | **Confirmed** | `services/api/matchlens/registry.py::_append_revision` L186-198 | `history[-1].status = "superseded"` changes a historical payload. |
| 5 | DEF-05 | Narrowed claim reuses statement/scope | **Confirmed** | `registry.py` L217 | New revision copies `record.statement` and original evidence scope; only lifecycle changes. |
| 6 | DEF-06 | Investigation question only affects ID | **Confirmed** | `services/api/matchlens/investigation.py` L280 | Question feeds the plan hash/ID; plan selection is unchanged. |
| 7 | DEF-07 | Invalid focus degrades to generic plan | **Confirmed** | `investigation.py` L144-160 | Missing focus leaves `focus_sequence=None` and continues with the fixed panel. |
| 8 | DEF-08 | Moment ID vs Sequence ID conflated | **Confirmed** | `investigation.py` L152-155 | Both `focus_type` values accept `sequence_id` or `possession_id`. |
| 9 | DEF-09 | Broadcast queue leaks internal approval data | **Confirmed** | `services/api/matchlens/main.py` L1546-1556 | Public GET returns `r.model_dump()` including editorial approver/note/history fields. |
| 10 | DEF-10 | Old rundown remains valid after withdrawal | **Confirmed** | `main.py` L1584-1590 | GET returns the stored rundown without re-checking lifecycle, current revision or dataset revision. |
| 11 | DEF-11 | MetricsService vs chart calculation divergence | **Confirmed** | `exploration.py`, `oaai.py`; `apps/web/app/page.tsx` L279/L292 | Charts still fetch exploration/OAAI endpoints; Registry is not the only computation source. |
| 12 | DEF-12 | Story/Export dataset revision and claim state | **Partially Fixed / Requires Verification** | `stories.py` L137-148; `main.py` L1593-1625 | Story filters current lifecycle and `broadcastable`; export does not explicitly compare claim dataset revision or current revision ID. Add regression tests. |
| 13 | DEF-13 | Investigation UI requires manual IDs | **Confirmed** | `apps/web/app/components/cockpit/InvestigationPanel.tsx` | Focus type/ID are typed by the user; chart selection is not passed. |
| 14 | DEF-14 | Third Agent is concept only | **Confirmed** | `services/api/matchlens/agents.py` L312 | Workflow is two-stage `Analyst → Verifier`; attribution specialist is a deterministic tool layer. |
| 15 | DEF-15 | Real match data is still partial | **Confirmed** | `services/api/matchlens/data/matches/sb_wc2022_final.json` | 12 events only, imported as `C1_PARTIAL`; no complete licensed match exists in-repo. |

No item is `Already Fixed`. Item 12 is the only partial fix; the remaining
dataset-equality check needs a test before it may be called closed.

---

## 3. Track status (V2)

| Track | Current state | Blocking gap | Next gate |
| --- | --- | --- | --- |
| A — Trust, Identity & Runtime | Stale-run/auth/revision lifecycle exist; metrics, revision immutability, completeness and projections are defective | `DEF-01`…`DEF-05`, `DEF-09`, `DEF-10` | Batch 1: A-01, A-02, A-04, A-03, A-05 |
| B — Football Data & Analytics | Importer, registry, xT static grid, OAAI heuristics exist | complete licensed match; chart migration; contribution ledger | B-01, B-04, B-05 |
| C — Agentic Investigation | Deterministic planner and two-agent workflow exist | typed intent, chart handoff, tool registry, state machine, claim promotion | C-01, C-02, C-03, C-05, C-08 |
| D — Football Product Experience | Four cockpit workspaces; responsive CSS | hub, match detail, URL state, real device/a11y | D-01, D-02, D-03, D-07 |
| E — Broadcast & Content Production | Queue/rundown/export APIs + token writes | projections, read-time validity, producer workspace, accounts | E-02/A-05, E-03/A-04, E-01 |
| F — Scientific Evaluation & Operations | Deterministic contract tests only | live ablation, real-match performance, user outcomes | F-01, F-04, F-07 |

---

## 4. Release reading

- The local demo is a **partial-data, heuristic-metric** build. It must not be
  presented as a full-real-match or calibrated-model product.
- Tests passing does not close `DEF-01`…`DEF-15`; each requires the acceptance in
  the roadmap.
- The next release gate is Batch 1 correctness, then the Slice 1 MVP
  (chart → investigation → gate preview without typed IDs), then a complete
  licensed match for Slice 2, then producer projections/manifest for Slice 3.
- The live multi-agent advantage, calibrated xG/xT and product outcome claims
  remain unproven until their named receipts exist.
