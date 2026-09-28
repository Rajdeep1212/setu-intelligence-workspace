import { test, expect } from "@playwright/test";

test.describe("connected staging journey", () => {
  test.skip(process.env.SETU_CONNECTED_INTEGRATION !== "1", "requires the loopback real-runtime backend");

  test("frontend, BFF, FastAPI, LangGraph, and staging retrieval stay connected", async ({ page }) => {
    test.setTimeout(900_000);
    const browserLogs: string[] = [];
    page.on("console", (message) => browserLogs.push(message.text()));
    await page.route("**/*", async (route) => {
      if (!route.request().url().startsWith("http://127.0.0.1:3000")) {
        throw new Error("Connected browser suite attempted a non-loopback request");
      }
      await route.continue();
    });
    await page.addInitScript(() => window.localStorage.clear());
    await page.goto("/workspace");
    await page.getByRole("button", { name: "New question" }).click();

    const question = "How do I register for e-Shram and what do I need?";
    const submittedPayloads: Array<{ query?: string; language?: string }> = [];
    page.on("request", (request) => {
      if (request.url().endsWith("/api/query") && request.method() === "POST") {
        submittedPayloads.push(request.postDataJSON() as { query?: string; language?: string });
      }
    });
    await page.getByLabel("Ask SETU a question").fill(question);
    await page.getByRole("button", { name: "Ask SETU" }).click();
    await expect.poll(() => submittedPayloads.length).toBe(1);
    expect(submittedPayloads[0]).toEqual({ query: question, language: "en" });
    await expect(page.getByRole("status")).toContainText("Request in progress");
    await page.getByRole("button", { name: "Response language: English" }).click();
    await page.getByRole("menuitemradio", { name: "বাংলা" }).click();
    await expect(page.getByRole("button", { name: "Response language: বাংলা" })).toBeVisible();

    const englishAnswer = "The official FAQ lists an Aadhaar number, an Aadhaar-linked mobile number, and bank account details for registration.";
    await expect(page.getByText(englishAnswer)).toBeVisible({ timeout: 600_000 });
    await expect(page.getByRole("heading", { name: question })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
    await expect(page.locator("article.conversation-answer-copy h3:empty")).toHaveCount(0);

    const links = page.getByRole("navigation", { name: "Official source and service links" });
    const sourceLink = links.getByRole("link", { name: /Official source: e-Shram/ });
    const applicationLink = links.locator('a[data-link-kind="application"]');
    const helpLink = links.locator('a[data-link-kind="help"]');
    await expect(sourceLink).toHaveAttribute("href", "https://eshram.gov.in/faqs");
    await expect(applicationLink).toHaveAttribute("href", "https://register.eshram.gov.in/");
    await expect(helpLink).toHaveAttribute("href", "https://gms.eshram.gov.in/");
    for (const link of [sourceLink, applicationLink, helpLink]) {
      await expect(link).toHaveAttribute("target", "_blank");
      await expect(link).toHaveAttribute("rel", "noreferrer");
    }
    await page.getByLabel("Open source 1 for claim 1").click();
    const evidence = page.getByRole("region", { name: "Retrieved sources" });
    await expect(evidence).toBeVisible();
    await expect(evidence).toContainText("Aadhaar linked Mobile number");

    const failureQuestion = "SETU integration provider failure";
    await page.getByLabel("Ask SETU a question").fill(failureQuestion);
    await page.getByRole("button", { name: "Ask SETU" }).click();
    await expect(page.locator('.inline-error[role="alert"]')).toContainText("temporarily unavailable");
    await expect(page.getByRole("heading", { name: question })).toBeVisible();
    await expect(page.getByText(englishAnswer)).toBeVisible();

    await page.getByRole("button", { name: "Response language: বাংলা" }).click();
    await page.getByRole("menuitemradio", { name: "English" }).click();
    const clarificationQuestion = "Where do I apply for the student credit card scheme?";
    await page.getByLabel("Ask SETU a question").fill(clarificationQuestion);
    await page.getByRole("button", { name: "Ask SETU" }).click();
    await expect(page.getByRole("heading", { name: "Clarification needed" })).toBeVisible();
    await expect(page.getByText("Which state or Union Territory's student credit card scheme do you mean?")).toBeVisible();

    await page.getByRole("button", { name: "New question" }).click();
    await page.getByRole("button", { name: "Response language: English" }).click();
    await page.getByRole("menuitemradio", { name: "বাংলা" }).click();
    const bengaliQuestion = "পশ্চিমবঙ্গ স্টুডেন্ট ক্রেডিট কার্ডের জন্য কীভাবে আবেদন করব?";
    await page.getByLabel("Ask SETU a question").fill(bengaliQuestion);
    await page.getByRole("button", { name: "Ask SETU" }).click();
    await expect(page.getByText("সরকারি ডব্লিউবিএসসিসি অনলাইন পোর্টালে নিবন্ধন করে প্রয়োজনীয় নথি আপলোড করতে বলা হয়েছে।")).toBeVisible({ timeout: 600_000 });
    await expect(page.getByRole("heading", { name: "How to apply" })).toBeVisible();
    await expect(page.locator('a[data-link-kind="application"]')).toHaveAttribute("href", "https://wbscc.wb.gov.in/");
    await expect(page.locator('a[data-link-kind="help"]')).toHaveAttribute("href", "https://sccgrievance.wb.gov.in/");

    const storage = await page.evaluate(() => Object.fromEntries(Object.entries(window.localStorage)));
    expect(Object.keys(storage).sort()).toEqual(["setu-response-language-v1", "setu-theme"]);
    expect(storage["setu-response-language-v1"]).toBe("bn");
    expect(JSON.stringify(storage)).not.toContain(question);
    expect(JSON.stringify(storage)).not.toContain(bengaliQuestion);
    expect(browserLogs.join("\n")).not.toContain(question);
    expect(browserLogs.join("\n")).not.toContain(bengaliQuestion);
    expect(browserLogs.join("\n")).not.toMatch(/X-API-Key|Bearer\s/i);
  });
});
