# MatchLens AI: Evaluation and Release Gates

R0.1 revision: 2026-10-19. Historical provider results: [TECH_SPIKE](TECH_SPIKE.md). Current product execution/failures: [R0.1_RESULTS](R0.1_RESULTS.md). The full held-out benchmark and S0/S1/M study remain **NOT RUN**. [SPEC](SPEC.md) owns the implemented short-format quantities.

## P0 versus P1

P0 requires the actual vertical slice, arithmetic/invariants, evidence/publication gates, dual-role tools/handoff, failure recovery, browser journey and a few manually inspected football cases. The 72 workflows and external blind assessment are **P1**, not a reason to delay a working product.

| P0 measure | Data / calculation | Pass criterion |
| --- | --- | --- |
| Legal continuous match | Seed17 and additional development seeds, every chapter/full prefix; wrong owner/ID/coordinates/restart negative cases | No accepted illegal event; exact prefix/replay identity |
| Arithmetic | Hand intervals A: 80/180s→150/180s, shots2→0, entries2→0. B: two recovery-shot chains, 8s each. C: one uninterrupted goal possession | Exact counts/durations/source links; defined rounding only |
| Publication | Wrong threat, false causality, contradictory refs, wrong scope, missing conservative variant, unknown/future refs, missing tools, unbound numbers | All invalid cases blocked; a disclaimer never repairs a false core |
| Real collaboration | Uncached actual HTTP runs; verify each role's get_evidence execution and returned tool message, hashed schema-checked handoff | Both roles real, no model fixture; useful accepted football interpretation in at least one complete browser journey |
| Semantic spot review | A/B/C outputs split into facts/inferences; compare every displayed claim against receipts and event chains | No severe unsupported published claim; explicitly record sample size and reviewer. No precision generalization from three cases |
| Recovery | Missing key/schema/provider/timeout/budget/epoch fault injection; real healthy retry after removal | No unfinished draft accepted; facts and exact as-of remain accessible; real healthy run returns after a recorded failure |
| Latency | Per actual run, queue/model times and dispatch count; report all failed runs too | <=25s model deadline +5s queue bound. <=15s successful insight remains a target, not a p95 claim from tiny n |
| Audience difference | Same IDs/refs; manually compare Fan consequence against Analyst comparison/limits | Actual information difference and no extra provider request |
| Browser reliability | Real fresh session → Focus → model → card → receipt → original event → modes/recap, desktop/390px | Journey works; historical as-of and fallback distinguishable. Three clean rehearsals + public ten-minute probe remain release gates |

Raw stage JSON errors are real failures, including successful HTTP responses. A bounded one-format-correction attempt is part of the workflow, counted in latency/cost. It may not silently change an assertion. A simpler flat provider wire schema maps to the canonical claim/variant contract without changing meaning.

The seed17 controlled scenario was revised after a real Verifier identified that a linked recovery lay on a window boundary while the prose treated it as part of the current recovery count. Keep that failed run; generator version `controlled-r01-2` moves the demo recovery inside the window. It is a **development** improvement, not a held-out win. Boundary-clipping regressions remain necessary.

## Evidence levels

Keep four separate records: deterministic correctness; actual model behavior; browser/deployment behavior; audience usefulness. A mocked provider can prove failure handling but cannot establish live AI quality. A real run can fail a gate. A successful local run does not establish public availability.

Every report records release commit, fixture/snapshot hashes, generator/metric/prompt/schema versions, SDK/lock versions, provider, requested/returned model, documented serving version and its dated source, endpoint/API mode, thinking/output options, UTC time, request/trace IDs, origin, usage and durations. A source-listed serving version is not a response-attested model version. Report unknown metadata as unknown. Store product results under `eval/results/<run-date>/<run-id>/`; the isolated Spike uses its own results folder. Exclude credentials/internal reasoning and retain failures.

## P1 broader data and independent oracles

| Set | Contents | Purpose |
| --- | --- | --- |
| D01–D06 | Six small manually countable development windows: legal scoring chain, controlled-time intervals, pass/shot denominators, direction flip, boundary clipping, ownership transfers | Derive exact arithmetic by hand; adjust implementation and trigger thresholds here |
| H01–H03 | Three held-out attacking-activity increases, with different score/location contexts | Useful positive explanations and key moments |
| H04–H06 | Three held-out possession increases without additional penetration | Distinguish possession from danger; avoid unsupported dominance claims |
| H07–H09 | Three held-out recovery/transition windows, including a misleading pressure count | Explain linked events while checking causal/team-tactic overstatement |
| H10–H12 | No meaningful change, insufficient coverage, and conflicting/unsupported supplied proposition | Appropriate quiet periods, qualification or abstention |
| Invalid fixtures | Duplicate/gapped seq, wrong owner, double goal, bad restart, unknown actor, out-of-bounds location | Reject corruption before inference |
| Failure fixtures | Injected provider/network/schema/epoch errors | Recovery mechanics only; labeled as injected |

Use distinct seeds and scenario configurations across development and held-out sets. Freeze held-out fixture hashes, questions, labels and scoring instructions before tuning prompts. Labels specify valid factual relationships, forbidden claims, evidence ranges, answerability and manually justified key-moment intervals. They are not copies of detector outputs or desired prose. Do not use hidden simulation phase boundaries as the key-moment oracle.

The developer creates arithmetic goldens directly from short event tables and labels key moments from visible football evidence before running the detector. A second person reviews labels and ambiguous outputs if available. Otherwise identify the study as single-rater and retain explanations for disputed labels. LLM scoring may triage outputs but is not the sole truth label. Neither labels, scenario intent nor future events enter model tools or prompts.

These fixtures test event-based reasoning on this simulator. They do not validate professional match tactics or generalize a performance estimate to real Premier League feeds.

## P1 broader metrics (P0 subset above)

| Metric | Calculation and data | Target / release consequence |
| --- | --- | --- |
| Event/state validity | All generated prefixes satisfy ownership, restart, score, bounds, period and ID invariants; run 50 seeded matches plus invalid fixtures | Zero invariant violations; all invalid fixtures rejected with an event-specific reason |
| Replay identity | Same seed/version emits same canonical fixture hash and same prefix state/receipts at every chapter; repeated twice | Exact equality; different-seed fixtures must differ |
| Metric arithmetic | Compare all counts, interval sums, denominators and window clipping with D01–D06 hand calculations | Exact integer/rational equality before rounding; display difference <= half the last displayed unit |
| Goal detection | Match each goal candidate to its SHOT event, once | 100% recall and no duplicate scoring/detection |
| Key-moment precision / recall | One-to-one match detector candidates to prelabelled team/type intervals, allowing at most 30 match seconds after the labelled interval end. Precision=matched/emitted; recall=matched/labelled | Each >=0.80 on held-out detectable moments; publish counts by trigger, including false alerts and quiet windows |
| Reference validity | Published refs resolve in the same snapshot/prefix; all displayed slots resolve to their recorded receipt/entity | 100%; a single cross-prefix/future ref blocks release |
| Numeric fidelity | Every displayed factual number equals its cited server value after defined rounding; inspect score, signs and percentage-point language | 100%; no freely generated numeric facts |
| Supported-claim precision | Human-supported atomic published claims / all atomic published claims; include observations and interpretations | >=0.95 and zero severe unavailable-data/causal claims; any unsupported severe claim blocks release |
| Useful coverage | Answerable held-out windows with >=1 useful supported claim / all answerable held-out windows | >=0.80; prevents success through universal abstention |
| Appropriate abstention | Insufficient/conflicting cases correctly withheld or explicitly qualified / all such cases | All three designated H10–H12 outcomes match their specific labels; report individually because n is small |
| Personalization fidelity | Same claim/evidence IDs and no conflicting facts across Fan/Analyst outputs for every published pair | 100% semantic consistency and contract word limits |
| Personalization usefulness | Fan gives a plain-language consequence; Analyst gives comparison, denominator/window and limitation. Human rubric scores each 0/1 on 12 windows | >=10/12 pairs satisfy both view rubrics; do not score a renamed heading as personalization |
| Deterministic latency | Server accepted-event→envelope emission via monotonic clock; browser control→matching state paint is a conservative user-visible measure | Server p95 <=100 ms; control-to-paint p95 <=500 ms at 1x/6x/30x, 100 observations each |
| Insight latency | Candidate enqueued→final publish/withhold/fallback, including queue/tools/format correction, measured server-side | Live successful insight p95 <=15 s; model terminal results <=25s plus <=5s queue wait. Report live success rate and fallback rate alongside latency |
| Recovery | Failure scenarios below; verify actual state and published content | Every injected case meets its behavior; no unreviewed draft appears; next healthy permitted run recovers |
| End-to-end reliability | Three consecutive fresh-session demo journeys plus a ten-minute public transport probe | All complete without manual state repair; at least one journey uses fresh uncached DeepSeek analysis through Agent Framework |
| Reproduction | Clean checkout with documented prerequisites and env configuration | Fixture, UI, evidence and recap run with documented commands; real AI path separately verified with funded endpoint |

For reference and numeric checks use all published content, including deterministic fallback. Deduplicate repeated claim IDs for claim precision, but mark the claim unsupported if either audience version adds an unsupported assertion. Split compound sentences into atomic assertions; unregistered factual prose is a contract failure. `qualified` is supported only if the qualification actually repairs the overstatement. No published claims makes precision **N/A**, not 100%; coverage will fail.

Key-moment matching is chronological and one-to-one, grouped by team/type; duplicate candidates are false positives. Exclude deliberately unanswerable windows only from the corresponding recall denominator and disclose why. Never exclude a timed-out or malformed model result from quality/coverage denominators.

Latency runs use a fixed device/browser, host/revision and concurrency: three active replay viewers, at most two inference workflows globally. Report cold start separately, p50/p95/max, sample count and clock measurement method. Backend durations use one monotonic clock. Browser control-to-paint starts before the control request and ends when the expected seq is painted; do not subtract unsynchronized server/browser clocks. Measure at least 30 real live workflows for each released configuration whose p95 is claimed; the study's 24 M runs can contribute if configuration/load match, with six additional release runs. If only smoke runs are affordable, list individual durations and label the p95 target unverified. Cached results never enter live-inference latency statistics.

## Semantic support rubric

For each atomic claim, review the cited events/receipts and label:

- **Supported:** evidence entails the stated observation, or supports a clearly bounded interpretation without stronger causal language.
- **Qualified but supported:** a visible limitation makes the interpretation proportionate to its window/sample.
- **Unsupported:** wrong relation, missing evidence, invented entity, unavailable metric, contradiction, or causation/intent beyond the data.
- **Not assessable:** missing run artifacts; count as a failed assessment for coverage and report separately.

“Two high recoveries were followed by a shot within ten seconds” can be checked from an ownership chain. “Their coach switched to a successful coordinated high press” cannot be established by these event records. Evidence citation existence alone is not semantic entailment.

## P1: small, fair single-agent versus multi-agent study — NOT RUN

Purpose: test whether a skeptical specialist improves useful evidence-backed output, rather than assuming an extra agent is beneficial.

| Arm | Reasoning process | Budget |
| --- | --- | --- |
| S0: single pass | One analyst writes claim and two audience views | Max3 requests; $0.06 conservative reservation; efficiency reference |
| S1: budget-matched self-review | Same agent/session proposes then critiques its draft | Max6 requests; $0.12 reservation; same per-request byte/output caps as M |
| M: specialist pair | Analyst proposes; fresh Verifier challenges canonical evidence | Same6 requests/$0.12 cap as S1 |

All arms use the same Flash profile/dated alias, thinking disabled, evidence/task/tools, flat JSON Object wire schema, identical gates and **25s workflow deadline**. Per request <=48,000 body bytes and <=1,024 output tokens. S1/M share the same correction allowance and total request/reservation bound. S1 gets the same evidence as M. Do not give treatment stronger validation/model/data. Pro review is separate. Store prompt/option hashes and actual input/output usage; matched caps are not a claim of identical realized spending.

Before implementing P1, separate the **common content gate** (schema/refs/core/slots/scope) from **route audit**. Current product gate deliberately requires two roles/tools/handoff. Requiring that trace from S0 would force the control to fail and invalidate the comparison. Offline S0 submits its primary to the same content predicates with an explicitly unreviewed control decision; S1 submits its self-review selection; M submits its independent review selection. Audit the intended route separately for each arm. Never serve the unreviewed S0 path as a verified product card.

Run12 held-out windows ×2 repeats ×3 arms = **72 workflows**. Randomize/interleave arms at identical concurrency. Do not assume seed/temperature makes DeepSeek deterministic. Worst dispatch ceiling:360, including tool continuations/corrections and no SDK retries. At $0.02/request, reserve up to **$7.20**, separately from product/Spike spending. The conservative byte-as-input-token bound is17.28M input and368,640 output tokens (peak/no-cache estimate $5.626368); actual usage should be far smaller and must be reported. Confirm budget/pricing before this P1 run. Any protocol reduction precedes held-out output inspection.

Blind the human scoring with shuffled output IDs; score before revealing arms. Primary comparison is **M versus S1**. S0 mainly shows the cost/quality tradeoff of a second reasoning stage. Report:

1. Supported-claim precision, useful coverage, appropriate abstention and severe errors.
2. A claim-level confusion/error table and raw per-window outcomes.
3. End-to-end time, requests and tokens; estimated cost only with recorded prices.
4. Paired per-window differences, not 72 independent matches. Summarize the two repeats within each window, then bootstrap windows with replacement (2,000 resamples, fixed analysis seed) for an exploratory 95% interval. The effective window sample is 12.

Preregistered decision rule: describe a **promising improvement on this benchmark** only if M reduces unsupported-claim rate by at least 10 percentage points versus S1, loses no more than 5 points of useful coverage, meets latency targets and produces no severe error. If both systems have no unsupported claims, there is no demonstrated reduction. A wide interval spanning zero is inconclusive; never claim statistical proof or broad superiority. Report negative findings and retain the simpler single-agent path if specialist review adds no useful benefit. Agent-role traces still demonstrate orchestration; they do not demonstrate quality improvement by themselves.

Do not reuse threshold/prompt tuning cases as held-out wins. If prompts change after inspecting the test set, relabel that set as development and create a fresh test set before another comparative claim.

## Failure matrix

| Injection / setup | Required observation |
| --- | --- |
| Missing credentials or 403 | No blind retries, statistics continue and status says AI unavailable |
| 429 with short/long Retry-After | No automatic retry; terminate within the workflow deadline, then permit a bounded manual retry |
| Timeout or 5xx during either agent | No approved interpretation from an unfinished review; fallback facts keep correct snapshot |
| Invalid JSON, numeric literal, unknown event ID | Gate withholds text; a superficially plausible card is never published |
| Verifier withholds or returns partial decisions | Affected claims withheld; accepted unrelated claims retain exact IDs |
| Seek/reset while model is running | Old-epoch result cannot publish into the new replay |
| Repeated analysis / two viewers | Idempotency and cache work; both see correct origin; sessions cannot read each other's runs |
| SSE gap or forced disconnect | No duplicate reducer updates; reconnect receives full authoritative state; public ten-minute probe remains a deployment gate |
| Process restart | Lost sessions explicitly restart; stable fixture can be replayed; no false durable-resume claim |
| Request/token reservation exhausted | No additional billed request is started; live-unavailable status visible; stored results retain provenance |
| Exporter fails | Product continues; run receipt identifies missing external trace |

Injected failures live in evaluation/operator tooling, not a public prompt interface. Label video failure injection if shown. Use a real healthy request after fault removal to establish recovery; a mocked success cannot close the live gate.

## Audience check

P1: ask one casual football viewer and one statistics-oriented viewer to perform five tasks: identify the changed team, explain the consequence, open its evidence, describe one limitation, and distinguish fresh analysis from saved/fallback output. Record completion and confusion, without inventing interviews. Target at least 4/5 tasks per person without hints; fix repeated misunderstandings before adding features. If no external participant is available, report a self-review only and leave audience usefulness unverified.

## Report and go/no-go

Create the real report only after execution. Use columns `metric | target | observed | n/denominator | run IDs | decision`; leave observed values `NOT RUN` until measured. Archive raw receipts before aggregating. The planned scripts and commands are in [ROADMAP](ROADMAP.md).

Release blockers: corrupt fixture or arithmetic, future evidence, unresolved refs, severe unsupported claims, silent mock substitution, no actual AI path, broken fresh-session journey, unlicensed material or no funded/free judging access. Failed comparative uplift blocks the uplift claim, not an otherwise useful release. Missed optional language/visual polish does not block P0. A latency failure requires product simplification and an honest scope change, not removal of failed samples.

## R0.2 rendering control

Keep `bound-facts-v1` identical across S0/S1/M. Measure original typed assertions, draft prose and independent review decisions separately from the deterministic public summary. A safe template is not evidence that a model produced a supported explanation or that two agents improved semantic accuracy. Retain rejection/coverage, raw-draft support and public-render safety as distinct outcomes. Budget-matched live comparison remains NOT RUN.
