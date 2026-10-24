import AxeBuilder from "@axe-core/playwright";
import { expect, Page, test } from "@playwright/test";
import {
  hasHorizontalOverflow,
  openCockpit,
  selectWorkspace,
  useEnglish,
  workspaceTablist,
  WORKSPACE_TABS,
} from "./helpers";

/**
 * Responsive and keyboard acceptance. The suite runs this file in a phone
 * viewport (Pixel 7) and in a tablet viewport (iPad Mini), so the same
 * assertions are proven on real rendered layouts instead of a compiled bundle.
 */
test.beforeEach(async ({ page }) => {
  await useEnglish(page);
});

/** Walk the real focus order until a workspace tab owns the focus. */
async function focusFirstWorkspaceTab(page: Page): Promise<void> {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    await page.keyboard.press("Tab");
    const isTab = await page.evaluate(() => document.activeElement?.getAttribute("role") === "tab");
    if (isTab) return;
  }
  throw new Error("the workspace tabs are not reachable with the keyboard");
}

test.describe("responsive acceptance", () => {
  test("the cockpit fits the viewport without sideways scrolling", async ({ page }) => {
    await openCockpit(page);
    expect(await hasHorizontalOverflow(page)).toBe(false);

    await selectWorkspace(page, WORKSPACE_TABS.matchCenter);
    await expect(workspaceTablist(page)).toBeVisible();
    expect(await hasHorizontalOverflow(page)).toBe(false);

    await selectWorkspace(page, WORKSPACE_TABS.storyAgent);
    expect(await hasHorizontalOverflow(page)).toBe(false);
  });

  test("the workspace tabs are reachable and operable with the keyboard", async ({ page }) => {
    await openCockpit(page);
    await focusFirstWorkspaceTab(page);

    // Move one step further so the activation really switches the workspace.
    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => {
      const element = document.activeElement as HTMLElement | null;
      return {
        role: element?.getAttribute("role") ?? null,
        selected: element?.getAttribute("aria-selected") ?? null,
      };
    });
    expect(focused.role).toBe("tab");

    await page.keyboard.press("Enter");
    await expect
      .poll(async () =>
        page.evaluate(() => document.activeElement?.getAttribute("aria-selected") ?? null),
      )
      .toBe("true");
  });

  test("the cockpit surfaces no serious accessibility violations", async ({ page }) => {
    await openCockpit(page);

    const scan = async () => {
      const results = await new AxeBuilder({ page }).analyze();
      return results.violations
        .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
        .map((violation) => ({
          id: violation.id,
          impact: violation.impact,
          nodes: violation.nodes.length,
          targets: violation.nodes.slice(0, 4).map((node) => node.target.join(" ")),
          detail: violation.nodes[0]?.failureSummary?.split("\n").slice(0, 2).join(" | "),
        }));
    };

    expect(await scan()).toEqual([]);

    // The light theme is a first-class surface, so it is audited as well.
    await page.getByRole("button", { name: "LIGHT", exact: true }).click();
    await expect(page.getByRole("button", { name: "DARK", exact: true })).toBeVisible();
    expect(await scan()).toEqual([]);
  });
});
