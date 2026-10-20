# MatchLens AI: Strategy

Technical revision: 2026-10-19, America/Los_Angeles. Owner: one developer with Codex assistance. The isolated provider Spike exists; the product is not implemented. Read [TECH_SPIKE](TECH_SPIKE.md) for actual compatibility results, [SPEC](SPEC.md) for product contracts, [ARCHITECTURE](ARCHITECTURE.md) for execution, [ROADMAP](ROADMAP.md) for tasks, [EVALUATION](EVALUATION.md) for release gates, and [DEMO_PLAN](DEMO_PLAN.md) for submission.

## Decision

Build **MatchLens AI — Football intelligence you can challenge**. Keep the repository name `match-lens`; use this narrower pitch instead of promising unrestricted real-time tactical intelligence.

The product is a small broadcast analysis desk. A viewer sees what changed, why it matters, and the evidence that could contradict the explanation. Its signature moment is **“More possession. But more danger?”** Two agents investigate the same immutable match window; one proposes an explanation, the other looks for counterevidence. A card is published, qualified, or withheld. A click reveals the event sequence and window comparison. Fan and Analyst modes present the same approved facts differently.

Primary category target: Best Multi-Agent System, alongside general prize competitiveness through a complete ingest → interpret → explain → render → personalize loop. **Drop Best Use of Microsoft Foundry from the current targets.** Foundry project creation is unavailable to this account and is no longer a development, inference, tracing or hosting prerequisite. If evaluation cannot demonstrate useful specialist collaboration, lead with the product's explainability and disclose the comparative result.

## Official rules: verified facts and implementation consequences

Read the complete official rules on 2026-10-19. The rules file's latest path-specific commit was `d7d8fc3c8befddf3ba530a16ce1092390bae8d1b`, dated 2026-09-28. Downloaded raw-file SHA-256: `9af798c584c5670f37c7c284e15fbe8baf40257dbe6e2cb0e04d2d2b21743034`.

Sources: [current rules](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md), [pinned rules](https://github.com/microsoft/insidethegamehackathon/blob/d7d8fc3c8befddf3ba530a16ce1092390bae8d1b/OFFICIAL%20RULES.md). Section references below point to that text. This table records rule facts; the final column is our implementation decision.

| Rule / section | Verified requirement | Project consequence |
| --- | --- | --- |
| §1 | Registration closes Oct 20, 2026, 12:00 PT; submission closes Oct 27, 23:59 PT | User reports registration complete; preserve confirmation and submit early |
| §4.3 | New project after registration began, Sep 29, 2026, 09:00 PT | Start fresh; preserve dated commits and dependency provenance |
| §§3, 4.6, 4.11–12 | Adult eligibility, exclusions, ownership, licensed dependencies and support conditions apply | Participant checks personal eligibility and applicable support terms |
| §§4.1, 4.7 | Synthetic, football-realistic events; intelligence, explanation, rendering and personalization | Build coherent event replay and two audience modes |
| §4.4 | Public GitHub; English pitch; public functioning demo video **under 120 seconds** | Target 115 seconds, own graphics and narration |
| §§4.8–9, 1 | Free working test access through Nov 10, 2026, 23:59 PT; English materials or translations | Fund judging access and supply reproducible English instructions |
| §§4.2, 8 | At most one general prize and one category prize | Focus category effort; two targets do not mean two category wins |
| §§5, 11.4–6 | Post-deadline changes restricted; rules prevail; ambiguities require clarification | Freeze a submission commit and recheck rules before submitting |

PT uses `America/Los_Angeles`: the deadline is `2026-10-27T23:59:00-07:00` / `2026-10-28T06:59:00Z`; judging ends `2026-11-10T23:59:00-08:00`. Daylight saving changes during the judging period.

The five-stage challenge is central to category fit. Player tagging, speed, pass difficulty, video auto-eventing and multilingual storytelling are suggestions in §4.1, not a requirement to implement every example. The rules name Microsoft hero technologies and require reasonable technology fit in Stage One; they do not require every listed SDK, MCP, Kubernetes, Fabric or A2A. §4.2 explicitly permits purposeful multi-agent collaboration using Microsoft Agent Framework or GitHub Copilot. Show the framework's actual runtime collaboration with DeepSeek, without claiming Foundry use.

§6 has a viability pass/fail stage followed by five equal 20% criteria:

| Criterion | Evidence we will show |
| --- | --- |
| Technological Implementation | Stateful reproducible synthetic data, clear contracts, traceable statistics, maintainable code |
| Agentic Design & Innovation | Distinct proposer/challenger roles, shared snapshot, bounded handoff, failure recovery and measured ablation |
| Real-World Impact & Applicability | A producer or viewer can inspect and correct a misleading match narrative before sharing it |
| User Experience & Presentation | One understandable match story, responsive dashboard, direct evidence navigation |
| Adherence to Hackathon Category | Distinct runtime roles, immutable handoff, counterevidence, recovery and an honest single-agent comparison |

**Verification boundary.** GitHub rules were rechecked during this revision. The user-provided form screenshots show the challenge “The Synthetic Match Insights Engine for Premier League Studio,” title/tagline limits of 140/300, and repository addition after saving. The form was not operated or submitted by the agent. Category selection, uploads, portal timezone, additional conditions and registration receipt still need checking. §4.2 calls the category “Best Multi-Agent System”; §8 uses “Best Multi-Agent Orchestration.” Use the form's actual label. Plan to the explicit submission deadline and judging end. If applicable, the entrant must resolve personal eligibility or §4.12 support ambiguity with the organizer; no organizer contact has been made.

## Why a dashboard plus generated commentary is insufficient

It can demonstrate API integration but leaves the difficult work invisible: detecting a meaningful change, separating possession from threat, finding opposing evidence, and retaining useful output during failure. Adding three role prompts without distinct evidence access or measured outcomes has little explanatory value for judges.

Existing products already cover broad storytelling. [OptaAI Studio](https://www.statsperform.com/products/opta-ai-studio/) advertises research, live insight and visual content workflows. The [Premier League–Microsoft announcement](https://www.premierleague.com/en/news/4338015) describes personalized fan experiences and real-time overlays. These sources establish a crowded baseline, not the feature boundaries of every competitor. Our differentiation hypothesis is an inspectable, challengeable explanation workflow with a reproducible evaluation. Do not claim to be the first system to verify sports narratives.

## Competing product directions

Effort estimates are developer hours, including integration, before contingency; these are planning judgments.

| Direction | User value / memorable demo | Agent purpose | Cost and risk | Decision |
| --- | --- | --- | --- | --- |
| **A. Evidence-first match desk** | Challenge an explanation and inspect event proof, including a positive recovery-to-shot discovery | Analyst proposes; Verifier independently tests adequacy and alternatives | Revised: 44–58h core +8–10h delivery +6h reserve; semantic review and honest UI states remain the main risk | **Choose**: visible football depth without video processing |
| **B. Personalized broadcast director** | Two synchronized on-screen programs for a fan and an analyst | Producer ranks moments; specialist writers select narrative and graphics | About 48–60 h; timing, layouts and content policy expand rapidly; weak separation from existing storytelling tools | Competitive alternative; keep only two-mode rendering |
| **C. Coaching counterfactual simulator** | Explore how pressing or substitutions might change a match | Planner and simulator compare interventions | Over 70 h; causal realism and validation unavailable with event-only synthetic inputs | Reject for this event; attractive visual claims would outrun evidence |

Direction B becomes the fallback product framing if independent verification adds no measured benefit. It does not justify implementing a second application.

## One core innovation, two supporting innovations

| Innovation | Value | Incremental effort within P0 | Main risk | Judge visibility |
| --- | --- | --- | --- | --- |
| **Core: challengeable insight cards** with counterevidence and publish/qualify/withhold decisions | Exposes why an explanation deserves attention and when it should change | 10–12 h | An LLM reviewer can share the proposer's errors; deterministic gates and human evaluation remain necessary | High: one disagreement and evidence click explain the product |
| **Support 1: reproducible synthetic challenge replay** with neutral, misleading and incomplete windows | Repeats the same football problem and supports fair comparisons | 5–6 h | Fixtures become answer scripts if labels leak | High: rerun an unseen seed and inspect the hash |
| **Support 2: two views of one approved fact set** | A casual fan understands the consequence; an analyst sees denominators and windows | 4–5 h | Tone changes without a useful information difference | High: mode switch keeps evidence IDs while changing information density |

These costs are included in the revised P0 estimate in ROADMAP. R0.1 uses one continuous 12-minute/140–180-event demonstration match and three fixed Focus cutoffs. B must discover a meaningful pattern; the product cannot rely only on rejecting an attractive story. Framework orchestration and local receipts enable the product rather than constitute another innovation claim.

## Technical choices

| Choice | Alternatives considered | Decision and reason |
| --- | --- | --- |
| UI | Next.js / Vite React | Next.js + TypeScript **static export**, shared CSS tokens; no extra styling dependency for this single screen. Static export actually builds |
| Backend | Python FastAPI / all-TypeScript | FastAPI: keep simulation, metrics and Python Agent Framework together; accept a small typed HTTP boundary |
| Real time | SSE / WebSocket / polling | SSE plus POST controls. One-way updates need no socket protocol; 1 s polling is the hosting fallback |
| Intelligence | One agent / two / three | Two: Analyst and Verifier. Narration is a validated structured output plus ordinary rendering; no third Narrator agent |
| Orchestration | Agent Framework / Copilot SDK BYOK | Agent Framework Python workflow, selected from the live Spike; keep Copilot in the experiment only. No two-runtime production stack |
| Model integration | DeepSeek Flash / Pro / Foundry | `OpenAIChatCompletionClient` + explicit `AsyncOpenAI` against DeepSeek Chat Completions; Flash for both roles. Pro is an opt-in P1 reviewer, not an automatic retry |
| Structured output | Strict JSON Schema / JSON Object | `response_format={type:json_object}` plus independent local validation. Real strict-schema requests returned HTTP 400 on both SDK paths |
| Thinking | Default enabled / explicit disabled | Explicitly disable thinking on the Flash live path. Keep reasoning-text roundtrip support outside P0; do not silently inherit provider defaults |
| Evidence tools | Local function tools / MCP / RAG | In-process bounded read-only functions. MCP adds a transport with no second consumer; defer it |
| State | Immutable fixtures + memory / database | Frozen generated events and per-session memory; only the **global budget ledger** uses SQLite so restart cannot silently renew inference allowance |
| Hosting | Existing authorized container host / Azure Container Apps / split hosting | One portable FastAPI container serving static UI. Choose an accessible, funded host; Azure is optional and cannot block product work |

[Microsoft's OpenAI provider guide](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/model-providers/openai) distinguishes Chat Completions from Responses. Use `OpenAIChatCompletionClient`; do not accidentally route this configuration through `OpenAIChatClient` or assume every OpenAI feature exists. The Spike pins core 1.22.0, OpenAI connector 1.17.0 and OpenAI SDK 3.35.1 in its lockfile. Transfer only the selected dependencies into the product after its first slice; Copilot remains an isolated comparison dependency.

The MVP's Microsoft proof is the actual Agent Framework graph, two independently prompted agents, tool receipt roundtrips and a typed handoff/publication boundary. Preserve model usage, decisions and elapsed times in local structured run receipts. [Agent Framework observability](https://learn.microsoft.com/en-us/agent-framework/agents/observability) supports OpenTelemetry; console or OTLP export is optional P1. No Azure telemetry service is required. A passing SDK Spike does not establish football quality or multi-agent uplift; the existing evaluation still applies.

The full route comparison, native-format limits and measured samples are in [TECH_SPIKE](TECH_SPIKE.md). Both routes can use the same licensed DeepSeek endpoint without Foundry. Agent Framework fits the existing Python architecture and exposes request options directly; Copilot adds a separate CLI runtime and session lifecycle that this product does not otherwise need. Do not refactor the simulator, metric formulas, evidence IDs, SSE or dashboard to accommodate an SDK.

## Scope and economics

P0 is one seeded match, three story chapters, deterministic metrics and candidate triggers, two live agents, evidence cards, Fan/Analyst views, automatic recap, a free test path and English delivery materials. P1 is the controlled agent comparison, broader fixtures, stronger chart polish and a measured recovery demonstration. P2 is one additional language or favorite-team framing after release gates pass. See [ROADMAP](ROADMAP.md) for the freeze rules.

High-cost, low-return exclusions: video ingestion/computer vision, licensed match feeds, 22-player tracking, calibrated xG/win probability, inferred formations, coach recommendations, open-ended chat, voice avatars, RAG, MCP/A2A without a consumer, Kafka, Kubernetes, multi-tenant accounts, mobile apps and enterprise-scale infrastructure. Do not call an arbitrary composite “momentum probability.” Show interpretable change metrics instead.

User instruction on 2026-10-19 removes Foundry dependence and authorizes a bounded real DeepSeek Spike with a supplied credential. Actual requests and their failures are recorded in [TECH_SPIKE](TECH_SPIKE.md); no Azure resources were created. The credential is not a repository artifact. The larger development/judging budget and public host still need confirmation; completing the Spike does not authorize unlimited experimentation.

DeepSeek's [current pricing](https://api-docs.deepseek.com/quick_start/pricing/) lists peak USD prices per million tokens: Flash input cache miss $0.30, hit $0.006, output $1.20; Pro input miss $1.32, hit $0.044, output $3.96. Off-peak is half. Flash currently resolves to V4.1-Flash-1017 and Pro to V4-Pro-0813 according to that page; log requested/returned model and the dated documentation separately because aliases can change. Public limits are not our account's measured throughput.

Estimate inference cost from provider-reported cache-hit/miss input and output, including tool continuations and known failed usage. R0.1 reserves $0.02 before each bounded Flash request (48k-byte input body, 1,024 output tokens, no hidden thinking); default global caps are 32 requests and $1 reserved. Six requests/run, eight manual workflows/session, process concurrency two. Reservation is conservative and is not actual billing. Completed session-local snapshot results retain original run provenance. Add hosting through Nov10 and retain judging funds separately. Public hosting/funding remain open gates.

Use per-request reservations, explicit output limits, bounded concurrency and fixed public fixtures. SDK retries must be disabled or counted at the actual HTTP boundary. A local inference ledger does not cap host charges. If funded runway cannot cover free testing, change the hosting plan before submission; a dead endpoint or requiring judges to buy API credit does not meet the planned delivery.

## Decisions that must survive implementation

1. Every important factual value is computed, versioned and cited; agents interpret it.
2. Neither future events nor hidden scenario labels enter a live agent's context.
3. A reviewer verdict is not a calibrated truth probability. Visible support labels are `supported`, `qualified`, or `insufficient`.
4. Fallback statistics, archived model output and fresh inference have different visible provenance.
5. Measure two-agent value against a budget-matched self-review baseline. If the result is inconclusive, publish that result.
6. Preserve at least Oct 26 as a full deployment, QA and recording day; no P1 feature may consume that reserve.

## R0.2 execution adjustment — Oct20 PT

The product now leads with Play Replay, free event-driven detection and an opt-in, bounded live investigation rather than requiring chapter selection first. Fan view prioritizes the finding; Analyst view adds snapshot-window comparisons and review limits. The fixed chapters remain optional investigation shortcuts. Public prose uses finite evidence-bound rendering after the real Analyst selection and independent Verifier decision. This is an explicit tradeoff: fewer expressive narratives, stronger binding between metric, value and period. It does not replace real agents, decide a verdict in advance or establish a quality uplift. See [R0.2_RESULTS](R0.2_RESULTS.md) for actual calls/failures and remaining release gates.
