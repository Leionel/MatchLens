import path from "node:path";
import { defineConfig, devices } from "@playwright/test";
import { API_DIR, BASE_URL, PRODUCER_TOKEN, RUNTIME_DIR, SERVER_COMMAND } from "./e2e/env";

export const PRODUCER_TOKEN_VALUE = PRODUCER_TOKEN;
export const STORAGE_STATE = path.join(__dirname, "e2e", ".auth.json");

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e/.artifacts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  globalSetup: path.join(__dirname, "e2e", "global-setup.ts"),
  // The HTML report must live outside the test-results folder: Playwright
  // clears its output directory, which would delete the traces and screenshots
  // that the CI artifact step uploads after a failure.
  reporter: process.env.CI
    ? [["github"], ["html", { outputFolder: "e2e/.playwright-report", open: "never" }]]
    : [["list"]],
  use: {
    baseURL: BASE_URL,
    storageState: STORAGE_STATE,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
      testIgnore: /responsive\.spec\.ts/,
    },
    {
      name: "responsive",
      use: { ...devices["Pixel 7"] },
      testMatch: /responsive\.spec\.ts/,
    },
    {
      // The iPad descriptor defaults to WebKit, which is not installed in CI.
      name: "tablet",
      use: { ...devices["iPad Mini"], defaultBrowserType: "chromium" },
      testMatch: /responsive\.spec\.ts/,
    },
  ],
  webServer: {
    command: SERVER_COMMAND,
    cwd: API_DIR,
    url: `${BASE_URL}/api/health`,
    // The suite owns its server: the run-scoped runtime directory below only
    // reaches a server that this process starts.
    reuseExistingServer: false,
    timeout: 240_000,
    stdout: "pipe",
    stderr: "pipe",
    env: {
      MATCHLENS_RUNTIME_DIR: RUNTIME_DIR,
      MATCHLENS_PRODUCER_TOKEN: PRODUCER_TOKEN,
      MATCHLENS_ALLOW_LOCAL_PRODUCER: "0",
      // The browser suite must be structurally unable to spend model budget:
      // the throwaway server runs with no provider key, so agent-mode paths
      // exercise the honest deterministic fallback only.
      DEEPSEEK_API_KEY: "",
    },
  },
});
