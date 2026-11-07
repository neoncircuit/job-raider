/**
 * Playwright configuration for the exported demo (Step 4, MH-4).
 *
 * The tests run on the static site with no backend and no API mock, on the
 * base path of GitHub Pages. Run `npm run build:demo` first, with
 * `NEXT_PUBLIC_BASE_PATH=/job-raider`.
 *
 * Set `PLAYWRIGHT_CHROMIUM_PATH` to use a browser that is already installed.
 * CI leaves it unset and installs the browser of this Playwright version.
 */

import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.DEMO_PORT ?? 4599);

export default defineConfig({
  testDir: "./tests/e2e-demo",
  timeout: 30000,
  expect: { timeout: 8000 },
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["list"],
  ],
  use: {
    // The final slash keeps the base path in a relative `page.goto`.
    baseURL: `http://localhost:${PORT}/job-raider/`,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    viewport: { width: 1280, height: 720 },
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined,
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "node scripts/serve-demo.mjs",
    url: `http://localhost:${PORT}/job-raider/`,
    reuseExistingServer: !process.env.CI,
  },
});
