# Slice B — Agentic Investigation: Results (2026-10-24)

Scope: Prompt 2 / Slice B — real MAF agentic investigation, agent-run lifecycle
persistence (roadmap `C-09`), and the evaluation harness groundwork (`F-01`
precondition). Everything below distinguishes **executed & verified**,
**code-complete but not live-measured**, and **blocked/not run**.

## 1. Executed and verified (code + real executed test/receipt)

### 1.1 Agent-planned investigation mode (`C-06` mount points)

- `services/api/matchlens/investigation.py` — `InvestigationPlan.execution_mode`
  widened to `deterministic_planner | maf_agent`; `agent_status` widened to
  `not_run | run | failed`; new `agent_run_id`, `agent_error` and a compact
  `agent_run` lifecycle summary. `ToolReceipt` gained an optional `role` so a
  receipt says which agent selected the tool.
- `run_maf_investigation()`: typed intent/scope resolution stays deterministic
  (planner contract); the MAF **Analyst** then selects registered tools
  dynamically through `FootballToolRegistry` (allow-list, per-tool budgets,
  receipt hashing — no new execution path), proposes one typed WireDraft; the
  **Verifier** independently inspects the draft with its own bounded registry;
  the online `publication_gate` decides. The returned plan is the same
  `InvestigationPlan` model the deterministic planner emits — the two modes are
  structurally isomorphic by construction.
- Fallback contract: no model key, no budget runway, unsupported intent,
  invalid focus, model failure or timeout all degrade to the deterministic
  planner with an honest marker (`agent_status`, `agent_error`, `unresolved`
  reason). No synthetic agent output is ever substituted.
- `services/api/matchlens/agents.py` — extracted the shared transport hooks
  (`_transport_hooks`) and model execution loop (`_run_model`) from `stage()`;
  added `stage_with_registry()` (registry-backed tool closures with
  model-facing descriptions) and the investigation prompt variants with a
  dynamic tool menu. `stage()` behavior is unchanged (existing tests pass).
- `services/api/matchlens/tools.py` — `TOOL_DESCRIPTIONS` for dynamic tool
  selection; registry budgets untouched.
- API: `POST /api/investigate` accepts `execution_mode`; `maf_agent` is rated
  separately (`investigate-agent` bucket) and requires
  `BudgetLedger.has_runway(6)`; promotion of an agent-backed plan moves the run
  record `GATED → PUBLISHED`.

Evidence: `services/api/tests/test_slice_b_agentic.py` (12 tests) — fallback
without key, fallback without runway, failure degradation to an isomorphic plan
with a preserved run record, unknown-intent never dispatches, registry budget
guards, deterministic mode unchanged; full suite **283 passed / 0 failed**
(`services\api\.venv\Scripts\python.exe -m pytest services/api/tests/ -q`),
frontend **typecheck + production build 0 errors**.

### 1.2 Agent Run lifecycle persistence (`C-09`)

- New `services/api/matchlens/runstore.py`: `AgentRunState` machine
  (`QUEUED → ANALYSING → TOOL_WAIT → HANDOFF → VERIFYING → GATED →
  PUBLISHED/WITHHELD`, plus `FAILED/CANCELLED`) with bounded transitions;
  `AgentRunStore` persists records + incremental audit snapshots to
  `agent_runs.json` (atomic tmp-file replace, `InvestigationStore` pattern,
  single-writer).
- Wired into both run paths: session analysis (`start_analysis`/`execute`) and
  the investigation agent path. A record is created only when a model run is
  actually possible; deterministic fallbacks are not agent runs. A task that
  dies before result mapping is closed by a done-callback, so no record stays
  ambiguous. Audit, request count, model, prompt version, accepted/rejected
  counts and the failure reason are persisted.
- API: `GET /api/agent-runs` (list + budget summary), `GET /api/agent-runs/{id}`,
  `POST /api/agent-runs/{id}/cancel` (closes non-terminal records left by a
  restart; live runs are cancelled through the session epoch).

Evidence: lifecycle transition/persistence/cancel tests in
`test_slice_b_agentic.py`; live API smoke on port 8010
(`MATCHLENS_RUNTIME_DIR=.runtime/slice-b`): deterministic investigation returns
`execution_mode=deterministic_planner, agent_status=not_run, gate approved`,
`GET /api/agent-runs` returns the record list with the budget summary.

### 1.3 Evaluation harness (`§6`, `F-01` groundwork)

- `services/api/matchlens/benchmark.py`: `run_agent_contract_benchmark()` — a
  **recorded-replay** arm replays genuine recorded model outputs from
  `evidence/*/runs/*.json` through the real slot-validation and
  publication-gate code paths; live comparison arms
  (`live_single_agent`, `live_self_review`, `live_analyst_verifier`,
  `live_pair_plus_tools`) are reported **Not Run** with all metrics `None`.
  No accuracy, significance or model-advantage number is produced.
- API: `GET /api/benchmark/agent-contract`.

Executed receipt (server on 8010): 12 recorded receipts found, 12 replayed,
11 recorded outputs re-validated, 11 failed (r0.1-era formats; failures listed
in the payload and kept in the denominator), gate accepted 4 / rejected 7.
These are contract outcomes, not accuracy claims.

### 1.4 UI: Deterministic / Real Agent / Not Run

- `InvestigationPanel` shows the execution-engine chip and the agent-status
  chip (`Not Run` / `Agent Run` / `Agent Failed (fell back)`), an engine
  selector (deterministic = free; real agent = consumes model budget), an
  expandable tool-receipt trajectory with per-role badges, the agent run
  trajectory (state history, model, request count, error) and the degradation
  reason.
- Browser acceptance (Playwright, served build): **17 passed / 0 failed**,
  including the new `requesting the real agent without a model key degrades
  honestly to the deterministic planner` journey and the existing real-match
  deterministic journey. The throwaway E2E server now runs with
  `DEEPSEEK_API_KEY=""` so the browser suite is structurally unable to spend
  model budget.

## 2. Code-complete, not live-measured (honestly Not Run)

- **Live `maf_agent` investigation**: the MAF path (dynamic tool selection →
  WireDraft → independent Verifier → `publication_gate`) is implemented and
  contract-tested offline, but has **no authorized paid run**; no live receipt,
  latency, token or quality number exists. Live results remain **Not Run**
  until an explicit budget authorization (hard cap unchanged: ledger
  `32 requests / $1.00` default; `has_runway` gate before dispatch).
- **Live ablation arms** (single agent, self-review, pair, pair+tools): harness
  placeholders report Not Run; no comparison conclusion is drawn anywhere.

## 3. Known limits carried forward

- The recorded-replay arm validates the *contract* of recorded outputs against
  today's code; it is not an empirical accuracy measurement.
- TOOL_WAIT is representable in the state machine but not yet tracked per tool
  call (audit rows carry the per-call evidence; the finer-grained transition
  would multiply store writes).
- Verifier independence is bounded by its own registry budget (6 calls) and
  request cap (3 per role); deeper ablation of verifier value is part of the
  live arms, Not Run.
