import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route("**/*", async (route) => {
    if (!route.request().url().startsWith("http://127.0.0.1:3000")) {
      throw new Error("Browser suite attempted a non-loopback request");
    }
    await route.continue();
  });
});

test("all primary routes render without leaking requests", async ({ page }) => {
  // Six full page loads in one test: allow three times the default budget so
  // parallel runs on a busy machine do not time out (seen locally at 25-32 s).
  test.slow();
  const external: string[] = [];
  const consoleIssues: string[] = [];
  page.on("request", (request) => { if (!request.url().startsWith("http://127.0.0.1:3000")) external.push(request.url()); });
  page.on("console", (message) => { if (message.type() === "error" || message.type() === "warning") consoleIssues.push(message.text()); });
  const routes = [["/", /Understand India's digital public infrastructure/], ["/workspace", /What are the core components/], ["/sources", /Evidence before inference/], ["/system", /Private by construction/], ["/case-study", /From one question to inspectable evidence/], ["/roadside", /Roadside Mode/]] as const;
  for (const [path, heading] of routes) { await page.goto(path); await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible(); }
  expect(external).toEqual([]);
  expect(consoleIssues).toEqual([]);
});

test("source explorer filters and opens sanitized detail", async ({ page }) => {
  await page.goto("/sources");
  await page.getByRole("button", { name: /India's Digital Public Infrastructure/ }).click();
  await expect(page.getByRole("dialog", { name: /India's Digital Public Infrastructure/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("textbox", { name: "Search sources" }).fill("no such source");
  await expect(page.getByText("No matching source")).toBeVisible();
});

test("workspace supports keyboard, theme, modes, and evidence inspection", async ({ page }, testInfo) => {
  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: /What are the core components/ })).toBeVisible();
  expect(testInfo.project.name).toMatch(/desktop|tablet|mobile/);
  await page.getByLabel("Focus retrieved citation 2 for claim 2").click();
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog", { name: "Navigate SETU" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: /Switch to dark theme/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: /Eligibility mode/ }).click();
  await expect(page.getByText("Illustrative eligibility experience")).toBeVisible();
  await page.getByRole("button", { name: /Continue/ }).click();
  await expect(page.getByLabel(/Demonstration annual family income/)).toBeVisible();
  const results = await new AxeBuilder({ page }).exclude(".resize-handle").analyze();
  expect(results.violations.filter((item) => item.impact === "critical" || item.impact === "serious")).toEqual([]);
});

test("message check card is accessible in both themes and keeps pasted links as text", async ({ page }) => {
  test.slow();
  const scamAnswer = {
    answer: "This message shows strong signs of a scam. The link uses a shortened address. Check challans only on https://echallan.parivahan.gov.in/.",
    citations: [],
    sections: [
      { text: "This message shows strong signs of a scam.", citation_ids: [] },
      { text: "The link uses a shortened address.", citation_ids: [] },
      { text: "Check challans only on https://echallan.parivahan.gov.in/.", citation_ids: [] },
    ],
    route: "scam_check",
    response_status: "scam_check",
    scam_check: {
      verdict: "likely_scam",
      signals: ["shortened_link", "payment_link_not_official"],
      links: [{ url: "https://echallan-parivahan-gov-in-pay-now.online/very/long/path/that/must/wrap", host: "echallan-parivahan-gov-in-pay-now.online", official: false, kinds: ["impersonating_domain"] }],
      debunks: [{ id: "fake-echallan-links-2026", kind: "channel_warning", topic: "Fake traffic e-challan messages", summary: "Scammers send fake challan links.", date: "2026-07-10", issuer: "PIB Fact Check", source: "https://www.business-standard.com/india-news/fake-traffic-challan-scam-pib-warning-whatsapp-sms-links-126071000400_1.html" }],
    },
  };
  await page.route("**/api/query", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(scamAnswer) }));
  for (const theme of ["light", "dark"]) {
    await page.addInitScript((value) => window.localStorage.setItem("setu-theme", value), theme);
    await page.goto("/workspace");
    await page.getByLabel("Ask SETU a question").fill("Your e-challan is pending, pay now bit.ly/3xYzAb");
    await page.getByRole("button", { name: "Run corpus investigation" }).click();
    const card = page.getByRole("article", { name: "Message check" });
    await expect(card).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await expect(card.getByRole("link")).toHaveCount(1);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    const results = await new AxeBuilder({ page }).include(".scam-answer").include(".scam-pill").analyze();
    expect(results.violations.filter((item) => item.impact === "critical" || item.impact === "serious")).toEqual([]);
  }
});

test("eligibility notice shows official next steps, accessible in both themes", async ({ page }) => {
  test.slow();
  const notice = "Live eligibility evaluation is intentionally unavailable. Verify eligibility with the applicable official source.";
  const body = {
    answer: notice,
    citations: [],
    sections: [{ text: notice, citation_ids: [] }],
    route: "check_eligibility",
    response_status: "eligibility_unverified",
    next_steps: [
      { id: "pmkisan_status", label: "Check PM-KISAN registration and payment status on the official portal", url: "https://pmkisan.gov.in/BeneficiaryStatus_New.aspx", operator: "Department of Agriculture & Farmers Welfare" },
      { id: "myscheme", label: "Find government schemes you may qualify for on myScheme", url: "https://www.myscheme.gov.in/", operator: "Digital India Corporation (MeitY)" },
    ],
  };
  await page.route("**/api/query", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }));
  await page.goto("/workspace");
  await page.getByLabel("Ask SETU a question").fill("Am I eligible for PM-KISAN?");
  await page.getByRole("button", { name: "Run corpus investigation" }).click();
  await expect(page.getByRole("article", { name: "Eligibility not assessed" })).toBeVisible();
  const steps = page.getByRole("navigation", { name: "Official next steps" });
  await expect(steps.getByRole("link")).toHaveCount(2);
  for (const theme of ["light", "dark"]) {
    if (theme === "dark") await page.getByRole("button", { name: /Switch to dark theme/ }).first().click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    const results = await new AxeBuilder({ page }).include(".next-steps").include(".notice-answer").analyze();
    expect(results.violations.filter((item) => item.impact === "critical" || item.impact === "serious")).toEqual([]);
  }
});
