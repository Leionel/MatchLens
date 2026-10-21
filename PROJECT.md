# Project: MatchLens AI — Strategic Roadmap Tracks C, D, E & Cockpit Refactor

## Architecture
MatchLens AI is an evidence-first interactive football tactical intelligence cockpit.
- **Backend**: Python 3.11+ / FastAPI (`services/api/matchlens/`), structured modularly:
  - `schema.py`: Core domain models, UnifiedEvent, MatchSnapshot, Claim, DerivedMetric.
  - `football.py`: Synthesizer, pitch coordinate transformations, possession sequences (S2), 9-zone density (S3).
  - `oaai.py`: Observed Attacking Activity Index calculation, momentum waves, inflection detection.
  - `contracts.py`: Publication Gate, Fact Slot binding, verification contracts.
  - `agents.py`: Microsoft Agent Framework multi-agent workflows.
  - `attribution.py` (Track C): Event Attribution Specialist, TemporalWindowDecomposition, CausalChainQuery, AlternativeHypothesisAssessment.
  - `gate.py` / Gate 2.0 (Track C): Claim level consistency, metric version validation, counterevidence gating.
  - `sufficiency.py` (Track C): Data Sufficiency assessment, observable proxies.
  - `benchmark.py` (Track C/E): A/B/C agent benchmark harness and evaluation.
  - `story.py` (Track D): BL-06 Match Story narrative engine, Content Approval Flow.
  - `export.py` (Track D): SVG/JSON/report export engine.
  - `validation.py` (Track E): BL-09 scientific evaluation benchmark, Bootstrap resampling, cross-match generalization.
  - `whatif.py` (Track E): Level 3 exploratory What-if sandbox.
- **Frontend**: Next.js 16 + React 19 + TypeScript (`apps/web`), static export mode:
  - `tokens.css`: Obsidian Tactical Dark design tokens (#0b0f19 / #111827, Pitch Emerald #10b981, Cyan/Sky #38bdf8).
  - `app/components/cockpit/`: Multi-pane architecture:
    - `TacticalHeader.tsx`: Match switcher, global timeline scrubber, 3 perspective switchers, live status.
    - `WorkspaceTabs.tsx`: Navigation bar for the 4 dedicated workspaces.
    - `MatchCenterWorkspace.tsx`: OAAI wave, cumulative xG, attacking corridors, live event feed.
    - `TacticalLabWorkspace.tsx`: Interactive 2D pitch, 9-zone density heatmap ΔD(z), S2 sequences, pass network.
    - `StoryAgentWorkbench.tsx`: Event Attribution breakdown, Gate 2.0 evidence audit, Match Story narrative generator, Content Approval flow.
    - `ValidationLabWorkspace.tsx`: xT grid contraction matrix, Agent A/B/C benchmark report, Data Sufficiency coverage audit.
    - `InspectorDrawer.tsx`: Collapsible side drawer for deep inspection of sequences, zones, and claims.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Event Attribution Specialist (3rd Agent) | Dedicated attribution agent outputting strictly Level 1-2 | M1 | ORIGINAL_REQUEST §R1 |
| 2 | TemporalWindowDecomposition Tool | Objective event contribution weighting in OAAI/xT shifts | M1 | ORIGINAL_REQUEST §R1 |
| 3 | CausalChainQuery Tool | Backward temporal and spatial chain extraction for sequences | M1 | ORIGINAL_REQUEST §R1 |
| 4 | AlternativeHypothesisAssessment Tool | Assessment of rival explanations & dispute annotations | M1 | ORIGINAL_REQUEST §R1 |
| 5 | Publication Gate 2.0 | Level consistency, event/metric ID verification, counterevidence rule | M1 | ORIGINAL_REQUEST §R1 |
| 6 | Data Sufficiency Notification System | Lack-of-tracking alert with observable proxies (6s recovery, ΔD) | M1 | ORIGINAL_REQUEST §R1 |
| 7 | A/B/C Agent Benchmark Harness | Quantitative audit harness comparing dual vs dual+tools vs tri-agent | M1 | ORIGINAL_REQUEST §R1 |
| 8 | BL-06 Match Story Narrative Engine | Structured narrative generated from OAAI inflection points & S2 | M2 | ORIGINAL_REQUEST §R2 |
| 9 | Content Approval Flow | Strict Gate 2.0 gating for published vs draft claims | M2 | ORIGINAL_REQUEST §R2 |
| 10 | 3 Perspective Switchers | Coach/Analyst, Broadcast/Media, Deep Fan profiles | M2 | ORIGINAL_REQUEST §R2 |
| 11 | Chart & Evidence Card Export Engine | Standard JSON, high-fidelity SVG, formatted reports | M2 | ORIGINAL_REQUEST §R2 |
| 12 | BL-09 Scientific Evaluation Benchmark | Bootstrap resampling, cross-match generalization, MAE/RMSE/r | M3 | ORIGINAL_REQUEST §R3 |
| 13 | Automated A/B/C Agent Evaluation | Multi-match evaluation on Qatar World Cup Final & simulations | M3 | ORIGINAL_REQUEST §R3 |
| 14 | What-if Counterfactual Analysis Sandbox | Level 3 exploratory simulation sandbox marked Research | M3 | ORIGINAL_REQUEST §R3 |
| 15 | Obsidian Tactical Dark Theme | Professional dark palette, emerald turf, cyan highlights | M4 | ORIGINAL_REQUEST §R4 |
| 16 | Tactical Header Control Center | Global match switcher, timeline scrubber, perspective switcher | M4 | ORIGINAL_REQUEST §R4 |
| 17 | Match Center Workspace | Match overview, OAAI wave, xG step curve, corridor analysis | M4 | ORIGINAL_REQUEST §R4 |
| 18 | Tactical Lab Workspace | 2D pitch, 9-zone density ΔD(z), S2 sequences, pass network | M4 | ORIGINAL_REQUEST §R4 |
| 19 | Story & Agent Workbench Workspace | Attribution breakdown, Gate 2.0 audit, Match Story, approval flow | M4 | ORIGINAL_REQUEST §R4 |
| 20 | Validation Lab Workspace | xT contraction matrix, Agent A/B/C benchmark, Data Sufficiency | M4 | ORIGINAL_REQUEST §R4 |
| 21 | Collapsible Inspector Drawer | Non-blocking drawer for sequence, region, and claim drill-down | M4 | ORIGINAL_REQUEST §R4 |
| 22 | Zero Regression & Verification | 100% pass on 98 existing pytests + new pytests, clean npm build | M5 | ORIGINAL_REQUEST §Acceptance |
| 23 | Functional Module Git Commits | Clean commits separated by Track C, Track D, Track E, UI Cockpit | M5 | ORIGINAL_REQUEST §Acceptance |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Track C: Evidence-Grounded Agent Intelligence & Gate 2.0 | Backend: 3rd Agent, 3 Tools, Gate 2.0, Sufficiency, A/B/C Harness + Tests | none | DONE |
| M2 | Track D: Broadcast & Personalization | Backend: BL-06 Match Story, Content Approval Flow, Perspectives, Export Engine + Tests | M1 | PLANNED |
| M3 | Track E: Research & Validation | Backend: BL-09 Benchmark, Bootstrap, Multi-Match Eval, What-if Sandbox + Tests | M1 | DONE |
| M4 | UI/UX Cockpit Modernization & 4 Workspaces | Frontend: Obsidian theme, 4 Workspaces, Header, Inspector Drawer, Full Build | M1, M2, M3 | DONE |
| M5 | Full Verification, Zero-Regression & Git Commits | Full 98+ pytest suite, npm run build, functional module git commits | M1, M2, M3, M4 | PLANNED |

## Interface Contracts
### Track C ↔ Track D
- `EventAttributionResult`: Provides weighted top events, causal chain, and rival hypotheses for any time window $[t_1, t_2]$.
- `Gate20Verdict`: Enforces `claim_level`, verified event IDs, and `counterevidence` before an insight can be approved into `MatchStory`.
### Track C/D/E ↔ Frontend (Cockpit)
- `/api/attribution/window`: Accepts `match_id`, `window_start`, `window_end`; returns `TemporalWindowDecomposition` + `AlternativeHypothesisAssessment`.
- `/api/story/{match_id}`: Returns structured story chapters tied to OAAI inflection points and S2 sequence IDs.
- `/api/export/card` & `/api/export/chart`: Returns SVG string or formatted JSON download.
- `/api/validation/benchmark`: Returns quantitative A/B/C benchmark metrics (Gate interception rate, accuracy, token cost, latency).
- `/api/validation/bootstrap`: Returns Bootstrap resampling confidence intervals and MAE/RMSE/r metrics.

## Code Layout
- `services/api/matchlens/`:
  - `attribution.py`: Tools (`temporal_window_decomposition`, `causal_chain_query`, `alternative_hypothesis_assessment`) & `EventAttributionSpecialist`.
  - `gate.py`: Gate 2.0 rules, claim validation, ID verification.
  - `sufficiency.py`: Data Sufficiency notification & proxy metrics.
  - `benchmark.py`: A/B/C agent comparison harness.
  - `story.py`: Match Story generation, chaptering, content approval.
  - `export.py`: JSON/SVG/formatted report exporter.
  - `validation.py`: BL-09 scientific benchmark, bootstrap resampling.
  - `whatif.py`: Level 3 counterfactual sandbox.
- `services/api/tests/`:
  - Existing 98 tests (preserved 100%).
  - `test_track_c.py`: Verification for 3rd agent, tools, Gate 2.0, Sufficiency, A/B/C harness.
  - `test_track_d.py`: Verification for Match Story, approval flow, export engine.
  - `test_track_e.py`: Verification for BL-09, bootstrap, what-if sandbox.
- `apps/web/`:
  - `app/tokens.css`: Design tokens.
  - `app/globals.css`: Tactical styling.
  - `app/components/cockpit/`:
    - `TacticalHeader.tsx`
    - `WorkspaceTabs.tsx`
    - `MatchCenterWorkspace.tsx`
    - `TacticalLabWorkspace.tsx`
    - `StoryAgentWorkbench.tsx`
    - `ValidationLabWorkspace.tsx`
    - `InspectorDrawer.tsx`
  - `app/page.tsx`: Modern cockpit entry integrating the 4 workspaces and drawer.
