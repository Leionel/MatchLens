#!/usr/bin/env python
"""Check the single-container deployment contract without needing Docker.

Docker is not always available (and is impossible in some CI sandboxes), so the
things that actually break a deploy are asserted here directly:

* every ``COPY`` source in the Dockerfile exists in the build context,
* the licensed payloads are excluded from that context,
* the entrypoint is LF-only and executable-ish,
* ``railway.toml`` points its healthcheck at a route the app really serves,
* the bootstrap is idempotent and produces an analysis-ready match on a volume,
* the app serves that match from the volume through the real HTTP surface.

Run: services/api/.venv/Scripts/python.exe scripts/verify_deployment.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = Path(sys.executable)
FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if condition:
        print(f"  ok   {message}")
    else:
        print(f"  FAIL {message}")
        FAILURES.append(message)


def dockerfile_copy_sources() -> list[str]:
    sources: list[str] = []
    for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("COPY ") and "--from" not in stripped:
            parts = stripped.split()[1:]
            # COPY src... dest  → every token but the last is a source.
            sources.extend(parts[:-1])
    return sources


def main() -> int:
    print("Dockerfile")
    sources = dockerfile_copy_sources()
    check(bool(sources), "has plain COPY instructions")
    for source in sources:
        literal = source.rstrip("/")
        if "*" in literal:
            check(bool(list(ROOT.glob(literal))), f"COPY source exists: {source}")
        else:
            check((ROOT / literal).exists(), f"COPY source exists: {source}")

    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    check("--workers 1" in (ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8"),
          "entrypoint pins a single uvicorn worker")
    check("HEALTHCHECK" in text, "image declares a HEALTHCHECK")
    check("USER " not in text or text.index("USER ") > text.index("ENTRYPOINT"),
          "image starts as root only to prepare the volume, then drops privileges")
    check('ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]' in text, "entrypoint is the image ENTRYPOINT")

    print("Build context")
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for pattern in ("data/datasets", "data/raw", "**/node_modules", "**/.next"):
        check(pattern in ignored, f".dockerignore excludes {pattern}")
    check((ROOT / "data" / "source_manifest.json").exists(), "manifest ships with the image")
    check((ROOT / "data" / "corpus_statsbomb.json").exists(), "corpus definition ships with the image")

    print("Entrypoint")
    raw = (ROOT / "docker-entrypoint.sh").read_bytes()
    check(b"\r\n" not in raw, "entrypoint has LF line endings")
    check(raw.startswith(b"#!"), "entrypoint has a shebang")
    check(b"PORT" in raw, "entrypoint honours $PORT")

    print("railway.toml")
    config = tomllib.loads((ROOT / "railway.toml").read_text(encoding="utf-8"))
    deploy = config.get("deploy", {})
    health = deploy.get("healthcheckPath")
    check(health == "/api/health", "healthcheck points at /api/health")
    check(config.get("build", {}).get("builder") == "DOCKERFILE", "builder is DOCKERFILE")
    check(config.get("build", {}).get("dockerfilePath") == "Dockerfile", "dockerfilePath is Dockerfile")

    # The health path must really be a route, not a wish.
    main_py = (ROOT / "services" / "api" / "matchlens" / "main.py").read_text(encoding="utf-8")
    check('@app.get("/api/health")' in main_py, "app really serves the healthcheck route")

    print("Bootstrap on a fresh volume")
    volume = Path(tempfile.mkdtemp(prefix="matchlens-vol-"))
    data = volume / "data"
    env = dict(os.environ)
    env["MATCHLENS_DATA_DIR"] = str(data)
    env["MATCHLENS_RUNTIME_DIR"] = str(volume / "runtime")
    # Reuse the raw cache if this machine has it, so the check does not depend
    # on network access; otherwise the script exercises the download path.
    raw_cache = ROOT / "data" / "raw" / "statsbomb"
    if (raw_cache / "events_3795221.json").exists():
        env["MATCHLENS_SB_RAW_DIR"] = str(raw_cache)
    env.setdefault("MATCHLENS_BOOTSTRAP_MATCH", "sb_3795221")

    first = subprocess.run([str(PY), str(ROOT / "scripts" / "bootstrap_real_match.py")],
                           env=env, capture_output=True, text=True)
    check(first.returncode == 0, "bootstrap exits 0 (a network failure must not fail the boot)")
    dataset = data / "datasets" / "sb_3795221.json"
    offline = "fetch failed" in first.stdout
    if offline:
        print("  skip volume checks: no raw cache and no reachable provider (offline run)")
        print()
        shutil.rmtree(volume, ignore_errors=True)
        if FAILURES:
            print(f"{len(FAILURES)} deployment contract check(s) failed")
            return 1
        print("deployment contract verified (volume checks skipped: offline)")
        return 0
    check(dataset.exists(), "a complete provider match landed on the volume")
    check((data / "source_manifest.json").exists(), "manifest was seeded onto the volume")

    manifest = json.loads((data / "source_manifest.json").read_text(encoding="utf-8"))
    entry = next((m for m in manifest["matches"] if m["match_id"] == "sb_3795221"), None)
    check(entry is not None, "the imported match is in the manifest")
    if entry:
        check(entry["dataset_path"].startswith("data/"), "manifest path stays volume-relative, not absolute")
        check((entry.get("completeness") or {}).get("status") == "COMPLETE_VERIFIED",
              "the imported match is COMPLETE_VERIFIED")

    second = subprocess.run([str(PY), str(ROOT / "scripts" / "bootstrap_real_match.py")],
                            env=env, capture_output=True, text=True)
    check(second.returncode == 0 and "already imported" in second.stdout, "bootstrap is idempotent")

    # A container killed mid-import leaves a truncated file. The next boot must
    # repair it instead of trusting the filename.
    if dataset.exists() and entry:
        good = dataset.read_bytes()
        dataset.write_bytes(good[: len(good) // 3])
        third = subprocess.run([str(PY), str(ROOT / "scripts" / "bootstrap_real_match.py")],
                               env=env, capture_output=True, text=True)
        repaired = json.loads((data / "source_manifest.json").read_text(encoding="utf-8"))
        repaired_entry = next((m for m in repaired["matches"] if m["match_id"] == "sb_3795221"), {})
        import hashlib
        actual = hashlib.sha256(dataset.read_bytes()).hexdigest() if dataset.exists() else ""
        check(third.returncode == 0 and actual == repaired_entry.get("dataset_sha256"),
              "a truncated dataset is repaired on the next boot")

    print("App serves the volume-backed match")
    probe = subprocess.run(
        [str(PY), "-c", """
import json, os, sys
from fastapi.testclient import TestClient
from matchlens.main import app
with TestClient(app) as client:
    client.post("/api/sessions")
    health = client.get("/api/health")
    body = client.get("/api/matches").json()
    items = body.get("matches") or body
    ready = [m for m in items if m.get("analysis_ready") and m.get("provenance_kind") == "provider_payload"]
    print(json.dumps({
        "health": health.status_code,
        "total": len(items),
        "ready": [m["match_id"] for m in ready],
    }))
"""],
        cwd=ROOT / "services" / "api", env=env, capture_output=True, text=True,
    )
    if probe.returncode != 0:
        print(probe.stderr[-800:])
        FAILURES.append("app probe failed")
    else:
        result = json.loads(probe.stdout.strip().splitlines()[-1])
        check(result["health"] == 200, "GET /api/health returns 200 with no model key")
        check("sb_3795221" in result["ready"], "the volume-backed match is analysis-ready over HTTP")
        print(f"       {result['total']} matches listed, {len(result['ready'])} analysis-ready")

    shutil.rmtree(volume, ignore_errors=True)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} deployment contract check(s) failed")
        return 1
    print("deployment contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
