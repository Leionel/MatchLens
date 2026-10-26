# R6.4 Release Review — Production Readiness & Judge Experience

Date: 2026-10-26 (overnight autonomous run). Branch `r6.4/ui-competition-polish` → PR #1 → `main` after CI green.
Pair document: [UI_COMPETITION_POLISH_RESULTS.md](UI_COMPETITION_POLISH_RESULTS.md) (UI specifics).

## 1. Current production state (verified live, low load)

Public URL: **https://p01--matchlens--zfs7xk57gw42.code.run** (Northflank single container).

| Probe | Result |
| --- | --- |
| `GET /` anonymous | 200, 3.3 s (cold), static export served by FastAPI |
| `GET /api/health` | 200; `model_configured: false`, OAAI cache = 8 entries |
| `GET /api/matches` | 200, 405 KB; **87 catalogued, 8 ready = 1 real (`sb_3795221` England 2–1 Denmark, 4691 events) + 6 synthetic + 1 excerpt** |
| Session create (anonymous) | 200, 1.4 s; cap = 8 concurrent sessions (`503 session_capacity` beyond) |
| Real match journey | set_match 200 (1.6 s) → seek 4020 s **35 s cold** (OAAI + snapshot build; warm afterwards) → state 200 (51 change points) |
| Deterministic investigation | 200, 7.8 s, 14 tool receipts, 9 findings, honest `WITHHELD / not_formed` for a generic moment question |
| Evidence | 200, 36 receipts with match context |
| Cross-session isolation | second session reading first session's snapshot → **404 `snapshot_not_in_session`** |
| Producer/editorial endpoints | fail closed: **503 `editorial_identity_not_configured`** without server token; local-producer backdoor requires env opt-in + loopback |
| 404 shape | `{"detail":"api_not_found"}` — no path or env leakage |
| Rate limits | keyed to client IP (`create:<ip>` + global buckets) |
| Public agent runs | `/api/agent-runs` = **0** — no model runs exist there; the UI labels model status honestly (`Not run this match`, `No model called`) |

Conclusion: the site is genuinely usable anonymously end-to-end on the deterministic journey, and its health endpoint is *not* the only thing that works — the real-match path was exercised, not assumed.

## 2. P0s resolved this round

- **A5 release safety**: all work on a dedicated branch; `main` untouched until CI green; container image built and smoke-tested locally before pushing (see §5).
- **B1 honest home data**: Real-ready / Synthetic / Catalogued counts, all dynamic; no "80 verified = 80 installed" conflation. On the public instance the featured card falls back cleanly if no real match is installed (`fallback_reason` disclosed in the API, explicit empty-state copy in the UI).
- **B2 replay semantics**: Historical / Simulated replay labels in header and scoreboard; replay score vs `OFFICIAL FT` kept as two distinct facts; extra time shown as its own stretch of the momentum curve.
- **B3 uninstalled matches**: catalog keeps them browsable; recommended/featured sections only ever surface installed, analysis-ready matches.
- **C featured investigation**: `/api/featured` — deterministic, disclosed algorithm (provider provenance → event count → strongest shot-backed in-clock change point), no model, no hardcoded snapshot, no fabricated conclusions; memoised per catalog signature; per-candidate failure degrades to an explicit fallback.
- **503 dead-end** (found during this round's own smoke): boot retries with backoff + explicit Retry state (P1-E "no infinite loading").

## 3. P1s resolved

- **A1 execution mode** explicit before the click; paid engine disabled when unconfigured.
- **A2 historical runs**: public has none (`agent-runs: 0`) — a read-only explorer would have been an empty shell, so it was not built; local `evidence/r0.2/runs/` remains documented in DEMO_PLAN §3 Variant C with the "Historical real analysis" labelling rule.
- **A3 result order**: already Conclusion → Evidence → Alternatives → Limits → Actions → technical details; verified on the running product.
- **B judge journey**: the Featured card *is* the lightweight journey (no tutorial, no popups); every step is a real UI action.
- **C challenge journey**: claim context carried into the challenge modal; real outcome (`MAINTAINED`) with audited receipts on the revision timeline; evidence ids now navigate back to the match moment.
- **D materials**: README Live demo = the real URL; DEMO_PLAN rebased onto one match/one clock with real receipts + a one-match-per-segment rule; submission copy updated (public demo is deterministic-only).

## 4. Resource & persistence assessment

- **Observed spec**: 0.1 vCPU / 256 MB (per maintainer's console reading; not verifiable from outside). Single worker, bounded caches (`snapshot_cache` 6 entries/64 MB cap, `oaai_cache` 32, `featured_cache` 4 small JSON payloads) fit 256 MB for the deterministic journey; the cold real-match seek (~35 s CPU) is the worst judge-visible moment.
- **Recommendation (console action, not code)**: move to 512 MB if available before judging day. No engine rewrite was made or is needed to "fit" 256 MB.
- **Persistence**: the repo's tested deployment contract mounts `/data/matchlens` (runtime state + imported data) and sets `MATCHLENS_RUNTIME_DIR` / `MATCHLENS_DATA_DIR` ([RENDER_DEPLOY.md](RENDER_DEPLOY.md), [RAILWAY_DEPLOY.md](RAILWAY_DEPLOY.md), `render.yaml`). Whether the *Northflank* service actually attaches that volume **must be checked in the Northflank console** — it cannot be proven from outside. Until verified: claim registry, revisions, agent runs and the budget ledger survive only for the life of the container, and the deploy re-imports `sb_3795221` on boot (`MATCHLENS_BOOTSTRAP=1`). In-process sessions are explicitly *not* durable and are never described as such in the UI.
- **Restart recovery**: with the volume mounted, restarts restore the corpus + registries; without it, boot re-imports the one real match and the synthetic library (both verified paths — the smoke test ran with `MATCHLENS_BOOTSTRAP=0` against an empty runtime and still served health/index/featured 200).

## 5. Engineering verification

| Check | Result |
| --- | --- |
| Backend suite | **378 passed** (156 s) |
| Frontend build + typecheck | **0 errors** |
| Playwright full suite (desktop + responsive) | **50 passed / 0 failed** |
| axe-core (3 core pages, wcag2a/aa) | **0 serious/critical** |
| Overflow at 6 viewports | none |
| Docker build (linux/amd64, 356 MB) | success; container smoke: `/api/health` 200, `/` 200, `/api/featured` 200 with `MATCHLENS_BOOTSTRAP=0` |
| GitHub Actions on PR #1 | all required checks green before merge (frontend build, backend pytest, integration corpus, browser e2e, docker build & smoke) |
| Rollback | single-revert per commit; `main` fast-forward history preserved |

Base-image note for reproducibility: this machine's Docker daemon mirror returned 401 for `python:3.13-slim`; pulling the three bases from their upstream registries and re-tagging resolved it. CI is unaffected.

## 6. Remaining risks (not fixed, and why)

1. **Northflank volume unverified** — console-only action; documented above, listed in §7.
2. **256 MB headroom** — works for the deterministic journey; a 512 MB upgrade is recommended, not required.
3. **Cold real-match seek ~35 s** on the public instance — cached after first build; UI shows progress. Fixing it means persistence-layer work that is riskier than the deadline allows.
4. **A featured moment can end `WITHHELD`** — honest gate behaviour; the result still leads with a real finding and states why nothing was registered.
5. **e2e `r6-2.spec.ts:278` order-dependent flake** — reproduced on `main` (8ab1a84) before this branch; passes in combined runs. Pre-existing, tracked here rather than hot-fixed.
6. **Light theme** spot-checked at 1440 on hub + detail; a full-theme sweep at every viewport was out of scope.

## 7. Manual actions needed in the Northflank console (owner)

1. Confirm a **persistent volume** is actually mounted at `/data/matchlens` and both `MATCHLENS_RUNTIME_DIR` / `MATCHLENS_DATA_DIR` point inside it; otherwise attach one or accept the re-import-on-boot behaviour knowingly.
2. Confirm the deployed **image digest / commit** matches the merge of PR #1 (the health endpoint deliberately does not expose build identity to anonymous visitors; check the console's deploy log instead).
3. Optionally upgrade to **512 MB** before judging day.
4. If live two-agent demos are wanted on the public URL: configure `DEEPSEEK_API_KEY` there consciously (budget ceiling stays `MATCHLENS_MAX_REQUESTS=32` / `$1.00`) — the current honest default is deterministic-only.

## 8. Go / No-Go for the 2026-10-27 submission

**GO.**

- The public site serves the full anonymous deterministic journey (verified live, not assumed from `/api/health`), is honest about what runs where, and recovers from capacity pressure.
- The first screen now explains the product and lands a judge on a sourced, gate-checked investigation in two clicks.
- All engineering gates are green on the merged branch; the container image matches what CI builds.
- Every remaining risk above is either a console action, a pre-existing flake, or a disclosed honesty behaviour — none blocks submission.

Caveat attached to the GO: the Go assumes items §7.1–7.2 are confirmed in the console before the demo video is recorded, since the closing card now names the live URL.
