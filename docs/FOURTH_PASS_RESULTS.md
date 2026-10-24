# Fourth-Pass Results

**Date**: 2026-10-24
**Baseline**: `207c8d951b5ae615410cf59d83f77a5dbd3f140c`
**Environment**: Windows 10.0.26200, Python 3.13.9 project venv, Node.js 24.16 local (CI 22), Next.js 16.4.2

---

## 1. Implemented slices

### Trust & runtime

- Run identity now freezes `match_id`, `dataset_revision`, `epoch` and snapshot;
  stale completion leaves audit only and cannot write a claim into a switched
  match.
- Editorial approval requires a server-configured producer/admin principal.
  Body names are not identities.
- ClaimRevision is append-only; lifecycle states are current / qualified /
  disputed / withdrawn / superseded. Narrowing resets editorial approval and
  removes the claim from Story/export.
- Dataset revision is a content hash over event facts plus schema, adapter,
  metric and model versions. It flows into snapshots, claims, graphs, rundowns
  and caches.
- Story has `as_of`/`mode` and a cache keyed by snapshot, dataset revision,
  approval signature and mode; the UI fetches only while paused/finished and
  aborts stale responses.
- OAAI and recovery responses carry match/epoch/at/revision; the UI rejects
  mismatches.

### Football investigation (deterministic first slice)

- Metrics Registry (`metrics.py`) with 13 definitions and one execution path.
- `/api/metrics` and `/api/metrics/{metric_id}`.
- `POST /api/investigate`: focuses on an OAAI point, event, sequence or metric;
  queries receipts; retrieves events; proposes competing explanations; runs a
  Gate 2.0 preview; returns per-tool receipts.
- Explicitly `agent_status="not_run"` and `execution_mode="deterministic_planner"`.
- Investigation tab renders findings, tool receipts, explanations, gate preview
  and not-inferable boundaries.

### Broadcast production

- `/api/broadcast/queue`, `/api/broadcast/rundown`,
  `/api/broadcast/export`.
- Rundown/export require a producer principal; only broadcastable current claims
  are accepted; export includes claim IDs, evidence hashes, dataset revision and
  approvers.
- Story UI has a producer token field, approve/reject actions, and disables
  copy/export until the story is approved for broadcast.

### Real match import

- `ingest.import_match` and `scripts/import_statsbomb_match.py` validate a
  licensed payload, explicit provider team IDs and metadata; write raw data and
  a provenance receipt with source/target hashes; mark short coverage as
  `C1_PARTIAL`.
- No network download is hidden in the importer.

---

## 2. Verification commands and observed output

### Backend

```powershell
services\api\.venv\Scripts\python.exe -m pytest services/api/tests/ -q
```

```text
209 passed in 55.05s
```

Fourth-pass targeted tests:

- `test_stale_agent_run_never_writes_claims_into_a_new_match`
- `test_editorial_approval_requires_server_identity`
- `test_editorial_rejected_gate_claim_cannot_be_approved`
- `test_claim_revision_history_is_append_only`
- `test_dataset_revision_hashes_content_not_file_metadata`
- `test_story_as_of_does_not_leak_future_events`
- `test_metrics_registry_reuses_receipts_and_reports_unavailable_xg`
- `test_investigation_returns_receipted_plan_without_persisting_claim`
- `test_broadcast_requires_editorial_approval_and_producer_identity`
- `test_statsbomb_import_requires_explicit_identity_and_license`

### Frontend

```powershell
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

```text
typecheck exit 0
next build exit 0
```

### Browser structural journey

Executed with the in-app browser via CDP. Screenshots remain unavailable
(`viewport=0x0, visible=false`).

1. Synthetic match at 09:00: Evidence Rail shows 100% observed coverage,
   as-of score, shortened content revision and gate status.
2. Story Workbench: backend chapters render recorded counts with the correct
   as-of; claims show gate/editorial chips, evidence hashes and revision count.
3. Producer token field is present; export buttons are disabled until editorial
   approval.
4. Investigation tab at 09:00: 11 tool receipts, supported transition
   explanation, explicit insufficient-evidence pressing hypothesis, Gate preview
   `approved`, `Agent not run / deterministic_planner`.
5. No client-side crash or console error was observed in the final run.

### Real data scale

The repository still contains only the 12-event `C1_PARTIAL` sample. The
importer was tested with a two-event fixture; a full licensed match was not
available, so no full-match metric, UI or Agent claim is made.

---

## 3. What is not done

| Item | State | Reason |
| --- | --- | --- |
| Full 2022 final / 2019 final data | Blocked/external | Payload not in repository |
| Live LLM investigation | Not implemented | Planner is deterministic; no model dispatch |
| Third Specialist Agent | Not implemented | Requires separate design/experiment |
| Live A/B/C comparison | Not run | Requires model budget and receipts |
| Real accounts / SSO | Not implemented | Token principals only |
| Match Hub and full IA | Not implemented | Roadmap phase 3 |
| URL deep links / browser back | Not implemented | Roadmap phase 3 |
| Visual rundown editor | Not implemented | Backend/queue actions only |
| Mobile device/accessibility audit | Not run | CSS only |
| External producer/audience review | Not run | No participants |
| Screenshot-based visual QA | Unavailable | In-app viewport 0×0 |

---

## 4. Remaining risks

1. The token model is a server boundary, not a multi-user account system. Token
   leakage has the same consequence as a producer credential.
2. The deterministic planner is intentionally conservative; it cannot answer
   open-ended questions outside its metric/explanation set.
3. Legacy xG remains heuristic/unavailable as a receipt; the UI now shows n/a
   instead of a fabricated value.
4. Dataset revision computation parses and hashes the event content; full-match
   performance must be measured after a real payload is imported.
5. Old runtime receipts with pre-fourth-pass snapshots are retained as audits but
   are not relabelled or treated as current.

---

## 5. Release reading

The fourth-pass trust and production slices are implemented and tested locally.
The product is **not** cleared for a real-data research release: a complete
licensed match, live agent evaluation and external review are still missing.
