import { expect, Page, test } from "@playwright/test";
import { openCockpit, readState, seekClock, setMatch, useEnglish } from "./helpers";

/**
 * The three claims the judge round added, asserted on the surfaces a judge
 * actually touches:
 *
 * 1. the plan says who produced it, and never stages two agents when only the
 *    deterministic planner ran;
 * 2. an approved claim can become a broadcast lower-third that carries its own
 *    match time, evidence refs and provenance;
 * 3. Fan / Coach / Media read the same fact with different emphasis.
 */
const AT = 420;

async function runDeterministicInvestigation(page: Page): Promise<void> {
  await page.goto(`/?workspace=story_agent&match=syn_default&at=${AT}`);
  await expect
    .poll(async () => Number((await readState(page)).snapshot_as_of ?? -1), { timeout: 30_000 })
    .toBe(AT);
  await page
    .getByLabel("What do you want to understand?")
    .fill("Why did attacking activity change around this moment?");
  await page.getByRole("button", { name: "Analyse" }).click();
  await expect(page.getByTestId("investigation-plan")).toBeVisible({ timeout: 90_000 });
}

test.beforeEach(async ({ page }) => {
  await useEnglish(page);
  await openCockpit(page);
  await setMatch(page, "syn_default");
  await seekClock(page, AT);
});

test.afterEach(async ({ page }) => {
  // The suite shares one session; leave the default fixture loaded.
  await setMatch(page, "syn_default");
});

test("a deterministic plan states that no model ran", async ({ page }) => {
  await runDeterministicInvestigation(page);

  const collaboration = page.getByTestId("agent-collaboration");
  await expect(collaboration).toBeVisible();
  await expect(collaboration).toHaveAttribute("data-mode", "deterministic_planner");

  // The honest sentence must be on screen, not buried in a disclosure.
  await expect(page.getByTestId("collab-deterministic")).toContainText(/no model was called|no model took part/i);
  // And there must be no fabricated analyst/verifier conversation.
  await expect(page.getByTestId("collab-analyst")).toHaveCount(0);
  await expect(page.getByTestId("collab-verifier")).toHaveCount(0);
});

test("an approved claim produces a lower-third with its time, refs and provenance", async ({ page }) => {
  await runDeterministicInvestigation(page);

  const verdict = page.getByTestId("investigation-conclusion");
  await expect(verdict).toBeVisible();

  const overlay = page.getByTestId("broadcast-overlay");
  // Only an approved claim may become a lower-third.
  const status = await page.getByTestId("investigation-verdict").getAttribute("data-verdict");
  if (status !== "approved") {
    await expect(overlay).toHaveCount(0);
    return;
  }

  await expect(overlay).toBeVisible();
  await expect(overlay).toHaveAttribute("data-provenance", "synthetic");
  await expect(overlay).toContainText("SYNTHETIC SIMULATED REPLAY");
  await expect(overlay).toContainText("PREVIEW · NOT BROADCAST OUTPUT");

  // The overlay must carry this plan's own match time.
  const plan = await readState(page);
  const at = Number(plan.snapshot_as_of ?? AT);
  const mm = Math.floor(at / 60).toString().padStart(2, "0");
  await expect(overlay).toContainText(new RegExp(`MATCH TIME ${mm}:`));

  // And at least one evidence reference, not just prose.
  await expect(page.getByTestId("broadcast-overlay-refs")).toBeVisible();
  await expect(page.getByTestId("broadcast-overlay-refs").locator("code").first()).toBeVisible();
});

test("Fan, Coach and Media change the emphasis, never the fact", async ({ page }) => {
  await page.goto(`/?workspace=match_center&match=syn_default&at=${AT}`);
  const card = page.getByTestId("match-insight-primary");
  await expect(card).toBeVisible();

  const title = await page.getByTestId("match-insight-title").innerText();
  const selector = page.locator(".r6-perspective select");

  await selector.selectOption("fan");
  await expect(card).toHaveAttribute("data-perspective", "fan");
  const fan = await page.getByTestId("match-insight-why").innerText();

  await selector.selectOption("coach");
  await expect(card).toHaveAttribute("data-perspective", "coach");
  const coach = await page.getByTestId("match-insight-why").innerText();

  await selector.selectOption("media");
  await expect(card).toHaveAttribute("data-perspective", "media");
  const media = await page.getByTestId("match-insight-why").innerText();

  // Three genuinely different readings...
  expect(new Set([fan, coach, media]).size).toBe(3);
  expect(coach).toMatch(/shots/i);
  expect(media).toMatch(/lower-third/i);

  // ...of the same unchanged fact.
  await expect(page.getByTestId("match-insight-title")).toHaveText(title);
  await expect(page.getByTestId("match-insight-primary")).toHaveAttribute("data-direction", /H|N|neutral/);
});
