import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.beforeEach(async ({ page }) => { await page.emulateMedia({ reducedMotion: "reduce" }); });

test("all primary routes render without leaking requests", async ({ page }) => {
  const external: string[] = [];
  const consoleIssues: string[] = [];
  page.on("request", (request) => { if (!request.url().startsWith("http://127.0.0.1:3000")) external.push(request.url()); });
  page.on("console", (message) => { if (message.type() === "error" || message.type() === "warning") consoleIssues.push(message.text()); });
  const routes = [["/", /Understand India's digital public infrastructure/], ["/workspace", /What are the core components/], ["/sources", /Evidence before inference/], ["/system", /Private by construction/], ["/case-study", /From one question to auditable evidence/]] as const;
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
  await page.getByLabel("Focus evidence 2").click();
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog", { name: "Navigate SETU" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: /Switch to dark theme/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: /Eligibility mode/ }).click();
  await expect(page.getByText(/not an official eligibility decision/i)).toBeVisible();
  await page.getByRole("button", { name: /Continue/ }).click();
  await expect(page.getByLabel(/Annual family income/)).toBeVisible();
  const results = await new AxeBuilder({ page }).exclude(".resize-handle").analyze();
  expect(results.violations.filter((item) => item.impact === "critical" || item.impact === "serious")).toEqual([]);
});
