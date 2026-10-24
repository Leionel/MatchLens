# MatchLens Football Semantics Specification

**Version**: 1.0 (third-pass)
**Code contract**: `services/api/matchlens/football.py::reduce_match`
**Status**: Enforced by `services/api/tests/test_third_pass_semantics.py`

This document defines the only admissible semantics for turning provider
events into possession, time, score, spatial and coverage state. Any code path
that bypasses `reduce_match` for these quantities is a contract violation.

---

## 1. Event identity and normalization

1. Canonical team codes are exactly `H` and `N`.
2. Provider identity is retained separately:
   - `NormalizedEvent.provider_team_id` — StatsBomb numeric team ID.
   - `NormalizedEvent.provider_team_name` — display name only.
   - `NormalizedEvent.possession_id` — provider possession ID, retained verbatim.
3. Home/away is resolved **only** from an explicit mapping:
   - `MatchMetadata.home_provider_team_id` / `away_provider_team_id`
   - or an explicit `team_map` / `home_team_id` / `away_team_id` passed to the reducer.
4. Name-substring inference (`"arg" in name`, `"home" in name`) is forbidden.
   An unmapped team raises `unmapped_provider_team`; it is never guessed.
5. Provider events are canonicalized in `MatchCatalog.load_normalized_events`
   by exact provider-ID mapping. Unknown IDs raise instead of being dropped.

---

## 2. Possession state machine

A possession is a continuous interval of observed control by one team.

### 2.1 Possession starts

A new possession ID is minted only when:

| Boundary | Reason code |
| --- | --- |
| First recorded event | `match_start` / `restart` |
| Restart / kick-off after a goal | `goal_restart` |
| Restart / half start | `restart` |
| Observed gain by the other team (recovery / interception / tackle) | `observed_gain` |
| Provider possession ID changes within the same team | `provider_possession_change` |
| Observed team change on a recorded event | `observed_team_change` |
| Data discontinuity larger than `max_gap_seconds` | `after_data_gap` / `observed_event` |
| First event after a shot ended the previous control | `after_shot` |
| A shot with no recorded build-up | `shot_without_buildup` |

### 2.2 Possession ends

Control ends at the event that terminates it:

- shot (saved, blocked, off-target or goal) — the shot belongs to the
  attacking possession, then control ends;
- goal / own goal;
- foul, dispossession, clearance, period end, final whistle;
- an observed gain by the opponent;
- a data gap.

Consecutive passes, carries, dribbles and other same-team actions **do not**
create a new possession. `possession_id` is stable for the whole sequence.

### 2.3 Controlled time

- Controlled time belongs to the possession owner, from the possession start
  timestamp to the possession end timestamp.
- The current event's team is **never** used to label the preceding interval.
- A gap larger than `max_gap_seconds` (default 15s) is recorded as
  `unobserved_intervals[{reason: "data_gap"}]`; it is not assigned to either
  team and is not treated as continuous possession.
- A half-time / period transition closes the possession at the last observed
  event and records `period_break`.
- A goal restart gap is recorded as `dead_ball` (its 2s is not controlled).
- For continuous data, a saved shot transfers control to the goalkeeper side
  at the save instant (`shot_rebound`); for partial data, that interval stays
  unknown until the next recorded touch.
- The final possession is extended to the requested `at` **only** when
  coverage is continuous. Partial coverage closes at the last observed event
  and records `coverage_end`.

### 2.4 Provider possession IDs

- `provider_possession_ids` is stored on each possession.
- Provider IDs are used as a boundary signal when present, but canonical
  possession IDs remain monotic integers local to the reduced state.
- Provider ID changes are visible in the possession record; inferred
  boundaries carry an explicit `start_reason`.

---

## 3. Coordinates

1. Pitch is 105m × 68m, inclusive bounds. `0` and `105` / `68` are legal.
2. Missing coordinates are `None`. They are **never** replaced by
   `(52.5, 34.0)` or any other pitch location.
3. `start` is `null` when either x or y is missing. `end` is `null` when the
   provider does not supply a valid end location; it is not copied from the
   start.
4. `located = false` events:
   - still count toward event totals and possession time;
   - are excluded from spatial metrics (entries, zones, channels, box touches,
     high recoveries, xT/OAAI spatial terms);
   - produce `value = null` / `status = "unobserved"` where a spatial
     denominator is empty.
5. Provider coordinates are standardized per event. StatsBomb coordinates are
   already attack-relative; the reducer marks them
   `coordinate_frame = "team_relative"`.
6. Synthetic coordinates use a fixed physical frame
   (`coordinate_frame = "fixed"`): H attacks right, N attacks left.
7. Downstream code must use `event_attacking_x()` / `event_channel()`, never a
   raw `x` with an assumed direction.

---

## 4. Match clock, periods and attack direction

| Provider field | Rule |
| --- | --- |
| Period 1 | match clock = period-relative seconds |
| Period 2 | 45:00 + period-relative time (or absolute minute when no timestamp) |
| Period 3/4 (extra time) | 90:00 / 105:00 + period-relative time |
| Period 5+ (shootout) | 120:00 + period-relative time; `is_shootout = true` |
| Stoppage time | preserved by provider minute/timestamp; never clamped to 45/90 |
| Attack direction | per-event `attack_direction`; frame decides whether x is physical or attack-relative |
| Half-time | possession closed; `period_break` gap recorded; no control across the break |

Shootout goals increment `shootout_score`, never the match `score`.

---

## 5. Score semantics

The reducer emits three separate fields:

| Field | Meaning |
| --- | --- |
| `score` | Goals **observed up to `at`** (`score_basis = "observed_prefix"`) |
| `official_score` | Provider's official final score, or `null` when not supplied |
| `shootout_score` | Penalty-shootout goals only |

Rules:

1. A goal is credited to the attacking team.
2. An own goal (`outcome = "own_goal"`) is credited to the opponent.
3. `own_goal_for` (provider already credits the beneficiary) is credited to
   the recorded team.
4. Shootout goals never enter `score`.
5. Partial summaries must not project the official final score backwards.
   A `2–2` observed prefix may coexist with an official `3–3` final.
6. `coverage.score_status` is `complete`, `prefix` or `partial_prefix`.

---

## 6. Coverage contract

State exposes:

```text
coverage.format_seconds
coverage.observed_start / observed_end / observed_span_seconds
coverage.controlled_seconds
coverage.unobserved_seconds
coverage.continuous
coverage.time_coverage
coverage.event_coverage           # null when the expected count is unknown
coverage.event_coverage_status   # "complete" | "unknown"
coverage.event_count
coverage.score_status
```

Rules:

1. Unobserved is not zero. A possession share with a zero denominator is
   `value = null`, `status = "unobserved"`.
2. Unobserved is not persistence: the tail after the last observed event is
   never credited to the last owner unless coverage is continuous.
3. Partial fixtures are labeled `C1_PARTIAL` and cannot produce per-90 rates
   (`rate_status = "withheld_partial_coverage"`).
4. Event coverage and time coverage are separate fields; neither may be
   inferred from the other.
5. A snapshot is never queried beyond `MatchContext.duration`.

---

## 7. Derived quantities

- `metric_receipts` uses possession IDs from the state machine. A shot belongs
  to the possession that produced it; saved shots are not detached.
- `build_sequences` groups by canonical possession ID and includes only real
  events.
- A receipt with no supporting event IDs must not be rendered as numeric 0
  when its denominator is unknown.
- Spatial counts (entries, high recoveries, box touches) require
  `located = true` and use the event's own coordinate frame.
- Player names come from recorded actors (`actor_name`), never from a
  synthetic roster keyed by `H6`/`N8`.

---

## 8. Invariants enforced by tests

1. Same-team consecutive passes keep one possession ID.
2. Alternating control produces exactly two possessions and correct time
   attribution to the previous owner.
3. Multiple events at one timestamp do not split possession.
4. Coordinates `0` and `105/68` are preserved; missing coordinates stay null.
5. Half-time is not controlled possession.
6. Goal + restart creates a new possession and an as-of score.
7. Own goals credit the opponent; shootout goals do not change the score.
8. Partial coverage never extends possession to the match end.
9. A data gap is unknown, never continuous control.
10. Unmapped provider teams are rejected, not guessed.
11. Shot, possession, sequence and metric receipts share the same possession ID.
12. Synthetic and normalized streams obey the same monotonic possession-ID
    contract.

Test file: `services/api/tests/test_third_pass_semantics.py`.
