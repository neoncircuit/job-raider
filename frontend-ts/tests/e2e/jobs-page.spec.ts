/**
 * Job Raider - Jobs Page E2E Tests
 *
 * Verifies the jobs search form renders and that submitting a search displays
 * results served by the mocked backend. Asserts against the real form
 * (`input[name="keywords"]`, the submit button) and a job title from the
 * mocked `sampleJobs` fixture — no speculative data-testid hooks.
 */

import { test, expect } from "./support/test";

test.describe("Jobs page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/jobs");
  });

  test("shows the search form", async ({ page }) => {
    await expect(page.locator('input[name="keywords"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test("renders results after a search", async ({ page }) => {
    await page.locator('input[name="keywords"]').fill("Software Engineer");
    await page.locator('button[type="submit"]').click();

    // The mocked POST /jobs/search returns sampleJobs; the first result's
    // title renders in the left-hand results list.
    await expect(page.getByText("Senior Software Engineer").first()).toBeVisible({
      timeout: 10000,
    });
  });
});
