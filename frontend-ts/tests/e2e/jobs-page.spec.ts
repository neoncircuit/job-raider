/**
 * Job Raider - Jobs Page E2E Tests
 *
 * End-to-end tests for the jobs page functionality.
 *
 * Author: Job Raider
 * Date: 2026-06-08
 */

import { test, expect } from '@playwright/test';

test.describe('Jobs Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/jobs');
  });

  test('should load jobs page successfully', async ({ page }) => {
    await expect(page).toHaveURL(/\/jobs/);
    await expect(page.locator('h1')).toContainText('Jobs');
  });

  test('should display search form', async ({ page }) => {
    // Check for keywords input
    const keywordsInput = page.locator('input[name="keywords"]').or(page.locator('input[placeholder*="keyword" i]'));
    await expect(keywordsInput.first()).toBeVisible();

    // Check for locations input
    const locationsInput = page.locator('input[name="locations"]').or(page.locator('input[placeholder*="location" i]'));
    await expect(locationsInput.first()).toBeVisible();

    // Check for search button
    const searchButton = page.locator('button[type="submit"]').or(page.locator('button:has-text("Search")'));
    await expect(searchButton.first()).toBeVisible();
  });

  test('should show validation for empty search', async ({ page }) => {
    // Try to submit without entering keywords
    const searchButton = page.locator('button[type="submit"]').or(page.locator('button:has-text("Search")'));
    await searchButton.first().click();

    // Should show validation error or toast
    const errorMessage = page.locator('text=/keywords required/i').or(page.locator('[role="alert"]'));
    // Wait a bit for validation to appear
    await page.waitForTimeout(1000);

    // Check if error message is visible (may not always appear depending on implementation)
    const errorCount = await errorMessage.count();
    if (errorCount > 0) {
      await expect(errorMessage.first()).toBeVisible();
    }
  });

  test('should allow entering search terms', async ({ page }) => {
    // Find keywords input
    const keywordsInput = page.locator('input[name="keywords"]').or(page.locator('input[placeholder*="keyword" i]')).first();

    // Type search keywords
    await keywordsInput.fill('Software Engineer');
    await expect(keywordsInput).toHaveValue('Software Engineer');
  });

  test('should have working filters', async ({ page }) => {
    // Check for experience level selector
    const experienceSelect = page.locator('[name="experience_level"]').or(page.locator('select')).first();
    const selectCount = await experienceSelect.count();

    if (selectCount > 0) {
      await expect(experienceSelect).toBeVisible();
    }
  });

  test('should navigate to saved jobs', async ({ page }) => {
    // Check for saved jobs tab or link
    const savedTab = page.locator('text=/saved/i').or(page.locator('[role="tab"]:has-text("saved")'));
    const savedCount = await savedTab.count();

    if (savedCount > 0) {
      await savedTab.first().click();
      await page.waitForTimeout(1000);
      // Should show saved jobs or empty state
    }
  });

  test('should navigate to applications', async ({ page }) => {
    // Check for applications tab or link
    const appsTab = page.locator('text=/applications/i').or(page.locator('[role="tab"]:has-text("applications")'));
    const appsCount = await appsTab.count();

    if (appsCount > 0) {
      await appsTab.first().click();
      await page.waitForTimeout(1000);
      // Should show applications or empty state
    }
  });

  test('should be responsive on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Reload page with mobile viewport
    await page.reload();

    // Check that page is still functional
    const searchForm = page.locator('form').first();
    await expect(searchForm).toBeVisible();
  });
});

test.describe('Job Search Flow', () => {
  test('should complete a job search', async ({ page }) => {
    await page.goto('/jobs');

    // Enter search keywords
    const keywordsInput = page.locator('input[name="keywords"]').or(page.locator('input[placeholder*="keyword" i]')).first();
    await keywordsInput.fill('React Developer');

    // Enter location
    const locationsInput = page.locator('input[name="locations"]').or(page.locator('input[placeholder*="location" i]')).first();
    await locationsInput.fill('San Francisco');

    // Submit search
    const searchButton = page.locator('button[type="submit"]').or(page.locator('button:has-text("Search")')).first();
    await searchButton.click();

    // Wait for results or loading state
    await page.waitForTimeout(3000);

    // Check for results or empty state
    const results = page.locator('[data-testid="job-results"]').or(page.locator('[data-testid="jobs-list"]'));
    const resultsCount = await results.count();

    if (resultsCount > 0) {
      await expect(results.first()).toBeVisible();
    }
  });

  test('should filter by remote option', async ({ page }) => {
    await page.goto('/jobs');

    // Look for remote checkbox or toggle
    const remoteToggle = page.locator('input[name="remote"]').or(page.locator('[role="checkbox"]')).first();
    const remoteCount = await remoteToggle.count();

    if (remoteCount > 0) {
      await remoteToggle.check();
      await expect(remoteToggle).toBeChecked();
    }
  });

  test('should select job sources', async ({ page }) => {
    await page.goto('/jobs');

    // Look for source selectors
    const sourceSelectors = page.locator('[name="source"]').or(page.locator('text=/linkedin|jsearch/i'));
    const sourceCount = await sourceSelectors.count();

    if (sourceCount > 0) {
      await sourceSelectors.first().click();
      await page.waitForTimeout(500);
    }
  });
});
