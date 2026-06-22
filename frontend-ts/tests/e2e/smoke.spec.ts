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
 *  - The Odysseus theme floats the desktop sidebar via an infinite CSS
 *    animation (`.cosmic-float`), so on desktop the link click uses `force` to
 *    bypass Playwright's actionability "stable" check; the mobile sheet's links
 *    are static and need no force.
 *
 * A single `navigateTo` helper centralises this, so each test runs unchanged on
 * both the chromium (desktop) and Mobile Chrome projects with no skips.
 */

import type { Page } from "@playwright/test";
import { test, expect } from "./support/test";

/**
 * Navigate to a primary route via whichever nav the current viewport exposes.
 *
 * On mobile, open the hamburger `<Sheet>` first; on desktop the sidebar is
 * persistent. Desktop sidebar links float (Odysseus `.cosmic-float`), so the
 * click bypasses the actionability "stable" check there; mobile sheet links are
 * static and use the default checks.
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
  await page.getByRole("link", { name: linkName, exact: true }).click({ force: !isMobile });
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

test.describe("Primary navigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
  });

  test("opens the Jobs page", async ({ page }) => {
    await navigateTo(page, "Jobs");
    await expect(page).toHaveURL(/\/jobs/);
    await expect(page.locator("h1")).toContainText("Jobs");
  });

  test("opens the Profile page", async ({ page }) => {
    await navigateTo(page, "Profile");
    await expect(page).toHaveURL(/\/profile/);
    await expect(page.locator("h1")).toContainText("Profile");
  });
});
