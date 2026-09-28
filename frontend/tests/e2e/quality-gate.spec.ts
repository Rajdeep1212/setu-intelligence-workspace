import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { writeFileSync } from "node:fs";

const sizes = { desktop: [1920, 1080], laptop: [1366, 768], tablet: [768, 1024], mobile: [390, 844] };
const origin = process.env.SETU_FRONTEND_TEST_ORIGIN ?? "http://127.0.0.1:3100";
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin)) throw new Error("Quality gate requires a loopback origin");
for (const [size, [width, height]] of Object.entries(sizes)) {
  test(`quality gate ${size}`, async ({ page }, info) => {
    test.skip(process.env.SETU_FRONTEND_QUALITY !== "1", "requires the isolated demo server on port 3100");
    test.setTimeout(120_000);
    await page.setViewportSize({ width, height });
    const errors: string[] = [];
    const unexpected: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error" && !message.text().includes("503")) errors.push(message.text()); });
    page.on("request", request => { if (new URL(request.url()).origin !== origin) unexpected.push(request.url()); });
    const audits: unknown[] = [];
    async function audit(state: string) {
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      const result = await new AxeBuilder({ page }).analyze();
      audits.push({ state, violations: result.violations.map(v => ({ id: v.id, impact: v.impact, description: v.description, nodes: v.nodes.map(n => ({ target: n.target, summary: n.failureSummary })) })) });
      writeFileSync(info.outputPath("axe.json"), JSON.stringify(audits, null, 2));
      await page.screenshot({ path: info.outputPath(`${state}.png`), fullPage: true });
      expect(result.violations.filter(v => v.impact === "critical" || v.impact === "serious")).toEqual([]);
    }
    await page.goto(`${origin}/`);
    await audit("landing");
    await page.getByRole("link", { name: /Open workspace/ }).first().click();
    const trigger = page.getByRole("button", { name: "Response language: English" });
    await trigger.click();
    await expect(page.getByRole("menuitemradio", { name: "हिंदी", exact: true })).toBeVisible();
    await expect(page.getByRole("menuitemradio", { name: "বাংলা", exact: true })).toBeVisible();
    await audit("language-menu");
    await page.keyboard.press("Escape");
    await expect(trigger).toBeFocused();
    await page.getByRole("button", { name: "New question" }).click();
    const input = page.getByLabel("Ask SETU a question");
    const button = page.getByRole("button", { name: "Ask SETU", exact: true });
    let calls = 0;
    let mode = "answer";
    let release: (() => void) | undefined;
    const payloads: Array<Record<string, unknown>> = [];
    const answers = { en: "Register using the official application portal.", hi: "आधिकारिक आवेदन पोर्टल पर पंजीकरण करें।", bn: "সরকারি আবেদন পোর্টালে নিবন্ধন করুন।" };
    await page.route("**/api/query", async route => {
      calls++;
      const payload = route.request().postDataJSON(); payloads.push(payload);
      if (mode === "pending") await new Promise<void>(resolve => { release = resolve; });
      if (mode === "failure") { await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: { code: "BACKEND_UNAVAILABLE", message: "Unavailable", request_id: "quality-fixture" } }) }); return; }
      const status = mode === "clarification" ? "clarification_needed" : mode === "unsupported" ? "abstained" : "answered";
      const answer = status === "clarification_needed" ? "Which state?" : status === "abstained" ? "Available evidence does not confirm this amount." : answers[payload.language as keyof typeof answers];
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ answer, response_status: status, data_mode: "local", citations: status === "answered" ? [{ chunk_id: "fixture-1", document_id: "fixture-doc", title: "e-Shram official FAQ", source: "Ministry of Labour", url: "https://eshram.gov.in/faqs", snippet: "Register using the official application portal." }] : [], sections: status === "answered" ? [{ text: answer, kind: "direct_answer", citation_ids: ["fixture-1"] }] : [], official_links: status === "answered" ? [{ kind: "application", label: "Official application page", url: "https://register.eshram.gov.in/" }, { kind: "help", label: "Official help page", url: "https://gms.eshram.gov.in/" }] : [] }) });
    });
    await input.fill("  My exact question  ");
    await input.press("Shift+Enter");
    expect(calls).toBe(0);
    await input.dispatchEvent("keydown", { key: "Enter", code: "Enter", isComposing: true });
    expect(calls).toBe(0);
    await input.fill("  My exact question  ");
    mode = "pending";
    await input.press("Enter");
    await expect.poll(() => calls).toBe(1);
    await expect(button).toBeDisabled();
    await input.press("Enter");
    expect(calls).toBe(1);
    await audit("loading");
    await page.getByRole("button", { name: /Response language:/ }).click();
    await page.getByRole("menuitemradio", { name: "हिंदी", exact: true }).click();
    mode = "answer"; release?.();
    await expect(page.locator(".conversation-answer-copy")).toContainText(answers.en);
    expect(payloads[0]).toEqual({ query: "  My exact question  ", language: "en" });
    await page.getByLabel("Open source 1 for claim 1").click();
    await expect(page.locator("#source-0")).toBeFocused();
    await expect(page.locator('a[data-link-kind="application"]')).toHaveAttribute("href", "https://register.eshram.gov.in/");
    await expect(page.locator('a[data-link-kind="help"]')).toHaveAttribute("href", "https://gms.eshram.gov.in/");
    if (size === "mobile") {
      const linksBox = await page.getByRole("navigation", { name: "Official source and service links" }).boundingBox();
      const composerBox = await page.locator(".conversation-composer-wrap").boundingBox();
      expect(linksBox && composerBox && linksBox.y + linksBox.height <= composerBox.y).toBeTruthy();
    }
    await audit("answer-citations");
    await input.fill("हिंदी प्रश्न"); await button.click();
    await expect(page.locator(".conversation-answer-copy")).toContainText(answers.hi);
    await audit("hindi");
    await page.getByRole("button", { name: /Response language:/ }).click();
    await page.getByRole("menuitemradio", { name: "বাংলা", exact: true }).click();
    await input.fill("বাংলা প্রশ্ন"); await button.click();
    await expect(page.locator(".conversation-answer-copy")).toContainText(answers.bn);
    await audit("bengali");
    mode = "clarification"; await input.fill("Student credit card?"); await button.click();
    await expect(page.getByText("Which state?", { exact: true })).toBeVisible();
    await audit("clarification");
    mode = "answer"; await input.fill("West Bengal"); await button.click();
    await expect(page.locator(".conversation-answer-copy")).toBeVisible();
    expect(payloads.at(-1)?.clarification_context).toEqual({ original_query: "Student credit card?" });
    mode = "unsupported"; await input.fill("Unverified amount?"); await button.click();
    await expect(page.getByText("Available evidence does not confirm this amount.")).toBeVisible();
    await audit("unsupported");
    mode = "answer"; await input.fill("Successful question"); await button.click();
    await expect(page.locator(".conversation-answer-copy")).toBeVisible();
    mode = "failure"; await input.fill("Question to retry"); await button.click();
    await expect(page.locator('.inline-error[role="alert"]')).toBeVisible();
    await expect(page.locator("#question-title")).toHaveText("Successful question");
    await expect(input).toHaveValue("Question to retry");
    await input.scrollIntoViewIfNeeded();
    const box = await button.boundingBox();
    expect(box && box.y >= 0 && box.y + box.height <= height).toBeTruthy();
    await audit("failure");
    mode = "answer"; await button.click();
    await expect(page.locator("#question-title")).toHaveText("Question to retry");
    await expect(page.locator('.inline-error[role="alert"]')).toHaveCount(0);
    for (const path of ["sources", "system", "case-study"]) { await page.goto(`${origin}/${path}`); await audit(path); }
    expect(errors).toEqual([]); expect(unexpected).toEqual([]);
  });
}
