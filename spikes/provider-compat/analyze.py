"""Offline audit of saved provider evidence. Makes no network requests."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "results"
records, cases = [], []
for summary in sorted(ROOT.rglob("summary.json")):
    data = json.loads(summary.read_text(encoding="utf-8"))
    path = summary.parent / "requests.json"
    requests = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    records.extend(requests)
    for case in data["cases"]:
        selected = [r for r in requests if r["route"].startswith(case["case"] + "-")]
        tool_receipts = 0
        for record in selected:
            for message in record["request"].get("messages", []):
                if message.get("role") == "tool":
                    try:
                        tool_receipts += json.loads(message.get("content", "")) == data["snapshot"]
                    except (TypeError, ValueError):
                        pass
        workflow = "typed" not in case["case"] and not case["case"].startswith("direct")
        assessment = case["status"]
        if workflow and assessment == "passed" and tool_receipts < 2:
            assessment = "harness_failure_tool_result_not_delivered"
        cases.append({"source": str(summary.relative_to(ROOT)), "case": case["case"],
                      "model": case["model"], "assessment": assessment,
                      "duration_ms": case["duration_ms"], "upstream_requests": case["upstream_requests"],
                      "verified_tool_receipt_roundtrips": tool_receipts,
                      "error": case.get("error"), "output": case.get("output")})

totals = {"prompt_tokens": 0, "completion_tokens": 0, "cache_hit_tokens": 0, "cache_miss_tokens": 0}
cost, known, unknown = 0.0, 0, 0
for record in records:
    responses = [record["response"]] if "response" in record else record.get("response_chunks", [])
    usage = next((r.get("usage") for r in reversed(responses) if r.get("usage")), None)
    if not usage:
        unknown += 1
        continue
    known += 1
    prompt, completion = usage["prompt_tokens"], usage["completion_tokens"]
    hit = usage.get("prompt_cache_hit_tokens", 0)
    miss = usage.get("prompt_cache_miss_tokens", prompt-hit)
    totals["prompt_tokens"] += prompt
    totals["completion_tokens"] += completion
    totals["cache_hit_tokens"] += hit
    totals["cache_miss_tokens"] += miss
    input_price, hit_price, output_price = (1.32, .044, 3.96) if record["request"]["model"] == "deepseek-v4-pro" else (.30, .006, 1.20)
    cost += (miss*input_price + hit*hit_price + completion*output_price)/1_000_000

assert len(records) <= 30, "Spike exceeded authorized request cap"
result = {"upstream_attempts": len(records), "http_200": sum(r.get("status") == 200 for r in records),
          "http_400": sum(r.get("status") == 400 for r in records),
          "requests_with_usage": known, "requests_without_usage": unknown,
          "usage_totals": totals, "known_usage_cost_usd_at_peak_prices": round(cost, 8),
          "cost_note": "Derived from reported usage and the 2026-10-19 USD price page; not an invoice. Unknown-usage attempts excluded, not assumed free.",
          "cases": cases}
(ROOT / "analysis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "cases"}, indent=2))
for case in cases:
    print(case["case"], case["assessment"], case["duration_ms"], case["upstream_requests"])
