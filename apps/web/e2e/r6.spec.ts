import fs from "node:fs";
import path from "node:path";
import { expect, Page, Route, test } from "@playwright/test";
import {
  hasHorizontalOverflow,
  overflowingElements,
  openCockpit,
  readState,
  seekClock,
  selectWorkspace,
  setMatch,
  useEnglish,
  WORKSPACE_TABS,
} from "./helpers";

const SHOTS = path.join(__dirname, ".artifacts", "screenshots");

async function capture(page: Page, name: string): Promise<void> {
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });
}

test.beforeEach(async ({ page }) => {
  await useEnglish(page);
});

test.describe("R6 interaction correctness", () => {
  test("Space on a focused control activates the control, not global replay", async ({ page }) => {
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await seekClock(page, 300);
    await page.goto("/?workspace=match_center&match=syn_default&at=300");
    await expect(page.getByTestId("replay-dock")).toBeVisible();

    const before = await readState(page);
    const detailTab = page.getByRole("tab", { name: new RegExp(WORKSPACE_TABS.matchCenter) });
    await detailTab.focus();
    await page.keyboard.press("Space");
    await expect(detailTab).toHaveAttribute("aria-selected", "true");
    expect((await readState(page)).paused).toBe(before.paused);

    // A page-level Space still toggles replay when no interactive element owns focus.
    await page.locator(".r6-page-head h1").click();
    await page.keyboard.press("Space");
    await expect.poll(async () => (await readState(page)).paused, { timeout: 10_000 }).toBe(false);
  });

  test("workspace history pushes once and browser back restores the previous page", async ({ page }) => {
    await openCockpit(page);
    await selectWorkspace(page, WORKSPACE_TABS.matchCenter);
    await selectWorkspace(page, WORKSPACE_TABS.storyAgent);

    await page.goBack();
    await expect(page.getByRole("tab", { name: new RegExp(WORKSPACE_TABS.matchCenter) })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page).toHaveURL(/workspace=match_center/);

    await page.goBack();
    await expect(page.getByRole("tab", { name: new RegExp(WORKSPACE_TABS.matchHub) })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  test("a zero clock stays zero and never asks for a future attribution window", async ({ page }) => {
    let futureWindow = false;
    page.on("request", (request) => {
      if (request.url().includes("/attribution?") && request.url().includes("window_end=600")) {
        futureWindow = true;
      }
    });
    await page.goto("/?workspace=story_agent&match=syn_default&at=0");
    await expect.poll(async () => (await readState(page)).at, { timeout: 10_000 }).toBe(0);
    await page.waitForTimeout(800);
    expect(futureWindow).toBe(false);
    await expect(page.getByTestId("header-current-match")).toContainText("00:00");
  });

  test("dragging the replay slider sends one seek, not one per pixel", async ({ page }) => {
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await seekClock(page, 300);
    await page.goto("/?workspace=match_center&match=syn_default&at=300");
    await expect(page.getByTestId("replay-slider")).toBeVisible();

    let seeks = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().endsWith("/api/control")) {
        if ((request.postData() || "").includes('"seek"')) seeks += 1;
      }
    });

    await page.getByTestId("replay-slider").evaluate((element) => {
      const input = element as HTMLInputElement;
      input.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
      for (const value of [320, 360, 420, 480]) {
        input.value = String(value);
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
      // A touch drag ends with both pointer and touch events; it must still seek once.
      input.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));
      input.dispatchEvent(new Event("touchend", { bubbles: true }));
    });

    await expect.poll(async () => (await readState(page)).at, { timeout: 10_000 }).toBe(480);
    expect(seeks).toBe(1);
  });

  test("full-time recap appears in Match Detail only", async ({ page }) => {
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await seekClock(page, 720);

    await page.goto("/?workspace=tactical_lab&match=syn_default&at=720");
    await expect(page.locator(".fulltime-recap-section")).toHaveCount(0);

    await page.goto("/?workspace=match_center&match=syn_default&at=720");
    await expect(page.locator(".fulltime-recap-section")).toBeVisible();
  });


  test("a late analysis response never repaints a newly selected match", async ({ page }) => {
    await openCockpit(page);
    await setMatch(page, "sb_3795221");
    await seekClock(page, 1800);
    await page.goto("/?workspace=match_center&match=sb_3795221&at=1800");
    await expect(page.getByTestId("match-detail-page")).toContainText("England");

    let delayed = false;
    await page.route("**/api/exploration/oaai?*", async (route) => {
      delayed = true;
      await new Promise((resolve) => setTimeout(resolve, 1200));
      await route.continue();
    });
    await page.getByRole("button", { name: /Bilateral/i }).click();
    await setMatch(page, "syn_default");
    await seekClock(page, 300);
    await page.goto("/?workspace=match_center&match=syn_default&at=300");
    await expect(page.getByTestId("match-detail-page")).toContainText("Harbor FC");
    await page.waitForTimeout(1800);
    expect(delayed).toBe(true);
    expect((await readState(page)).match_id).toBe("syn_default");
    await expect(page.getByTestId("match-detail-page")).not.toContainText("England");
  });


  test("the contextual evidence drawer still opens after being removed from layout", async ({ page }) => {
    await openCockpit(page);
    await page.getByRole("button", { name: "Open evidence inspector" }).click();
    const drawer = page.locator(".inspector-drawer.open");
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText(/Tactical Inspector|战术审计/i);
    await drawer.getByRole("button", { name: /close/i }).click();
    await expect(page.locator(".inspector-drawer.open")).toHaveCount(0);
  });

  test("OAAI change points report direction instead of assuming a rise", async ({ page }) => {
    const mockPoints = [
      {
        change_point_id: "CP-NEG", at: 300, oaai_amplitude: -1.8, leading_team: "N",
        change_type: "away_surge", claim_level: 2, window_seconds: 120, disclaimer: "mock", top_contributors: [],
      },
      {
        change_point_id: "CP-POS", at: 360, oaai_amplitude: 0.9, leading_team: "H",
        change_type: "home_surge", claim_level: 2, window_seconds: 120, disclaimer: "mock", top_contributors: [],
      },
      {
        change_point_id: "CP-NEUTRAL", at: 420, oaai_amplitude: 0, leading_team: "neutral",
        change_type: "lead_turn", claim_level: 2, window_seconds: 120, disclaimer: "mock", top_contributors: [],
      },
    ];
    const patchState = async (route: Route) => {
      const response = await route.fetch();
      const json = await response.json();
      json.oaai = { ...(json.oaai || {}), change_points: mockPoints };
      await route.fulfill({
        status: response.status(),
        headers: { ...response.headers(), "content-type": "application/json" },
        body: JSON.stringify(json),
      });
    };
    // The product reads its snapshot through the SSE stream with a polling
    // fallback. Patching both keeps the test's change-point fixture stable.
    await page.route("**/api/stream", (route) => route.abort());
    await page.route("**/api/state", patchState);

    await openCockpit(page);
    await setMatch(page, "syn_default");
    await page.goto("/?workspace=match_center&match=syn_default&at=720");

    const primary = page.getByTestId("match-insight-primary");
    await expect(primary).toBeVisible();
    await expect(primary).toHaveAttribute("data-direction", "N");
    await expect(page.getByTestId("match-insight-title")).toContainText(/Northbridge United activity peaked/i);
    await expect(page.getByTestId("match-insight-title")).not.toContainText(/rose/i);

    const neutralRow = page.locator(".r6-insight-neutral-row").filter({ hasText: "07:00" });
    await expect(neutralRow.getByRole("button", { name: "Harbor FC" })).toBeVisible();
    await expect(neutralRow.getByRole("button", { name: "Northbridge United" })).toBeVisible();
  });

  test("model copy distinguishes availability, the current result and a recorded run", async ({ page }) => {
    await page.route("**/api/agent-runs?*", (route) =>
      route.fulfill({
        json: {
          runs: [
            {
              run_id: "arun-visible", trigger: "investigation", match_id: "syn_default",
              snapshot_id: "snap-visible", investigation_id: null, dataset_revision: null, epoch: 0,
              model: "deepseek-flash", prompt_version: "test", state: "GATED", state_history: [],
              audit: [], requests: 4, accepted_count: 1, rejected_count: 0, origin: "live_model",
              error: null, created_at: 1, updated_at: 2,
            },
          ],
          scope: "session_owner",
        },
      }),
    );
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await page.goto("/?workspace=match_center&match=syn_default&at=720");

    const fetched = await page.evaluate(async () => {
      const response = await fetch("/api/agent-runs?limit=50");
      return { status: response.status, body: await response.json() };
    });
    expect(fetched.status).toBe(200);
    expect(fetched.body.runs).toHaveLength(1);

    await expect(page.getByTestId("match-model-fact")).toContainText(/Latest/i);
    const status = page.getByTestId("match-model-status");
    await expect(status).toHaveAttribute("data-recent-run-state", "GATED");
    await expect(page.getByTestId("match-model-recent")).toContainText("GATED");
    await expect(page.getByTestId("match-model-recent")).toContainText("live model");
    await expect(page.getByTestId("match-model-current")).toContainText(/No AI result/i);
  });

  test("the phone header exposes language and evidence through one tools menu", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openCockpit(page);
    await page.goto("/?workspace=match_center&match=syn_default&at=300");
    const header = page.locator(".r6-topbar");

    await expect(header.getByRole("button", { name: "Open evidence inspector", exact: true })).toBeHidden();
    await expect(header.getByTestId("mobile-tools-trigger")).toBeVisible();

    await header.getByTestId("mobile-tools-trigger").click();
    await expect(header.getByTestId("mobile-tools-menu")).toBeVisible();
    await header.getByRole("button", { name: "Evidence inspector", exact: true }).click();
    await expect(page.locator(".inspector-drawer.open")).toBeVisible();
    await expect(header.getByTestId("mobile-tools-menu")).toBeHidden();
    await page.locator(".inspector-drawer.open").getByRole("button", { name: /close/i }).click();
    await expect(page.locator(".inspector-drawer.open")).toHaveCount(0);

    await header.getByTestId("mobile-tools-trigger").click();
    await header.getByRole("button", { name: "切换为中文", exact: true }).click();
    await expect(page.getByRole("tab", { name: "比赛详情" })).toBeVisible();
    expect(await hasHorizontalOverflow(page), await overflowingElements(page)).toBe(false);
  });

  test("Match Detail sections on a phone hide density and support arrow-key tabs", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await page.goto("/?workspace=match_center&match=syn_default&at=720");

    const tabs = page.getByRole("tablist", { name: "Match detail sections" });
    await expect(tabs).toBeVisible();
    await expect(tabs.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("match-insight-primary")).toBeVisible();
    await expect(page.getByText("Recent key events")).toBeVisible();
    await expect(page.locator("#r6-panel-tactical")).toBeHidden();
    await expect(page.locator("#r6-panel-events")).toBeHidden();

    await tabs.getByRole("tab", { name: "Overview" }).focus();
    await page.keyboard.press("ArrowRight");
    await expect(tabs.getByRole("tab", { name: "Tactical" })).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("#r6-panel-tactical")).toBeVisible();
    await expect(page.getByTestId("match-insight-primary")).toBeHidden();
    expect(await hasHorizontalOverflow(page), `tactical overflow ${await overflowingElements(page)}`).toBe(false);

    await page.keyboard.press("ArrowRight");
    await expect(tabs.getByRole("tab", { name: "Events" })).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("#r6-panel-events")).toBeVisible();

    await page.keyboard.press("ArrowRight");
    await expect(tabs.getByRole("tab", { name: "More" })).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("#r6-panel-more .fulltime-recap-section")).toBeVisible();
    expect(await hasHorizontalOverflow(page), `more overflow ${await overflowingElements(page)}`).toBe(false);
  });

  test("the tactical explorer splits its dense panels into phone tasks", async ({ page }) => {
    await page.setViewportSize({ width: 412, height: 915 });
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await page.goto("/?workspace=tactical_lab&match=syn_default&at=720");

    const tabs = page.getByRole("tablist", { name: "Tactical explorer sections" });
    await expect(tabs.getByRole("tab", { name: "Pitch" })).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("#r6-panel-pitch")).toBeVisible();
    await expect(page.locator("#r6-panel-metrics")).toBeHidden();

    await tabs.getByRole("tab", { name: "Sequences" }).click();
    await expect(page.locator("#r6-panel-sequences")).toBeVisible();
    await expect(page.locator("#r6-panel-pitch")).toBeHidden();

    await tabs.getByRole("tab", { name: "Metrics" }).click();
    await expect(page.locator("#r6-panel-metrics").first()).toBeVisible();
    expect(await hasHorizontalOverflow(page), await overflowingElements(page)).toBe(false);
  });

  test("Match Hub recommends analysis-ready matches and collapses advanced filters", async ({ page }) => {
    await openCockpit(page);
    await page.goto("/?workspace=match_hub");

    await expect(page.getByTestId("match-hub-recommended")).toBeVisible();
    await expect(page.getByTestId("match-recommended").first()).toBeVisible();
    await expect(page.getByTestId("match-card").first()).toHaveAttribute("data-analysis-ready", /true|false/);
    await expect(page.getByTestId("match-hub-team-filter")).toBeHidden();

    await page.getByTestId("match-hub-advanced").locator("summary").click();
    await expect(page.getByTestId("match-hub-team-filter")).toBeVisible();
    await page.getByTestId("match-hub-team-filter").selectOption("England");
    await expect(page.getByTestId("match-hub-count")).toContainText("of");
  });

  test("cancelling an investigation registers a request key with the server", async ({ page }) => {
    await page.route("**/api/investigate", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 900));
      await route.continue();
    });
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await page.goto("/?workspace=story_agent&match=syn_default&at=300");

    await page.getByLabel("What do you want to understand?").fill("Which recorded actions shaped this spell?");
    const investigate = page.waitForRequest((request) => request.url().endsWith("/api/investigate"));
    await page.getByRole("button", { name: "Analyse" }).click();
    const request = await investigate;
    const body = JSON.parse(request.postData() || "{}");
    expect(body.request_key).toMatch(/^[A-Za-z0-9_-]{8,64}$/);

    const cancel = page.waitForResponse((response) =>
      response.url().includes("/api/investigation-requests/") && response.url().endsWith("/cancel"),
    );
    await page.getByRole("button", { name: "Cancel" }).click();
    const cancelResponse = await cancel;
    const cancelPayload = await cancelResponse.json();
    expect(cancelPayload).toMatchObject({
      state: "cancel_requested",
      request_key: body.request_key,
    });

    // The browser request was deliberately held before the server registered it.
    // The cancel is remembered, so the delayed investigation must return as a
    // server-confirmed cancellation rather than producing a result.
    await expect(page.getByTestId("investigation-cancel-status")).toHaveAttribute(
      "data-cancel-state",
      "confirmed",
      { timeout: 30_000 },
    );
    await expect(page.getByTestId("investigation-plan")).toHaveCount(0);
  });


  test("R6 screenshots at 1440, 1024, 768, 390 and 360 without horizontal overflow", async ({ page }) => {
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await seekClock(page, 720);
    await page.goto("/?workspace=match_center&match=syn_default&at=720");
    await expect(page.getByTestId("match-insight-primary")).toBeVisible();

    for (const width of [1440, 1024, 768]) {
      await page.setViewportSize({ width, height: 960 });
      await page.waitForTimeout(150);
      expect(await hasHorizontalOverflow(page), `overflow at ${width}px`).toBe(false);
      await capture(page, `match-detail-${width}`);
    }

    for (const width of [390, 360]) {
      await page.setViewportSize({ width, height: 844 });
      const tabs = page.getByRole("tablist", { name: "Match detail sections" });
      await expect(tabs).toBeVisible();
      for (const tab of ["Overview", "Tactical", "Events", "More"]) {
        await tabs.getByRole("tab", { name: tab }).click();
        await expect(tabs.getByRole("tab", { name: tab })).toHaveAttribute("aria-selected", "true");
        await page.waitForTimeout(100);
        expect(
          await hasHorizontalOverflow(page),
          `match detail ${tab} overflow at ${width}px: ${await overflowingElements(page)}`,
        ).toBe(false);
        await capture(page, `match-detail-${width}-${tab.toLowerCase()}`);
      }
    }

    await page.setViewportSize({ width: 412, height: 915 });
    await page.goto("/?workspace=tactical_lab&match=syn_default&at=720");
    await expect(page.getByTestId("tactical-explorer-page")).toBeVisible();
    const tacticalTabs = page.getByRole("tablist", { name: "Tactical explorer sections" });
    for (const tab of ["Pitch", "Sequences", "Metrics"]) {
      await tacticalTabs.getByRole("tab", { name: tab }).click();
      expect(
        await hasHorizontalOverflow(page),
        `tactical ${tab} overflow at 412px: ${await overflowingElements(page)}`,
      ).toBe(false);
      await capture(page, `tactical-explorer-412-${tab.toLowerCase()}`);
    }

    await page.goto("/?workspace=match_center&match=syn_default&at=720");
    await page.getByTestId("mobile-tools-trigger").click();
    expect(await hasHorizontalOverflow(page), await overflowingElements(page)).toBe(false);
    await capture(page, "mobile-tools-menu-412");
    await page.keyboard.press("Escape");

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/?workspace=story_agent&match=syn_default&at=720");
    await expect(page.getByTestId("investigation-advanced")).toBeVisible();
    expect(await hasHorizontalOverflow(page)).toBe(false);
    await capture(page, "intelligence-studio-390");

    await page.goto("/?workspace=match_hub&match=syn_default");
    await expect(page.getByRole("heading", { name: "Football intelligence you can challenge." })).toBeVisible();
    expect(await hasHorizontalOverflow(page), await overflowingElements(page)).toBe(false);
    await capture(page, "match-hub-390");
    await page.getByTestId("match-hub-advanced").locator("summary").click();
    expect(await hasHorizontalOverflow(page), await overflowingElements(page)).toBe(false);
    await capture(page, "match-hub-390-filters");
  });
});
