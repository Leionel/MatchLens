# R6.2 — Final Competition Sprint: Trust, Journey, Presentation

**Baseline**: `057f062` (tag `v6.1-competition-baseline`)
**Scope rule**: fix what makes a real football claim wrong or unreadable; do not
add capability that the user journey cannot reach.

This round is deliberately narrow. The product already had a working shell,
80 real provider matches, MAF investigation, evidence, revision and broadcast.
R6.2 repairs the places where that machinery published a true-looking number or
dropped a real recorded fact, and re-orders the surfaces so the answer comes
before the apparatus.

---

## 1. P0 — correctness

### 1.1 A three-minute window was published as a match total

`Match Detail`'s metrics row read `H.shots.current`, `N.shots.current`,
`H.goals.current` and `N.goals.current`. In this codebase `.current` is the
`[at-180s, at]` window, not the match.

Reproduced on `sb_3795221` (England–Denmark) at 70:00 — the payload both the
real-match and browser CI jobs install, so the regression test pins the same
snapshot the browser suite drives:

| Receipt | Value | Window |
| --- | --- | --- |
| `H.shots.current` | **0** | 4020 s – 4200 s |
| `H.shots.match` | **8** | 0 s – 4200 s |
| `H.possession.current` | **36.15 %** | 4020 s – 4200 s |
| `H.possession.match` | **58.53 %** | 0 s – 4200 s |
| `H.goals.match` | **1** | 0 s – 4200 s |
| `state.score` | **1 – 1** | — |

The scoreboard said 1:1 while the row beside it said 0 shots. Both numbers were
correct; only one of them answered the question the row was asking. The same
trap reproduces on the 2022 final (`sb_3869685`, 0 vs 6 shots, 2:0) and on
`sb_3869685` at 40:00, where possession read 59 % for a window against 62 % for
the match.

**Fix.** The row is now `全场 / Whole match` and reads `.match` only. The live
window is a separate, explicitly labelled strip (`最近 3 分钟 · 2220s–2400s`).
The scoreboard's possession gauge names its own scope (`data-scope="window"`,
`Last 3 min`) so it can never be compared with the match share as if they were
the same measurement. Unobserved receipts render as `—`, never `0`.

### 1.2 Event display and event drawing were one predicate

`state.events.filter((e) => e.start && e.end)` guarded both the pitch and the
event lists. An event with no coordinates is not an unknown event: it is a
recorded event whose position is missing. At 70:00 of `sb_3795221` the filter
deleted 41 of 77 recorded events from the feed; at 40:00 of the 2022 final it
deleted 68 of 160.

**Fix.** `apps/web/lib/eventValidity.ts` separates the two questions:

- `isDisplayable` — identity, clock and kind. Required by every list.
- `isDrawable` — both endpoints. Required only by the 105×68 pitch.
- `isLocatable` — at least one endpoint; enough for a marker.

The feed now lists every readable event; the pitch receives only segments; a
shortlisted event that cannot be placed carries a `no coords` tag instead of
disappearing. The shortlist also ranks by recorded importance (goal > shot >
foul > save > recovery > turnover) rather than by coordinate availability.

### 1.3 A stale investigation could paint over a different context

`InvestigationPanel` guarded responses with a request token, but compared the
response's `match_id` against the match id captured **when the request was
sent** — a value that is equal by construction. It could never detect that the
cockpit had moved on.

**Fix.** The live match id is read at response time through a ref, and the
response is dropped when it belongs to another fixture.

The rest of the isolation follows what each path costs:

| Event | Deterministic run (free) | Paid agent run |
| --- | --- | --- |
| Match switch | reset + server cancel | reset + server cancel |
| Snapshot move | result kept, **labelled** as belonging to the earlier moment | cancelled through the existing server path |

The labelling is a first-class banner (`investigation-stale`) with the result's
moment, the current moment, and a one-click re-run — not a silent replacement.

### 1.4 Story chapters and metric windows disagreed at the boundaries

Two independent defects in `stories.py`:

1. `phase_events` used `start <= t <= end` while every metric receipt uses
   `start < t <= end`. An event exactly on a chapter boundary was counted by two
   chapters and by one metric window.
2. Chapter claim refs used `max(0, as_of - 180) <= chapter_end and as_of >=
   chapter_start`, a 180-second overlap test. A claim observed on a boundary
   satisfied both neighbouring chapters, so the same evidence appeared in two
   narratives.

**Fix.** One interval convention, `(start, end]`, shared by chapters, receipts
and citations. A claim is cited by the chapter that owns its observation
instant. Chapters must tile the match; a gap or an overlap raises
`story_chapters_must_tile_the_match_without_overlap`.

### 1.5 The studio suggested questions it could not answer

All three English suggestion chips and two of three Chinese chips classified as
`UNKNOWN`, so a first-time reader who clicked a suggestion was told the question
was out of scope (`Scope required: focus_type, focus_id, intent`).

**Fix.** The chips are now questions the deterministic planner maps to a
supported intent (`WHY_CHANGE`, `COMPARE_WINDOWS`, `CHECK_SAMPLE`), and a
parametrised test pins the mapping in both languages. A failed plan now states
what actually happened ("no conclusion for the `moment` focus at 0s") instead of
blaming the intent.

---

## 2. P1 — the journey

`real match → notice → explain → evidence → investigate → challenge/revision`

- **Match Detail** leads with score, then one labelled totals row, then the
  live-window strip, then the activity trend. The redundant `events` count moved
  to the Events tab badge it duplicated.
- **AI insight** states what changed, its evidence level, the top recorded
  action, and now what the card *cannot* decide — before the disclosure that
  holds the model/run status.
- **Intelligence Studio** result order is conclusion → evidence → alternative
  explanations → what cannot be decided → action. Tool receipts, the gate audit,
  the OAAI ledger and the agent trajectory live behind one disclosure
  (`investigation-technical`).
- **Event → investigation.** Selecting an event raises a context strip with the
  event's identity, `Locate on pitch`, and `Investigate this event`. The
  selection survives a state tick that no longer carries the event, because the
  selection is an identity, not a membership test.
- **Player → investigation.** `MatchPlayerFocus` reuses `player_spotlight`
  rather than inventing another statistics surface; selecting a player marks
  them on the pitch, and each card opens a `player`-focus investigation.
- **Back to the match.** An investigation result carries `Back to this moment`,
  which seeks the match to the plan's own `as_of` and returns to Match Detail.
- **Real data first.** Recommended matches sort real provider payloads ahead of
  synthetic fixtures regardless of event count, and a synthetic card is labelled
  `Demo · synthetic` on its face.

---

## 3. Verification

Backend: `services/api/.venv/Scripts/python.exe -m pytest services/api/tests/ -q`
→ **364 passed** (346 at the R6.1 baseline). The new
`tests/test_r6_2_boundaries.py` adds 18 cases: the window counterexample, the
goal-vs-score agreement, the possession share identity, the declared-window
rule, unlocated-but-readable events, the goal-without-coordinates rule, the
half-open interval convention, the chapter tiling invariant, the claim
double-count counterexample, chapter monotonicity, no-future-leakage, and the
suggestion-to-intent mapping in both languages. The file runs in the
`real-match` CI job, which installs `sb_3795221`, so it is executed rather than
skipped.

Browser: `npx playwright test` → **47 passed, 1 skipped** (37 + 1 at baseline).
Typecheck and production build: 0 errors.

The demo path is itself a test (`apps/web/e2e/demo-path.spec.ts`): hub →
real match → labelled totals → insight limit → investigation → conclusion and
limits → back to the moment. It is also the capture run for the submission
screenshots in `evidence/r6.2/`:

| File | Surface |
| --- | --- |
| `browser-hub-1440.png` | Match Hub, real payloads first, `Real data` badges |
| `browser-detail-1440.png` | Match Detail: 1:1, `WHOLE MATCH` 8/5 shots, `Last 3 min window 4020s–4200s` 0/0 |
| `browser-detail-390.png` | the same page as a phone overview |
| `browser-investigation-1440.png` | conclusion, evidence with event ids, limits, `Back to this moment` |

Browser (`apps/web/e2e/r6-2.spec.ts`) runs the real corpus:

| Test | What it proves |
| --- | --- |
| match totals | the totals row shows `.match` while the strip shows the empty window |
| feed completeness | the feed lists every readable event, including undrawable ones |
| key event | an unplaceable recorded action is shown and tagged |
| match switch | a mid-flight investigation never appears under another fixture |
| stale label | a result from an earlier snapshot is labelled, not passed off |
| result order | conclusion/evidence/limits first, machinery collapsed |
| event journey | event → investigate → back to the same match moment |
| player journey | player card → investigate, with a real selection |
| layout | 1440/768/390/360 without horizontal overflow |

---

## 4. Carried to the post-competition roadmap

- Second-order boundary work: a live `investigate` that races the deep-link
  clock restore still runs at 0'. The panel now reports it honestly; the fix is
  to gate the action on the session having a frozen snapshot.
- `B-04` is only partly closed: chapters no longer count events with their own
  rule for membership, but the narrative still quotes counts from
  `PHASE_METRIC_IDS` rather than a per-chapter receipt set.
- No visual-regression baselines; axe-core remains the accessibility gate.
- xG/xT calibration, a third agent, and cross-match statistical tests remain out
  of scope by decision, not by omission.
