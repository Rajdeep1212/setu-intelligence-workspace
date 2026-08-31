import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "test-results",
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:3000", channel: "msedge", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 950 } } },
    { name: "tablet", use: { viewport: { width: 820, height: 1050 } } },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: "msedge" } },
  ],
});
