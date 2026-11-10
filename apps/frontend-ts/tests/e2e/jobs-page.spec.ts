/**
 * Job Raider - Jobs Page E2E Tests
 *
 * Verifies the jobs search form renders and that submitting a search displays
 * results served by the mocked backend. Asserts against the real form
 * (`input[name="keywords"]`, the submit button) and a job title from the
 * mocked `sampleJobs` fixture — no speculative data-testid hooks.
 */

import type { Page } from "@playwright/test";

import { test, expect } from "./support/test";

/**
 * Search for jobs, and wait for the first mocked result.
 *
 * On a cold dev server, a fill or a click before hydration can be lost: the
 * hydrated input resets to its empty state, so no search runs. Retry until
 * the results show; the mocked search is safe to repeat, and a search that
 * never works still fails after the overall timeout.
 *
 * @param page - The page on /jobs.
 * @param keywords - Text for the Keywords field.
 * @returns Resolved once the first result is visible.
 */
async function searchJobs(page: Page, keywords: string): Promise<void> {
  const firstResult = page.getByText("Senior Software Engineer").first();
  await expect(async () => {
    await page.locator('input[name="keywords"]').fill(keywords);
    await page.locator('button[type="submit"]').click();
    await expect(firstResult).toBeVisible({ timeout: 3_000 });
  }).toPass({ timeout: 20_000 });
}

test.describe("Jobs page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/jobs");
  });

  test("shows the search form", async ({ page }) => {
    await expect(page.locator('input[name="keywords"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test("renders results after a search", async ({ page }) => {
    // The mocked POST /jobs/search returns sampleJobs; the first result's
    // title renders in the left-hand results list.
    await searchJobs(page, "Software Engineer");
  });

  test("generates a cover letter and displays proofread validation", async ({
    page,
  }) => {
    await searchJobs(page, "Software Engineer");

    // Open the first job detail panel by clicking the row's overlay button.
    // On narrow viewports the detail opens in a bottom sheet.
    await page
      .getByRole("button", { name: /View Senior Software Engineer/ })
      .first()
      .click();

    const generateButton = page.getByRole("button", {
      name: "Generate Cover Letter",
    });
    await expect(generateButton).toBeVisible({ timeout: 10000 });
    await generateButton.click();

    // The generated cover-letter content and proofread result should appear.
    await expect(page.getByText("I am excited about")).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByText("Proofread").first()).toBeVisible();
    await expect(page.getByText("Ready to send")).toBeVisible();
    await expect(page.getByText("Quality Breakdown")).toBeVisible();
  });
});
