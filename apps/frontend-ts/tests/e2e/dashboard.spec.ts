/**
 * Job Raider - Dashboard E2E Tests
 *
 * Verifies the dashboard renders its stat cards and pipeline sections from
 * the mocked metrics/health/history data. Assertions are scoped to `<main>`
 * (the AppShell content region) to avoid matching sidebar navigation, and
 * target values unique to the mocked fixtures so a pass proves the mock
 * wired through rather than coincidental static text.
 */

import { test, expect } from "./support/test";

test.describe("Dashboard page", () => {
  test("renders stat cards and pipeline sections from mocked data", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await expect(page.locator("h1")).toContainText("Dashboard");

    const main = page.locator("main");

    // Section headings render once the cards mount.
    await expect(main.getByText("System Health")).toBeVisible();
    await expect(main.getByText("Recent Pipeline Runs")).toBeVisible();

    // Mocked metrics populate a stat sub-text (unique to the fixture).
    await expect(main.getByText("20.0% screening rate")).toBeVisible();

    // Mocked pipeline history renders a run row (unique to the fixture).
    await expect(main.getByText(/12 scraped/)).toBeVisible();
  });
});
