import { createHash } from "node:crypto";
import { test, expect } from "@playwright/test";

function fingerprint(value: string) {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

test("hydrated composer preserves the synthetic question in the browser request", async ({ page }) => {
  const exact = "  How do I register for e-Shram and what do I need?\u00a0";
  let browserRequest: { query?: string; language?: string } | undefined;
  await page.route("**/api/query", async (route) => {
    browserRequest = route.request().postDataJSON() as { query?: string; language?: string };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "Diagnostic response.",
        citations: [],
        sections: [],
        official_links: [],
        route: "retrieve_docs",
        confidence: null,
        response_status: "abstained",
      }),
    });
  });

  await page.goto("/workspace");
  await page.getByRole("button", { name: "New question" }).click();
  const composer = page.getByLabel("Ask SETU a question");
  await composer.fill(exact);
  const composerValue = await composer.inputValue();
  await page.getByRole("button", { name: "Ask SETU" }).click();
  await expect.poll(() => browserRequest).toBeTruthy();

  const observed = browserRequest?.query ?? "";
  const diagnostics = [
    { boundary: "playwright_fixture", length: exact.length, fingerprint: fingerprint(exact), equals_fixture: true },
    { boundary: "hydrated_composer", length: composerValue.length, fingerprint: fingerprint(composerValue), equals_fixture: composerValue === exact },
    { boundary: "browser_request_body", length: observed.length, fingerprint: fingerprint(observed), equals_fixture: observed === exact },
  ];
  console.log("QUESTION_BOUNDARIES=" + JSON.stringify(diagnostics));
  expect(composerValue).toBe(exact);
  expect(browserRequest).toEqual({ query: exact, language: "en" });
});
