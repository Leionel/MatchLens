# Third-Pass Deep Audit & Semantic Integrity Remediation

**Repository**: https://github.com/Leionel/MatchLens
**Review baseline**: `9b9bb4c752ce497e86cf3f07fd8a49d2a40d07d7` (HEAD at start: `e317451`)
**Audit date**: 2026-10-23
**Auditors**: Football Data Architect / Multi-Agent Reliability Engineer / Research Integrity Auditor / Senior QA Engineer (single-agent execution, no external reviewers)

This pass did not ask “is the feature implemented?”. It asked “does the
output mean what the product says it means?”. Each finding below was
reproduced against the baseline before it was fixed.

---

## P0-A — Football reducer semantics

### A1. Possession time was credited to the next owner

**Finding**: In the normalized-event branch of `reduce_match`, `owner` was
overwritten with the current event's team *before* appending the interval from
the previous event to the current event. The interval was therefore labelled
with the team that took over, not the team that had controlled the ball.

**Reproduction** (baseline): a sequence `H pass @0, H pass @10, N recovery @20`
produced an interval `[0,20] team=N`. Expected `[0,20] team=H`.

**Fix**: `reduce_match` now implements a possession state machine. Control is
closed at the boundary event with the previous owner; a new possession starts
at the boundary. Intervals are emitted per possession, never per adjacent-event
pair. Missing / dead / period-break / data-gap intervals are separate.

**Tests**: `test_possession_time_belongs_to_previous_owner_not_next_event`,
`test_half_time_break_is_not_attributed_as_possession`,
`test_data_gap_is_unknown_not_continuous_possession`.

### A2. `possession_id` incremented on every event

**Finding**: the normalized branch executed `possession += 1` for every event;
consecutive passes, carries and the shot all had different IDs. Provider
possession IDs were parsed but discarded.

**Fix**:
- canonical possession IDs advance only at defined boundaries (restart, goal
  restart, observed gain, provider possession change, observed team change,
  data discontinuity, after shot);
- `provider_possession_id` is retained on every event and on the possession;
- `start_reason` records why a possession was opened;
- `build_sequences` no longer needs the “saved shot = pid − 1” hack.

**Tests**: `test_same_team_consecutive_passes_keep_one_possession`,
`test_shots_sequences_and_metrics_share_one_possession_identity`,
`test_adapter_preserves_provider_possession_and_team_ids`.

### A3. Zero coordinates were replaced by pitch centre

**Finding**: normalized events used expressions such as `x or 52.5`,
`y or 34.0`, `end_x or raw_x`. Legal `0` coordinates were falsy and became
`52.5/34.0`; missing end locations were silently copied from the start.

**Fix**:
- `_location_pair` preserves `None` and validates inclusive `[0,105]×[0,68]`;
- `start`/`end` are `null` when absent; `located` is explicit;
- `state["ball"]` is `null` until a located event is observed;
- spatial metrics skip unlocated events; possession time still counts.

**Tests**: `test_zero_and_pitch_boundary_coordinates_are_preserved`,
`test_missing_location_is_unknown_never_pitch_centre`.

### A4. Team / direction / identity inference

**Finding**:
- `t_mapped = "H" if "arg" in raw_team.lower()` (and `"home"`) guessed the
  home team from a display name;
- `MatchCatalog.get_match_context` used the same substring trick;
- possession kind mapping collapsed carries into passes and treated “Half End”
  as a restart;
- attack direction was assumed fixed for all providers, although StatsBomb
  coordinates are already attack-relative;
- own goals were credited to the event team; shootout goals entered the score.

**Fix**:
- explicit `home_provider_team_id` / `away_provider_team_id` in metadata
  (`sb_wc2022_final`: 779 / 771; values taken from the bundled event file);
- `MatchCatalog.load_normalized_events` canonicalizes by exact provider ID and
  raises on unknown IDs;
- `coordinate_frame = "fixed" | "team_relative"` is carried on every event;
  `event_attacking_x` / `event_channel` are the only downstream accessors;
- carries are `carry`; `Half End` is `period_end`; shootout is period ≥ 5;
- `own_goal` credits the opponent; `own_goal_for` credits the recorded team;
  shootout goals go to `shootout_score`.

**Tests**: `test_unmapped_provider_team_is_rejected_not_guessed`,
`test_own_goal_credits_opponent_and_shootout_does_not_change_score`,
`test_adapter_preserves_provider_possession_and_team_ids`.

### A5. Synthetic and normalized consistency

The reducer is shared by both branches. Synthetic generation still validates
ID/order/actor/ball continuity/restart/goal-mouth/coordinate bounds, and the
same state machine produces the intervals and possession IDs. Existing
synthetic arithmetic oracles (80/180→150/180, 2→0 shots, 2→0 entries, 8s
transition chains, 718 controlled seconds) remain green.

Test file: `services/api/tests/test_third_pass_semantics.py` (15 tests).

---

## P0-B — Historical match execution

### B1. Snapshots were capped at 720 seconds

**Finding**: `freeze()` defaulted to `format_seconds=720`. Most call sites in
`main.py` (focus, seek, ask, explain, evidence graph, auto-detection) passed no
format. A historical match’s context said 5400s, but every snapshot was
reduced with a 720s cap; `at > 720` raised `clock_out_of_bounds` (HTTP 500) or
silently produced a 12-minute snapshot.

**Reproduction** (baseline): `POST /api/control {"action":"set_match",
"match_id":"sb_wc2022_final"}` then `{"action":"seek","at":3000}` → 500.

**Fix**:
- `Engine.reduce_state` / `Engine.snapshot_for` and the module helper
  `freeze_with_context` are the only snapshot paths used by routes;
- every call receives `MatchContext.duration`, `coordinate_frame`,
  `continuous_coverage`, explicit provider mapping and official score;
- `freeze()` raises on `at > format_seconds` rather than silently clamping;
- evidence graph validates `at` against the context and returns 422 on
  out-of-range queries.

**Tests**: `test_historical_match_uses_its_own_clock_and_never_projects_final_score`,
`test_seek_clamps_to_match_context_duration`,
`test_evidence_graph_respects_match_context_clock`.

### B2. Final score was shown at kick-off

**Finding**: for historical matches `view()` returned
`match_ctx.home_score/away_score` (the official final 3–3) at `at=0`.

**Fix**: `score` is always the observed prefix from the reducer
(`score_basis = "observed_prefix"`); `official_score` is exposed separately.
A partial sample may show `2–2` observed while the official score is `3–3`.
Shootout goals are isolated in `shootout_score`.

**Test**: at `at=720` the score is `0–0`; at `at=1400` it is `1–0`; the
official score remains `3–3` in both responses.

### B3. Partial coverage was treated as continuous possession

**Finding**: the last interval was extended from the last event to `at`, and
the 12-event sample was reduced with `at=5400`, crediting over 5,000 seconds
to whichever team touched the ball last.

**Fix**:
- `coverage.continuous` comes from `MatchContext.continuous_coverage`;
  `C1_PARTIAL` is never continuous;
- partial states close at the last observed event and record
  `coverage_end`;
- possession receipts with a zero denominator return
  `value = null, status = "unobserved"`;
- `ask_the_match` explicitly answers “Unknown, not zero” for those windows;
- catalog cross-match rates are withheld for partial fixtures.

**Tests**: `test_partial_coverage_does_not_extend_possession_to_match_end`,
`test_partial_coverage_reports_unknown_not_zero`,
`test_cross_match_withholds_per90_for_partial_fixture`.

---

## P0-C — Benchmark and research integrity

### C1. Constant benchmark metrics

**Finding**: `validation.py` assigned `block_a=0.375`, `acc_a=0.625`,
`block_b=0.250`, `acc_b=0.750`, `block_c=0.125`, `acc_c=0.875`, plus constant
token costs and latency formulas. `recommendation` asserted Config C was
“statistically significant” without a test.

**Fix**:
- three honestly named pipeline configurations:
  `A_reference_only`, `B_gate20`, `C_gate20_plus_tools`;
- every rate derives from executed verdicts on an 8-claim hand-authored
  fixture; the result is named `contract_agreement_rate`, not accuracy;
- token cost is `null`, `live_model_status = "not_run"`;
- latency is measured with `perf_counter` for the executed loop;
- recommendation no longer claims model superiority;
- `validation.AgentBenchmarkEvaluator` delegates to the same executed harness.

**Tests**: `test_abc_benchmark_harness`,
`test_agent_benchmark_evaluator_abc_synthetic`,
`test_agent_benchmark_deterministic_contract_labeling`.

### C2. Event-count claims

Verified in the repository:

| Claim | Actual |
| --- | --- |
| 4,354 events for `sb_wc2022_final` | 12 events |
| 3,120 events for `sb_cl2019_final` | file absent |
| “4350+ real events” mounted | 12-event sample only |

Full details and reproduction commands:
[RESEARCH_PROVENANCE_AUDIT.md](RESEARCH_PROVENANCE_AUDIT.md).

### C3. Real multi-agent architecture

**Finding**: the online MAF workflow is `Analyst → Verifier` (two model
agents). `EventAttributionSpecialist` is a deterministic tool bundle.
`publication_gate_2_0` is not invoked by `AgentRunner`; the online gate is
`publication_gate`. Docs described a tri-agent system and Gate 2.0 online
participation.

**Fix**: documentation is corrected in
`RESEARCH_PROVENANCE_AUDIT.md` and the retraction banner in
`AGENT_EVALUATION_V2.md`. No code was renamed to pretend a third agent exists.
A true third agent remains a separate design task (role, tool permissions,
cost, audit, controlled experiment).

### C4. Research wording

Removed/retracted:

- “statistically significant” benchmark superiority;
- “Configuration C achieved X% verified claim accuracy”;
- “4,350+ real events”;
- “significant SSE performance improvement” without measurement;
- “Agent C narrowed 75–82% of causal claims” (no agent/run exists).

Kept and labeled as exploratory or unverified where appropriate.

---

## P0-D — Story, claim and approval trust

### D1. Caller-controlled approval

**Finding**: `MatchStoryEngine.generate_story(... verified_claims=...)`
accepted arbitrary dicts and approved the story when a caller supplied
`status="approved"`, `verdict="verified"` or `gate_passed=True`. The SVG export
always printed `GATE 2.0 VERIFIED`.

**Fix**:
- new `ClaimRegistry` persists `ClaimRecord` with match, snapshot, claim,
  gate version, gate status, violations, source run, evidence hash and
  editorial decision;
- gate verdicts are produced by executing `publication_gate_2_0` against the
  frozen snapshot (or by persisting an accepted online `publication_gate`
  card, with its run ID);
- `generate_story` has no `verified_claims`/`status`/`gate_passed` parameter;
  it reads `registry.records_for(match_id, snapshot_id)`;
- broadcast approval requires **both** gate approval and an attributed
  editorial approval; otherwise the story is `draft_pending_editorial`;
- SVG badges reflect the real status.

**Tests**: `test_story_approval_ignores_caller_fields_by_construction`,
`test_gate_verdict_is_required_and_editorial_approval_is_separate`,
`test_fabricated_editorial_approval_is_rejected`,
`test_story_endpoint_never_claims_broadcast_approval_without_editorial`.

### D2. Narrative content

**Finding**: fan/coach/media templates asserted “star performance”, “crucial
battlepoints”, “corridor progression”, “defenders on high alert” regardless of
events. Chapter tags included `StarPerformance` and `KeyShift`. Chapters could
reference no events.

**Fix**: narratives report recorded event counts (passes, progressive passes,
entries, recoveries, shots, goals) with an explicit statement that off-ball
positioning and tactical intent are unobserved. Tags are factual
(`recorded_events`, `shots_N`, `goals_N`, …). Without gate-approved evidence,
the story is a short descriptive summary.

**Tests**: `test_no_claims_gives_descriptive_draft_without_star_or_tactical_fabrication`,
`test_story_export_formats_do_not_claim_unearned_verification`.

### D3. Challenge idempotency

**Finding**:
- same `idempotency_key` + different payload recomputed the challenge and
  returned the old revision list;
- a second legitimate challenge of the same type on the same claim/snapshot
  was suppressed;
- revisions were session-only.

**Fix**:
- request hash stored with every challenge;
- same key + same hash → reuse stored result (works across restart);
- same key + different hash → `409 idempotency_key_conflict`;
- different payloads are stored as separate revisions;
- challenge results persist in `ClaimRegistry`, reconstructed as
  `rev-restored-*` after restart.

**Tests**: `test_challenge_idempotency_key_conflict_and_distinct_payloads`,
`test_challenge_result_survives_process_restart`.

---

## P1-E — Evidence graph and cross-match

### E1. Evidence graph

**Finding**: the graph was Hypothesis → Metric only. It had no events, no gate
verdict, no challenge/revision, used Python `hash()` for limitation node IDs
(randomized across processes), and inserted `value: 0` for missing receipts.

**Fix**: `services/api/matchlens/evidence.py` builds:

```
Match → Snapshot → Event
                 → Metric Receipt → Event
                 → Claim → Gate Verdict
                          → Challenge → Revision
                          → Limitation / Evidence Gap
```

- node IDs are SHA-256 content hashes (stable across processes);
- missing receipt/event → `evidence_gap` with `value = null`;
- `published` = gate approved **and** editorial approved; gate-verified but
  unpublished claims are explicit;
- query time is bounded by `MatchContext.duration`;
- every node carries `source` and `data_version`.

**Tests**: `test_graph_contains_real_event_receipt_claim_gate_chain`,
`test_graph_ids_are_stable_across_calls`,
`test_missing_receipt_becomes_evidence_gap_not_zero`,
`test_editorial_approval_marks_claim_published_and_challenge_links_revision`.

### E2. Cross-match intelligence

**Finding**: comparison returned only total event/pass/shot counts; partial
fixtures and full synthetic matches were presented as equivalent.

**Fix**: `get_batch_summary` returns:
- per-match coverage, continuous flag, event count, observed end, duration;
- per-90 rates only for continuous, complete matches;
- `rate_status = "withheld_partial_coverage"` otherwise;
- `team_summaries` (same club across matches, with sample size);
- chronological `trend`;
- `comparable`, `warnings`, `load_status`, `metric_version`.

**Tests**: `test_cross_match_withholds_per90_for_partial_fixture`,
`test_same_team_cross_match_rates_are_comparable`.

### E3. Load failures

**Finding**: `load_multiple_matches` replaced every failure with `[]`, making
missing, unparsable, unsupported and genuinely empty sources indistinguishable.

**Fix**: `load_multiple_matches_with_status` returns `ok`, `missing`,
`parse_error`, `unsupported`, `zero_events`. The default loader raises
`batch_load_failed` instead of silently returning empty lists.

**Test**: `test_load_status_distinguishes_missing_parse_error_unsupported_and_zero`.

---

## P1-F — Runtime and resource reliability

| Issue | Finding | Fix / measurement |
| --- | --- | --- |
| Repeated parsing | `exploration_cache` keyed by session + match, no data version; contexts cached by ID only | keys include source fingerprint `data_version`; `MatchCatalog.data_version` uses mtime+size |
| Snapshot cost | every `view()` could create snapshots at several crossed timestamps | single `snapshot_for` helper; state cache per session/at/version; moment scan capped at 240 samples on large feeds and reports `moments_scan_truncated` |
| Reducer/OAAI per SSE tick | OAAI was O(steps × events) | no-dead-time path now incremental O(events + steps); benchmark below |
| Match switch race | old task epoch checked on commit | unchanged contract re-verified; `invalidate()` cancels; commit requires epoch and timestamp |
| Restart recovery | claims were memory-only | registry persists claims, editorial decisions and challenges; sessions still restart explicitly |
| Anonymous research APIs | heavy endpoints had no quota | per-source quotas added to compare, exploration, validation, benchmark, story, evidence graph, attribution, sufficiency, xt compare |
| Full-history timeout/memory | not measured before | measured (see results): 4,144 events, reducer 25ms, OAAI 38ms, snapshot 529ms, evidence graph 298ms, peak 16.5MB |

Measured input is a **synthetic volume stress** stream; the 12-event stream is
real data. See `evidence/third_pass/runtime_benchmark.json`.

---

## What was not executed

- Live DeepSeek / LLM A/B/C dispatch (no key used; **Not Run**).
- Full 2022 World Cup final / 2019 Champions League data (not in repository).
- A true third agent design/experiment.
- External human research review and audience study.
- A ten-minute public-network SSE soak test.

These remain open items in [THIRD_PASS_RESULTS.md](THIRD_PASS_RESULTS.md).
