import { Page, expect } from "@playwright/test";

/** Tab labels of the cockpit workspace bar in English. */
export const WORKSPACE_TABS = {
  matchHub: "Match Hub",
  matchCenter: "Match Detail",
  tacticalLab: "Tactical Explorer",
  storyAgent: "Intelligence Studio",
  producer: "Producer",
  validationLab: "Research Lab",
} as const;

/** Force the English locale before the app boots, so specs never assert on Chinese copy. */
export async function useEnglish(page: Page): Promise<void> {
  await page.addInitScript(() => {
    try {
      window.localStorage.setItem("matchlens-locale", "en");
    } catch {
      // Storage can be unavailable in hardened contexts; the default locale is fine.
    }
  });
}

/** The product navigation is one tablist among others, so it is addressed directly. */
export function workspaceTablist(page: Page) {
  return page.locator(".r6-nav-tabs:visible, .r6-mobile-nav:visible");
}

/** Open the cockpit and wait until the session state has rendered. */
export async function openCockpit(page: Page, query = ""): Promise<void> {
  await page.goto(`/${query}`);
  await expect(workspaceTablist(page)).toBeVisible();
  await expect(page.getByRole("tab", { name: new RegExp(WORKSPACE_TABS.matchHub) })).toBeVisible();
}

export async function selectWorkspace(page: Page, label: string): Promise<void> {
  const professional = label === WORKSPACE_TABS.producer || label === WORKSPACE_TABS.validationLab;
  if (professional) {
    await page.getByTestId("pro-tools-toggle").click();
    await page.getByRole("menuitem", { name: new RegExp(label) }).click();
    return;
  }
  await page.getByRole("tab", { name: new RegExp(label) }).click();
  await expect(page.getByRole("tab", { name: new RegExp(label) })).toHaveAttribute("aria-selected", "true");
}

/** Move the match clock through the real control endpoint of the current session. */
export async function seekClock(page: Page, at: number): Promise<void> {
  const response = await page.request.post("/api/control", { data: { action: "seek", at } });
  expect(response.ok()).toBeTruthy();
}

/** Load a match into the session the same way the match hub does. */
export async function setMatch(page: Page, matchId: string): Promise<void> {
  const response = await page.request.post("/api/control", {
    data: { action: "set_match", match_id: matchId },
  });
  expect(response.ok()).toBeTruthy();
}

export async function postJson(page: Page, path: string, body: unknown, headers?: Record<string, string>) {
  const response = await page.request.post(path, { data: body, headers });
  return response;
}

/** Read the live cockpit state of the current session. */
export async function readState(page: Page): Promise<any> {
  const response = await page.request.get("/api/state");
  expect(response.ok()).toBeTruthy();
  return response.json();
}

/** True when the document is wider than its viewport, i.e. the layout overflows sideways. */
export async function hasHorizontalOverflow(page: Page): Promise<boolean> {
  return page.evaluate(() => {
    const doc = document.documentElement;
    return doc.scrollWidth > doc.clientWidth + 1;
  });
}

/** The elements that actually push the document wider than the viewport. */
export async function overflowingElements(page: Page): Promise<string> {
  return page.evaluate(() => {
    const viewport = document.documentElement.clientWidth;
    const rows = Array.from(document.querySelectorAll<HTMLElement>("body *"))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          tag: element.tagName,
          cls: typeof element.className === "string" ? element.className.slice(0, 70) : "",
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
          text: (element.textContent || "").replace(/\s+/g, " ").trim().slice(0, 40),
        };
      })
      .filter((row) => row.right > viewport + 1 || row.left < -1)
      .sort((a, b) => b.right - a.right)
      .slice(0, 8);
    return JSON.stringify({ viewport, scrollWidth: document.documentElement.scrollWidth, rows });
  });
}
