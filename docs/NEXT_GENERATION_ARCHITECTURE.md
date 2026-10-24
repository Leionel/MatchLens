# Next-Generation Architecture

**Status**: target architecture + what is already implemented in this pass.
**Constraint**: preserve the Obsidian Tactical design system and the existing
FastAPI/Next.js runtime; do not introduce a second analytics or claim system.

---

## 1. Core chain

```text
Provider payload
  → NormalizedEvent + provider identity
  → DatasetRevision (content hash + schema/adapter/metric/model versions)
  → MatchContext
  → Possession state machine
  → Snapshot (frozen event prefix, coverage, score basis)
  → Metrics Registry (single definition + execution service)
  → Investigation Plan (bounded tools + receipts)
  → Agent deliberation (optional, audited)
  → Claim Draft → Gate Verdict → ClaimRegistry
  → Challenge → Immutable ClaimRevision
  → Editorial Decision (authenticated producer)
  → Broadcast Rundown → Export
  → Evidence Graph (trace of every node)
```

Every arrow carries the same `match_id`, `dataset_revision`, `snapshot_id` and
as-of clock. An object without those fields cannot enter the publication chain.

---

## 2. Data and coverage layer

### DatasetRevision

```text
content_sha256 = SHA256(canonical event facts)
dataset_revision = SHA256(
  match_id, provider, content_sha256,
  home/away provider IDs,
  schema_version, adapter_version, metric_version, model_version,
  coverage, event_count
)
```

- Event facts include clock, period, team/provider identity, action, outcome,
  player, possession and coordinates. Event IDs alone are not sufficient.
- Snapshots store `dataset_revision` and use it as their source digest.
- Caches, claims, evidence nodes, rundowns and exports must reject
  incompatible revisions.
- Provider team IDs are canonical; display names are not identity.

### Coverage

`continuous`, `observed_start`, `observed_end`, `controlled_seconds`,
`event_coverage`, `time_coverage`, `score_status`. Unobserved is never zero
and never persistence.

### Import

`ingest.import_match` requires source file, license, explicit provider team IDs
and metadata, validates the event payload, writes a provenance receipt with
source/target hashes, and marks partial fixtures when coverage is short. It
performs no hidden network download.

---

## 3. Metrics layer

`metrics.py` is the single registry. Each metric declares:

- ID, label, unit, team/player/match scope;
- event inputs and formula;
- numerator/denominator semantics;
- capability dependencies;
- missing-value policy;
- model status (`deterministic`, `heuristic`, `calibrated`, `unavailable`);
- version and limitations.

Execution returns a `MetricValue` with `value`, `status`, evidence event IDs,
snapshot ID, dataset revision and coverage. A missing denominator or location
returns `unobserved`; a missing calibrated model returns `not_available`.

The registry is exposed at `/api/metrics` and `/api/metrics/{id}`. Legacy chart
functions still exist; migration is incremental, not duplicated.

---

## 4. Investigation layer

```text
Investigation Request
  → resolve focus (OAAI point / event / sequence / metric)
  → get_match_context
  → query_metric panel
  → search_events / possession sequence
  → candidate explanations
  → alternative hypothesis checks
  → Gate 2.0 preview
  → auditable plan
```

Current implementation is a **deterministic planner**, not an LLM agent:

- `execution_mode="deterministic_planner"`;
- `agent_status="not_run"`;
- every tool call is a receipt with a result hash and snapshot ID;
- gate preview is never persisted automatically;
- unsupported off-ball/pressing/causal explanations are explicitly
  `insufficient_evidence`.

The next step is to let the MAF Analyst select from this tool registry while the
planner remains the bounded execution substrate. A third Specialist Agent is a
separate design and experiment, not a rename.

---

## 5. Claim and revision layer

### Claim lifecycle

```text
gate-approved current
  ├─ challenge maintained  → new current revision
  ├─ challenge narrowed    → qualified, editorial reset, not broadcastable
  ├─ challenge withdrawn   → withdrawn, not broadcastable
  └─ challenge inconclusive→ disputed, not broadcastable
```

- Original statement, evidence scope and hash are immutable in the history.
- Revisions are append-only; status is the only mutable lifecycle marker.
- A Claim's identity is `(match_id, snapshot_id, claim_id)`, never claim_id
  alone.
- `broadcastable = gate approved AND editorial approved AND lifecycle current`.
- Story/export/rundown consume the same registry.

### Editorial identity

- Producer/admin tokens are server configuration, compared in constant time.
- The client supplies no approver name.
- Optional local producer mode requires explicit env opt-in and a loopback
  client.
- Editorial decisions record principal, role, time, previous status, note and
  dataset revision.
- Without a configured identity boundary, editorial actions are closed.

---

## 6. Product surfaces

| Surface | Current | Next |
| --- | --- | --- |
| Match Hub | Not built; cockpit is the entry | Discover/search/recent matches and competition grouping |
| Match Detail | Match Center | Same with public scoreboard, lineups and event taxonomy |
| Tactical Explorer | Tactical Lab | URL-addressable selection and player/team deep links |
| Intelligence Studio | Story Workbench + Investigation tab | LLM-planned investigation over the tool registry |
| Broadcast Studio | Producer token, approval, rundown/export APIs | Visual queue, ordering, preview and withdrawal |
| Validation Lab | Contract benchmark, coverage warnings | Real held-out model evaluation |

The UI keeps the Obsidian Tactical tokens, but the information hierarchy moves
from “controls first” to “match first, evidence second, tools on demand”.

---

## 7. Invariants

1. No numeric zero for an unknown denominator or missing position.
2. No claim without event/metric receipt references.
3. No approval from client-supplied status or name.
4. No revision without a parent and immutable original.
5. No export of a non-current or non-editorially-approved claim.
6. No stale run writes after epoch/match change.
7. No story event after `as_of`.
8. No cache reuse across dataset revisions.
9. No synthetic and complete-real distributions treated as equivalent.
10. No “third agent” claim without a real MAF stage and experiment.
