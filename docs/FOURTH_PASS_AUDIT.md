# Fourth-Pass Audit — Trust, Identity, Revision and Investigation

**Audit date**: 2026-10-24
**Baseline**: `207c8d951b5ae615410cf59d83f77a5dbd3f140c`
**Status vocabulary**: Confirmed Bug · Architectural Weakness · Product Gap ·
Research Opportunity · Requires Runtime Verification.

This pass did not re-open issues already remediated in the third pass. Each
item below was checked against the baseline code before implementation.

---

## 1. Confirmed bugs

### 1.1 Stale agent runs wrote claims before epoch validation

**Evidence**: `main.py::Engine.execute` called
`registry.register_verified_claim(s.match_id, ...)` before checking
`epoch == s.epoch`. A model completion during a match switch could therefore
write an old snapshot's claim under the new session match ID. `task.cancel()`
was not a sufficient boundary because completion and cancellation race.

**Remediation**:
- `Run` now freezes `match_id`, `dataset_revision`, `epoch` and `snapshot_id`
  at creation.
- Registration is inside a single identity check: epoch, run match, snapshot
  match and as-of clock must all agree.
- A stale result writes only the run audit record with a `superseded` entry;
  it never mutates cache, current analysis state or the registry.
- Regression: `test_stale_agent_run_never_writes_claims_into_a_new_match`.

**Status**: Confirmed Bug — fixed.

### 1.2 Editorial approval trusted a caller-supplied name

**Evidence**: `EditorialDecisionBody.approver` was a free string and
`POST /api/story/editorial-approval` passed it directly to the global registry.
Any anonymous caller could approve any gate-passed claim.

**Remediation**:
- New `auth.py` principal resolution from `MATCHLENS_PRODUCER_TOKEN` /
  `MATCHLENS_ADMIN_TOKEN` using constant-time comparison.
- Roles: viewer (read), analyst (run analysis), producer / admin (editorial).
- Optional local producer mode requires an explicit env opt-in **and** a
  loopback client.
- No token and no local mode → `503 editorial_identity_not_configured`;
  a wrong token → `403 editorial_role_required`.
- Registry records the server principal, role, timestamp, previous decision and
  an append-only `editorial_history`.
- Regression: `test_editorial_approval_requires_server_identity`.

**Status**: Confirmed Bug (security) — fixed for the current token model.
A real multi-user account system remains a Product Gap.

### 1.3 Claim challenges had no durable revision lifecycle

**Evidence**: `resolve_challenge` returned an outcome string; the registry
stored the challenge result but not a superseding conclusion version. A narrowed
or withdrawn claim could still appear in later Story output, and the frontend
deduplicated claims by `claim_id` alone across snapshots.

**Remediation**:
- `ClaimRevision` append-only model: version, parent revision, status,
  outcome, immutable statement/evidence snapshot, dataset revision and
  challenge request hash.
- `ClaimRecord` now tracks `lifecycle_status`, `current_revision_id` and
  `revision_count`; `broadcastable` requires `current`.
- Challenge resolutions append a revision. Maintained stays current; narrowed
  becomes qualified; withdrawn becomes withdrawn; inconclusive/rejected becomes
  disputed. Editorial approval is reset when a revision narrows or withdraws.
- `GET /api/claims/history` returns the full chain.
- Story filters to current lifecycle claims; export and rundown reject
  non-broadcastable claims.
- Frontend claim identity now includes `snapshot_id`.
- Regression: `test_claim_revision_history_is_append_only`,
  `test_broadcast_requires_editorial_approval_and_producer_identity`.

**Status**: Confirmed Bug / Architectural Weakness — fixed for the existing
assertion-based claim set; free-form claim versioning remains a Product Gap.

### 1.4 Dataset version was not content-addressed

**Evidence**: `MatchCatalog.data_version` used file mtime and size. A content
edit preserving both would leave every cache, snapshot and claim looking
compatible. `snapshot.source_data_digest` hashed event IDs only.

**Remediation**:
- `content_revision_from_events` hashes canonical event facts (timestamps,
  team/provider identity, action, outcome, player, possession, coordinates,
  own-goal/shootout flags) and then includes schema, adapter, metric and model
  versions, provider mapping and coverage in a `dataset_revision`.
- `MatchContext` exposes `dataset_revision`, `content_sha256`, per-layer
  versions; snapshots store `dataset_revision` and use it as
  `source_data_digest`.
- Claims, evidence graph nodes and rundowns carry the revision.
- Regression: `test_dataset_revision_hashes_content_not_file_metadata`
  rewrites an event with the same ID and restores mtime; the revision changes.

**Status**: Confirmed Bug — fixed. Existing saved runs with old snapshots are
retained as historical artifacts but are not relabelled.

### 1.5 Story had no as-of boundary

**Evidence**: `GET /api/matches/{id}/story` always built the state at the full
observed end, so a live story could include future events. There was no server
cache keyed by snapshot/data/review version.

**Remediation**:
- `as_of` and `mode=live|recap` parameters, bounded by MatchContext duration.
- Story chapters use only the requested state prefix; returned `as_of` and
  `dataset_revision` identify the boundary.
- Cache key includes match, snapshot, perspective, dataset revision, approval
  signature and mode.
- Frontend requests only while paused/finished, passes snapshot as-of and
  aborts stale responses.
- Regression: `test_story_as_of_does_not_leak_future_events`.

**Status**: Confirmed Bug — fixed.

---

## 2. Architectural weaknesses

### 2.1 Metrics were spread across modules

`metric_receipts`, `exploration`, `oaai`, `attribution` and UI code each
computed or formatted overlapping quantities. There was no single definition
of unit, denominator, missing policy or evidence references.

**Remediation**: `metrics.py` now defines a registry with metric ID, unit,
scope, event inputs, formula, numerator/denominator semantics, capabilities,
missing policy, model status and limitations. `/api/metrics` exposes the
definitions; `/api/metrics/{id}` executes against a frozen snapshot. It reuses
`metric_receipts` rather than introducing a second possession algorithm.
Unavailable xG is `not_available`, never zero.

**Status**: Architectural Weakness — partially remediated. Charts and some
legacy endpoints still call domain functions directly; migrating every chart is
a roadmap item.

### 2.2 Async UI responses were not identity-checked

OAAI smoothing and recovery-window requests only updated state if a response
arrived; a late response from an old match/epoch could overwrite the current
view. Backend exploration responses now include `match_id`, `epoch`, `at` and
`dataset_revision`; frontend handlers reject mismatched responses.

**Status**: Architectural Weakness — fixed for these two handlers; challenge
and story responses are also checked at their own boundaries.

### 2.3 The online workflow has two model agents, not a specialist agent

No third model agent exists. `EventAttributionSpecialist` is a deterministic
tool layer. Adding a third agent requires a real MAF stage, independent tool
permissions, cost accounting and a controlled comparison.

**Status**: Product Gap / Research Opportunity.

### 2.4 Investigation was assertion-shaped

The online Analyst can only choose among a small assertion set. A generic
Investigation Plan, tool registry and dynamic hypotheses were absent.

**Remediation (first slice)**:
- `investigation.py` resolves a selected OAAI point, event, sequence or metric;
  queries the Metrics Registry; retrieves real events; proposes competing
  explanations; previews Gate 2.0; returns per-tool receipts.
- It is explicitly `deterministic_planner` / `agent_status="not_run"`.
- `POST /api/investigate` and an Investigation UI tab expose the plan.
- It does not persist a claim automatically.

**Status**: Architectural Weakness — first deterministic slice implemented.
LLM-planned, open-ended investigation remains a Research Opportunity.

### 2.5 Story approval and export were not a production workflow

The third pass added gate/editorial separation but no queue, rundown, identity
or export boundary.

**Remediation**:
- `/api/broadcast/queue` exposes claim status.
- `/api/broadcast/rundown` requires a producer principal and only accepts
  broadcastable, dataset-compatible current claims.
- `/api/broadcast/export` requires a producer principal and a broadcastable
  story; it returns JSON/Markdown/SVG plus claim IDs, evidence revision and
  approvers.
- Story UI has a producer-token field and approve/reject actions; export
  buttons stay disabled until editorial approval.

**Status**: Architectural Weakness — backend/UI slice implemented. Multi-user
accounts and full visual rundown editing remain Product Gaps.

---

## 3. Product gaps

1. **Information architecture**: the app still opens directly into a dense
   cockpit rather than a Match Hub → Match Detail → Explorer → Studio flow.
   Existing workspaces were retained and refined, not rebuilt around a hub.
2. **Real profile system**: roles are token principals, not accounts. No
   cross-user isolation of drafts or rundowns beyond the server token boundary.
3. **Full real matches**: the repository still ships a 12-event
   `C1_PARTIAL` sample. The new importer requires the operator to supply a
   licensed payload; it does not download data or fabricate a full match.
4. **Player/team identity registry**: cross-match comparisons still use display
   names in some UI paths; a stable provider-ID registry is not complete.
5. **Live Story**: as-of requests are correct, but the UI only refreshes on
   pause/finish to avoid request storms. Continuous live story pacing is not
   implemented.
6. **Deep links/back-button restoration**: cross-workspace selections exist in
   memory but not in the URL state model.

---

## 4. Research opportunities

- Compare Deterministic Only / Single Agent / Single Agent + Self Review /
  Analyst + Verifier / Analyst + Verifier + Specialist Tools /
  Analyst + Specialist Agent + Verifier on the same frozen claims.
- Calibrate xG and xT on complete licensed data with train/validation/test
  splits, calibration curves, bootstrap intervals and cross-match error.
- Test whether the deterministic Investigation Plan improves analyst useful
  coverage versus a free-form LLM investigation, with failures in denominators.

None of these were run in this pass.

---

## 5. Requires runtime verification (not claimed)

- Real multi-user authentication and authorization.
- A complete licensed 90-minute match through import → metrics → UI → Agent.
- Mobile-device layout and touch behavior.
- Continuous SSE and long-run memory under a full match.
- External producer/analyst usability review.
