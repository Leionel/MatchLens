"""Bounded live compatibility probe; no application or simulated model responses."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from dotenv import load_dotenv
from jsonschema import validate
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

ROOT = Path(__file__).resolve().parent
SNAPSHOT = {
    "snapshot_id": "spike-possession-v1", "synthetic": True,
    "as_of_seq": 42, "window_seconds": 180,
    "receipts": [
        {"id": "r-possession", "previous": 45, "current": 65, "unit": "percent"},
        {"id": "r-shots", "previous": 2, "current": 1, "unit": "count"},
        {"id": "r-entries", "previous": 3, "current": 2, "unit": "count"},
    ],
    "event_ids": ["e38", "e40", "e42"],
}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "snapshot_id": {"const": SNAPSHOT["snapshot_id"]},
        "claim_id": {"const": "C1"},
        "statement": {"type": "string", "minLength": 1},
        "evidence_refs": {"type": "array", "minItems": 3,
                          "items": {"enum": [r["id"] for r in SNAPSHOT["receipts"]]}},
    },
    "required": ["snapshot_id", "claim_id", "statement", "evidence_refs"],
}
VERDICT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "snapshot_id": {"const": SNAPSHOT["snapshot_id"]},
        "claim_id": {"const": "C1"},
        "verdict": {"enum": ["publish", "qualify", "withhold"]},
        "reason": {"type": "string", "minLength": 1},
        "evidence_refs": SCHEMA["properties"]["evidence_refs"],
    },
    "required": ["snapshot_id", "claim_id", "verdict", "reason", "evidence_refs"],
}


class Ping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()
                if k not in {"reasoning_content", "reasoning", "api_key", "authorization"}}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


class Gateway:
    """Spike-only accounting boundary. Forwards genuine requests without rewriting them."""

    def __init__(self, key, output, request_cap=30):
        self.key, self.output, self.cap = key, output, request_cap
        self.records, self.lock = [], threading.Lock()
        self.http = httpx.Client(timeout=30, trust_env=True)
        self.server = None

    def save(self):
        self.output.write_text(json.dumps(clean(self.records), indent=2), encoding="utf-8")

    def start(self):
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                body = json.loads(raw)
                route = self.path.split("/")[1]
                # No API can escape the single upstream destination or request cap.
                if not self.path.endswith("/chat/completions"):
                    return self.reply(400, b'{"error":{"message":"chat completions only"}}')
                cap = body.get("max_tokens", body.get("max_completion_tokens"))
                if len(raw) > 20000 or not isinstance(cap, int) or not 1 <= cap <= 768:
                    return self.reply(400, b'{"error":{"message":"spike input/output bound"}}')
                if body.get("model") not in {"deepseek-flash", "deepseek-v4-pro"}:
                    return self.reply(400, b'{"error":{"message":"model not allowlisted"}}')
                with gateway.lock:
                    if len(gateway.records) >= gateway.cap:
                        return self.reply(429, b'{"error":{"message":"spike request cap"}}')
                    record = {"attempt": len(gateway.records)+1, "route": route,
                              "started_at": now(), "request": clean(body)}
                    gateway.records.append(record)
                    gateway.save()  # Reserve before sending. No automatic retries.
                started = time.perf_counter()
                try:
                    response = gateway.http.post(
                        "https://api.deepseek.com/chat/completions", json=body,
                        headers={"Authorization": "Bearer " + gateway.key})
                    data = response.content
                    record["status"] = response.status_code
                    record["duration_ms"] = round((time.perf_counter()-started)*1000, 2)
                    record["request_id"] = response.headers.get("x-ds-request-id") or response.headers.get("x-request-id")
                    # Buffer SSE only for accounting; do not claim TTFT from this probe.
                    if "text/event-stream" in response.headers.get("content-type", ""):
                        chunks = []
                        for line in data.decode().splitlines():
                            if line.startswith("data: ") and line[6:] != "[DONE]":
                                chunks.append(clean(json.loads(line[6:])))
                        record["response_chunks"] = chunks
                    else:
                        record["response"] = clean(response.json())
                    gateway.save()
                    self.reply(response.status_code, data, response.headers.get("content-type", "application/json"))
                except Exception as exc:
                    record["error_type"] = type(exc).__name__
                    record["duration_ms"] = round((time.perf_counter()-started)*1000, 2)
                    gateway.save()
                    self.reply(502, b'{"error":{"message":"upstream transport failed"}}')

            def reply(self, status, data, content_type="application/json"):
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.http.close()


def evidence(snapshot_id):
    if snapshot_id != SNAPSHOT["snapshot_id"]:
        raise ValueError("snapshot outside scope")
    return json.dumps(SNAPSHOT)


def instructions(role):
    schema = SCHEMA if role == "Analyst" else VERDICT_SCHEMA
    task = ("Explain whether increased possession implies increased attacking threat."
            if role == "Analyst" else
            "Check the handed-off claim against all receipts. Do not infer coaching intent or causality.")
    return (f"You are MatchLens {role}. {task} You MUST call get_evidence once before answering. "
            "Use only its evidence, preserve its snapshot_id and claim_id C1. "
            "Return only one JSON object, no markdown. JSON schema: " + json.dumps(schema))


async def maf_stage(base, model, role, prompt, calls, typed=False):
    from agent_framework import Agent
    from agent_framework.openai import OpenAIChatCompletionClient

    def get_evidence(snapshot_id: str) -> str:
        """Read the immutable football snapshot and all three metric receipts."""
        calls.append({"agent": role, "tool": "get_evidence", "snapshot_id": snapshot_id})
        return evidence(snapshot_id)

    async with AsyncOpenAI(base_url=base, api_key="local-accounting-only", max_retries=0, timeout=32,
                           http_client=httpx.AsyncClient(trust_env=False)) as sdk:
        client = OpenAIChatCompletionClient(model=model, async_client=sdk,
                    function_invocation_configuration={"max_iterations": 2, "max_function_calls": 2})
        opts = {"response_format": Ping if typed else {"type": "json_object"},
                "extra_body": {"thinking": {"type": "disabled"}, "max_tokens": 512}}
        agent = Agent(client=client, name=role, instructions=instructions(role) if not typed else "Return JSON {\"ok\":true}.",
                      tools=None if typed else [get_evidence], default_options=opts)
        response = await agent.run(prompt)
        return response.text


async def maf_handoff(base, model, calls):
    from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

    class Stage(Executor):
        def __init__(self, role):
            super().__init__(id=role.lower())
            self.role = role

        @handler
        async def run(self, value: str, ctx: WorkflowContext[str]) -> None:
            output = json.loads(await maf_stage(base, model, self.role, value, calls))
            validate(output, SCHEMA if self.role == "Analyst" else VERDICT_SCHEMA)
            if self.role == "Analyst":
                calls.append({"handoff": "Analyst->Verifier", "snapshot_id": output["snapshot_id"],
                              "claim_id": output["claim_id"]})
                await ctx.send_message(json.dumps({"snapshot_id": SNAPSHOT["snapshot_id"], "draft": output}))
            else:
                await ctx.yield_output(json.dumps(output))

    analyst, verifier = Stage("Analyst"), Stage("Verifier")
    workflow = WorkflowBuilder(start_executor=analyst).add_edge(analyst, verifier).build()
    result = await workflow.run("Investigate snapshot spike-possession-v1 using get_evidence.")
    output = result.get_outputs()
    if not output:
        raise ValueError("workflow produced no output")
    return json.loads(output[-1])


async def copilot_probe(base, model, calls, *, typed=False):
    from copilot import CopilotClient
    from copilot.tools import Tool, ToolResult

    # The provider gets only a loopback dummy credential; the real key stays in Gateway.
    safe_env = {k: v for k, v in os.environ.items()
                if k not in {"GH_TOKEN", "GITHUB_TOKEN", "COPILOT_GITHUB_TOKEN", "DEEPSEEK_API_KEY"}
                and not k.startswith("COPILOT_OTEL")}
    safe_env["NO_PROXY"] = "127.0.0.1,localhost"
    with tempfile.TemporaryDirectory(prefix="matchlens-copilot-") as work:
        client = CopilotClient(mode="empty", use_logged_in_user=False, env=safe_env,
                               base_directory=work, working_directory=work, log_level="error")
        await client.start()
        try:
            async def stage(role, prompt):
                def tool_handler(invocation):
                    args = invocation.arguments or {}
                    if isinstance(args, str):
                        args = json.loads(args)
                    calls.append({"agent": role, "tool": "get_evidence", "snapshot_id": args.get("snapshot_id")})
                    return ToolResult(text_result_for_llm=evidence(args["snapshot_id"]), result_type="success")

                tool = Tool(name="get_evidence", description="Read the immutable football snapshot and metric receipts.",
                    parameters={"type": "object", "properties": {"snapshot_id": {"type": "string"}},
                                "required": ["snapshot_id"], "additionalProperties": False},
                    handler=tool_handler, skip_permission=True)
                session = await client.create_session(
                    name=role, model=model, reasoning_effort="none",
                    provider={"type": "openai", "base_url": base, "wire_api": "completions",
                              "api_key": "local-accounting-only", "max_output_tokens": 512, "max_prompt_tokens": 6000},
                    system_message={"mode": "replace", "content": instructions(role)},
                    tools=[] if typed else [tool], available_tools=[] if typed else ["get_evidence"],
                    on_permission_request=lambda *args: {"kind": "denied-by-rules"},
                    enable_session_telemetry=False, enable_config_discovery=False, enable_skills=False,
                    enable_host_git_operations=False, enable_session_store=False,
                    skip_custom_instructions=True, infinite_sessions={"enabled": False},
                    mcp_servers={}, streaming=False)
                try:
                    if typed:
                        return (await session.send_and_wait_typed("Return JSON {\"ok\":true}.", Ping, timeout=35)).model_dump()
                    result = await session.send_and_wait(prompt, timeout=35)
                    if result is None:
                        raise ValueError("no assistant result")
                    parsed = json.loads(result.data.content)
                    validate(parsed, SCHEMA if role == "Analyst" else VERDICT_SCHEMA)
                    return parsed
                finally:
                    await session.abort()
                    await session.disconnect()

            if typed:
                return await stage("Analyst", "")
            draft = await stage("Analyst", "Investigate snapshot spike-possession-v1 using get_evidence.")
            calls.append({"handoff": "Analyst->Verifier", "snapshot_id": draft["snapshot_id"], "claim_id": draft["claim_id"]})
            return await stage("Verifier", json.dumps({"snapshot_id": SNAPSHOT["snapshot_id"], "draft": draft}))
        finally:
            await client.stop()


async def direct(base, model, strict=False):
    async with AsyncOpenAI(base_url=base, api_key="local-accounting-only", max_retries=0, timeout=32,
                           http_client=httpx.AsyncClient(trust_env=False)) as client:
        fmt = {"type": "json_schema", "json_schema": {"name": "Ping", "strict": True, "schema": Ping.model_json_schema()}} if strict else {"type": "json_object"}
        result = await client.chat.completions.create(model=model,
            messages=[{"role": "user", "content": 'Return only JSON {"ok":true}.'}],
            response_format=fmt, max_tokens=128, extra_body={"thinking": {"type": "disabled"}})
        value = json.loads(result.choices[0].message.content)
        Ping.model_validate(value)
        return value


async def main(args):
    if args.env_file:
        load_dotenv(args.env_file)
    key = os.environ.get("DEEPSEEK_API_KEY")
    result_root = ROOT / "results"
    previous_requests = sum(len(json.loads(p.read_text(encoding="utf-8")))
                            for p in result_root.rglob("requests.json")) if result_root.exists() else 0
    output = result_root / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {"started_at": now(), "origin": "live_provider", "request_cap": 30,
              "prior_upstream_requests": previous_requests,
              "versions": {p: importlib.metadata.version(p) for p in ["agent-framework-core", "agent-framework-openai", "github-copilot-sdk", "openai"]},
              "snapshot": SNAPSHOT, "snapshot_sha256": hashlib.sha256(json.dumps(SNAPSHOT, sort_keys=True).encode()).hexdigest(), "cases": []}
    if not key:
        report["status"] = "blocked_missing_credentials"
        (output / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(report["status"])
        return
    remaining = min(args.request_cap, 30 - previous_requests)
    if remaining <= 0:
        raise RuntimeError("Cumulative 30-request spike cap reached")
    gateway = Gateway(key, output / "requests.json", remaining)
    url = gateway.start()
    cases = [c for c in args.cases.split(",") if c]
    try:
        for case in cases:
            calls, start, before = [], time.perf_counter(), len(gateway.records)
            route = f"{case}-{int(start*1000)}"
            base = f"{url}/{route}/v1"
            model = "deepseek-v4-pro" if case.endswith("pro") else "deepseek-flash"
            item = {"case": case, "model": model, "started_at": now(), "tool_and_handoff_events": calls}
            try:
                async with asyncio.timeout(80):
                    if case.startswith("direct"):
                        result = await direct(base, model, strict="strict" in case)
                    elif case.startswith("maf-typed"):
                        result = await maf_stage(base, model, "Analyst", 'Return JSON {"ok":true}.', calls, typed=True)
                    elif case.startswith("maf"):
                        result = await maf_handoff(base, model, calls)
                    else:
                        result = await copilot_probe(base, model, calls, typed="typed" in case)
                item["output"] = result
                if case.startswith("maf") and "typed" not in case or case.startswith("copilot") and "typed" not in case:
                    received = 0
                    for req in gateway.records[before:]:
                        for message in req["request"].get("messages", []):
                            if message.get("role") == "tool":
                                try:
                                    received += json.loads(message.get("content", "")) == SNAPSHOT
                                except (TypeError, ValueError):
                                    pass
                    item["verified_tool_receipt_roundtrips"] = received
                    if received < 2 or not any("handoff" in event for event in calls):
                        raise ValueError("Missing two genuine tool-receipt roundtrips or handoff")
                item["status"] = "passed"
            except Exception as exc:
                # Never put provider credentials or full transport headers in a report.
                message = str(exc).replace(key, "[REDACTED]")
                item.update(status="failed", error_type=type(exc).__name__, error=message[:1000])
            item.update(duration_ms=round((time.perf_counter()-start)*1000, 2),
                        upstream_requests=len(gateway.records)-before)
            report["cases"].append(item)
            report["upstream_requests"] = len(gateway.records)
            (output / "summary.json").write_text(json.dumps(clean(report), indent=2), encoding="utf-8")
            print(json.dumps({k: item[k] for k in ["case", "status", "duration_ms", "upstream_requests"]}), flush=True)
    finally:
        gateway.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--request-cap", type=int, default=30, choices=range(1, 31))
    parser.add_argument("--cases", default="direct-json,direct-strict,maf-flash,maf-typed,copilot-flash,copilot-typed,maf-pro")
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ"))
    asyncio.run(main(parser.parse_args()))
