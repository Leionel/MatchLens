"""Run real DeepSeek Flash dual-agent workflow for Chapter C on the current version."""
import asyncio
import json
import os
import secrets
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))

from matchlens.agents import AgentRunner, Run, PROMPT_VERSION
from matchlens.budget import BudgetLedger
from matchlens.football import freeze, generate_match


async def main():
    load_dotenv(ROOT / ".env")
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("ERROR: DEEPSEEK_API_KEY not found in .env")
        return 1

    ledger = BudgetLedger(ROOT / ".runtime/budget.sqlite3", int(os.getenv("MATCHLENS_MAX_REQUESTS", "32")), float(os.getenv("MATCHLENS_MAX_RESERVED_USD", "1.0")))
    if not ledger.has_runway(6):
        print("Insufficient whole-workflow allowance; no model request sent.")
        ledger.close()
        return 1
    print(f"Initial Budget summary: {ledger.summary()}")

    runner = AgentRunner(key, ledger, deadline=35)
    events = generate_match(17)
    snap = freeze(events, 720, seed=17)
    print(f"Snapshot ID: {snap.id}")
    print(f"Snapshot Candidate: {snap.data['candidate']}")
    print(f"Goals receipt: {snap.data['receipts']['H.goals.match']}")

    run = Run("run-c-verify-" + secrets.token_hex(4), snap)

    async def progress(status: str):
        print(f"[{time.strftime('%H:%M:%S')}] Workflow progress: {status}")

    started = time.perf_counter()
    result = await runner.analyse(run, progress)
    elapsed = time.perf_counter() - started

    print(f"\nElapsed: {elapsed:.2f}s")
    print(f"Result status: {result.get('status')}")
    print(f"Result origin: {result.get('origin')}")
    print(f"Accepted claims count: {len(result.get('accepted', []))}")
    print(f"Rejected claims count: {len(result.get('rejected', []))}")
    if result.get("accepted"):
        for card in result["accepted"]:
            print("\n--- ACCEPTED CARD ---")
            print(f"Claim ID: {card['claim_id']}")
            print(f"Assertion: {card['assertion']}")
            print(f"Verdict: {card['verdict']}")
            print(f"Scope: {card['scope']}")
            print(f"Refs: {card['refs']}")
            print(f"Fan: {card['fan']}")
            print(f"Analyst: {card['analyst']}")
            print(f"Reason: {card['reason']}")
            print(f"Limitations: {card['limitations']}")
    if result.get("rejected"):
        for rej in result["rejected"]:
            print("\n--- REJECTED CLAIM ---")
            print(rej)

    print(f"\nTotal Run Requests: {run.requests}")
    print(f"Final Budget summary: {ledger.summary()}")

    # Save run artifact
    record = {
        "run_id": run.id,
        "snapshot_id": snap.id,
        "evidence": snap.data,
        "prompt_version": PROMPT_VERSION,
        "draft": run.draft,
        "review": run.review,
        "result": result,
        "audit": run.audit,
        "requests": run.requests,
        "raw_outputs": run.raw_outputs,
    }
    out_path = ROOT / ".runtime/runs" / f"{run.id}.json"
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Saved run record to {out_path}")
    ledger.close()
    return 0


if __name__ == "__main__":
    asyncio.run(main())
