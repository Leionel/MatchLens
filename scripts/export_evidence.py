"""Export actual sanitized operator receipts and source identity, never config."""
import hashlib
import importlib.metadata
import json
import platform
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))
from matchlens.agents import PROMPT_VERSION
from matchlens.budget import BudgetLedger
from matchlens.football import CHAPTERS, freeze, generate_match


def main():
    out = ROOT / "evidence/r0.1"
    (out / "runs").mkdir(parents=True, exist_ok=True)
    runs = []
    for path in sorted((ROOT / ".runtime/runs").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        # Our run writer never stores headers/config; refuse an accidentally
        # embedded credential before copying anything into public evidence.
        if "sk-" in path.read_text(encoding="utf-8"):
            raise ValueError("credential_pattern_in_receipt")
        shutil.copyfile(path, out / "runs" / path.name)
        result = data.get("result") or {}
        runs.append({"run_id": data["run_id"], "as_of": data["evidence"]["as_of"],
                     "snapshot_id": data["snapshot_id"], "generator_version": data["evidence"].get("generator_version", "not-recorded"),
                     "prompt_version": data.get("prompt_version", result.get("prompt_version", "not-recorded")),
                     "status": result.get("status", "superseded"), "accepted": len(result.get("accepted", [])),
                     "duration_ms": result.get("duration_ms"), "requests": data["requests"]})
    ledger = BudgetLedger(ROOT / ".runtime/budget.sqlite3", 64, 1.5)
    budget = ledger.summary()
    ledger.close()
    source_files = [*ROOT.glob("services/api/matchlens/*.py"), *ROOT.glob("apps/web/app/*"),
                    ROOT / "services/api/uv.lock", ROOT / "apps/web/package-lock.json"]
    manifest = {"exported_at_utc": datetime.now(timezone.utc).isoformat(), "source_revision": "uncommitted-working-tree",
        "python_version": platform.python_version(),
        "current_prompt_version": PROMPT_VERSION, "provider": "DeepSeek official HTTPS Chat Completions", "model_requested": "deepseek-flash",
        "options": {"response_format": "json_object", "thinking": "disabled", "max_tokens": 1024, "sdk_retries": 0},
        "versions": {p: importlib.metadata.version(p) for p in ("agent-framework-core", "agent-framework-openai", "openai", "fastapi", "uvicorn", "pydantic")},
        "source_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files},
        "current_snapshots": [{"chapter": c["id"], "as_of": c["at"], "id": freeze(generate_match(), c["at"]).id} for c in CHAPTERS],
        "budget": budget, "runs": runs, "statuses": dict(Counter(r["status"] for r in runs)),
        "note": "All development attempts retained. HTTP success is not publication/semantic success. Verifier-only challenge is separate. No held-out comparative experiment."}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"runs": len(runs), "statuses": manifest["statuses"], "budget": budget}, indent=2))


if __name__ == "__main__":
    main()
