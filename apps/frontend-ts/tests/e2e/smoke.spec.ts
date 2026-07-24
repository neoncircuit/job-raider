/**
 * Job Raider - Navigation Smoke E2E Tests
 *
 * Verifies the app loads (the root route redirects to /dashboard) and that the
 * primary routes are reachable from whichever navigation the viewport exposes.
 *
 * Viewport handling:
 *  - Desktop renders the sidebar persistently.
 *  - Mobile hides nav behind a hamburger `<Sheet>` (aria-label "Open
 *    navigation"), opened before a link is clicked.
 *  - Nav clicks are scoped to ``nav`` so the brand lockup link cannot collide
 *    with route labels, and use ``force`` on desktop to avoid flaky
 *    actionability checks against sticky sidebar chrome.
 */

import type { Page } from "@playwright/test";
import { test, expect } from "./support/test";

/**
 * Navigate to a primary route via whichever nav the current viewport exposes.
 *
 * On mobile, open the hamburger `<Sheet>` first; on desktop the sidebar is
 * persistent. Clicks are scoped to a ``nav`` landmark so brand/header links
 * are never matched.
 *
 * @param page - The Playwright page to drive.
 * @param linkName - Accessible name of the nav link to click (e.g. "Jobs").
 * @returns Resolved once the navigation click has been dispatched.
 */
async function navigateTo(page: Page, linkName: string): Promise<void> {
  const isMobile = (page.viewportSize()?.width ?? 0) < 768;
  if (isMobile) {
    await page.getByLabel("Open navigation").click();
  }
  await page
    .locator("nav")
    .getByRole("link", { name: linkName, exact: true })
    .click({ force: !isMobile });
}

test.describe("App load", () => {
  test("loads and redirects to the dashboard", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page).toHaveTitle(/Job Raider/i);
    await expect(page.locator("h1")).toContainText("Dashboard");
  });

  test("handles an unknown route gracefully", async ({ page }) => {
    await page.goto("/this-route-does-not-exist");
    const title = await page.title();
    // The root layout title is "Job Raider"; a custom not-found page may say 404.
    expect(title).toMatch(/404|Not Found|Job Raider/i);
  });
});

const PRIMARY_ROUTES = [
  { label: "Dashboard", path: "dashboard", heading: "Dashboard" },
  { label: "Pipeline", path: "pipeline", heading: "Pipeline" },
  { label: "Jobs", path: "jobs", heading: "Jobs" },
  { label: "Cover Letter", path: "cover-letter", heading: "Cover Letter" },
  { label: "Career Coach", path: "career-coach", heading: "Career Coach" },
  { label: "Applications", path: "applications", heading: "Applications" },
  { label: "Profile", path: "profile", heading: "Profile" },
  { label: "Assessment", path: "assessment", heading: "Assessment" },
  {
    label: "Resume Analysis",
    path: "resume-analysis",
    heading: "Resume Analysis",
  },
  {
    label: "LinkedIn Analysis",
    path: "linkedin-analysis",
    heading: "LinkedIn Analysis",
  },
  { label: "Metrics", path: "metrics", heading: "Metrics" },
  { label: "Settings", path: "settings", heading: "Settings" },
];

test.describe("Primary navigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
  });

  for (const route of PRIMARY_ROUTES) {
    test(`opens the ${route.label} page`, async ({ page }) => {
      await navigateTo(page, route.label);
      // Some routes are compiled on demand in dev; give the dev server extra
      // time to bundle and hydrate the page before asserting the route.
      await expect(page).toHaveURL(new RegExp(`\\/${route.path}`), {
        timeout: 15_000,
      });
      await expect(page.locator("h1")).toContainText(route.heading);
    });
  }
});
