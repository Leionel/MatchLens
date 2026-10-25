import { expect, request as playwrightRequest, test } from "@playwright/test";
import { BASE_URL, PRODUCER_TOKEN } from "./env";

/**
 * Cross-session ownership and provider publication boundary, exercised against
 * the same throwaway server the browser suite uses. These are API-level
 * adversarial checks; the UI journey is covered separately.
 */
test.describe("session ownership", () => {
  test("one anonymous session cannot read, cancel or promote another's investigation", async () => {
    // Do not inherit the suite's global storage state: these contexts must be
    // two genuinely independent anonymous browsers.
    const emptyState = { cookies: [], origins: [] };
    const first = await playwrightRequest.newContext({ baseURL: BASE_URL, storageState: emptyState });
    const second = await playwrightRequest.newContext({ baseURL: BASE_URL, storageState: emptyState });
    try {
      expect((await first.post("/api/sessions")).ok()).toBeTruthy();
      expect((await second.post("/api/sessions")).ok()).toBeTruthy();

      const investigation = await first.post("/api/investigate", {
        data: {
          match_id: "syn_default",
          at: 720,
          team: "H",
          focus_type: "moment",
          question: "What produced the attacking activity?",
        },
      });
      expect(investigation.ok()).toBeTruthy();
      const plan = await investigation.json();
      expect(plan.owner_session_id).toBeUndefined();

      expect((await first.get(`/api/investigations/${plan.investigation_id}`)).status()).toBe(200);
      expect((await second.get(`/api/investigations/${plan.investigation_id}`)).status()).toBe(404);
      expect((await second.post(`/api/investigations/${plan.investigation_id}/cancel`)).status()).toBe(404);
      expect((await second.post(`/api/investigations/${plan.investigation_id}/promote`)).status()).toBe(404);
      const otherList = await second.get("/api/investigations?match_id=syn_default");
      expect((await otherList.json()).count).toBe(0);

      const producer = await first.get(
        `/api/investigations/${plan.investigation_id}`,
        { headers: { "X-MatchLens-Token": PRODUCER_TOKEN } },
      );
      expect(producer.ok()).toBeTruthy();
    } finally {
      await first.dispose();
      await second.dispose();
    }
  });
});

test.describe("provider data boundary", () => {
  test("anonymous bulk endpoint is a bounded projection while the producer gets the stream", async () => {
    const anonymous = await playwrightRequest.newContext({ baseURL: BASE_URL });
    try {
      const publicResponse = await anonymous.get("/api/matches/sb_3795221/events?limit=10000");
      expect(publicResponse.ok()).toBeTruthy();
      const publicBody = await publicResponse.json();
      expect(publicBody.access_tier).toBe("public_analysis_projection");
      expect(publicBody.events).toBeUndefined();
      expect(publicBody.sample.length).toBeLessThanOrEqual(24);

      const producerResponse = await anonymous.get("/api/matches/sb_3795221/events", {
        headers: { "X-MatchLens-Token": PRODUCER_TOKEN },
      });
      expect(producerResponse.ok()).toBeTruthy();
      const producerBody = await producerResponse.json();
      expect(producerBody.access_tier).toBe("internal_event_access");
      expect(producerBody.events.length).toBe(4691);
    } finally {
      await anonymous.dispose();
    }
  });
});
