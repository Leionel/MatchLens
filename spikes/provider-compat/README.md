# MatchLens provider compatibility Spike

This isolated probe uses real DeepSeek responses. It does not implement the match engine, dashboard or football-quality benchmark. Findings and limitations: [TECH_SPIKE](../../docs/TECH_SPIKE.md).

Selected production direction: Microsoft Agent Framework + Flash, native JSON Object and independent local validation. Pro is optional. Copilot SDK is an evaluated alternative only.

## Recorded run

`results/analysis.json` aggregates 30 upstream attempts and preserves the setup and callback errors separately from actual compatibility failures. Do not rerun paid cases just to inspect it:

```powershell
uv sync --project spikes/provider-compat --frozen
uv run --project spikes/provider-compat python spikes/provider-compat/analyze.py
```

`spike.py` checks the existing result ledger and refuses more than 30 upstream attempts in that scope. Current scope is exhausted. Further live tests require a new approved request budget and a separate clean output scope/checkout; preserve the existing receipts. Defaults must not be used as permission to consume more API credit.

For a newly authorized clean checkout/output scope, configure `DEEPSEEK_API_KEY` in the environment or pass an ignored local env file. Do not put a real key in source or command examples. A single selected-route handoff is:

```powershell
uv run --project spikes/provider-compat python spikes/provider-compat/spike.py --cases maf-flash --request-cap 4 --run-id fresh-maf
```

The original study also ran `direct-json`, `direct-strict`, `maf-typed`, `copilot-flash`, `copilot-typed`, `maf-pro`, and two Flash repeats. Strict typed-format cases are expected to fail on the observed API profile. They are not application acceptance tests.

The runner includes an accounting-only loopback boundary. Both SDKs send actual requests through it; it uses the official upstream endpoint and never fabricates a model answer. The real credential stays out of SDK session logs and the repository. It buffers responses, so compare complete-case times only, not TTFT. Custom tools are allowlisted; Copilot builtin tools, skills, configuration discovery and GitHub-user authentication are disabled.

The Python Copilot SDK downloads/caches its pinned native runtime (1.0.100 in the recorded run). This executable is an extra deployment dependency. It is not included in the selected product container.
