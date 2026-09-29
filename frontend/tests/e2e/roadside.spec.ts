import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const LOOPBACK = "http://127.0.0.1:3000";

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
});

test("Roadside Mode reloads and works with the network off after one online visit", async ({ page, context }) => {
  const external: string[] = [];
  context.on("request", (request) => {
    const url = request.url();
    if (!url.startsWith(LOOPBACK) && !url.startsWith("data:") && !url.startsWith("blob:")) external.push(url);
  });

  await page.goto("/roadside");
  await expect(page.getByRole("heading", { level: 1, name: "Roadside Mode" })).toBeVisible();
  await expect(page.getByText("Saved for offline use on this device")).toBeVisible({ timeout: 30_000 });

  await context.setOffline(true);
  await page.reload();

  const westBengal = page.getByRole("region", { name: "On-the-spot amount in West Bengal" });
  await expect(westBengal.getByText("₹5,000")).toBeVisible();
  await expect(westBengal.getByText("₹10,000")).toBeVisible();
  await expect(westBengal.getByText(/208-WT/)).toBeVisible();
  await expect(westBengal.getByRole("link", { name: /Official source/ })).toHaveAttribute("href", /^https:\/\/transport\.wb\.gov\.in\//);

  // The page is interactive offline, not just a cached picture.
  await page.getByLabel("State").selectOption("IN-DL");
  const delhi = page.getByRole("region", { name: "On-the-spot amount in Delhi" });
  await expect(delhi.getByText("No verified amount yet")).toBeVisible();
  await expect(delhi).not.toContainText("₹");

  await context.setOffline(false);
  expect(external).toEqual([]);
});

test("Roadside Mode has no accessibility violations in either theme", async ({ page }) => {
  // Four full axe scans; mobile emulation is slower, so allow three times the default budget.
  test.slow();
  await page.goto("/roadside");
  await expect(page.getByRole("heading", { level: 1, name: "Roadside Mode" })).toBeVisible();
  for (const selection of [["IN-WB", "phone_device"], ["IN-KA", "helmet"], ["IN-WB", "red_light"]] as const) {
    await page.getByLabel("State").selectOption(selection[0]);
    await page.getByLabel("Offence").selectOption(selection[1]);
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    // Long offence names must not push the page wider than the screen.
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  }
  // The header hides the theme button on phones, so set the saved preference the
  // toggle reads (localStorage "setu-theme") and reload. Works on every viewport.
  await page.evaluate(() => localStorage.setItem("setu-theme", "dark"));
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("heading", { level: 1, name: "Roadside Mode" })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
