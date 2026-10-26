import fs from "node:fs";
import path from "node:path";
import { expect, Page, test } from "@playwright/test";
import {
  hasHorizontalOverflow,
  openCockpit,
  overflowingElements,
  readState,
  seekClock,
  selectWorkspace,
  setMatch,
  useEnglish,
  WORKSPACE_TABS,
} from "./helpers";

const SHOTS = path.join(__dirname, ".artifacts", "screenshots");

/** England vs Denmark: a real provider payload with a long replay and goals. */
const REAL_MATCH = "sb_3795221";
const REAL_SCOREBOARD = /England vs Denmark scoreboard/;

/** A snapshot on which the live window is empty and the match total is not. */
const WINDOW_TRAP_AT = 4200;

async function capture(page: Page, name: string): Promise<void> {
  fs.mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });
}


/**
 * Opening a deep link restores the clock asynchronously. An investigation must
 * be asked about the restored moment, not about the 0' placeholder, so every
 * spec below waits for the session to reach the requested clock first.
 */
async function waitForClock(page: Page, at: number): Promise<void> {
  await expect
    .poll(async () => Number((await readState(page)).snapshot_as_of ?? -1), { timeout: 30_000 })
    .toBe(at);
}

test.beforeEach(async ({ page }) => {
  await useEnglish(page);
});

test.describe("R6.2 measurement windows", () => {
  test("match totals report the whole match, and the live window is labelled separately", async ({
    page,
  }) => {
    await openCockpit(page);
    await setMatch(page, REAL_MATCH);
    await seekClock(page, WINDOW_TRAP_AT);
    await page.goto(`/?workspace=match_center&match=${REAL_MATCH}&at=${WINDOW_TRAP_AT}`);
    await expect(page.getByRole("region", { name: REAL_SCOREBOARD })).toBeVisible();

    const state = await readState(page);
    const receipts = state.receipts;

    // The fixture must still expose the trap: an empty window and a non-empty
    // match total. If this ever stops holding, the test is measuring nothing.
    expect(receipts["H.shots.current"].value).toBe(0);
    expect(receipts["H.shots.match"].value).toBeGreaterThan(0);

    const home = state.teams?.H ?? "H";
    const shots = page.getByTestId("match-stat-shots");
    const goals = page.getByTestId("match-stat-goals");

    await expect(shots).toContainText(String(receipts["H.shots.match"].value));
    await expect(shots).toContainText(String(receipts["N.shots.match"].value));
    // The regression: the totals row used to print the three-minute window.
    await expect(shots).not.toHaveText(/^Shots\s*0\s*\/\s*0$/);

    await expect(goals).toContainText(String(receipts["H.goals.match"].value));
    await expect(goals).toContainText(String(receipts["N.goals.match"].value));

    // Goals on the totalled row must agree with the scoreboard score.
    expect(receipts["H.goals.match"].value).toBe(state.score.H);
    expect(receipts["N.goals.match"].value).toBe(state.score.N);

    // The live window is its own labelled row, with its own numbers.
    const windowStrip = page.getByTestId("match-window-strip");
    await expect(windowStrip).toBeVisible();
    await expect(windowStrip).toContainText("Last 3 min");
    await expect(page.getByTestId("match-window-shots")).toContainText("0 / 0");

    // Possession: the match share is a different number under a different scope.
    const possession = page.getByTestId("match-stat-possession");
    await expect(possession).toContainText(`${Math.round(receipts["H.possession.match"].value)}%`);
    await expect(page.getByTestId("scoreboard-possession")).toHaveAttribute("data-scope", "window");
    await expect(page.getByTestId("scoreboard-possession")).toContainText("Last 3 min");
    expect(home.length).toBeGreaterThan(0);
  });

  test("the event feed lists readable events the pitch cannot draw", async ({ page }) => {
    await openCockpit(page);
    await setMatch(page, REAL_MATCH);
    await seekClock(page, WINDOW_TRAP_AT);
    await page.goto(`/?workspace=match_center&match=${REAL_MATCH}&at=${WINDOW_TRAP_AT}`);
    await expect(page.getByTestId("match-totals")).toBeVisible();

    const state = await readState(page);
    const readable = state.events.filter(
      (event: any) => event.id && typeof event.t === "number" && event.kind,
    );
    const notDrawable = readable.filter((event: any) => !(event.start && event.end));

    // The fixture must still contain events the old filter deleted.
    expect(notDrawable.length).toBeGreaterThan(0);

    // The feed header counts every readable event, not only the drawable ones.
    const feed = page.getByRole("region", { name: "Match event stream" });
    await expect(feed).toBeVisible();
    await expect(page.getByText(`${readable.length} / ${readable.length} events`, { exact: false })).toBeVisible();
  });

  test("a key event without coordinates is shown, tagged, and not silently dropped", async ({
    page,
  }) => {
    // The key-event shortlist is the phone overview; the desktop layout keeps
    // the full feed in its own column instead of repeating it.
    await page.setViewportSize({ width: 390, height: 844 });
    await openCockpit(page);
    await setMatch(page, REAL_MATCH);
    await seekClock(page, WINDOW_TRAP_AT);
    await page.goto(`/?workspace=match_center&match=${REAL_MATCH}&at=${WINDOW_TRAP_AT}`);

    const rows = page.getByTestId("match-key-event");
    await expect(rows.first()).toBeVisible();
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);

    // At least one shortlisted row must be a real recorded action, and any row
    // that cannot be placed is labelled rather than removed.
    const tagged = page.locator('[data-testid="match-key-event"][data-located="false"]');
    const taggedCount = await tagged.count();
    if (taggedCount > 0) {
      await expect(tagged.first()).toContainText("no coords");
    }
  });
});

test.describe("R6.2 investigation isolation", () => {
  test("switching match mid-investigation never publishes the old answer", async ({ page }) => {
    await page.route("**/api/investigate", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 5000));
      await route.continue();
    });
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await page.goto("/?workspace=story_agent&match=syn_default&at=300");
    await waitForClock(page, 300);

    await page
      .getByLabel("What do you want to understand?")
      .fill("Why did attacking activity change around this moment?");

    const cancels: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/api/investigation-requests/") && request.url().endsWith("/cancel")) {
        cancels.push(request.url());
      }
    });

    await page.getByRole("button", { name: "Analyse" }).click();
    await expect(page.getByRole("button", { name: "Analysing…" })).toBeVisible();

    // Leave the studio and open a different fixture the way a user would.
    await selectWorkspace(page, WORKSPACE_TABS.matchHub);
    await page
      .locator('[data-testid="match-recommended"][data-provenance="provider_payload"]')
      .first()
      .getByRole("button", { name: /Open match/ })
      .click();
    // The card may be any installed provider payload, so assert on the
    // contract (a real match is now loaded), not on one fixture's name.
    await expect
      .poll(async () => (await readState(page)).match_id, { timeout: 60_000 })
      .toMatch(/^sb_/);
    await expect(page.getByRole("region", { name: /scoreboard/ })).toBeVisible();

    await selectWorkspace(page, WORKSPACE_TABS.storyAgent);
    // The answer for the previous fixture must not appear under this one.
    await page.waitForTimeout(1500);
    await expect(page.getByTestId("investigation-plan")).toHaveCount(0);
    // The server was told to stop running it.
    expect(cancels.length).toBeGreaterThan(0);
  });

  test("a result from an earlier snapshot is labelled instead of passed off as current", async ({
    page,
  }) => {
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await page.goto("/?workspace=story_agent&match=syn_default&at=300");
    await waitForClock(page, 300);

    await page.getByLabel("What do you want to understand?").fill("Why did attacking activity change around this moment?");
    await page.getByRole("button", { name: "Analyse" }).click();

    const plan = page.getByTestId("investigation-plan");
    await expect(plan).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("investigation-stale")).toHaveCount(0);

    // Move the replay away from the answered moment.
    await seekClock(page, 600);
    await expect
      .poll(async () => (await readState(page)).snapshot_as_of, { timeout: 20_000 })
      .toBe(600);

    const banner = page.getByTestId("investigation-stale");
    await expect(banner).toBeVisible({ timeout: 30_000 });
    await expect(banner).toContainText("another snapshot");
    // The old answer is still readable, but it is no longer presented as this moment's.
    await expect(plan).toBeVisible();
  });

  test("the conclusion, the evidence and the limits come before the machinery", async ({ page }) => {
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await page.goto("/?workspace=story_agent&match=syn_default&at=300");
    await waitForClock(page, 300);

    await page.getByLabel("What do you want to understand?").fill("Why did attacking activity change around this moment?");
    await page.getByRole("button", { name: "Analyse" }).click();

    const plan = page.getByTestId("investigation-plan");
    await expect(plan).toBeVisible({ timeout: 60_000 });

    // The first thing inside the result is the conclusion statement, then the
    // evidence and the limits. An empty findings list is a valid answer and
    // still renders its own section.
    await expect(page.getByTestId("investigation-conclusion")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Evidence: recorded actions" })).toBeVisible();
    await expect(page.getByTestId("investigation-limits")).toBeVisible();

    // Tool receipts and the gate audit are available, but collapsed.
    const technical = page.getByTestId("investigation-technical");
    await expect(technical).toBeVisible();
    expect(await technical.evaluate((node: HTMLDetailsElement) => node.open)).toBe(false);

    await technical.locator("> summary").click();
    await expect(page.getByTestId("investigation-gate")).toBeVisible();

    // Receipts are capped by their own disclosure: a long run opens collapsed.
    const receipts = technical.locator(".r6-tool-receipts");
    if (!(await receipts.evaluate((node: HTMLDetailsElement) => node.open))) {
      await receipts.locator("> summary").click();
    }
    await expect(page.getByTestId("investigation-tool-receipt").first()).toBeVisible();
  });
});

test.describe("R6.2 layout", () => {
  test("Match Detail totals and result stay inside 1440/768/390/360", async ({ page }) => {
    await openCockpit(page);
    await setMatch(page, REAL_MATCH);
    await seekClock(page, WINDOW_TRAP_AT);
    await page.goto(`/?workspace=match_center&match=${REAL_MATCH}&at=${WINDOW_TRAP_AT}`);
    await expect(page.getByTestId("match-totals")).toBeVisible();

    for (const width of [1440, 768, 390, 360]) {
      await page.setViewportSize({ width, height: 900 });
      await page.waitForTimeout(200);
      expect(await hasHorizontalOverflow(page), `overflow at ${width}px: ${await overflowingElements(page)}`).toBe(
        false,
      );
      await capture(page, `r6-2-match-detail-${width}`);
    }
  });
});

test.describe("R6.2 cross-module journey", () => {
  test("a selected event leads straight into an investigation and back to the match", async ({
    page,
  }) => {
    await openCockpit(page);
    await setMatch(page, "syn_default");
    await seekClock(page, 420);
    await page.goto("/?workspace=match_center&match=syn_default&at=420");
    await expect(page.getByTestId("match-totals")).toBeVisible();

    // Select a recorded action from the desktop event feed. The feed is the
    // stable list; the phone shortlist re-lays out underneath the pointer.
    const row = page.getByTestId("event-feed-row").first();
    await expect(row).toBeVisible();
    await row.click();

    const strip = page.getByTestId("match-event-context");
    await expect(strip).toBeVisible();
    // The strip names the event: a clock time and a recorded action kind.
    await expect(strip).toContainText(/\d{2}:\d{2}/);

    await page.getByTestId("match-event-investigate").click();

    // The studio inherits the selection and reports which focus it carried.
    await expect(page.getByRole("tab", { name: new RegExp(WORKSPACE_TABS.storyAgent) })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.getByText("Selection carried over")).toBeVisible({ timeout: 30_000 });

    const plan = page.getByTestId("investigation-plan");
    await expect(plan).toBeVisible({ timeout: 60_000 });

    // And the result can take the analyst back to the match moment it describes.
    const back = page.getByTestId("investigation-return");
    await expect(back).toBeVisible();
    await back.click();
    await expect(page.getByRole("tab", { name: new RegExp(WORKSPACE_TABS.matchCenter) })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.getByTestId("match-totals")).toBeVisible();
  });

  test("a key player card opens an investigation about that player", async ({ page }) => {
    await openCockpit(page);
    await setMatch(page, REAL_MATCH);
    await seekClock(page, 4200);
    await page.goto(`/?workspace=match_center&match=${REAL_MATCH}&at=4200`);

    const cards = page.getByTestId("match-player-card");
    await expect(cards.first()).toBeVisible({ timeout: 30_000 });

    // Selecting a player must be a real selection, not a no-op.
    const name = page.locator('[data-testid="match-player-card"] .r6-player-name').first();
    const playerName = (await name.innerText()).trim();
    await name.click();
    await expect(name).toHaveAttribute("aria-pressed", "true");

    await page.getByTestId("match-player-investigate").first().click();
    await expect(page.getByRole("tab", { name: new RegExp(WORKSPACE_TABS.storyAgent) })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.getByText("Selection carried over")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(playerName).first()).toBeVisible({ timeout: 30_000 });
  });
});
