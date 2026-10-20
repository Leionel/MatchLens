"""Live semantic challenge, separate from normal two-agent product journeys."""
import asyncio
import json
import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))

from matchlens.agents import AgentRunner, Run, WireReview
from matchlens.budget import BudgetLedger
from matchlens.contracts import ClaimDraft, REQUIRED
from matchlens.football import freeze, generate_match


async def main():
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    ledger = BudgetLedger(root / ".runtime/budget.sqlite3", int(os.getenv("MATCHLENS_MAX_REQUESTS", "32")), float(os.getenv("MATCHLENS_MAX_RESERVED_USD", "1")))
    runner = AgentRunner(os.environ["DEEPSEEK_API_KEY"], ledger)
    snap = freeze(generate_match(), 360)
    # Deliberately false human-authored challenge, never used by the product.
    variant = {"id": "primary", "scope": "window", "refs": sorted(REQUIRED["attacking_threat_increased"]),
               "fan": "Harbor's attacking activity increased in this window.",
               "analyst": "Harbor produced greater attacking output, supported by the shot and entry comparison in this window."}
    draft = ClaimDraft.model_validate({"snapshot_id": snap.id, "claims": [{"id": "claim-contradicted-threat",
        "assertion": "attacking_threat_increased", "primary": variant,
        "conservative": {**variant, "id": "conservative", "fan": "Harbor's attacking activity increased, although the sample is short."}}]})
    run = Run("challenge-"+secrets.token_hex(6), snap, draft=draft.model_dump())
    try:
        raw = await runner.stage(run, "Verifier", json.dumps({"snapshot_id": snap.id, "draft": draft.model_dump()}))
        review = WireReview.model_validate_json(raw).canonical().model_dump()
        report = {"kind": "human_authored_false_claim_live_verifier_challenge", "not_a_new_two_agent_journey": True,
                  "snapshot_id": snap.id, "evidence": snap.data, "draft": draft.model_dump(), "review": review,
                  "raw_outputs": run.raw_outputs, "audit": run.audit, "requests": run.requests}
        path = root / "evidence/r0.1/verifier-challenge.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"verdict": review["decisions"][0]["verdict"], "requests": run.requests}))
    finally:
        ledger.close()


if __name__ == "__main__":
    asyncio.run(main())
