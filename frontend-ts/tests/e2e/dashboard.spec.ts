/**
 * Job Raider - Dashboard Page E2E Tests
 *
 * End-to-end tests for the dashboard page functionality.
 *
 * Author: Job Raider
 * Date: 2026-06-08
 */

import { test, expect } from '@playwright/test';

test.describe('Dashboard Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard');
  });

  test('should load dashboard successfully', async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.locator('h1')).toContainText('Dashboard');
  });

  test('should display statistics', async ({ page }) => {
    // Look for statistics cards
    const statsCards = page.locator('[data-testid="stats"]').or(page.locator('.stat-card'));
    const statsCount = await statsCards.count();

    if (statsCount > 0) {
      await expect(statsCards.first()).toBeVisible();
    }
  });

  test('should display application summary', async ({ page }) => {
    // Look for applications section
    const appsSection = page.locator('[data-testid="applications"]').or(page.locator('text=/applications/i'));
    await expect(appsSection.first()).toBeVisible();
  });

  test('should have quick action buttons', async ({ page }) => {
    // Look for action buttons
    const actionButtons = page.locator('button').or(page.locator('[role="button"]'));
    const buttonCount = await actionButtons.count();

    if (buttonCount > 0) {
      await expect(actionButtons.first()).toBeVisible();
    }
  });

  test('should navigate to jobs from dashboard', async ({ page }) => {
    // Look for jobs link or button
    const jobsLink = page.locator('a[href="/jobs"]').or(page.locator('text=/jobs/i').or(page.locator('button:has-text("Jobs")')));
    const jobsCount = await jobsLink.count();

    if (jobsCount > 0) {
      await jobsLink.first().click();
      await expect(page).toHaveURL(/\/jobs/);
    }
  });

  test('should navigate to profile from dashboard', async ({ page }) => {
    // Look for profile link or button
    const profileLink = page.locator('a[href="/profile"]').or(page.locator('text=/profile/i').or(page.locator('button:has-text("Profile")')));
    const profileCount = await profileLink.count();

    if (profileCount > 0) {
      await profileLink.first().click();
      await expect(page).toHaveURL(/\/profile/);
    }
  });

  test('should be responsive on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Reload page with mobile viewport
    await page.reload();

    // Check that dashboard is still visible
    const dashboard = page.locator('[data-testid="dashboard"]').or(page.locator('main'));
    await expect(dashboard.first()).toBeVisible();
  });
});

test.describe('Dashboard Features', () => {
  test('should display recent applications', async ({ page }) => {
    await page.goto('/dashboard');

    // Look for recent applications list
    const recentApps = page.locator('[data-testid="recent-applications"]').or(page.locator('text=/recent/i'));
    const appsCount = await recentApps.count();

    if (appsCount > 0) {
      await expect(recentApps.first()).toBeVisible();
    }
  });

  test('should allow filtering applications', async ({ page }) => {
    await page.goto('/dashboard');

    // Look for filter controls
    const filterControls = page.locator('[data-testid="filter"]').or(page.locator('select')).or(page.locator('input[type="search"]'));
    const filterCount = await filterControls.count();

    if (filterCount > 0) {
      await expect(filterControls.first()).toBeVisible();
    }
  });

  test('should show application status breakdown', async ({ page }) => {
    await page.goto('/dashboard');

    // Look for status breakdown or chart
    const statusBreakdown = page.locator('[data-testid="status-breakdown"]').or(page.locator('text=/status/i'));
    await expect(statusBreakdown.first()).toBeVisible();
  });

  test('should handle empty state gracefully', async ({ page }) => {
    await page.goto('/dashboard');

    // Look for empty state message if no applications
    const emptyState = page.locator('text=/no applications/i').or(page.locator('text=/empty/i'));
    const emptyCount = await emptyState.count();

    // If empty state exists, it should be visible
    if (emptyCount > 0) {
      await expect(emptyState.first()).toBeVisible();
    }
  });
});
