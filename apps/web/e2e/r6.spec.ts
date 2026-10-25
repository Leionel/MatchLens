import fs from "node:fs";
import path from "node:path";
import { expect, Page, test } from "@playwright/test";
import {
  hasHorizontalOverflow,
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
      input.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));
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

  test("R6 screenshots at 1440, 1024, 768, 390 and 360 without horizontal overflow", async ({ page }) => {
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await seekClock(page, 720);
    await page.goto("/?workspace=match_center&match=syn_default&at=720");
    await expect(page.getByTestId("match-insight-primary")).toBeVisible();

    for (const width of [1440, 1024, 768, 390, 360]) {
      await page.setViewportSize({ width, height: width <= 390 ? 844 : 960 });
      await page.waitForTimeout(150);
      expect(await hasHorizontalOverflow(page), `overflow at ${width}px`).toBe(false);
      await capture(page, `match-detail-${width}`);
    }

    await page.setViewportSize({ width: 412, height: 915 });
    await page.goto("/?workspace=tactical_lab&match=syn_default&at=720");
    await expect(page.getByTestId("tactical-explorer-page")).toBeVisible();
    expect(await hasHorizontalOverflow(page), "overflow at 412px tactical").toBe(false);
    await capture(page, "tactical-explorer-412");

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/?workspace=story_agent&match=syn_default&at=720");
    await expect(page.getByTestId("investigation-advanced")).toBeVisible();
    expect(await hasHorizontalOverflow(page)).toBe(false);
    await capture(page, "intelligence-studio-390");

    await page.goto("/?workspace=match_hub&match=syn_default");
    await expect(page.getByRole("heading", { name: "Start with a real match" })).toBeVisible();
    expect(await hasHorizontalOverflow(page)).toBe(false);
    await capture(page, "match-hub-390");
  });
});
