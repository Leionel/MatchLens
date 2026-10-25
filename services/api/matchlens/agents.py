"""Real Microsoft Agent Framework graph; no synthetic model responses."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx
from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatCompletionClient
from openai import AsyncOpenAI
from pydantic import Field
from typing import Literal

from .budget import BudgetExceeded, BudgetLedger, MAX_BODY_BYTES, MAX_OUTPUT_TOKENS
from .contracts import Assertion, ClosedModel, ClaimDraft, VerifierDecision, QUANTITATIVE_WORDS, SLOT, bind_slots, publication_gate, validate_draft
from .football import Snapshot, build_sequences, tool_evidence

PROMPT_VERSION = "football-roles-r02-2-bound-facts"


class WireDraft(ClosedModel):
    """One useful claim per slice; flat wire shape avoids fragile nested JSON."""
    snapshot_id: str
    claim_id: str = Field(pattern=r"^claim-[a-z-]{1,32}$")
    assertion: Assertion
    scope: Literal["window", "match", "causal"]
    refs: list[str] = Field(min_length=1, max_length=12)
    fan: str = Field(min_length=15, max_length=350)
    analyst: str = Field(min_length=25, max_length=650)
    conservative_fan: str | None = None
    conservative_analyst: str | None = None

    def canonical(self) -> ClaimDraft:
        primary = {"id": "primary", "scope": self.scope, "refs": self.refs, "fan": self.fan, "analyst": self.analyst}
        conservative = None
        if self.conservative_fan is not None or self.conservative_analyst is not None:
            conservative = {**primary, "id": "conservative", "scope": "window", "fan": self.conservative_fan, "analyst": self.conservative_analyst}
        return ClaimDraft.model_validate({"snapshot_id": self.snapshot_id, "claims": [{"id": self.claim_id,
            "assertion": self.assertion, "primary": primary, "conservative": conservative}]})


class WireReview(ClosedModel):
    snapshot_id: str
    claim_id: str
    verdict: Literal["publish", "qualify", "withhold"]
    selected_variant: Literal["primary", "conservative"] | None
    reason: str = Field(min_length=8, max_length=400)
    limitations: list[str] = Field(max_length=3)

    def canonical(self) -> VerifierDecision:
        return VerifierDecision.model_validate({"snapshot_id": self.snapshot_id, "decisions": [self.model_dump(exclude={"snapshot_id"})]})


@dataclass
class Run:
    id: str
    snapshot: Snapshot
    match_id: str = ""
    dataset_revision: str | None = None
    epoch: int = 0
    audit: list[dict] = field(default_factory=list)
    role: str = ""
    requests: int = 0
    draft: dict | None = None
    review: dict | None = None
    raw_outputs: list[dict] = field(default_factory=list)
    focus_team: str = "H"
    #: Set by the investigation route; the model call races it so a server-side
    #: cancel aborts the in-flight provider request instead of waiting for it.
    cancel_event: Any | None = None


def instructions(role: str, focus_team: str = "H", tool_menu: str | None = None) -> str:
    t = "N" if focus_team == "N" else "H"
    if tool_menu is None:
        tools_sentence = (
            "You may also use decompose_window, query_causal_chain, assess_alternative_hypotheses, "
            "explain_oaai_contributors and query_metric to inspect event contributions, sequence chains, "
            "metric observations and rival explanations."
        )
    else:
        tools_sentence = (
            "You may also call the registered investigation tools listed at the end of this prompt "
            "to inspect event contributions, sequence chains, metric observations and rival explanations."
        )
    common = f"""You are MatchLens AI, an evidence-grounded football intelligence system adhering to the Four-Level Tactical Inference Framework:
- Level 1 (Observable Facts): Direct counts and raw coordinates of completed passes, recoveries, shots, and goals.
- Level 2 (Metric Attribution): Mathematical formula decompositions (e.g. OAAI, xT delta, Attacking Activity Index). Not tactical causality.
- Level 3 (Statistical Association): Multi-event empirical correlation with rival hypothesis testing.
- Level 4 (Causal Inference): Strictly guarded. Never claim causal tactical impact without 25Hz tracking, off-ball defensive shape, and counterfactual validation.

You MUST call get_evidence with the supplied snapshot_id at least once in your role's session before your first answer, even when another agent supplied evidence. {tools_sentence} Only tool evidence is authoritative. Return one JSON object, no markdown.

Football principles:
- Possession measures controlled ball time; entries measure passes crossing attacking third (x=70m); shots measure attempts.
- More possession alone does NOT equal increased attacking threat.
- A shot following a recovery is an observed temporal association (Level 1/2); it CANNOT prove high-press intent or tactical causation.
- A short window cannot establish a whole-match tactical trend.
- Goal chains show recorded on-ball actions only.
- In continuous demo fixtures with no halftime, say 'current/previous window'. In multi-period matches, respect period boundaries. Each standard comparison window is 180 seconds; start/end/as_of are match seconds.
- Prose rules: describe only the selected assertion. No invented names, timings, coordinates, percentages or statistics. All quantities in prose MUST be slots like {{{{{t}.shots.current}}}} with a matching ref; NEVER write literal digits or spelled-out number words like 'zero', 'twice', 'two shots'. If you discuss or compare the previous window, you MUST include the corresponding .previous receipts in refs. No ungrounded claims of 'fatigue', 'tactical brilliance', 'caused', 'because', or 'forced' in public text.
"""
    if role == "Analyst":
        task = f"""Investigate the candidate question using the receipts and selected events. Choose ONE useful supported core assertion, or propose a tentative assertion for review if evidence is insufficient. Do not select a verdict.
Allowed assertions and mandatory refs:
possession_without_penetration: all six {t}.possession/{t}.shots/{t}.entries previous/current receipts; increased possession with no increase in shots and entries.
attacking_threat_increased: {t}.shots and {t}.entries previous/current; both must increase.
recoveries_followed_by_shots: {t}.high_recoveries.current and {t}.transition_shots.current; at least two linked transition shots. Mention the short sample, not a general tactical cause. If you mention previous window values, you must include the matching .previous receipts.
recoveries_caused_shots: cannot be proven by these events; do not disguise it as association.
goal_sequence: {t}.goals.match and its event chain; scope MUST be 'match'. Describe the uninterrupted on-ball passing and recovery chain culminating in the goal without claiming tactical causality.
Normally use scope 'window'; only goal_sequence uses 'match'. primary.id='primary'. conservative is null unless a narrower version of the SAME true assertion is useful; conservative.id='conservative'. A conservative variant cannot reverse an incorrect assertion. Keep refs explicit and prose concise. claim id uses 'claim-' plus lowercase words. JSON structure: {{snapshot_id,claims:[{{id,assertion,primary:{{id,scope,refs,fan,analyst}},conservative:null or variant}}]}}.
"""
    else:
        task = """Independently inspect the handed-off claims and ALL relevant evidence, including contrary measures. Check the precise Fan and Analyst prose as well as the assertion, scope and refs. Do not invent or revise prose.
publish: the primary is supported; selected_variant='primary'.
qualify: the core assertion is TRUE and a provided conservative variant of that SAME assertion is supported; selected_variant='conservative'. Narrowing an excessive scope is allowed. Adding a disclaimer cannot repair a false assertion.
withhold: core assertion false, evidence contradicted/insufficient/unverifiable, no supported variant, or prose overstates the evidence; selected_variant=null. No supplied conservative variant means qualify is impossible: choose publish or withhold.
Do not force any particular verdict. Give a BRIEF reason, at most 45 words and 400 characters; at most three concise limitations. JSON structure: {snapshot_id,decisions:[{claim_id,verdict,selected_variant,reason,limitations:[]}]}.
"""
    # Replace the canonical nested shape in task instructions with the smaller
    # provider wire contract. Mapping preserves values, never repairs meaning.
    task = task[:task.index("JSON structure:")] if "JSON structure:" in task else task
    task = task.replace("primary.id='primary'. conservative is null unless a narrower version of the SAME true assertion is useful; conservative.id='conservative'.", "conservative_fan and conservative_analyst are both null unless a narrower version of the SAME true assertion is useful.")
    schema = WireDraft.model_json_schema() if role == "Analyst" else WireReview.model_json_schema()
    return common+task+"\nUse the FLAT JSON schema below. No claims/decisions array or primary object. No extra fields. "+json.dumps(schema, separators=(",", ":"))+(("\n\n"+tool_menu) if tool_menu else "")


def investigation_tool_menu() -> str:
    """Dynamic-tool menu shown to investigation agents (roadmap C-06)."""
    from .tools import TOOL_BUDGET, TOOL_DESCRIPTIONS

    lines = [f"- {name}: {TOOL_DESCRIPTIONS.get(name, name)} (at most {TOOL_BUDGET[name]} call(s))" for name in TOOL_BUDGET]
    return (
        "Registered investigation tools for this session. Call them by exact name to gather "
        "evidence for the question; tool names not in this list do not exist. The registry "
        "enforces the per-tool call budget and rejects calls outside the frozen snapshot.\n"
        + "\n".join(lines)
    )


def investigation_instructions(role: str, focus_team: str = "H") -> str:
    return instructions(role, focus_team=focus_team, tool_menu=investigation_tool_menu())


class AgentRunner:
    def __init__(self, key: str | None, ledger: BudgetLedger, deadline: float = 25):
        self.key, self.ledger, self.deadline = key, ledger, deadline

    def _transport_hooks(self, run: Run, role: str):
        """Durable reservation + audit hooks shared by every model dispatch."""

        async def before(request: httpx.Request) -> None:
            raw = request.content
            body = json.loads(raw)
            if request.url.host != "api.deepseek.com" or request.url.scheme != "https" or request.url.path != "/chat/completions":
                raise ValueError("provider_endpoint_not_allowed")
            if len(raw) > MAX_BODY_BYTES or body.get("model") != "deepseek-flash" or body.get("max_tokens") != MAX_OUTPUT_TOKENS or body.get("thinking") != {"type": "disabled"}:
                raise ValueError("provider_request_bound")
            if run.requests >= 6:
                raise BudgetExceeded("run_request_budget_exhausted")
            if sum(e.get("type") == "http_dispatch" and e.get("role") == role for e in run.audit) >= 3:
                raise BudgetExceeded("role_request_budget_exhausted")
            request_id = self.ledger.reserve(run.id, role)
            run.requests += 1
            request.extensions["matchlens_request_id"] = request_id
            run.audit.append({"type": "http_dispatch", "role": role, "request_id": request_id,
                              "body_bytes": len(raw), "model": body["model"], "max_tokens": body["max_tokens"]})
            for message in body.get("messages", []):
                content = message.get("content", "")
                if message.get("role") == "tool" and isinstance(content, str) and run.snapshot.id in content:
                    run.audit.append({"type": "tool_receipt", "role": role, "snapshot_id": run.snapshot.id,
                                      "tool_call_id": message.get("tool_call_id"), "sha256": hashlib.sha256(content.encode()).hexdigest()})

        async def after(response: httpx.Response) -> None:
            await response.aread()
            try:
                data = response.json()
            except ValueError:
                data = {}
            request_id = response.request.extensions["matchlens_request_id"]
            self.ledger.complete(request_id, response.status_code, data.get("usage"))
            run.audit.append({"type": "http_receipt", "role": role, "request_id": request_id,
                              "status": response.status_code, "usage": data.get("usage"), "returned_model": data.get("model")})

        return before, after

    @staticmethod
    async def _await_with_cancel(run: Run, awaitable: Any) -> Any:
        """Await a provider call unless the request was cancelled on the server."""
        cancel_event = getattr(run, "cancel_event", None)
        if cancel_event is None:
            return await awaitable
        from .investigation import InvestigationCancelled

        if cancel_event.is_set():
            close = getattr(awaitable, "close", None)
            if close is not None:
                close()
            raise InvestigationCancelled(run.id)
        task = asyncio.ensure_future(awaitable)
        waiter = asyncio.ensure_future(cancel_event.wait())
        try:
            await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
            if waiter.done() and not task.done():
                raise InvestigationCancelled(run.id)
            return task.result()
        finally:
            if not waiter.done():
                waiter.cancel()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, waiter, return_exceptions=True)

    async def _run_model(self, run: Run, role: str, tools: list, prompt: str, instructions_text: str,
                         *, max_iterations: int, max_function_calls: int) -> str:
        before, after = self._transport_hooks(run, role)
        # Real credential exists only in the server-side SDK, never tools or receipts.
        async with httpx.AsyncClient(timeout=httpx.Timeout(23), event_hooks={"request": [before], "response": [after]}) as transport:
            async with AsyncOpenAI(api_key=self.key, base_url="https://api.deepseek.com", max_retries=0,
                                   timeout=23, http_client=transport) as sdk:
                client = OpenAIChatCompletionClient(model="deepseek-flash", async_client=sdk,
                    function_invocation_configuration={"max_iterations": max_iterations, "max_function_calls": max_function_calls})
                agent = Agent(client=client, name=role, instructions=instructions_text,
                    tools=tools, default_options={"response_format": {"type": "json_object"},
                    "extra_body": {"thinking": {"type": "disabled"}, "max_tokens": MAX_OUTPUT_TOKENS}})
                session = agent.create_session()
                response = await self._await_with_cancel(run, agent.run(prompt, session=session))
                raw = response.text
                run.raw_outputs.append({"role": role, "attempt": "initial", "text": raw})
                try:
                    self.validate_stage(raw, role, run)
                except ValueError as exc:
                    # One bounded format correction, same role/session/evidence.
                    # No code changes the assertion or fabricates missing prose.
                    feedback = str(exc)[:900]
                    run.audit.append({"type": "schema_correction", "role": role, "validation": feedback})
                    t_slot = "N" if run.focus_team == "N" else "H"
                    response = await self._await_with_cancel(run, agent.run(
                        "Your JSON failed local validation: "+feedback+
                        ". Return a corrected complete JSON object using the evidence already retrieved. "
                        "Do not call tools again. Follow the flat output schema, without extra fields or nested claim objects. "
                        f"Slots are exactly {{{{{t_slot}.possession.current}}}}, not .value; percentage slots already include %. "
                        "No literal digits in public prose, including reasons/limitations. Change only invalid fields; preserve other text. "
                        "Never change claim_id, assertion or scope. Keep review reason below 400 characters.", session=session))
                    raw = response.text
                    run.raw_outputs.append({"role": role, "attempt": "format_correction", "text": raw})
                    try:
                        original = json.loads(run.raw_outputs[-2]["text"])
                        corrected = json.loads(raw)
                    except ValueError:
                        raise ValueError("format_correction_core_not_comparable")
                    if any(original.get(k) != corrected.get(k) for k in ("claim_id", "assertion", "scope")):
                        raise ValueError("format_correction_changed_core")
                    self.validate_stage(raw, role, run)
                return raw

    async def stage(self, run: Run, role: str, prompt: str) -> str:
        run.role = role

        def get_evidence(snapshot_id: str) -> str:
            """Read immutable metric receipts, sample limitations and recorded football event chains."""
            if snapshot_id != run.snapshot.id:
                raise ValueError("snapshot_outside_tool_scope")
            run.audit.append({"type": "tool", "role": role, "name": "get_evidence", "snapshot_id": snapshot_id})
            return json.dumps(tool_evidence(run.snapshot, focus_team=run.focus_team), separators=(",", ":"))

        def get_event_chain(event_ids: list[str]) -> str:
            """Inspect at most twenty specific original events inside this snapshot prefix."""
            if len(event_ids) > 20 or len(set(event_ids)) != len(event_ids):
                raise ValueError("event_tool_bound")
            known = {e["id"]: e for e in run.snapshot.data["events"]}
            if any(i not in known for i in event_ids):
                raise ValueError("event_outside_snapshot")
            run.audit.append({"type": "tool", "role": role, "name": "get_event_chain", "snapshot_id": run.snapshot.id, "event_ids": event_ids})
            return json.dumps({"snapshot_id": run.snapshot.id, "events": [known[i] for i in event_ids]}, separators=(",", ":"))

        def get_sequence(sequence_id: str) -> str:
            """Inspect a specific possession sequence with player involvements and step-by-step progression."""
            seqs = build_sequences(run.snapshot.data)
            match = next((s for s in seqs if s["sequence_id"] == sequence_id), None)
            if not match:
                raise ValueError("sequence_not_found")
            run.audit.append({"type": "tool", "role": role, "name": "get_sequence", "snapshot_id": run.snapshot.id, "sequence_id": sequence_id})
            return json.dumps({"snapshot_id": run.snapshot.id, "sequence": match}, separators=(",", ":"))

        def decompose_window(window_seconds: float = 120.0) -> str:
            """Decompose top contributing on-ball actions (shots, recoveries, progressive moves) in recent window."""
            from .attribution import EventAttributionSpecialist
            at = float(run.snapshot.data.get("as_of", 180))
            w_start = max(0.0, at - float(window_seconds))
            res = EventAttributionSpecialist.temporal_window_decomposition(
                run.snapshot.data.get("events", []),
                window_start_s=w_start,
                window_end_s=at,
                team=run.focus_team,
            )
            run.audit.append({"type": "tool", "role": role, "name": "decompose_window", "snapshot_id": run.snapshot.id})
            return res.model_dump_json()

        def query_causal_chain(target_event_id: str = "", lookback_seconds: float = 30.0) -> str:
            """Query step-by-step backwards causal chain leading to a critical turn or shot."""
            from .attribution import EventAttributionSpecialist
            events = run.snapshot.data.get("events", [])
            tid = target_event_id or (events[-1].get("id", events[-1].get("event_id", "")) if events else "")
            res = EventAttributionSpecialist.causal_chain_query(
                events, target_event_id=str(tid), lookback_seconds=float(lookback_seconds)
            )
            run.audit.append({"type": "tool", "role": role, "name": "query_causal_chain", "snapshot_id": run.snapshot.id, "target_event_id": str(tid)})
            return res.model_dump_json()

        def explain_oaai_contributors(at: float = 0.0, team: str = "") -> str:
            """Recompute OAAI event contributions at a selected time using the frozen snapshot ledger."""
            from .oaai import compute_oaai_contribution_ledger
            data = run.snapshot.data
            target = float(at or data.get("as_of", 0))
            ledger = compute_oaai_contribution_ledger(
                data.get("events", []),
                at=target,
                team=(team or run.focus_team),
                dead_intervals=data.get("dead_intervals", []),
                limit=8,
            )
            run.audit.append({"type": "tool", "role": role, "name": "explain_oaai_contributors",
                              "snapshot_id": run.snapshot.id, "at": target})
            return json.dumps(ledger, separators=(",", ":"))

        def query_metric(metric_id: str, team: str = "", window: str = "current") -> str:
            """Query a registered football metric observation for this frozen snapshot."""
            from .metrics import MetricsService
            if window not in ("previous", "current", "match"):
                raise ValueError("invalid_metric_window")
            value = MetricsService.query(
                run.snapshot,
                metric_id,
                team=(team or run.focus_team),
                window=window,  # type: ignore[arg-type]
                match_id=run.match_id,
            )
            run.audit.append({"type": "tool", "role": role, "name": "query_metric",
                              "snapshot_id": run.snapshot.id, "metric_id": metric_id,
                              "team": value.team, "window": window})
            return value.model_dump_json()

        def assess_alternative_hypotheses(primary_hypothesis: str = "") -> str:
            """Assess candidate alternative rival hypotheses against empirical event receipts."""
            from .attribution import EventAttributionSpecialist
            at = float(run.snapshot.data.get("as_of", 180))
            w_start = max(0.0, at - 180.0)
            res = EventAttributionSpecialist.alternative_hypothesis_assessment(
                run.snapshot.data.get("events", []),
                primary_hypothesis=primary_hypothesis or "possession dominance",
                window_start_s=w_start,
                window_end_s=at,
                team=run.focus_team,
            )
            run.audit.append({"type": "tool", "role": role, "name": "assess_alternative_hypotheses", "snapshot_id": run.snapshot.id})
            return res.model_dump_json()

        return await self._run_model(
            run, role,
            [get_evidence, get_event_chain, get_sequence, decompose_window, query_causal_chain,
             assess_alternative_hypotheses, explain_oaai_contributors, query_metric],
            prompt,
            instructions(role, focus_team=run.focus_team),
            max_iterations=3, max_function_calls=2,
        )

    async def stage_with_registry(self, run: Run, role: str, registry, prompt: str,
                                  *, max_function_calls: int = 6) -> str:
        """Investigation stage whose tool calls run through FootballToolRegistry.

        The model selects tools dynamically, but every call goes through the
        same allow-list, per-tool budgets and receipt hashing as the
        deterministic planner (roadmap C-06). No new execution path exists.
        """
        from .tools import TOOL_BUDGET, TOOL_DESCRIPTIONS, ToolError

        run.role = role

        def get_evidence(snapshot_id: str) -> str:
            """Read immutable metric receipts, sample limitations and recorded football event chains."""
            if snapshot_id != run.snapshot.id:
                raise ValueError("snapshot_outside_tool_scope")
            run.audit.append({"type": "tool", "role": role, "name": "get_evidence", "snapshot_id": snapshot_id})
            return json.dumps(tool_evidence(run.snapshot, focus_team=run.focus_team), separators=(",", ":"))

        def make_registry_tool(name: str):
            def call(**kwargs) -> str:
                try:
                    tool_call = registry.call(name, kwargs)
                except ToolError as exc:
                    run.audit.append({"type": "tool_error", "role": role, "name": name, "error": exc.code})
                    raise ValueError(exc.code)
                run.audit.append({"type": "tool", "role": role, "name": name, "snapshot_id": run.snapshot.id,
                                  "tool_sequence": tool_call.sequence, "status": tool_call.status,
                                  "result_sha256": tool_call.result_sha256})
                return json.dumps(
                    {"sequence": tool_call.sequence, "status": tool_call.status, "summary": tool_call.summary,
                     "result": tool_call.result, "error": tool_call.error, "result_sha256": tool_call.result_sha256},
                    separators=(",", ":"), default=str,
                )
            call.__name__ = name
            call.__doc__ = TOOL_DESCRIPTIONS.get(name, name)
            return call

        tools = [get_evidence] + [make_registry_tool(name) for name in TOOL_BUDGET]
        return await self._run_model(
            run, role, tools, prompt,
            investigation_instructions(role, focus_team=run.focus_team),
            max_iterations=3, max_function_calls=max_function_calls,
        )

    @staticmethod
    def validate_stage(raw: str, role: str, run: Run) -> None:
        if role == "Analyst":
            draft = WireDraft.model_validate_json(raw).canonical()
            validate_draft(draft, run.snapshot)
            for claim in draft.claims:
                for variant in (claim.primary, claim.conservative):
                    if variant:
                        for prose in (variant.fan, variant.analyst):
                            bind_slots(prose, variant.refs, run.snapshot)
                            if QUANTITATIVE_WORDS.search(SLOT.sub("", prose)):
                                raise ValueError("unbound_spelled_number: use a referenced metric slot or omit the unsupported quantity")
        else:
            review = WireReview.model_validate_json(raw).canonical()
            for decision in review.decisions:
                for prose in (decision.reason, *decision.limitations):
                    bind_slots(prose, list(run.snapshot.data["receipts"]), run.snapshot)

    async def analyse(self, run: Run, progress: Callable[[str], Awaitable[None]]) -> dict:
        if not self.key:
            return {"status": "fallback", "origin": "deterministic", "error": "model_not_configured", "accepted": [], "rejected": []}
        runner = self
        started = time.perf_counter()

        class Stage(Executor):
            def __init__(self, role: str):
                super().__init__(id=role.lower())
                self.role = role

            @handler
            async def process(self, value: str, ctx: WorkflowContext[str]) -> None:
                await progress("analysing" if self.role == "Analyst" else "verifying")
                raw = await runner.stage(run, self.role, value)
                if self.role == "Analyst":
                    draft = WireDraft.model_validate_json(raw).canonical()
                    validate_draft(draft, run.snapshot)
                    run.draft = draft.model_dump()
                    run.audit.append({"type": "handoff", "from": "Analyst", "to": "Verifier", "snapshot_id": run.snapshot.id,
                                      "claim_ids": [c.id for c in draft.claims],
                                      "draft_sha256": hashlib.sha256(draft.model_dump_json().encode()).hexdigest()})
                    await ctx.send_message(json.dumps({"snapshot_id": run.snapshot.id, "draft": run.draft}))
                else:
                    review = WireReview.model_validate_json(raw).canonical()
                    run.review = review.model_dump()
                    await ctx.yield_output(review.model_dump_json())

        try:
            async with asyncio.timeout(self.deadline):
                analyst, verifier = Stage("Analyst"), Stage("Verifier")
                workflow = WorkflowBuilder(start_executor=analyst).add_edge(analyst, verifier).build()
                result = await workflow.run(json.dumps({"snapshot_id": run.snapshot.id, "task": "Investigate the candidate; read evidence before deciding."}))
                outputs = result.get_outputs()
                if not outputs or not run.draft:
                    raise ValueError("workflow_missing_output")
                review = VerifierDecision.model_validate_json(outputs[-1])
                gated = publication_gate(ClaimDraft.model_validate(run.draft), review, run.snapshot, run.audit)
                return {"status": "completed", "origin": "live_model", **gated,
                        "duration_ms": round((time.perf_counter()-started)*1000), "model": "deepseek-flash", "prompt_version": PROMPT_VERSION}
        except asyncio.CancelledError:
            run.audit.append({"type": "cancelled", "role": run.role})
            raise
        except Exception as exc:
            # Avoid serializing SDK exception bodies/headers which may contain secrets.
            def contains_budget(value, seen=None):
                seen = seen or set()
                if id(value) in seen:
                    return False
                seen.add(id(value))
                if isinstance(value, BudgetExceeded):
                    return True
                children = (*value.args, value.__cause__, value.__context__, *getattr(value, "exceptions", ())) if isinstance(value, BaseException) else ()
                return any(contains_budget(arg, seen) for arg in children)
            error = "analysis_timeout" if isinstance(exc, TimeoutError) else "inference_budget_exhausted" if contains_budget(exc) else "analysis_failed"
            detail = str(exc).replace(self.key or "<no-key>", "[REDACTED]")[:500]
            run.audit.append({"type": "failure", "role": run.role, "error_type": type(exc).__name__, "detail": detail})
            return {"status": "fallback", "origin": "deterministic", "error": error,
                    "error_type": type(exc).__name__, "accepted": [], "rejected": [], "duration_ms": round((time.perf_counter()-started)*1000)}
