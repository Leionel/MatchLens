# Research Provenance Audit (Third Pass)

**Audit date**: 2026-10-23
**Audited baseline**: `e317451` (HEAD at audit start; reducer fixes applied afterwards)
**Scope**: every quantitative research claim in `docs/AGENT_EVALUATION_V2.md`,
`docs/SECOND_PASS_RESULTS.md`, `docs/EVALUATION.md`, and the benchmark code.

This audit separates four states:

- **Verified by execution** — a command in this repository reproduces it.
- **Verified by inspection** — the code path/config is present and does what is
  stated, but no experiment establishes a general claim.
- **Unverified / Not Run** — no artifact or run receipt exists.
- **External / Unavailable** — the data is not in this repository and cannot be
  reproduced from a clean checkout.

A passing test suite is not evidence for a research claim. Tests establish
contract behavior; they do not establish model accuracy, causality or
generalization.

---

## 1. Dataset claims

| Claim | Where | Actual repository evidence | Status |
| --- | --- | --- | --- |
| `sb_wc2022_final` has 4,354 events | `AGENT_EVALUATION_V2.md` §3 | `services/api/matchlens/data/matches/sb_wc2022_final.json` contains **12** events (6,525 bytes). `MatchContext.observed_end = 5363s`. It is labeled `C1_PARTIAL`. | **Unverified — false for this repository** |
| `sb_cl2019_final` has 3,120 events | `AGENT_EVALUATION_V2.md` §3, `SECOND_PASS_RESULTS.md` | No `sb_cl2019_final.json`, no loader entry, no download receipt, no checksum. `MatchCatalog.get_match("sb_cl2019_final")` returns `None`. | **External / Unavailable** |
| “4,350+ real StatsBomb events” are mounted | `INTEGRITY_REMEDIATION_V2.md` §P0.2 | Only the 12-event sample exists. | **Unverified — false for this repository** |
| `syn_default` contains 72 events | `AGENT_EVALUATION_V2.md` §3 | `generate_match(seed=17)` produces 142–150 events depending on generator version; the deterministic benchmark reports the actual count in `dataset.event_count`. | **Unverified — stale number** |

### Reproduction

```powershell
services\api\.venv\Scripts\python.exe -c "import json; d=json.load(open('services/api/matchlens/data/matches/sb_wc2022_final.json',encoding='utf-8')); print(len(d['events']))"
# 12
services\api\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'services/api'); from matchlens.catalog import MatchCatalog; print(MatchCatalog.get_match('sb_cl2019_final'))"
# None
```

If the full open-data files are supplied later, they must be added with
license, source URL, checksum and a run receipt before any claim is restored.

---

## 2. Agent benchmark claims

| Claim | Code reality at audit start | Status |
| --- | --- | --- |
| Config A accuracy `0.625`, block `0.375` | `validation.py` assigned these as literals; latency was `420 + random`; cost `0.008` USD. | **Fabricated — removed** |
| Config B accuracy `0.750`, block `0.250` | Same pattern; `alt_cov 0.44` literal. | **Fabricated — removed** |
| Config C accuracy `0.875`, block `0.125` | Same pattern; `alt_cov 0.86` literal. | **Fabricated — removed** |
| “Config C outperforms A/B” | Followed from the literals, not from execution. | **Retracted** |
| Token costs `0.008 / 0.012 / 0.018` | Constants; no model call. | **Fabricated — now `null` / Not Run** |
| Latency `420/680/950ms` | Constants plus jitter. | **Fabricated — now measured per deterministic run** |

### Replacement

`services/api/matchlens/benchmark.py` now executes three **pipeline
configurations** (not agents):

1. `A_reference_only` — event-ID existence.
2. `B_gate20` — the real Gate 2.0 rule engine.
3. `C_gate20_plus_tools` — Gate 2.0 plus real attribution tools.

Every rate is computed from the executed verdicts on an eight-claim,
hand-authored contract fixture. The output is labeled **contract agreement**,
not accuracy. `token_cost_usd = null`, `live_model_status = "not_run"`.
`docs/AGENT_EVALUATION_V2.md` is annotated as retracted.

---

## 3. Architecture claims

| Claim | Actual code | Verdict |
| --- | --- | --- |
| Three independent model agents deliberate online | `AgentRunner.analyse` builds `WorkflowBuilder(start_executor=analyst).add_edge(analyst, verifier)`: **two** model agents. | **False** |
| `EventAttributionSpecialist` is the third agent | It is a deterministic Python tool (`decompose_window`, `query_causal_chain`, `assess_alternative_hypotheses`) exposed to both agents. It makes no model call. | **False** |
| Gate 2.0 participates in online publication | The online path calls `publication_gate(...)` (draft/review/receipt contract). `publication_gate_2_0(...)` is used by registry verification and the benchmark, not by `AgentRunner`. | **False for online path** |
| “Tri-agent” empirical comparison exists | No independent third-agent run receipts exist in the repository. | **Not Run** |

Correct description: **two-agent Analyst→Verifier workflow with deterministic
attribution tools and a deterministic publication gate.** If a third agent is
introduced later, it needs its own role, tool permissions, cost accounting,
audit trace and a controlled comparison — renaming a tool is not an agent.

---

## 4. Story, challenge and evidence claims

| Claim | Audit result | Status |
| --- | --- | --- |
| Story approval can be trusted when `status="approved"` / `gate_passed=True` | `stories.py` previously trusted caller fields. | **Vulnerability fixed**: approval now comes only from `ClaimRegistry` records with an executed gate verdict plus a separate editorial decision. |
| Story narratives describe real tactical events | The old fan/coach templates asserted “star performance”, “crucial battlepoints”, corridor progression, and always emitted `GATE 2.0 VERIFIED` on the SVG. | **Removed**: narratives are descriptive event counts with an explicit off-ball limitation. |
| Evidence graph is a real relation chain | The old graph was hypothesis→metric with `hash()`-based limitation IDs and `value: 0` for missing receipts. | **Rebuilt**: match→snapshot→event→receipt→claim→gate→challenge→revision, content-hash IDs, missing receipt = `evidence_gap` with `value: null`. |
| Challenge idempotency is safe | Same key with a different payload re-ran and returned old revisions; different legitimate challenges were suppressed. | **Fixed**: same key + same payload reuses; same key + different payload returns 409; distinct payloads are stored separately; results persist in the registry. |

---

## 5. Cross-match and validation claims

| Claim | Status |
| --- | --- |
| “Cross-match generalization” evaluated on the World Cup final | **Exploratory only**: the test input is a 12-event partial sample; the report now labels coverage and withholds per-90 comparison. It is not evidence of league-wide generalization. |
| Bootstrap confidence intervals on xG/xT | **Computed** by resampling the actual input; with 12 events the interval is a small-sample description, not a calibrated property of a population. |
| xT grid monotonicity | **Verified by execution** on the static default grid; fitting on sparse subsets is labeled as research path. |
| “Gate 2.0 real pass rate 64.3%” | **Not Run / Unverified** — no run receipts or scoring sheet. |
| “Agent C narrowed 75–82% of causal claims” | **Not Run / Unverified** — no independent agent exists to produce these counts. |
| Zone counts 412 / 1,289 / 328 | **Unverified — impossible** with the 12-event sample. |

---

## 6. What *is* verified by execution

These are contract facts, not research conclusions:

- reducer possession, score, coverage and coordinate invariants
  (`test_third_pass_semantics.py`, 15 tests);
- historical clock/score/coverage API behavior
  (`test_third_pass_runtime.py`);
- evidence-graph relations, stable IDs and missing-receipt handling
  (`test_third_pass_evidence.py`);
- cross-match rate withholding and load-status separation
  (`test_third_pass_crossmatch.py`);
- benchmark outputs contain no constant accuracy/token/latency values
  (`test_track_c.py`, `test_track_e.py`);
- Story approval requires a registry gate verdict and editorial decision
  (`test_track_d.py`, `test_second_pass_repro.py`);
- challenge idempotency conflict/restart behavior
  (`test_third_pass_runtime.py`).

---

## 7. Remaining open research items

1. Full StatsBomb 2022 final and 2019 Champions League event files: **not in
   repository**; cannot reproduce any event-count or cross-match claim.
2. Live-model A/B/C comparison: **Not Run**; no billed dispatches executed in
   this audit.
3. Third independent agent: **Not Implemented**; needs a separate design and
   controlled experiment.
4. Calibrated xG/xT and league-level generalization: **Not Established**.

These items must stay `Not Run` / `Unavailable` in reports until artifacts
exist. Do not infer them from unit tests or deterministic contract runs.
