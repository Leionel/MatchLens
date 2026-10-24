# MatchLens Capability Status (single current matrix)

**Updated**: 2026-10-24
**Rule**: code + executed test is the status source. Roadmap documents are
intent, not evidence.

Status values: **Implemented/verified**, **Implemented/partial**,
**Not implemented**, **Blocked/external**, **Not run**.

| ID | Capability | Status | Backend | Frontend | Data / dependency | Evidence | Current gap / next |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F-01 | Possession state machine | Implemented/verified | `football.reduce_match` | Match Center | event stream | 15 semantics tests | none for on-ball events |
| F-02 | Historical clock, periods, extra time, shootout | Implemented/verified | reducer + adapter | header/scoreboard | provider periods | semantics/runtime tests | full real file absent |
| F-03 | As-of score vs official final | Implemented/verified | reducer/state | Evidence Rail | match metadata | runtime tests | none |
| F-04 | Coverage as Unknown, not zero | Implemented/verified | coverage object | Evidence Rail/story | metadata | partial-coverage tests | full-match coverage unverified |
| F-05 | Content-addressed Dataset Revision | Implemented/verified | `catalog.content_revision_from_events` | rail version | event content | revision test | migration of old runs |
| F-06 | Full StatsBomb import | Implemented/partial | `ingest.py`, script | none | licensed payload | import test | **no licensed full match supplied** |
| F-07 | Real 2022 final full analysis | Blocked/external | loader ready | UI ready | 4,354-event file absent | provenance audit | cannot claim |
| F-08 | Metrics Registry | Implemented/partial | `metrics.py` | API only | event data | metrics tests | chart endpoints not all migrated |
| F-09 | xG calibrated model | Not implemented | `models/xg.py` heuristic | shows n/a | calibrated model | provenance audit | `not_available` |
| F-10 | xT grid/fitting | Implemented/partial | `models/xt.py` | Validation Lab | static grid | existing tests | not calibrated on full data |
| F-11 | OAAI | Implemented/verified | `oaai.py` | OAAI timeline | event data | arithmetic tests | heuristic, not momentum/causality |
| F-12 | Deterministic Investigation Plan | Implemented/verified | `investigation.py` | Investigation tab | snapshot | fourth-pass tests | no LLM planning yet |
| F-13 | Football Tool Registry for agents | Implemented/partial | `agents.py` tools | agent workbench | model key | no live run | no open-ended planner |
| F-14 | Two-agent MAF workflow | Implemented/verified (code) | `agents.py` | Story Workbench | DeepSeek key | CI tests only | live model A/B/C not run |
| F-15 | Third Specialist Agent | Not implemented | — | — | — | provenance audit | needs separate design |
| F-16 | Claim Registry + Gate verdicts | Implemented/verified | `registry.py`, `gate.py` | claim list | snapshot | trust tests | free-form claims still limited |
| F-17 | Claim Revision lifecycle | Implemented/verified | `registry.py` | history API used by claims | registry | history test | visual full-history timeline absent |
| F-18 | Server-side editorial identity | Implemented/verified | `auth.py` | producer token field | env token | auth tests | no real accounts/SSO |
| F-19 | Broadcast queue/rundown/export | Implemented/partial | `broadcast.py` + API | approve/reject, export gate | producer token | broadcast test | no visual rundown editor |
| F-20 | Story as-of / live vs recap | Implemented/verified | story endpoint + cache | Story tab | snapshot | story boundary test | live story pacing is pause-based |
| F-21 | Evidence Graph | Implemented/verified | `evidence.py` | inspector/evidence | registry | graph tests | event node cap 400 |
| F-22 | Cross-match coverage comparison | Implemented/partial | `catalog.get_batch_summary` | Validation Lab | complete matches | crossmatch tests | team/player stable ID registry incomplete |
| F-23 | Explain any chart | Implemented/partial | `explain.py` | chart click | snapshot | existing tests | full OAAI contribution ledger closure incomplete |
| F-24 | What-if sandbox | Implemented/partial | `whatif.py` | Validation Lab | event data | existing tests | research identification not implemented |
| F-25 | Stale-run isolation | Implemented/verified | `Run` identity + epoch | — | — | fourth-pass test | — |
| F-26 | Async UI response guards | Implemented/verified | exploration responses | page handlers | — | typecheck + code | challenge/story handled separately |
| F-27 | Match Hub / discover / search | Not implemented | catalog list | no hub page | — | product gap | new IA |
| F-28 | URL deep links / refresh restore | Not implemented | — | — | — | product gap | add URL state |
| F-29 | Multi-user drafts/isolation | Not implemented | token roles only | — | accounts | product gap | account system |
| F-30 | Live multi-agent A/B/C experiment | Not run | benchmark harness is deterministic | — | model budget | provenance audit | must run with receipts |
| F-31 | Real browser/Screenshot QA | Partial | — | — | in-app viewport | fourth-pass results | screenshots unavailable |
| F-32 | Mobile/tablet device QA | Not run | — | responsive CSS | device | product gap | real device test |

## Release reading

- The local demo can run with the synthetic match and the 12-event partial
  sample.
- It must not be presented as a full-real-match or calibrated-model product.
- The next release gate is a complete licensed match imported through F-06,
  followed by F-21/F-22/F-30 evidence.
