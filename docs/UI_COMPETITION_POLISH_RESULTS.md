# R6.4 Competition UI Polish — Results

Branch: `r6.4/ui-competition-polish` (PR #1, squash-merged to `main` after CI green).
Baseline audited: `8ab1a84`. All screenshots in this document are real captures of the
running product at `evidence/r6.4/` (baseline captures of the pre-change build are in
`.runtime` scratch, not committed).

## 1. Before / After

| Surface | Before | After | Why it is better |
| --- | --- | --- | --- |
| Match Hub first screen | "Start with a real match" heading, `87 analysis ready / 87 catalogued` (ambiguous — the public deployment had 8 ready), then a filter form, then an 87-row catalog | Value-proposition hero ("Football intelligence you can challenge." / "Understand the moment. Inspect the evidence. Challenge the conclusion."), a **Featured Investigation** card (real match, real OAAI change point, supporting events, "Explore this moment →"), and three honest counts: **Real matches ready / Simulated scenarios / Catalogued** (all from `/api/matches`) | A judge sees what the product does and where to click within seconds; the counts cannot claim installed matches that are only catalogued |
| Featured → investigation | No path; a visitor browsed rows and hopefully found Investigate | `Explore this moment` deep-links into Intelligence Studio with the question pre-filled, the replay clock aligned to the moment, and the deterministic plan already running | First sourced result in two clicks, no README needed |
| Replay semantics | Header and scoreboard said **"Live replay"** for recorded historical matches | Header: **Historical replay** (provider) / **Simulated replay** (synthetic); scoreboard status pill uses the same rule | A recorded match replayed along its own clock is not a live feed — the label no longer lies |
| Scoreboard vs totals | The scoreboard repeated a `LAST 3 MIN` possession gauge *and* a separate labelled `Last 3 min` strip below — the same measurement twice | Gauge removed; the labelled strip is the only window scope; `WHOLE MATCH` row untouched | One number, one scope, one place |
| Key players | Two "Unknown 0 0 0" cards (unattributed event buckets) rendered as if broken | Filtered out; named players with recorded actions fill the slots | Debug-looking cards gone; real actors (Müller, Robben, Sneijder…) shown |
| Boot failure | `503 session_capacity` → dead spinner + toast, forever | Backoff retry (1.5/3/5/8 s) with status copy, then an explicit **Retry connection** state | A judge hitting a full session cap recovers without F5-ing blindly |
| Intelligence Studio empty state | Question box, then ~60 % blank viewport | Execution-mode line (**"Deterministic · No model called"** / **"Real multi-agent · Model required"**), paid engine disabled when no model is configured, and **"Saved investigations in this session"** from real `GET /api/investigations` records | The mode is stated before the first click; the empty state is real data, not a placeholder |
| Evidence → match | Clicking an event id in the evidence drawer set an invisible selection | The drawer click aligns the replay clock to the event's own second and returns to Match Detail with the event selected | Evidence is now a door back to the pitch, per Click-to-Inspect |

## 2. Visual audit (main findings → resolution)

- **P0 First-screen focus** was the catalog, not the product → replaced by hero + featured card (see §1).
- **P0 Duplicate information**: scoreboard gauge vs window strip vs totals row → deduplicated.
- **P0 Dishonest labels**: "Live replay", "analysis ready 87" → replaced with source-aware labels and three-state counts.
- **P1 Broken-looking states**: Unknown player cards; 503 dead-end; blank studio viewport → fixed as above.
- **P2 Catalog noise**: per-row repeated `Provider data · N events · Complete` chips were reviewed and deliberately **kept** — they are the only provenance signal inside the catalog, and filters hide them anyway; visual weight was already reduced in the previous round.
- Not flagged after inspection: the apparent "RESULTS FOR ANALYSTS" red banner in the low-res audit capture does not exist in the DOM (misread of a downscaled screenshot).

## 3. User journeys (verified in the running product)

**A first-visit (Journey A+C):** Hub → featured card shows *Portugal 0 : 0 France, Moment 106′, OAAI +2.73* with supporting events (Leão shot blocked…) → **Explore this moment** → Studio opens with the question and clock aligned → deterministic plan with receipts. Two clicks, zero jargon.

**B investigation (Journey B):** Same panel shows Conclusion → Evidence (findings with event ids) → Alternative explanations (e.g. *opponent pressing structure* marked `insufficient_evidence · L4` with the reason) → What this cannot decide → Back to this moment. Mode line reads **Deterministic · No model called**.

**C registered claim + challenge (Journey D):** At a goal-backed moment (Inter, 36:40) the deterministic plan forms `goal_sequence` → **Confirm and register claim** → `claim-goal-sequence-n / 918d58b7f1bd` → Challenge modal (claim context carried, adversarial angles) → submit → auto-switched to **Revisions (1)** with a real outcome (`MAINTAINED`, summary: the claim asserts only on-ball observational metrics) and audited receipts.

**D broadcast (Journey E):** The approved claim renders the broadcast preview: `HISTORICAL PROVIDER DATA · MATCH TIME 36:40`, score bug, headline, `APPROVED L1 registered claim`, `EVIDENCE REFS N.goals.match` — and the strip is explicitly labelled **PREVIEW · NOT BROADCAST OUTPUT**. Producer approval still requires the producer token (fail-closed; public instance returns `503 editorial_identity_not_configured` without one).

**E mobile (Journey F):** hub → detail → insight → investigation → evidence all captured at 390×844 and 360×800; no horizontal overflow; core actions ≥ 34 px touch targets; the boot-retry state is reachable on mobile too.

## 4. Screenshots (real, in `evidence/r6.4/`)

`final-hub-{1440,1920,768,390,360}.png`, `final-hub-1440-light.png`, `final-detail-{1440,1920,390,360}.png`,
`final-detail-1440-light.png`, `final-studio-{1440,390}.png`, `final-tactical-1440.png`,
`final-validation-1440.png`, `final-producer-1440.png`, `new-journey-c.png` (deterministic result),
`journey-d-registered.png` (claim + broadcast preview), `journey-d-modal.png` (challenge modal),
`journey-d-timeline2.png` (revision timeline).

## 5. Functionality preserved

No analysis, Agent, Evidence, Challenge, Revision, Producer, budget or provenance capability was removed or weakened. The deterministic planner, publication gate, claim registry, revision timeline, broadcast export, what-if sandbox, xT grid, profiles and cross-match compare all remain; the e2e suite (50 tests) passes unchanged except two assertions updated to the new hub headline and the removed duplicate gauge. Backend contracts are additive only (`/api/featured`).

## 6. Verification results

| Check | Result |
| --- | --- |
| Backend `pytest tests/ -q` | **378 passed** (baseline moved 313 → 378; 4 new `/api/featured` tests) |
| Frontend `npm run build` | **0 errors** (Next.js 16 static export) |
| Playwright full suite | **50 passed / 0 failed / 1 skipped** (corpus-gated) |
| axe-core (wcag2a/2aa/21a/21aa) hub + detail + studio | **0 serious/critical violations** |
| Horizontal overflow 1440/1920/1024/768/390/360 | none |
| Console page errors across all captures | none |
| Docker image build + smoke (`MATCHLENS_BOOTSTRAP=0`) | health 200, index 200, featured 200 |
| Public smoke (live Northflank instance) | session / set_match real / seek / deterministic investigate / evidence all 200; cross-session evidence 404 (`snapshot_not_in_session`); producer endpoints fail closed; `/api/agent-runs` = 0 (no model runs there, honestly labelled) |

## 7. Commits & CI

- `c64aeeb` feat(api): deterministic featured-investigation endpoint (+4 tests)
- `b3f471d` feat(web): featured-investigation first screen, honest states and replay semantics
- `aa2b48c` docs: point submission materials at the real deployment and fix demo data mixing
- `ea23e26` test(e2e): sync spec contracts with the R6.4 hub and scoreboard changes
- PR #1: https://github.com/Leionel/MatchLens/pull/1 (CI: all required checks green before merge)

## 8. Remaining risks

- **Public first-seek latency**: the first seek into a real match builds OAAI + snapshot (~35 s on the 0.1 vCPU public instance). Cached afterwards; the UI shows progress. Not fixable without caching changes that are riskier than the deadline allows.
- **Featured moment may end `WITHHELD`**: the gate only registers claims the window receipts support. The result still shows a real finding as the headline and says why nothing was registered. Selection prefers shot-backed points to raise the odds; no guarantee is claimed.
- **e2e `r6-2.spec.ts:278`** fails when run fully isolated, passes in combined runs; reproduced on `main` before this branch (pre-existing, order-dependent).
- **Historical recorded model runs** (`evidence/r0.2/runs/`) are referenced by the demo plan but the public deployment has zero model runs, so no read-only historical-run explorer was added — showing an empty explorer would be noise. They remain available locally.
