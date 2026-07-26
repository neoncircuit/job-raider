/**
 * Job Raider - Playwright Configuration
 *
 * Playwright configuration for end-to-end testing.
 * Provides cross-browser E2E testing with fast, reliable execution.
 *
 * Author: Job Raider
 * Date: 2026-06-08
 */

import { defineConfig, devices } from "@playwright/test";

/** Dev-server port. Override with PLAYWRIGHT_PORT when :3000 is already bound (e.g. Docker). */
const PORT = Number(process.env.PLAYWRIGHT_PORT ?? 3000);
const BASE_URL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./tests/e2e",

  // Timeout for each test (milliseconds)
  timeout: 30000,

  // Timeout for each expect() assertion (milliseconds)
  expect: {
    timeout: 5000,
  },

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Opt out of parallel tests on CI
  workers: process.env.CI ? 1 : undefined,

  // Reporter to use
  reporter: [
    ["html", { outputFolder: "playwright-report" }],
    ["junit", { outputFile: "playwright-results/junit.xml" }],
    ["list"],
  ],

  // Shared settings for all tests
  use: {
    // Base URL for tests - can be overridden per test
    baseURL: BASE_URL,

    // Collect trace when retrying the failed test
    trace: "on-first-retry",

    // Take screenshot on failure
    screenshot: "only-on-failure",

    // Record video on failure
    video: "retain-on-failure",

    // Browser context options
    viewport: { width: 1280, height: 720 },
    navigationTimeout: 15000,
  },

  // CI installs only the Chromium browser (`npx playwright install --with-deps
  // chromium`), so the project matrix is restricted to Chromium-based devices
  // to avoid failures on Firefox/WebKit (whose binaries are not installed).
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },

    {
      name: "Mobile Chrome",
      use: { ...devices["Pixel 5"] },
    },
  ],

  // Run your local dev server before starting the tests
  webServer: {
    command: `npm run dev -- --port ${PORT}`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    // Bind mounts (e.g. Docker Desktop on Windows) can make Next cold-start
    // exceed two minutes; keep CI runners comfortable with five minutes.
    timeout: 300000,
  },
});
