import { test, expect, type Page } from "@playwright/test";

// The font files the browser actually drew with, read from Chromium (not the CSS stack, which always "matches").
async function renderedFonts(page: Page, selector: string): Promise<string[]> {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("DOM.enable");
  await cdp.send("CSS.enable");
  const { root } = await cdp.send("DOM.getDocument");
  const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector });
  const { fonts } = await cdp.send("CSS.getPlatformFontsForNode", { nodeId });
  return fonts.map((font) => font.familyName);
}

test("English renders in Inter and Bengali in Noto Sans Bengali, without letter spacing or cramped lines", async ({ page }) => {
  await page.goto("/workspace");
  const box = page.getByLabel("Ask SETU a question");
  await box.fill("ভারতের ডিজিটাল জনপরিকাঠামোর মূল উপাদানগুলি কী?");
  const heading = page.locator("#investigation-title");
  await expect(heading).toHaveAttribute("lang", "bn");
  await page.evaluate(() => document.fonts.ready);

  expect(await renderedFonts(page, ".answer-card p")).toContain("Inter");
  const bengaliFonts = await renderedFonts(page, "#investigation-title");
  expect(bengaliFonts).toContain("Noto Sans Bengali");
  expect(bengaliFonts).not.toContain("Nirmala UI");

  const style = await heading.evaluate((element) => { const cs = getComputedStyle(element); return { letterSpacing: cs.letterSpacing, ratio: parseFloat(cs.lineHeight) / parseFloat(cs.fontSize) }; });
  expect(style.letterSpacing).toBe("normal");
  expect(style.ratio).toBeGreaterThanOrEqual(1.3);
});
