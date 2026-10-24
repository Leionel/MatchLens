import { expect, Page, test } from "@playwright/test";
import { PRODUCER_TOKEN } from "./env";
import {
  openCockpit,
  readState,
  seekClock,
  selectWorkspace,
  setMatch,
  useEnglish,
  WORKSPACE_TABS,
} from "./helpers";

/**
 * A real StatsBomb Open Data match: England 2-1 Denmark, UEFA Euro 2020
 * semi-final. It is imported as a full provider payload, so every surface
 * below must read the provider's own events rather than a synthetic fixture.
 */
const REAL_MATCH = "sb_3795221";
const REAL_MATCH_SCOREBOARD = /England vs Denmark scoreboard/;

/** The hand-written excerpt must never be presented as a complete match. */
const EXCERPT_MATCH = "sb_wc2022_final";

/**
 * Deterministic fixtures. Every test owns a different match, because the claim
 * registry is persistent state: a withdrawal in one test would otherwise change
 * the claim lifecycle another test asserts on.
 */
const LIFECYCLE_MATCH = "syn_default";
const PRODUCER_MATCH = "syn_transitions";
const STALE_MATCH = "syn_balanced";
const GATE_CLOCK = 720;
/**
 * The stale-rundown test needs a snapshot whose deterministic plan is actually
 * gate-approved: the gate only forms an assertion when the metric receipts of
 * the window support it, and that is a property of the fixture, not of the UI.
 */
const STALE_CLOCK = 600;

test.beforeEach(async ({ page }) => {
  await useEnglish(page);
});

/** Load a match, park the clock on a snapshot and open the given workspace. */
async function openWorkspace(
  page: Page,
  workspace: string,
  matchId: string,
  at: number,
): Promise<void> {
  await openCockpit(page);
  await setMatch(page, matchId);
  await seekClock(page, at);
  await page.goto(`/?workspace=${workspace}&match=${matchId}&at=${at}`);
  await expect(page.getByRole("tab", { name: new RegExp(workspaceTabLabel(workspace)) })).toHaveAttribute(
    "aria-selected",
    "true",
  );
}

/** Workspace ids used in the deep links, mapped to their English tab labels. */
function workspaceTabLabel(workspace: string): string {
  const labels: Record<string, string> = {
    match_hub: WORKSPACE_TABS.matchHub,
    match_center: WORKSPACE_TABS.matchCenter,
    tactical_lab: WORKSPACE_TABS.tacticalLab,
    story_agent: WORKSPACE_TABS.storyAgent,
    producer: WORKSPACE_TABS.producer,
    validation_lab: WORKSPACE_TABS.validationLab,
  };
  return labels[workspace] ?? workspace;
}

/**
 * Run the deterministic investigation and register the gate-approved claim.
 * The path is deliberately free of a model call, so the suite never spends
 * budget it was not granted.
 */
async function registerDeterministicClaim(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Investigation", exact: true }).click();
  await page.getByPlaceholder("What produced this attacking spell?").fill("What produced the attacking activity?");
  await page.getByRole("button", { name: "Run investigation" }).click();

  const plan = page.getByTestId("investigation-plan");
  await expect(plan).toBeVisible();
  await expect(plan).toContainText("approved");

  await page.getByRole("button", { name: "Confirm and register claim" }).click();
  await expect(plan).toContainText("Registered:");
}

/** A queue row that the editor is allowed to approve and to publish. */
function approvableRow(page: Page) {
  return page
    .locator(
      '[data-testid="producer-claim-row"][data-gate-status="approved"][data-lifecycle-status="current"]',
    )
    .first();
}

test.describe("match library", () => {
  test("the library separates provider payloads, excerpts and synthetic fixtures", async ({ page }) => {
    await openCockpit(page);

    const cards = page.getByTestId("match-card");
    await expect(cards.first()).toBeVisible();

    await expect(
      page.locator(`[data-testid="match-card"][data-provenance="provider_payload"]`).first(),
    ).toBeVisible();
    await expect(
      page.locator(`[data-testid="match-card"][data-provenance="synthetic"]`).first(),
    ).toBeVisible();

    const excerpt = page.locator(`[data-testid="match-card"][data-match-id="${EXCERPT_MATCH}"]`);
    await expect(excerpt).toHaveAttribute("data-provenance", "provider_schema_excerpt");
    await expect(excerpt.getByTestId("match-provenance")).toHaveText("Sample excerpt");

    const provider = page.locator(`[data-testid="match-card"][data-match-id="${REAL_MATCH}"]`);
    await expect(provider.getByTestId("match-provenance")).toHaveText("Provider data");
  });

  test("searching the library narrows to the real match without hiding its provenance", async ({ page }) => {
    await openCockpit(page);
    await page.getByPlaceholder("e.g. France or 2022").fill("England 2-1 Denmark");

    const card = page.locator(`[data-testid="match-card"][data-match-id="${REAL_MATCH}"]`);
    await expect(card).toBeVisible();
    await expect(page.getByTestId("match-card")).toHaveCount(1);
    await expect(card.getByTestId("match-provenance")).toHaveText("Provider data");
  });

  test("the library narrows by competition and season and reports the visible share", async ({ page }) => {
    await openCockpit(page);

    // The catalog is fetched after the cockpit mounts, so the rows have to be
    // waited for before the corpus can be counted.
    await expect(page.getByTestId("match-card").first()).toBeVisible();
    const total = await page.getByTestId("match-card").count();
    expect(total).toBeGreaterThan(0);

    const euro = page.locator(`[data-testid="match-library-competition"][data-competition="UEFA Euro"]`);
    await expect(euro).toBeVisible();
    await euro.click();

    const euroRows = page.getByTestId("match-card");
    await expect(euroRows.first()).toBeVisible();
    const shown = await euroRows.count();
    expect(shown).toBeGreaterThan(0);
    expect(shown).toBeLessThan(total);
    await expect(page.getByTestId("match-hub-count")).toContainText(`${shown} of ${total}`);

    // Every remaining row belongs to the selected competition.
    const competitions = await euroRows.evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-match-id") ?? ""),
    );
    expect(competitions.length).toBe(shown);

    // The season chips narrow the same competition further.
    const season = page.locator(`[data-testid="match-library-season"][data-season="2024"]`);
    await expect(season).toBeVisible();
    await season.click();
    await expect(page.getByTestId("match-card").first()).toBeVisible();
    const seasonRows = await page.getByTestId("match-card").count();
    expect(seasonRows).toBeGreaterThan(0);
    expect(seasonRows).toBeLessThan(shown);
    await expect(page.getByTestId("match-hub-count")).toContainText(`${seasonRows} of ${total}`);
  });

  test("the detail page reports the source and the coverage of the selected match", async ({ page }) => {
    await openCockpit(page);

    const card = page.locator(`[data-testid="match-card"][data-match-id="${REAL_MATCH}"]`);
    await card.click();

    const detail = page.getByTestId("match-library-detail");
    await expect(detail).toBeVisible();
    await expect(detail).toContainText("England");
    await expect(detail).toContainText("Denmark");

    await page.getByTestId("match-library-tab-coverage").click();
    await expect(detail).toContainText("COMPLETE_VERIFIED");

    await page.getByTestId("match-library-tab-source").click();
    await expect(detail).toContainText("statsbomb_open_data");
    await expect(detail).toContainText(REAL_MATCH);
  });
});

test.describe("real match journey", () => {
  test("a provider match keeps its identity through match centre, timeline and tactical lab", async ({ page }) => {
    await openCockpit(page);

    const card = page.locator(`[data-testid="match-card"][data-match-id="${REAL_MATCH}"]`);
    await card.click();

    // Selecting a row opens the record of that match; the analysis session is
    // only switched on an explicit action.
    await expect(card).toHaveAttribute("aria-current", "true");
    await expect(page.getByTestId("match-library-detail")).toContainText("England");

    await page.getByTestId("match-library-enter").click();

    await expect(page).toHaveURL(new RegExp(`match=${REAL_MATCH}`));
    const scoreboard = page.getByRole("region", { name: REAL_MATCH_SCOREBOARD });
    await expect(scoreboard).toBeVisible();
    await expect(scoreboard.getByRole("heading", { name: "England" })).toBeVisible();
    await expect(scoreboard.getByRole("heading", { name: "Denmark" })).toBeVisible();

    // The official provider score is shown next to the live replay score.
    await expect(scoreboard).toContainText(/OFFICIAL FT 2.1/);
    // The coverage badge reports what was actually observed, not a claim of
    // full coverage.
    await expect(scoreboard).toContainText(/coverage . \d+% observed/);

    // The events of the provider payload reach the match centre timeline.
    const state = await readState(page);
    expect(state.match_id).toBe(REAL_MATCH);
    expect(state.match_context.provider).toBe("statsbomb_open_data");
    expect(state.match_context.data_coverage).toBe("C1");
    expect(state.match_context.home_team_name).toBe("England");
    expect(state.teams.H).toBe("England");
    expect(state.official_score).toEqual({ H: 2, N: 1 });
    expect(state.events.length).toBeGreaterThan(0);

    // Tactical lab reads the same event stream and derives real sequences.
    await selectWorkspace(page, WORKSPACE_TABS.tacticalLab);
    const tactical = await readState(page);
    expect(tactical.sequences.length).toBeGreaterThan(0);
  });

  test("the real match clock follows its extra-time format, not the synthetic constants", async ({
    page,
  }) => {
    await openCockpit(page);

    const card = page.locator(`[data-testid="match-card"][data-match-id="${REAL_MATCH}"]`);
    await card.click();
    await page.getByTestId("match-library-enter").click();
    await expect(page).toHaveURL(new RegExp(`match=${REAL_MATCH}`));

    const state = await readState(page);
    const context = state.match_context;

    // The anchor match went to extra time: two 45-minute halves plus two
    // 15-minute extra-time halves, so the nominal clock is 120 minutes and the
    // last recorded period is the fourth one. The synthetic fixture constants
    // (720s, two periods) must never be reused for this match.
    expect(context.duration).toBe(7200);
    expect(context.period).toBe(4);
    expect(context.match_clock_basis).toBe("match_elapsed");

    // The provider clock keeps running through the accumulated stoppage time,
    // so the recorded stream reaches past the nominal match clock. The clock
    // the cockpit exposes is the nominal one and never exceeds it.
    expect(context.observed_end).toBeGreaterThan(context.duration);

    const clamped = await page.request.post("/api/control", {
      data: { action: "seek", at: Math.ceil(context.observed_end) },
    });
    expect(clamped.ok()).toBeTruthy();
    const body = await clamped.json();
    expect(body.at).toBe(context.duration);
  });

  test("a deep link restores the match, the workspace and the clock after a reload", async ({ page }) => {
    await page.goto(`/?workspace=match_center&match=${REAL_MATCH}&at=1800`);
    await expect(page.getByRole("region", { name: REAL_MATCH_SCOREBOARD })).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`match=${REAL_MATCH}`));

    await page.reload();
    await expect(page.getByRole("region", { name: REAL_MATCH_SCOREBOARD })).toBeVisible();

    await expect.poll(async () => (await readState(page)).at, { timeout: 20_000 }).toBe(1800);
    const state = await readState(page);
    expect(state.match_id).toBe(REAL_MATCH);
  });

  test("the metric registry reads the provider match with one consistent team, window and snapshot", async ({
    page,
  }) => {
    await openCockpit(page);

    const read = async () => {
      const response = await page.request.get(
        `/api/metrics/possession?match_id=${REAL_MATCH}&at=1800&team=H&window=current`,
      );
      expect(response.ok()).toBeTruthy();
      return response.json();
    };

    const first = await read();
    expect(first.match_id).toBe(REAL_MATCH);
    expect(first.team).toBe("H");
    expect(first.window).toBe("current");
    expect(first.snapshot_id).toBeTruthy();
    expect(first.status).not.toBe("unavailable");
    // The observation has to be bound to provider events, not to a fixture.
    expect(first.event_ids.length).toBeGreaterThan(0);
    expect(first.event_ids.every((id: string) => !id.startsWith("syn_"))).toBeTruthy();

    // The same team, window and snapshot must produce the same observation.
    const second = await read();
    expect(second.snapshot_id).toBe(first.snapshot_id);
    expect(second.value).toBe(first.value);
    expect(second.event_ids).toEqual(first.event_ids);
  });

  test("a deterministic investigation on the real match produces tool receipts and no model call", async ({ page }) => {
    await openWorkspace(page, "story_agent", REAL_MATCH, 1800);

    await page.getByRole("button", { name: "Investigation", exact: true }).click();
    await page.getByPlaceholder("What produced this attacking spell?").fill("What produced this attacking spell?");
    await page.getByRole("button", { name: "Run investigation" }).click();

    const plan = page.getByTestId("investigation-plan");
    // A full provider payload runs the OAAI pipeline over every event, so the
    // deterministic plan on a real match is slower than on a synthetic one.
    await expect(plan).toBeVisible({ timeout: 90_000 });

    // The plan must be produced by the deterministic tool layer, never by a
    // paid model call, and the UI has to say so explicitly.
    await expect(page.getByTestId("investigation-execution-mode")).toHaveAttribute(
      "data-execution-mode",
      "deterministic_planner",
    );
    await expect(page.getByTestId("investigation-agent-status")).toHaveAttribute(
      "data-agent-status",
      "not_run",
    );
    await expect(page.getByTestId("investigation-agent-status")).toHaveText("Not Run");

    const investigation = await page.request.post("/api/investigate", {
      timeout: 90_000,
      data: {
        match_id: REAL_MATCH,
        at: 1800,
        team: "H",
        focus_type: "moment",
        question: "What produced this attacking spell?",
      },
    });
    expect(investigation.ok()).toBeTruthy();
    const body = await investigation.json();
    expect(body.match_id).toBe(REAL_MATCH);
    expect(body.execution_mode).toBe("deterministic_planner");
    expect(body.agent_status).toBe("not_run");
    expect(body.tool_receipts.length).toBeGreaterThan(0);
    expect(body.tool_receipts.every((r: any) => r.status === "ok")).toBeTruthy();
    // The completeness of the real match must reach the investigation plan.
    expect(body.completeness.status).toBe("COMPLETE_VERIFIED");
    expect(body.completeness.synthetic).toBe(false);
    // Off-ball shape is never inferred from an event stream.
    expect(body.not_inferable.join(" ")).toMatch(/pressing intent/i);
  });

  test("requesting the real agent without a model key degrades honestly to the deterministic planner", async ({ page }) => {
    await openWorkspace(page, "story_agent", LIFECYCLE_MATCH, 540);

    await page.getByRole("button", { name: "Investigation", exact: true }).click();
    // The throwaway E2E server has no provider key, so the agent request must
    // come back from the deterministic planner with the degradation recorded.
    await page.getByTestId("investigation-engine-select").selectOption("maf_agent");
    await page.getByPlaceholder("What produced this attacking spell?").fill("Why did the attacking activity change?");
    await page.getByRole("button", { name: "Run investigation" }).click();

    const plan = page.getByTestId("investigation-plan");
    await expect(plan).toBeVisible();
    await expect(page.getByTestId("investigation-execution-mode")).toHaveAttribute(
      "data-execution-mode",
      "deterministic_planner",
    );
    await expect(page.getByTestId("investigation-agent-status")).toHaveAttribute(
      "data-agent-status",
      "not_run",
    );
    await expect(page.getByTestId("investigation-agent-error")).toContainText("model_not_configured");
  });
});

test.describe("claim lifecycle", () => {
  test("a registered claim can be withdrawn and the revision is recorded in the timeline", async ({ page }) => {
    await openWorkspace(page, "story_agent", LIFECYCLE_MATCH, GATE_CLOCK);
    await registerDeterministicClaim(page);

    // The challenge modal must target a claim the registry actually knows.
    await page.getByRole("button", { name: "Deliberation", exact: true }).click();
    await page.getByRole("button", { name: /^Revisions/ }).click();
    await page.getByRole("button", { name: /Challenge Current Insight/ }).click();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible();
    const select = modal.locator("select.challenge-claim-select");
    await expect(select).toBeEnabled();
    const options = await select.locator("option").allTextContents();
    expect(options.length).toBeGreaterThan(0);
    expect(options.join(" ")).not.toContain("claim-current");

    await modal.getByText("6. Withdraw This Claim").click();
    await modal.getByRole("button", { name: /Execute Adversarial Challenge/ }).click();

    await expect(modal).toBeHidden();
    await expect(page.getByText("WITHDRAWN").first()).toBeVisible();

    const state = await readState(page);
    expect(state.revisions.length).toBeGreaterThan(0);
    expect(state.revisions.some((r: any) => r.outcome === "withdrawn")).toBeTruthy();
  });
});

test.describe("producer workspace", () => {
  test("an editor approves a claim, builds a rundown and exports a manifest", async ({ page }) => {
    await openWorkspace(page, "story_agent", PRODUCER_MATCH, GATE_CLOCK);
    await registerDeterministicClaim(page);

    await selectWorkspace(page, WORKSPACE_TABS.producer);
    await page.getByLabel("Producer token").fill(PRODUCER_TOKEN);

    const row = approvableRow(page);
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByRole("status")).toContainText("Editorial state updated");

    // Only a fully approved claim may enter a rundown.
    await expect(row.getByLabel("Add to rundown")).toBeEnabled();
    await row.getByLabel("Add to rundown").check();

    await page.getByRole("button", { name: /Build and validate rundown/ }).click();
    await expect(page.getByRole("status")).toContainText(/Rundown/);
    await expect(page.getByText("All rundown items are valid")).toBeVisible();

    const exportButton = page.getByRole("button", { name: "JSON", exact: true });
    await expect(exportButton).toBeEnabled();
    await exportButton.click();
    await expect(page.getByRole("status")).toContainText(/Export complete/);
    await expect(page.getByText("Export manifest")).toBeVisible();
  });

  test("a withdrawal invalidates a rundown that was already built", async ({ page }) => {
    await openWorkspace(page, "story_agent", STALE_MATCH, STALE_CLOCK);
    await registerDeterministicClaim(page);

    await selectWorkspace(page, WORKSPACE_TABS.producer);
    await page.getByLabel("Producer token").fill(PRODUCER_TOKEN);

    const row = approvableRow(page);
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByRole("status")).toContainText("Editorial state updated");
    await row.getByLabel("Add to rundown").check();
    await page.getByRole("button", { name: /Build and validate rundown/ }).click();
    await expect(page.getByText("All rundown items are valid")).toBeVisible();

    // Withdraw the published claim behind the producer's back.
    const snapshotId = (await readState(page)).snapshot_id;
    const claims = await page.request.get(
      `/api/challengeable-claims?snapshot_id=${encodeURIComponent(snapshotId)}`,
    );
    expect(claims.ok()).toBeTruthy();
    const body = await claims.json();
    expect(body.claims.length).toBeGreaterThan(0);
    const target = body.claims.find((c: any) => c.lifecycle_status === "current");
    expect(target).toBeTruthy();

    const withdrawal = await page.request.post("/api/challenge", {
      data: {
        claim_id: target.claim_id,
        snapshot_id: snapshotId,
        challenge_type: "withdraw_claim",
        team: "H",
      },
    });
    expect(withdrawal.ok()).toBeTruthy();

    // The producer must notice that its rundown is stale and must not export it.
    await page.reload();
    await selectWorkspace(page, WORKSPACE_TABS.producer);
    await page.getByLabel("Producer token").fill(PRODUCER_TOKEN);
    await expect(page.getByText(/Stale items:/).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "JSON", exact: true })).toBeDisabled();

    const rundown = await page.request.get(
      `/api/broadcast/rundown?match_id=${STALE_MATCH}&snapshot_id=${encodeURIComponent(snapshotId)}`,
    );
    expect(rundown.ok()).toBeTruthy();
    expect((await rundown.json()).valid).toBe(false);
  });
});
