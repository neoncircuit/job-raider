/**
 * Job Raider - Navigation Smoke E2E Tests
 *
 * Verifies the app loads (the root route redirects to /dashboard) and that the
 * primary routes are reachable from whichever navigation the viewport exposes.
 *
 * Viewport handling:
 *  - Desktop renders the sidebar persistently.
 *  - Mobile hides nav behind a hamburger `<Sheet>` (aria-label "Open
 *    navigation"), opened and waited until the dialog is visible before a
 *    link is clicked. Clicks are scoped to that dialog so the hidden desktop
 *    sidebar ``nav`` (still in the DOM under ``hidden md:flex``) cannot win
 *    the locator race.
 *  - Desktop nav clicks are scoped to the sidebar ``aside`` and use ``force``
 *    to avoid flaky actionability checks against sticky sidebar chrome.
 */

import type { Page } from "@playwright/test";
import { test, expect } from "./support/test";

/**
 * Navigate to a primary route via whichever nav the current viewport exposes.
 *
 * On mobile, open the hamburger sheet and wait until the Navigation dialog is
 * visible before clicking a link inside it. On desktop, click inside the
 * persistent sidebar. This avoids matching the desktop ``nav`` that stays in
 * the DOM (but hidden) on mobile viewports.
 *
 * @param page - The Playwright page to drive.
 * @param linkName - Accessible name of the nav link to click (e.g. "Jobs").
 * @returns Resolved once the navigation click has been dispatched.
 */
async function navigateTo(page: Page, linkName: string): Promise<void> {
  const isMobile = (page.viewportSize()?.width ?? 0) < 768;
  if (isMobile) {
    const openNav = page.getByLabel("Open navigation");
    const dialog = page.getByRole("dialog", { name: "Navigation" });
    await expect(openNav).toBeVisible();
    // A tap before hydration can be lost. Retry open until the sheet is
    // visible; do not click again when it is already open (overlay).
    await expect(async () => {
      if (!(await dialog.isVisible())) {
        await openNav.click({ timeout: 2_000 });
      }
      await expect(dialog).toBeVisible({ timeout: 2_000 });
    }).toPass({ timeout: 15_000 });
    await dialog.getByRole("link", { name: linkName, exact: true }).click();
    return;
  }

  await page
    .locator("aside")
    .getByRole("link", { name: linkName, exact: true })
    .click({ force: true });
}

test.describe("App load", () => {
  test("loads and redirects to the dashboard", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page).toHaveTitle(/Job Raider/i);
    await expect(page.locator("h1")).toContainText("Dashboard");
  });

  test("handles an unknown route gracefully", async ({ page }) => {
    // Dev compile of not-found can exceed the default 15s navigationTimeout on
    // slow Docker bind mounts; wait for DOM only and allow a longer budget.
    await page.goto("/this-route-does-not-exist", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
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
  // Soft navigation waits on the RSC payload. On a cold Next.js dev server
  // (especially Docker bind mounts) a first visit can exceed 15 s.
  test.describe.configure({ timeout: 90_000 });

  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await expect(page.locator("h1")).toContainText("Dashboard");
  });

  for (const route of PRIMARY_ROUTES) {
    test(`opens the ${route.label} page`, async ({ page }) => {
      await navigateTo(page, route.label);
      // Some routes are compiled on demand in dev; give the dev server extra
      // time to bundle and hydrate the page before asserting the route.
      await expect(page).toHaveURL(new RegExp(`\\/${route.path}`), {
        timeout: 60_000,
      });
      await expect(page.locator("h1")).toContainText(route.heading);
    });
  }
});
