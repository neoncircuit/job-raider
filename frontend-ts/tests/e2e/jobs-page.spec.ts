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

  test("generates a cover letter and displays proofread validation", async ({ page }) => {
    await page.locator('input[name="keywords"]').fill("Software Engineer");
    await page.locator('button[type="submit"]').click();

    await expect(page.getByText("Senior Software Engineer").first()).toBeVisible({
      timeout: 10000,
    });

    // Open the first job detail panel
    await page.getByText("Senior Software Engineer").first().click();

    // Generate a cover letter
    await page.getByRole("button", { name: "Generate Cover Letter" }).click();

    // The letter and proofread result should appear
    await expect(page.getByText("Cover Letter").first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("I am excited about")).toBeVisible();
    await expect(page.getByText("Proofread").first()).toBeVisible();
    await expect(page.getByText("Ready to send")).toBeVisible();
    await expect(page.getByText("Quality Breakdown")).toBeVisible();
  });
});
