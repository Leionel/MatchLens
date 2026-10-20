# MatchLens AI: Delivery Roadmap

R0.1 revision, Oct 19 PT. Deadline **Oct 27 23:59 PT**; internal submit Oct 27 18:00. **Feature freeze Oct 25 18:00; preserve Oct 26 for deployment/rehearsal/video.** See [R0.1_REVIEW](R0.1_REVIEW.md) for decisions and [R0.1_RESULTS](R0.1_RESULTS.md) for actual work, including failures.

Replace 42h P0 with **44–58h core implementation/QA + 8–10h deployment/docs/video + 6h reserve**. This is demanding for one developer; cut optional work before consuming recording day. The full simulator, generalized seek/cache framework and complete 72-workflow comparison no longer block P0.

## Priorities

| Priority | Scope |
| --- | --- |
| P0 | One legal continuous 12-minute/140–180-event scenario; deterministic receipts; three Focus chapters; real MAF Analyst/Verifier; evidence/publication gates; Fan/Analyst; linked recap; honest fallback; global/session budgets; local and judge-accessible test path; English README and real <120s video |
| P1 | General candidate ticks/cooldowns; wider event/held-out cases; S0/S1/M matched study; external audience check; polling/public ingress hardening; measured visual polish |
| P2 | Additional language/favorite perspective; durable workflow checkpoint only for a concrete need |
| Out of scope | Full 90-minute simulator, tracking/CV/video ingestion, xG/win probability, formations/coaching causality, open chat, third agent, RAG/MCP/A2A, Kafka/Kubernetes, multiple services/replicas |

## Daily implementation boundaries

| Date / effort | Goal, dependency and concrete tasks | Acceptance | Downgrade / visible value |
| --- | --- | --- | --- |
| **Oct 19–20 / 12–16h** | Tracer bullet: controlled generator/reducer → receipts/frozen snapshot → tested MAF route → gates → HTTP → real browser. Depends on local key, not Azure. Add false-core/causal/contradiction tests, Focus, evidence click and local receipt | Real dual-role tools/handoff, at least one useful accepted football interpretation, inspectable raw events; failed outputs retained, no scripted answers | Simplify UI/event variety first; preserve all correctness gates. Viewer can challenge an actual explanation |
| **Oct 21 / 7–9h** | Three-chapter continuity, positive recovery discovery, goal chain/recap, audience distinction. Cover schema/failure recovery and replay epochs. Confirm host and total funded runway | A/B/C same prefix; B meaningful chain; C score/goal source; old results isolated; real healthy run after failure | Fixed three cutoffs only, no arbitrary seek. A complete short football story |
| **Oct 22 / 7–9h** | Container/static build; authorized host; persistent global budget; rate/origin/session controls; direct deployed-host DeepSeek probe | Public fresh session, actual provider call, 10-minute stream/reconnect, key absent from bundle/logs; one worker/replica | Use 1s polling if ingress streams fail, or alternate authorized simple host. Do not wait for Azure role |
| **Oct 23 / 7–9h** | P0 regression/failure coverage, a few manually reviewed football runs; readability/keyboard/mobile; inspect evidence and replay after faults | No future refs/unbound numbers/false core; documented live outcomes and failure recovery, 390px path | Stop P1 experiments; no external quality/uplift claim without data. Judge understands why insight matters |
| **Oct 24 / 7–9h** | Clean setup/README, license/provenance, free judging access; real fresh-session journeys. P1 only if P0 stable | Another checkout builds/runs; three journeys; useful Fan/Analyst differences; host budget through Nov 10 | Skip paired study and optional polish; mark NOT RUN. Reproducible usable release |
| **Oct 25 / 4–6h** | Fix release candidate, package evidence, prompts/thresholds freeze at18:00. Optional P1 matched study consumes separate capacity only | Release/image IDs, actual reports, no planned feature in pitch; rollback retained | Publish incomplete study honestly; no new contracts/features |
| **Oct 26 / 7–8h reserved** | Final deployment check, three rehearsals, real capture, English narration/captions, <=115s edit | Fresh funded judge path; video actually <120s, legible, public URL works | Fix/re-record affected scene only. No optional feature rescue |
| **Oct 27 / 1–2h +6h reserve** | Rules/portal/links/access recheck and submit by18:00 | Public repo/test/video, received submission, retained release SHA | Reserve for defects/upload only |

Core effort above sums 44–58h; deployment/docs/video finalization adds 8–10h beyond core work, plus 6h reserve. P1 is uncommitted and must not make this calendar longer. Record actual remaining effort after the tracer bullet rather than counting its unit tests as product completion.

## Executable next tasks

| Ticket | Dependency / deliverable | Done means |
| --- | --- | --- |
| R01 | First actual browser/live slice | `football.py`, `contracts.py`, `agents.py`, `main.py`, UI and real run artifacts agree; inspectable accepted claim |
| R02 | R01; harden bounds/recovery | Persistent reserve-before-send, session/IP limits, duplicates, cancellation-resistant stale result, timeout/schema/missing-key fallback; healthy live retry |
| R03 | R01; football/story | Manual A/B/C review with source chains, same-match recap and audience difference; no expected verdict in model input |
| R04 | R01/R02; host | Authorized funded host, persistent ledger, actual outbound/provider call and public transport probe |
| R05 | R01–R04; release | Clean-checkout setup, English materials, actual screenshot/video, free judge access through Nov10 |
| R06 P1 | Stable prompts/held-out data and separate budget | S0/S1/M protocol in EVALUATION; failures included; no uplift claim until results exist |

No blank horizontal scaffold. Implement one demonstrable boundary at a time. Any changed API/metric requires SPEC + backend + consumer + affected regression together.

## Verification commands

From root: `uv sync --project services/api`; `(cd services/api; uv run pytest -q)`; `npm --prefix apps/web ci`; `npm --prefix apps/web run typecheck`; `npm --prefix apps/web run build`.

Start: `powershell -File scripts/run.ps1`. Actual configured live HTTP journey: `services/api/.venv/Scripts/python.exe scripts/live_validation.py --out evidence/r0.1/new-run.json`. This spends requests under the persistent global cap. Prior Spike cap remains separate and unchanged. Never rerun paid work just because docs changed.

Hosting probe, complete paired experiment and final media verification remain release tasks until their entrypoints/artifacts exist. A successful local build is not public deployment; a real tool trace is not a quality comparison.

## Next 24 hours: five priorities

1. Close and record the real product tracer bullet, including its failed outputs and corrected schema protocol.
2. Manually review A/B/C for football meaning, source alignment and Fan/Analyst difference; correct publication or wording failures before broad tests.
3. Finish timeout/budget/session/epoch regressions and demonstrate a real healthy analysis after a failure.
4. Select an accessible authorized host, confirm production/judging budget, and test its actual DeepSeek egress. Foundry is not a dependency.
5. Deploy the thin slice and rehearse the 115s story. Stop optional work if it consumes Oct26.
