import path from "node:path";

/**
 * Repository root, resolved from this file so the config and the specs agree.
 * This module lives in `<repo>/apps/web/e2e`, so the root is three levels up.
 */
export const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");

export const API_DIR = path.join(REPO_ROOT, "services", "api");

export const VENV_PYTHON =
  process.platform === "win32"
    ? path.join(API_DIR, ".venv", "Scripts", "python.exe")
    : path.join(API_DIR, ".venv", "bin", "python");

/**
 * The CI job installs the backend with uv and has no local virtualenv, so the
 * server command can be overridden. Everything else about the server contract
 * (single worker, loopback, editorial token) stays identical.
 */
export const DEFAULT_SERVER_COMMAND = `"${VENV_PYTHON}" -m uvicorn matchlens.main:app --host 127.0.0.1 --port 8000 --workers 1`;

export const SERVER_COMMAND = process.env.MATCHLENS_E2E_SERVER_CMD || DEFAULT_SERVER_COMMAND;

/** Editorial token of the throwaway server the suite drives. */
export const PRODUCER_TOKEN = process.env.MATCHLENS_E2E_PRODUCER_TOKEN || "e2e-producer-token";

export const BASE_URL = process.env.MATCHLENS_E2E_BASE_URL || "http://127.0.0.1:8000";

/**
 * Identifier of this suite run. The claim registry is persistent state, so two
 * runs of the same suite must not share a runtime directory: a withdrawal from
 * an earlier run would otherwise make a later run observe a different claim
 * lifecycle than the test expects.
 */
export const RUN_ID = process.env.MATCHLENS_E2E_RUN_ID || `run-${Date.now().toString(36)}`;

// Exported to the environment so the web server started by Playwright and the
// global setup in this process always resolve to the same directory.
process.env.MATCHLENS_E2E_RUN_ID = RUN_ID;

/** Runtime directory of the throwaway server, so a local run never touches real state. */
export const RUNTIME_DIR = path.join(REPO_ROOT, ".runtime", "e2e", RUN_ID);
