# MatchLens AI: Product and Data Specification

R0.1, 2026-10-19 PT. [R0.1_REVIEW](R0.1_REVIEW.md) records changes; [STRATEGY](STRATEGY.md) retains product/competition rationale. This contract maps to `services/api/matchlens` and `apps/web`; execution evidence belongs in [R0.1_RESULTS](R0.1_RESULTS.md).

## User journeys

Answer what changed, why it matters and what supports the interpretation. English, desktop first, keyboard usable, readable at 390 px.

| Journey | Acceptance |
| --- | --- |
| Open/replay | Fictional teams, synthetic **12-minute format**, clock, score and event locations; play/pause, restart, 1x/6x/30x |
| Focus | A at 06:00, B at 09:00, C at 12:00 reconstruct the same match prefix and pause. Analysis displays its fixed as-of time |
| Investigate | Explicit button runs real Analyst → Verifier; queued/analysing/verifying/completed/fallback states |
| Challenge | Inline evidence panel: definition, window, arithmetic, source IDs, original events; selecting an event highlights its coordinates |
| Personalize | Different approved Fan/Analyst prose, same claim/refs, no extra inference |
| Resume | Exit Focus resumes from the focused time; epoch changes isolate late results. Historical cards retain their as-of/snapshot |
| Finish | Score plus accepted session cards form a **12-minute demonstration-match recap**, with no new model claims |
| Recover | Explicit statistics-only result; later bounded healthy run may recover |

A compares possession against penetration; B actively investigates recovery-to-shot chains; C explains the goal sequence. Questions come from computed facts, never expected verdicts. Overlay Preview reuses approved Fan text and the score at that insight's snapshot; no video processing.

## Synthetic match and reducer

One seeded controlled generator produces **148 events at seed 17**, target 140–180, over 720 continuous seconds. This is not a 90-minute or tracking simulation. Hidden phase choices set possession durations/action profiles; seeded pass endpoints/receivers provide reproducible variation. Every chapter is a prefix of the same sequence. Additional seeds are development checks, not real-match validation.

Frozen `Event` fields: `id=E0001…`, contiguous `seq`, strictly increasing integer `t` (seconds 0…720), `kind`, `team=H|N`, roster `actor`, nullable `receiver`, `start/end=[x,y]`, `outcome`. Unknown fields rejected. API additionally exposes reducer-derived **after-event** `possession_id,owner_after,holder_after`; a saved shot therefore reports the keeper's resulting possession. Transition-shot matching uses the shot's pre-transfer possession.

| Kind | Legal transition |
| --- | --- |
| `restart` | Centre kickoff, initially or entitled opponent after a goal; starts possession |
| `pass` | Current holder to a different teammate, complete only; possession retained |
| `recovery` | Opponent gains control at existing ball location; new possession, no duplicate transfer |
| `shot` | Current holder; saved transfers to opponent keeper; goal increments score once and requires kickoff. No extra GOAL event |
| `end` | Current-holder marker at 720s; ends demo match |

Reducer rejects ID/order/time corruption, unknown actors/receivers, non-owner actions, ball discontinuity, coordinate bounds and illegal restart/outcomes. Score is derived. Pitch: stadium metres, 105×68; Harbor +x, Northbridge −x. No halftime direction switch. Failed passes, pressure/fouls, loose balls, substitutions, tracking and full laws/physics simulation are deferred. Correct ownership, score, time and prefix identity are mandatory.

## Deterministic metrics

Previous `(t−360,t−180]`, current `(t−180,t]`, clipped at zero. Clip controlled intervals at boundaries; goal-to-kickoff dead time excluded. Comparative analysis requires two complete 180s windows; incomplete startup metrics are descriptive. Possession/attacking-activity comparisons require complete windows. Recovery-chain detection needs a complete current window; a goal can trigger immediately at its actual event time.

| Receipt | Formula |
| --- | --- |
| `H|N.possession.previous|current` | Team-controlled seconds / both teams' controlled seconds ×100, two-decimal display |
| `…shots.…` | All saved shots and goals |
| `…entries.…` | First completed pass from attack_x <=70 to >70 per possession; later re-entry in same possession excluded |
| `…high_recoveries.…` | Recovery at gaining team's attack_x >=70; not proof of pressing |
| `…transition_shots.…` | Shot <=10s after recovery without intervening loss; link gain/shot and elapsed seconds |
| `H.goals.match` | Harbor goals plus uninterrupted same-team event chain ending in each goal |

Attack_x = x for Harbor, 105−x for Northbridge. Receipt fields: `id,value,unit,event_ids,definition,start,end`, optional `numerator,denominator,chains`. UI does no metric recomputation. Boundary comparisons use counts/durations rather than rounded display values when relevant.

Candidate question: current linked transition shots >=2 → investigate recoveries; otherwise compare possession/shots/entries; an observed goal takes priority. Publication independently checks the assertion. R0.2 scans newly crossed event boundaries, latches candidate questions once per type, and binds each snapshot to its detection time. Default replay is 30x. Optional automatic inference is non-blocking, priority ordered (goal, recovery chain, possession divergence, activity), has a 30-match-second cooldown and at most two auto workflows/session. No hidden phase labels or future events enter tools. Detector generalization remains unmeasured. No xG, player speed, fatigue, formations, coaching intent, predictions or causal effects.

## Evidence and publication

Snapshot = canonical JSON string + SHA-256-derived ID. Includes versions, seed/match ID, format length, as-of, score, receipts, all in-prefix events/intervals and limitations. Copies are returned to callers; no phase labels or future events. Hash proves identity, not truth.

`ClaimDraft={snapshot_id,claims[]}` (1–2). Claim: `id,assertion,primary,conservative?`. Variant: `id=primary|conservative`, `scope=window|match|causal`, receipt `refs`, `fan`, `analyst`. A conservative variant shares the **same core assertion**.

R0.1 provider wire format deliberately emits one flat claim: `snapshot_id,claim_id,assertion,scope,refs,fan,analyst,conservative_fan?,conservative_analyst?`; the two conservative strings must both exist or both be null. Mapping into the canonical contract is mechanical. Review wire is one flat decision. Each role gets at most one same-session format correction, preserving claim/assertion/scope; failed correction closes the run. All original/corrected outputs and requests are retained. No factual repair is performed by code.

| Core assertion | Independent gate predicate / required refs |
| --- | --- |
| `possession_without_penetration` | Possession rises; neither shots nor entries rises; all six comparison receipts |
| `attacking_threat_increased` | Both shots and entries rise; four comparison receipts |
| `recoveries_followed_by_shots` | >=2 linked transition shots plus a current high recovery; both receipts |
| `recoveries_caused_shots` | Unsupported by these events; never publishable |
| `goal_sequence` | Goal and original event chain exist; match scope and goal receipt |

`VerifierDecision={snapshot_id,decisions[]}`. Decision: `claim_id,verdict,selected_variant,reason,limitations[]`; exact decision coverage required.

- `publish` selects supported primary.
- `qualify` selects a supplied conservative variant of that same **true** core; narrowing scope may repair overstatement.
- `withhold` selects no variant: false, contradicted, insufficient/unverifiable assertion or no adequate wording.

A limitation cannot repair an incorrect threat or causal assertion. Verifier cannot write arbitrary replacement prose. No debate loop. Local checks cover schema, identity/refs, complete review, both roles' actual tool-result roundtrips, validated handoff, core predicate, selected scope/variant, required refs and fact slots. Draft prose uses `{{H.shots.current}}` slots; numeric literals, spelled quantities, unknown slots and unavailable/causal concepts are checked. Final public Fan/Analyst facts use the finite `bound-facts-v1` renderer: metric names, periods, values and chain lengths come together from the approved assertion and frozen receipts. Draft language and original Verifier rationale stay in the operator record. This narrows expressive freedom to prevent incidental prose from adding claims; it never rescues a false core. Public review reason/limitations also bind numeric slots. Meaning beyond the bounded predicates requires semantic/manual review; citations alone are not entailment.

Published card: exact selected Fan/Analyst text, claim/assertion/verdict/variant/scope/refs, public review, snapshot/as-of. Result: `origin=live_model|deterministic`, run/model/prompt identity, duration, requests, sanitized audit. Session-cache reuse retains original run/as-of, is identified by UI and incurs no new inference. Fallback contains facts/error status, not a simulated AI answer.

## HTTP/SSE

Same-origin, opaque HttpOnly/SameSite cookie. One fixture; no prompts/uploads/arbitrary paths. Errors use FastAPI `{detail:…}`; expired session 401 requests reload.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/health` | Configuration/liveness, no inference |
| `POST /api/sessions` | Reuse valid cookie or create bounded anonymous session |
| `GET /api/state` | Full authoritative clock/score/prefix/metrics, Focus result and history |
| `POST /api/control` | `focus|exit_focus|play|pause|speed|restart`, optional chapter/speed |
| `POST /api/analyse` | Investigate a Focus or detected snapshot; 202; deduplicate active/completed work, at most one explicit retry of a failed snapshot |
| `GET /api/evidence/{snapshot_id}` | Frozen evidence owned by session, otherwise 404 |
| `GET /api/stream` | `event:state` full JSON on revision change, comment heartbeat |

State contains monotonic epoch/revision; browser ignores stale versions. Reconnect resynchronizes full state; no cursor/ring buffer. P1: polling fallback/public transport probe, arbitrary seek. Recap and old evidence always retain original as-of.

## R0.2 runtime additions

`POST /api/control` also accepts `{action:"focus_moment",moment_id:"…"}` for a previously detected moment at or before the current clock. State returns `moments`, `auto_status`, `snapshot_as_of` and `analysis_receipts`. Live scoreboard receipts advance; analytical comparison receipts stay at the snapshot time. Changing audience never calls a model.

Paid automatic investigation requires `MATCHLENS_AUTO_ANALYSE=1`; free detection is always available. Whole-workflow admission checks six-request runway plus in-flight allowances before creating a task. Per-dispatch SQLite reservations remain authoritative. This is a single-worker deployment. Historical real runs must match the current canonical prefix and pass current gates before import; they retain original snapshot/run IDs and are explicitly marked historical. Original files are never rewritten.
