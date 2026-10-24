# Product Upgrade Roadmap

**Baseline**: fourth pass on `207c8d9`.
**Principle**: each phase must ship a vertical slice with backend, UI, tests and
evidence. No phase is “complete” because a schema or a mock exists.

---

## Phase 0 — Trust & Runtime (this pass)

- [x] Freeze Run identity and prevent stale writes.
- [x] Server-side editorial token roles; anonymous approval closed.
- [x] Append-only ClaimRevision lifecycle.
- [x] Content-addressed DatasetRevision.
- [x] Story `as_of` and live/recap separation.
- [x] Async OAAI/recovery identity guards.
- [x] Tests for stale runs, auth, revisions, revision hash, story boundary.

**Acceptance**: fourth-pass tests pass; CI green; no client-supplied approval.

---

## Phase 1 — Football Investigation (deterministic slice shipped)

- [x] Metrics service with definitions and missing-data policy.
- [x] `/api/metrics` and `/api/metrics/{id}`.
- [x] Investigation Plan with tool receipts and Gate preview.
- [x] Investigation tab in Story Workbench.
- [x] Explicit `agent_status=not_run`.

Next:

- [ ] Let the MAF Analyst plan over the same tool registry; keep the planner as
      the execution substrate.
- [ ] Add a visible tool-call trace to the Inspector.
- [ ] Add a controlled comparison: deterministic plan vs single-agent vs
      Analyst+Verifier on the same frozen windows.
- [ ] Add claim conversion from an approved investigation without auto-publish.

**Acceptance**: a previously unseen selected event/zone produces a useful,
receipted plan; unsupported causal explanations are rejected; the model run is
audited and failures appear in denominators.

---

## Phase 2 — Real Match Intelligence

- [x] Licensed payload importer with provenance receipt.
- [x] Full/partial coverage classification.
- [ ] Obtain a licensed complete 90-minute payload; import with explicit
      provider IDs.
- [ ] Validate lineups, substitutions, cards, periods, shootout and identity.
- [ ] Compute per-match metrics from the same registry.
- [ ] Browser journey on the full match (seek, event, sequence, player, Story).

**Blocked**: the repository currently has only the 12-event sample. A synthetic
full match can test mechanics but cannot be presented as real-data validation.

**Acceptance**: event count and observed range match the source receipt; a full
match passes coverage/per-90 tests; no synthetic/real distribution mixing.

---

## Phase 3 — Unified Product Experience

- [ ] Match Hub: competition/date/search cards.
- [ ] Match Detail: score, timeline, shots, lineups, stats, key insights.
- [ ] URL state for workspace/event/sequence/player/zone/snapshot; back/refresh.
- [ ] Split `StoryAgentWorkbench` and `TacticalLabWorkspace` into data hooks,
      domain selectors and presentational components.
- [ ] Loading / empty / partial coverage / error states across workspaces.
- [ ] Mobile/tablet and keyboard/a11y verification on real devices.

**Acceptance**: a casual fan reaches score and key events without opening a
tactical panel; an analyst can deep-link a sequence and return via history.

---

## Phase 4 — Broadcast Production

- [x] Queue API, rundown API, export API.
- [x] Producer token actions in the claim list; export disabled until approval.
- [x] Withdrawn/qualified claims excluded.
- [ ] Account/SSO system with producer/admin roles and per-user isolation.
- [ ] Visual rundown ordering, preview, defer and re-review.
- [ ] Export artifact storage and provenance manifest download.

**Acceptance**: anonymous users cannot approve; a producer can approve, order,
export and withdraw; the exported artifact maps to claim evidence hashes.

---

## Phase 5 — Research Evaluation

- [ ] Calibrated xG on complete licensed data (train/validation/test).
- [ ] xT cross-match generalization with calibration and error analysis.
- [ ] Multi-agent arms (deterministic, single, self-review, pair, tools,
      specialist) with paired window bootstrap.
- [ ] Failure-inclusive denominator and reproducible run receipts.

**Acceptance**: every accuracy/CI/p-value claim has a run receipt; negative
results are retained; no “significant improvement” without the preregistered
decision rule.

---

## Dependency order

```text
Phase 0 trust
  → Phase 1 metrics + investigation
  → Phase 2 complete licensed data
  → Phase 3 product IA
  → Phase 4 accounts + broadcast
  → Phase 5 research evaluation
```

Phase 3 visual work may proceed in parallel, but it must not use fabricated
metrics or imply data coverage that Phase 2 has not established.
