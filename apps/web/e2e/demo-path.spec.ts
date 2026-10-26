import fs from "node:fs";
import path from "node:path";
import { expect, Page, test } from "@playwright/test";
import { openCockpit, readState, seekClock, setMatch, useEnglish, WORKSPACE_TABS } from "./helpers";

/**
 * The representative demo path, asserted end to end on the payload CI installs:
 * open a real match, read the score and the two measurement scopes, notice the
 * activity change, ask about it, read the conclusion and its evidence, and
 * return to the moment it describes.
 *
 * It is also the capture run for the competition screenshots, so the pictures
 * in the submission are the ones this test produced.
 */
const REAL_MATCH = "sb_3795221";
const DEMO_AT = 4200;
const SHOTS = path.join(__dirname, ".artifacts", "screenshots");

async function shot(page: Page, name: string, full = false): Promise<void> {
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: full });
}

test.beforeEach(async ({ page }) => {
  await useEnglish(page);
});

test("a real match can be read, questioned and returned from without leaving the journey", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openCockpit(page);
  await setMatch(page, REAL_MATCH);
  await seekClock(page, DEMO_AT);

  // 1. The hub leads with real payloads.
  await page.goto("/?workspace=match_hub");
  const recommended = page.getByTestId("match-recommended").first();
  await expect(recommended).toHaveAttribute("data-provenance", "provider_payload");
  await expect(recommended).toContainText("Real data");
  await shot(page, "demo-1-hub");

  // 2. Match Detail separates the match total from the live window.
  await page.goto(`/?workspace=match_center&match=${REAL_MATCH}&at=${DEMO_AT}`);
  await expect(page.getByTestId("match-totals")).toContainText("Whole match");
  await expect(page.getByTestId("match-window-strip")).toContainText("Last 3 min");
  await expect(page.getByTestId("match-insight-limit")).toBeVisible();
  await shot(page, "demo-2-detail");

  // 3. The same page on a phone.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByTestId("match-totals")).toBeVisible();
  await shot(page, "demo-3-detail-phone");
  await page.setViewportSize({ width: 1440, height: 900 });

  // 4. Ask about the change the chart is showing.
  await page.goto(`/?workspace=story_agent&match=${REAL_MATCH}&at=${DEMO_AT}`);
  await expect
    .poll(async () => Number((await readState(page)).snapshot_as_of ?? -1), { timeout: 30_000 })
    .toBe(DEMO_AT);
  await page
    .getByLabel("What do you want to understand?")
    .fill("Why did attacking activity change around this moment?");
  await page.getByRole("button", { name: "Analyse" }).click();

  const plan = page.getByTestId("investigation-plan");
  await expect(plan).toBeVisible({ timeout: 90_000 });
  await expect(page.getByTestId("investigation-conclusion")).toBeVisible();
  await expect(page.getByTestId("investigation-limits")).toBeVisible();
  await shot(page, "demo-4-investigation");

  // 5. Back to the moment the answer is about.
  await page.getByTestId("investigation-return").click();
  await expect(page.getByRole("tab", { name: new RegExp(WORKSPACE_TABS.matchCenter) })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByTestId("match-totals")).toBeVisible();

  // The suite shares one server session, so leaving the provider match loaded
  // would disable the library's "enter" action for the specs that follow and
  // silently change what they are testing. Put the default fixture back.
  await setMatch(page, "syn_default");
});
