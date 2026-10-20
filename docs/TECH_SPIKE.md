# Provider Spike and Technology Decision

Decision date: **2026-10-19, America/Los_Angeles**. Raw receipts use UTC, approximately 2026-10-20 02:47–02:53 UTC, which is Oct 19 locally. Scope: provider/SDK compatibility only. The core product, football metrics and user journeys in [SPEC](SPEC.md) are unchanged.

## Decision

**Use Microsoft Agent Framework Python + the official DeepSeek Chat Completions API.** `deepseek-flash` serves Analyst and Verifier in P0. Keep `deepseek-v4-pro` as an opt-in P1 reviewer/evaluation option. Use native JSON Object mode, then local schema/reference checks. Explicitly disable thinking on the live path. Foundry is removed as a hard dependency and award target. Copilot SDK remains a tested alternative, not a second production runtime.

This follows an actual two-agent tool/handoff test, rather than treating the phrase “OpenAI-compatible” as proof. It preserves Python/FastAPI, the simulator, deterministic metrics, evidence contracts, SSE, Next.js and the dashboard plan. The only planned product-specific integration is a small provider-construction/options module.

## What was tested

The [Spike code](../spikes/provider-compat/spike.py) is isolated from future product code. Its input is a hand-counted synthetic window: controlled possession 45→65%, shots 2→1, pass entries 3→2. It is explicitly a small compatibility fixture, not a running match engine. Snapshot SHA-256: `cb454a9cf303f77a40f43ee4fba4f7ce80758b211754a338c4b182f9766d8133`.

Both roles must call the same bounded `get_evidence(snapshot_id)` tool. Analyst emits a JSON claim; an independent local validator checks the draft; Verifier receives that exact snapshot/claim ID and retrieves the receipts again. Validate its JSON decision too. The selected framework executes this through a real `WorkflowBuilder` graph with two agent-backed executors. Copilot uses two fresh SDK sessions with an explicit application-controlled handoff. This establishes structured coordination; neither path demonstrates autonomous delegation or multi-agent quality uplift.

Versions actually installed and executed:

| Component | Version |
| --- | --- |
| Python / Windows | 3.13.9 / Windows x64 |
| `agent-framework-core` | 1.22.0 |
| `agent-framework-openai` | 1.17.0 |
| `openai` | 3.35.1 |
| `github-copilot-sdk` | 1.0.23 |
| SDK-managed Copilot runtime | 1.0.100, downloaded/cached during setup |
| `jsonschema` | 4.26.0 |

Dependency versions and transitive resolution are preserved in [pyproject.toml](../spikes/provider-compat/pyproject.toml) and [uv.lock](../spikes/provider-compat/uv.lock).

## Actual results

Durations are complete local probe-case durations including SDK work, tool calls and local checks. They are not TTFT, public-host latency, p95, or a controlled SDK speed benchmark.

| Case | Observed outcome | Requests / elapsed | Evidence |
| --- | --- | --- | --- |
| Direct Flash JSON Object | Valid JSON parsed and locally validated | 1 / 2.678 s | [Foundation](../spikes/provider-compat/results/01-foundation/summary.json) |
| Direct Flash strict `json_schema` | HTTP 400: response-format type unavailable | 1 / 1.111 s | [Foundation requests](../spikes/provider-compat/results/01-foundation/requests.json) |
| MAF + Flash, native JSON Object, tools and graph handoff | Both roles retrieved actual tool receipts; draft/decision validated | 4 / 6.244 s | [Foundation](../spikes/provider-compat/results/01-foundation/summary.json) |
| MAF typed response format | Connector emitted strict `json_schema`; HTTP 400 | 1 / 1.064 s | Foundation requests |
| MAF + Pro, JSON Object, tools and graph handoff | Both roles retrieved receipts; Verifier qualified an overbroad interpretation | 4 / 10.738 s | [Comparison](../spikes/provider-compat/results/02-route-comparison/summary.json) |
| Copilot typed-output helper + Flash | Runtime emitted strict `json_schema`; HTTP 400 | 1 / 0.887 s | [Comparison requests](../spikes/provider-compat/results/02-route-comparison/requests.json) |
| Copilot + Flash after fixing the harness tool-result type | Two fresh sessions, both successful tool roundtrips, valid handoff/decision | 4 / 11.182 s | [Confirmation](../spikes/provider-compat/results/03-confirmation/summary.json) |
| MAF + Flash repeat A | Two verified tool roundtrips and valid handoff | 4 / 7.362 s | Confirmation |
| MAF + Flash repeat B | Two verified tool roundtrips and valid handoff | 4 / 5.992 s | Confirmation |

Flash/MAF has three successful full-chain samples: **5.992–7.362 s**, each four requests. Copilot has one corrected successful sample and Pro has one. Different native format/thinking behavior, a shared provider cache, sequential execution and unequal sample counts prevent attributing the observed timing difference solely to SDK overhead. These measurements support a practical integration choice; they do not establish a general performance ranking.

### Harness errors retained separately

The first setup attempt accidentally sent loopback traffic through an inherited proxy and had an unresolved workflow annotation. It made **zero upstream DeepSeek requests**. After bypassing proxies only for loopback and correcting the Python annotation scope, the foundation run succeeded. See the [initial setup record](../spikes/provider-compat/results/summary.json).

The first Copilot tool callback returned a wire-style dictionary instead of this SDK version's `ToolResult` dataclass. The model received tool failures and withheld the claim. Six upstream requests were consumed. Its original summary marked JSON parsing as passed; that is **not a successful tool test**. The offline [analysis](../spikes/provider-compat/results/analysis.json) correctly classifies it as `harness_failure_tool_result_not_delivered`. The original requests are retained, and the corrected run verifies exact snapshot JSON in both agents' subsequent tool messages. Do not attribute this callback mistake to DeepSeek or use its 21.743 s duration as SDK performance evidence.

### Structured output boundary

`response_format={type:json_object}` succeeded with MAF and direct DeepSeek. A typed Pydantic response request emitted strict JSON Schema and failed. Copilot's typed helper failed for the same wire-level reason; its successful ordinary `send_and_wait` path used prompted JSON plus local validation, with no provider `response_format` in the captured request.

Thus schema-constrained generation is **not** verified. P0 requires valid JSON, local schema validation, snapshot/reference validation and semantic review as separate steps. Malformed or unsupported output is withheld. Do not remove any gate because a JSON parse succeeded. Beta strict **tool arguments** and the Responses API were not tested; they are distinct from strict output schema.

## Route comparison

| Dimension | Agent Framework + DeepSeek | Copilot SDK + DeepSeek BYOK | Decision implication |
| --- | --- | --- | --- |
| Orchestration | Explicit typed graph; model-backed roles plus ordinary validators; graph actually executed | Actual two-session handoff works; SDK also offers a broad agent runtime, but native delegation was not tested | The known graph already matches this product |
| Tool Calling | Both real roles called the local read-only function; exact receipts returned to model | Same after using native `ToolResult`; custom tool allowlist and disabled builtin tools tested | Both feasible; no MCP required |
| Structured output | Native JSON Object plus local validation verified; strict typed output failed | Prompted JSON plus local validation verified once; native typed helper failed | MAF exposes the narrower compatible format directly |
| Real-time controls | Explicit `thinking=disabled`, provider `max_tokens`, transport retry count and loop limits | Native session lifetime/abort work; requested `reasoning_effort=none` was absent from captured provider bodies | Prefer explicit request-level control; do not assume runtime effort reached DeepSeek |
| Observability | HTTP receipts and actual graph/tool events observed; OpenTelemetry supported by official docs | Runtime session/tool events supported; gateway receipts observed; runtime adds another process boundary | Local run receipts are mandatory; exporters/monitoring UI unverified P1 |
| Cost | Direct DeepSeek usage, small product-specific prompts and fixed turn caps | Also direct DeepSeek BYOK; no GitHub login used. Runtime may add prompts/loops; token use must be measured | Count actual HTTP requests, not calls to an SDK convenience method |
| Deployment | Python libraries in the existing FastAPI process | Python SDK works, but also needs a pinned platform runtime, startup/cleanup and session configuration | Avoid the extra executable in P0 |
| Competition | Rules explicitly name MAF; distinct roles, state, recovery and comparison remain necessary | Rules also name GitHub Copilot; merely using another Microsoft SDK does not earn a documented bonus | No scoring reason to ship both; Foundry prize removed |

[Copilot SDK documentation](https://github.com/github/copilot-sdk) describes its JSON-RPC runtime and BYOK without GitHub authentication. Its [BYOK guide](https://github.com/github/copilot-sdk/blob/main/docs/auth/byok.md) documents OpenAI-compatible endpoints and provider billing; this was actually exercised with `use_logged_in_user=False`, the local-only provider credential and the real upstream key held by the accounting boundary. DeepSeek's [Copilot integration page](https://api-docs.deepseek.com/quick_start/agent_integrations/github_copilot/) is a VS Code extension tutorial, not proof of SDK compatibility.

The [MAF provider guide](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/model-providers/openai) distinguishes Chat Completions and Responses. [DeepSeek's Chat Completions reference](https://api-docs.deepseek.com/api/create-chat-completion/) documents JSON Object, output caps, thinking control and tool calling. [Thinking-mode documentation](https://api-docs.deepseek.com/guides/thinking_mode/) requires reasoning-content continuation during thinking/tool turns. The selected MAF profile explicitly disables thinking; the Copilot request capture did not contain an equivalent switch. No private reasoning text is published in these artifacts.

The [competition rules §4.2](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md) support either purposeful collaboration route. Category fit still depends on the final project; SDK compatibility does not establish eligibility by itself, product completeness or measured superiority.

## Usage and cost evidence

The Spike reached its **30-upstream-request cap and stopped**. The offline audit found:

- 27 HTTP 200 responses with provider usage; three HTTP 400 format rejections without usage.
- Reported input **18,521 tokens**, including **11,008 cache-hit / 7,513 cache-miss** tokens; output **3,310 tokens**.
- Known reported usage priced at the Oct 19 published USD peak rates: **$0.00901916**. This is a calculated estimate, not an invoice or confirmed balance deduction. Attempts without usage are excluded, not asserted free.

The [analysis JSON](../spikes/provider-compat/results/analysis.json) and [offline analyzer](../spikes/provider-compat/analyze.py) reproduce those totals from recorded responses. Pricing source: [DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/). Input hit/miss and output rates differ by model and time; retain the dated price profile. Neither published concurrency limits nor these single-session samples establish the account's safe sustained rate.

The Spike-only loopback gateway fixed the upstream destination, allowed only the two named models, reserved requests before sending, imposed request/output-size bounds and captured sanitized wire evidence. It did not modify request bodies or synthesize provider replies. MAF/OpenAI transport and gateway had no automatic retries; Copilot internal retry suppression was not proven, so all its upstream attempts were counted. The bridge buffered responses for accounting: no TTFT claim is available. It is not a proposed production service.

## Remaining implementation gates

1. Transfer the tested options and dependencies into a real product slice; replace the tiny Spike schema with SPEC's complete claim, audience-block and publication contracts.
2. Verify actual event generation, deterministic metrics, epoch isolation, fallback deadlines, SSE/browser behavior and public hosting. None was established by this Spike.
3. Run held-out football-quality and budget-matched single/self-review/multi-agent evaluation on the same Flash option/version profile. Pro quality gains are unmeasured.
4. Confirm a funded provider account and test host through Nov 10. The research key and this completed 30-request budget do not constitute an unrestricted production budget.
5. Remove credentials from temporary test storage; retain only sanitized artifacts. No further live requests are needed for this selection.
