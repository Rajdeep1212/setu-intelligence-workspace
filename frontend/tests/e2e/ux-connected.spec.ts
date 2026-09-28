import { test, expect } from "@playwright/test";
import { writeFileSync, mkdirSync } from "node:fs";

test("six connected staging UX paths", async ({ page }, testInfo) => {
  test.skip(process.env.SETU_CONNECTED_INTEGRATION !== "1", "requires isolated real staging runtime");
  test.setTimeout(1_800_000);
  const directory = process.env.SETU_UX_EVIDENCE_DIR ?? testInfo.outputPath("evidence");
  const remainingOnly = process.env.SETU_CONNECTED_REMAINING_ONLY === "1";
  const hindiOnly = process.env.SETU_CONNECTED_HINDI_ONLY === "1";
  const origin = process.env.SETU_FRONTEND_TEST_ORIGIN ?? "http://127.0.0.1:3000";
  if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin)) throw new Error("Connected gate requires a loopback origin");
  mkdirSync(directory, { recursive: true });
  const observations: unknown[] = [];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/*", async (route) => {
    expect(new URL(route.request().url()).origin).toBe(origin);
    await route.continue();
  });
  await page.goto(`${origin}/workspace`);
  await page.getByRole("button", { name: "Response language: English" }).click();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "New question" }).click();
  const composer = page.getByLabel("Ask SETU a question");
  async function language(label: string) {
    await page.getByRole("button", { name: /Response language:/ }).click();
    await page.getByRole("menuitemradio", { name: label, exact: true }).click({ timeout: 10_000 });
  }
  async function ask(name: string, question: string, expectedStatus: string, switchWhilePending = false) {
    await composer.fill(question);
    const started = Date.now();
    const responsePromise = page.waitForResponse((response) => response.url().endsWith("/api/query") && response.request().method() === "POST", { timeout: 610_000 });
    await page.getByRole("button", { name: "Ask SETU", exact: true }).click();
    if (switchWhilePending) await language("हिंदी");
    const response = await responsePromise;
    const body = await response.json();
    const payload = response.request().postDataJSON();
    observations.push({ name, payload, status: response.status(), seconds: (Date.now() - started) / 1000, body });
    writeFileSync(`${directory}/connected.json`, JSON.stringify({ observations, errors }, null, 2));
    // Preserve evidence and continue the remaining independent journeys if one
    // retrieval fails; never repeat an expensive failed query in this run.
    const expectedHttp = expectedStatus === "failure" ? 503 : 200;
    expect.soft(response.status(), name).toBe(expectedHttp);
    if (response.status() !== expectedHttp) return null;
    if (expectedStatus === "failure") {
      await expect(page.locator('.inline-error[role="alert"]')).toContainText("temporarily unavailable");
      await expect(composer).toHaveValue(question);
    } else {
      expect.soft(body.response_status, name).toBe(expectedStatus);
      if (body.response_status !== expectedStatus) return null;
      await expect(page.getByRole("heading", { name: question, exact: true })).toBeVisible().catch(async () => {
        // Clarification replies display the original question with the exact reply.
        await expect(page.locator("#question-title")).toContainText(question);
      });
      expect(body.data_mode).toBe("local");
      const ids = new Set(body.citations.map((citation: { chunk_id: string }) => citation.chunk_id));
      for (const section of body.sections) for (const id of section.citation_ids) expect(ids.has(id)).toBe(true);
      if (expectedStatus === "answered") {
        expect(body.citations.length).toBeGreaterThan(0);
        await expect(page.locator(".conversation-answer-copy")).toContainText(body.sections[0]?.text ?? body.answer);
      }
    }
    await page.locator("#question-title").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${directory}/after-${name}-desktop.png`, fullPage: true });
    await page.setViewportSize({ width: 393, height: 851 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `${directory}/after-${name}-mobile.png`, fullPage: true });
    await page.setViewportSize({ width: 1440, height: 950 });
    return body;
  }
  if (!remainingOnly) {
    if (!hindiOnly) {
      const english = "How do I register for e-Shram and what do I need?";
      const englishResult = await ask("english-application", english, "answered", true);
      if (englishResult) {
        await expect(page.locator('a[data-link-kind="application"]')).toHaveAttribute("href", "https://register.eshram.gov.in/");
        await expect(page.locator('a[data-link-kind="help"]')).toHaveAttribute("href", "https://gms.eshram.gov.in/");
      }
      await ask("controlled-failure", "SETU integration provider failure", "failure");
      if (englishResult) await expect(page.locator("#question-title")).toHaveText(english);
    } else {
      await language("\u0939\u093f\u0902\u0926\u0940");
    }
    const hindi = await ask("hindi-eligibility-recovery", "PMSBY के लिए कौन पात्र है?", "answered");
    if (hindi) {
      await expect(page.locator(".conversation-answer-copy")).toHaveAttribute("lang", "hi");
      await expect(page.locator('a[data-link-kind="application"]')).toHaveCount(0);
    }
    if (hindiOnly) {
      expect(errors).toEqual([]);
      return;
    }
    await language("বাংলা");
    const bengali = await ask("bengali-english-evidence", "পশ্চিমবঙ্গ স্টুডেন্ট ক্রেডিট কার্ডের জন্য কীভাবে আবেদন করব?", "answered");
    if (bengali) {
      await page.getByLabel("Open source 1 for claim 1").click();
      await expect(page.getByRole("heading", { name: "West Bengal Student Credit Card Scheme" })).toBeVisible();
      await expect(page.getByRole("region", { name: "Retrieved sources" }).getByRole("link", { name: "View source" })).toHaveAttribute("href", bengali.citations[0].url);
    }
  }
  await language("English");
  const clarification = await ask("clarification", "Where do I apply for the student credit card scheme?", "clarification_needed");
  if (clarification) {
    const reply = await ask("clarification-reply", "West Bengal", "answered");
    if (reply) await expect(page.locator('a[data-link-kind="application"]')).toHaveAttribute("href", "https://wbscc.wb.gov.in/");
  }
  await page.getByRole("button", { name: "New question" }).click();
  await language("हिंदी");
  await ask("unsupported-amount", "ई-श्रम कार्ड बनते ही ₹3,000 मिलते हैं ना?", "abstained");
  expect(errors).toEqual([]);
});
