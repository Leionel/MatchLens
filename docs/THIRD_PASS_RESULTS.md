# Third-Pass Results & Verification Record

**Date**: 2026-10-23
**Environment**: Windows 10.0.26200 x64, Python 3.13.9 (project venv), Node.js 24.16.0 local / 22 in CI, Next.js 16.4.2
**Baseline at audit start**: `e317451` (review baseline `9b9bb4c`)
**Scope**: P0-A…P1-F from the third-pass brief plus UI refinement.

> A green test suite is contract evidence, not release evidence. Live-model
> quality, full-data reproducibility and external review remain **Not Run**.

---

## 1. Commands and raw results

### 1.1 Backend test suite

```powershell
services\api\.venv\Scripts\python.exe -m pytest services/api/tests/ -q
```

Raw output (final run):

```text
199 passed in 10.58s
```

The remaining warning is the FastAPI duplicate-operation-ID warning that was
subsequently removed by splitting the catch-all route into four explicit
operations; the contract test was re-run green afterwards (3 passed); the final full run was 199 passed in 10.58s.

### 1.2 Frontend typecheck and production build

```powershell
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

```text
> matchlens-web@0.1.0 typecheck
> tsc --noEmit
# exit 0

> next build
✓ Compiled successfully
✓ Generating static pages (4/4)
Route (app): /, /_not-found, /icon.svg
# exit 0
```

### 1.3 OpenAPI contract

`services/api/tests/test_third_pass_contract.py` (3 tests): required paths
exist; story/graph response keys exist; benchmark has no fabricated
cost/accuracy and reports `live_model_status = "not_run"`. **3 passed.**

### 1.4 Targeted suites

| Suite | Command | Result |
| --- | --- | --- |
| Football semantics | `pytest tests/test_third_pass_semantics.py -q` | 15 passed |
| Historical runtime / E2E seek | `pytest tests/test_third_pass_runtime.py -q` | 10 passed |
| Evidence Graph E2E | `pytest tests/test_third_pass_evidence.py -q` | 5 passed |
| Cross-match coverage | `pytest tests/test_third_pass_crossmatch.py -q` | 3 passed |
| OpenAPI contract | `pytest tests/test_third_pass_contract.py -q` | 3 passed |
| Story approval adversarial | included in runtime suite + `test_track_d.py` | passed |
| Challenge idempotency/restart | `test_third_pass_runtime.py` | passed |

---

## 2. Runtime benchmark (actual measurements)

Script: `scripts/benchmark_third_pass.py`
Artifact: `evidence/third_pass/runtime_benchmark.json`

Inputs:

- `sb_wc2022_sample_12`: the bundled real StatsBomb sample, 12 events, partial coverage.
- `synthetic_volume_x1`: 148 synthetic events.
- `synthetic_volume_x8`: 1,184 events.
- `synthetic_volume_x28`: 4,144 events.
- The scaled streams are a **volume stress generator** (events replicated at the same match clock), not realistic football data.

Medians over three runs (ms):

| Stream | Events | reduce_match | build_sequences | OAAI (720s) | player spotlight |
| --- | ---: | ---: | ---: | ---: | ---: |
| sample_12 | 12 | 0.05 | 0.02 | 0.69 | 0.04 |
| volume_x1 | 148 | 0.72 | 0.22 | 2.89 | 0.30 |
| volume_x8 | 1,184 | 6.48 | 5.08 | 11.00 | 5.35 |
| volume_x28 | 4,144 | 24.33 | 20.61 | 38.59 | 21.34 |

Largest snapshot:

```text
event_count: 4144
snapshot_bytes: 3,151,138
freeze: 608.18 ms (single run)
evidence_graph: 346.70 ms (single run)
graph nodes/edges: 763 / 763
peak traced memory: 16.47 MB
```

Interpretation:

- The OAAI no-dead-time path is incremental (`O(events + steps)`), so doubling
  the event count no longer doubles the causal-prefix rescan.
- Snapshot serialization (3.1 MB) is the dominant cost at 4k events, not the
  reducer or OAAI. Snapshot creation is cached per session/at/version; it is
  not on the per-tick SSE path.
- No p95 or “significant speed-up” claim is made: these are single-machine
  medians on a synthetic volume stream.

---

## 3. Browser journey

Tooling: Qoder in-app browser via CDP. The in-app browser reported
`viewport=0x0, visible=false`, so **screenshots were unavailable**. Verification
was structural (accessibility snapshot) plus computed-style checks. This is an
explicit limitation, not a visual inspection.

Executed journey:

1. Fresh session, synthetic match: scoreboard, Evidence Rail, OAAI, tactical
   stage, event stream render without fatal errors.
2. Switched to `sb_wc2022_final`: header competition changes to
   `FIFA World Cup`; coverage becomes **Partial**; official final `3–3` is shown
   separately from the as-of score.
3. Seek to `24:00`: as-of score becomes `1–0`, official remains `3–3`;
   observed coverage bar reaches `24.7%`; the event stream lists real
   Argentina/France events and the stage labels use Argentina/France.
4. Story tab: backend chapters (Opening/Middle/Final phase) render recorded
   counts; registry claims show `Gate pass` + `Pending editorial`, with evidence
   hashes and a separate gate-version label. No caller-controlled approval UI.
5. Validation tab: benchmark table shows executed rule pipeline results,
   `Live model: Not Run`, `Token cost —`, measured latency; no constant
   accuracy/cost claims.
6. Computed-style check after the Radix migration:
   `bodyBackground = rgb(252,252,253)` in light mode (`slate1`), body text
   `rgb(28,32,36)` (`slate12`), border width `0.67px` at DPR scaling,
   panel radius `10px`; font sizes in use: `12/14/18/28/34px` (34 is the
   scoreboard numeral display).

Console and network: no JavaScript errors were observed in the final runs;
`/api/sessions`, `/api/stream`, `/api/control`, `/api/matches/.../story`,
and `/api/benchmark/abc` returned 200. A transient `Request failed (500)` was
traced to a real `NameError` in `exploration.py` during the migration and fixed;
the final journey was repeated after the fix.

User-supplied screenshot review (after the structural run) found two real visual
defects and both were fixed:

- the pitch watermark read as a huge clipped `HFC ENTRY LINE (70M)` because a CSS
  normalisation pass promoted a 2px SVG-viewBox label to 12px; it was restored
  to 2px and verified at 79×8px rendered size;
- light-theme layer buttons and secondary labels used `slate-7`, which is a
  near-white grey in the light scale; text tokens were moved to
  `slate-11`/`slate-12`, and active controls now use the Radix soft-accent pair
  (`green-3` background + `green-11` text).

Computed style after the fix: `body` 14px; interface sizes 12/14/18/28 (plus the
scoreboard numerals 34); Borders 0.5px CSS (0.67px device at the current DPR).

Not executed:

- No screenshot-based visual QA (hidden viewport).
- No mobile-device emulation run; responsive rules are implemented but not
  device-verified.
- No ten-minute public-network SSE soak.

---

## 4. Code-to-Claim Audit

Chain: `Football Events → Possession → Metrics → Snapshot → Agent → Gate → Story → Evidence Graph`.

| Link | Verified implementation | Residual boundary |
| --- | --- | --- |
| Events | `StatsBombAdapter` keeps provider team/possession IDs; canonical IDs are single-prefixed; unknown providers raise | Only 12 real events bundled |
| Possession | `reduce_match` state machine; boundary-based IDs; previous-owner time; period/data gaps separated | Synthetic `shot_rebound` is a continuity assumption, labeled |
| Metrics | `metric_receipts` uses possession IDs; empty denominators return `null`/`unobserved` | xG cumulative receipt is not implemented as a document-wide metric |
| Snapshot | Every route uses `freeze_with_context` + `MatchContext.duration`; 5400s historical snapshots work; as-of score | Snapshot JSON at 4k events is ~3.1 MB |
| Agent | MAF `Analyst → Verifier` (two model agents); deterministic tools are not called “agents” | No third model agent; no live A/B/C run |
| Gate | Online `publication_gate` writes accepted cards to `ClaimRegistry` with `publication_gate-v1`; deterministic registry uses `publication_gate_2_0` (`2.0`) | Gate 2.0 is not the online gate |
| Story | Reads only registry records for the match+snapshot; broadcast approval requires both gate and editorial decision | UI does not yet expose a governed editorial approval flow |
| Evidence Graph | Stable SHA-256 node IDs; real events, receipts, claims, gate verdicts, challenges, revisions; missing receipts become `evidence_gap` with `null` | Event nodes capped at 400 per graph response (`events_truncated` flag) |

Version consistency: snapshots carry `source_data_digest`, `data_version`,
`metric_version`, coordinate frame and coverage. The UI `data_version` is a
source fingerprint (mtime+size) for historical files and
`synthetic-controlled-r02` for synthetic data.

---

## 5. Deliberately not executed / open items

| Item | Status | Why |
| --- | --- | --- |
| Full 2022 World Cup final event file (4,354 events) | **Unavailable** | Not in repository; cannot be reproduced |
| `sb_cl2019_final` | **Unavailable** | File and metadata absent |
| Live DeepSeek A/B/C benchmark | **Not Run** | No billed dispatch performed |
| True third agent | **Not Implemented** | Requires design, tool permissions, cost and controlled experiment |
| Calibrated xG/xT and league generalization | **Not Established** | 12-event sample is insufficient |
| External human research/audience review | **Not Run** | No participants |
| Remote GitHub Actions CI | **Not executed locally** | Workflow file exists; remote run occurs on push |
| Screenshot visual QA | **Not available** | In-app browser viewport 0×0 |
| Mobile device verification | **Not Run** | Only CSS breakpoints implemented |

---

## 6. Release decision

The third-pass contract fixes are **verified by execution**. The product does
**not** meet a research-release bar yet because the full datasets, live-model
evaluation and external review are absent. Can it be demonstrated locally with
the 12-event historical sample and the synthetic match? Yes, subject to the
browser-viewport limitation above. Can its benchmark tables be cited as model
accuracy or cross-league generalization? No.
