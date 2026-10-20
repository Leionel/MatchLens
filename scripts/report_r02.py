"""Offline receipt revalidation and release inspection; sends no model requests."""
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))
from matchlens.budget import BudgetLedger
from matchlens.contracts import ClaimDraft, VerifierDecision, publication_gate
from matchlens.football import freeze, generate_match


def main():
    out = ROOT / "evidence/r0.2"
    records, revalidation = [], []
    for p in sorted((out / "runs").glob("*.json")):
        d = json.loads(p.read_text())
        result = d.get("result") or {}
        records.append({"file": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                        "run_id": d["run_id"], "snapshot_id": d["snapshot_id"], "prompt_version": d.get("prompt_version"),
                        "requests": d["requests"], "duration_ms": result.get("duration_ms"),
                        "accepted_at_execution": len(result.get("accepted", [])), "audit_counts": dict(Counter(e["type"] for e in d.get("audit", [])))})
        snap = freeze(generate_match(), d["evidence"]["as_of"])
        checked = {"run_id": d["run_id"], "exact_snapshot": snap.id == d["snapshot_id"] and snap.data == d["evidence"]}
        try:
            checked.update(publication_gate(ClaimDraft.model_validate(d["draft"]), VerifierDecision.model_validate(d["review"]), snap, d["audit"]))
        except ValueError as exc:
            checked.update(accepted=[], error=str(exc))
        revalidation.append(checked)
    (out / "revalidation.json").write_text(json.dumps(revalidation, indent=2), encoding="utf-8", newline="\n")
    v = dotenv_values(ROOT / ".env")
    ledger = BudgetLedger(ROOT / ".runtime/budget.sqlite3", int(v.get("MATCHLENS_MAX_REQUESTS") or 32), float(v.get("MATCHLENS_MAX_RESERVED_USD") or 1))
    budget = ledger.summary()
    ledger.close()
    paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
    secret_paths, broken, hashes = [], [], {}
    for name in paths:
        p = ROOT / name
        if not p.is_file():
            continue
        if p.suffix in (".py", ".ts", ".tsx", ".css", ".json", ".md", ".toml", ".lock", ".ps1", ".yml", ".yaml"):
            try:
                text = p.read_text(encoding="utf-8-sig")
            except UnicodeError:
                continue
            if re.search(r"sk-[A-Za-z0-9]{20,}", text):
                secret_paths.append(name)  # Never print the matching value.
        if name.startswith(("services/api/matchlens/", "apps/web/app/")) or name in ("services/api/uv.lock", "apps/web/package-lock.json"):
            hashes[name] = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    for p in [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]:
        for target in re.findall(r"\]\(([^)]+)\)", p.read_text(encoding="utf-8", newline="\n")):
            if "://" in target or target.startswith("#"):
                continue
            target = target.split("#")[0]
            # This exporter creates its own manifest after link inspection.
            if target and not (p.parent / target).exists() and (p.parent / target).resolve() != (out / "manifest.json").resolve():
                broken.append({"doc": p.relative_to(ROOT).as_posix(), "target": target})
    suites = ElementTree.parse(out / "pytest.xml").getroot().findall("testsuite")
    manifest = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "git_base": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "working_tree": True, "hash_line_endings": "CRLF normalized to LF, matching Git eol=lf", "source_hashes_captured_after_verification": hashes,
                "source_binding_note": "Original runs have prompt/snapshot versions, not per-file hashes. These current code hashes are a release inspection snapshot, not retroactive execution attestation. Gate revalidation is separate from original outcomes.",
                "runs": records, "budget": budget, "checks": {"python_tests": sum(int(s.attrib["tests"]) for s in suites),
                "python_failed": sum(int(s.attrib["failures"]) + int(s.attrib["errors"]) for s in suites),
                "secret_pattern_matches": secret_paths, "broken_local_doc_links": broken}, "browser_checks": "browser-checks.json",
                "not_run": ["container build: Linux Docker daemon unavailable", "public deployment/egress", "independent human review", "S0/S1/M", "latest B model"]}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps({"tests": manifest["checks"]["python_tests"], "run_count": len(records), "ledger_requests": budget["requests_reserved"],
                      "secret_match_count": len(secret_paths), "broken_local_doc_links": broken,
                      "current_gate_acceptance": [(r["run_id"], len(r["accepted"])) for r in revalidation]}, indent=2))
    return int(bool(secret_paths or broken or manifest["checks"]["python_failed"]))


if __name__ == "__main__":
    raise SystemExit(main())
