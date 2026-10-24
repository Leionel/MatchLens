import fs from "node:fs";
import path from "node:path";
import { request as playwrightRequest } from "@playwright/test";
import { BASE_URL } from "./env";

const STATE_FILE = path.join(__dirname, ".auth.json");

/** Bootstrap exactly one server session and reuse it for every spec.
 *
 * The backend caps concurrent sessions and rate-limits session creation per
 * address, so a fresh session per test would eventually be rejected. Sharing
 * one cookie also mirrors how a single analyst uses the cockpit.
 */
export default async function globalSetup(): Promise<void> {
  const context = await playwrightRequest.newContext({ baseURL: BASE_URL });
  const response = await context.post("/api/sessions");
  if (!response.ok()) {
    throw new Error(`session bootstrap failed with status ${response.status()}`);
  }
  const state = await context.storageState();
  fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
  fs.writeFileSync(STATE_FILE, JSON.stringify(state), "utf8");
  await context.dispose();
}
