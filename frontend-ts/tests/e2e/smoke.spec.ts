/**
 * Job Raider - Smoke E2E Tests
 *
 * Basic smoke tests to verify application loads and critical paths work.
 * These tests should always pass before running more complex E2E tests.
 *
 * Author: Job Raider
 * Date: 2026-06-08
 */

import { test, expect, testUserData } from '../utils/test-setup';
import type { Page } from '@playwright/test';

test.describe('Application Smoke Tests', () => {
  test('should load homepage', async ({ page }) => {
    await page.goto('/');

    // Check that page loads without errors
    await expect(page).toHaveTitle(/Job Raider/i);

    // Check for main navigation
    const nav = page.locator('nav');
    await expect(nav).toBeVisible();
  });

  test('should navigate to jobs page', async ({ page }) => {
    await page.goto('/');

    // Click on Jobs link in navigation
    await page.click('text=Jobs');

    // Should be on jobs page
    await expect(page).toHaveURL(/\/jobs/);

    // Should see search form
    const searchForm = page.locator('form[data-testid="job-search-form"]');
    await expect(searchForm).toBeVisible();
  });

  test('should navigate to dashboard', async ({ page }) => {
    await page.goto('/');

    // Click on Dashboard link in navigation
    await page.click('text=Dashboard');

    // Should be on dashboard page
    await expect(page).toHaveURL(/\/dashboard/);

    // Should see dashboard content
    const dashboard = page.locator('[data-testid="dashboard"]');
    await expect(dashboard).toBeVisible();
  });

  test('should navigate to profile page', async ({ page }) => {
    await page.goto('/');

    // Click on Profile link in navigation
    await page.click('text=Profile');

    // Should be on profile page
    await expect(page).toHaveURL(/\/profile/);

    // Should see profile form
    const profileForm = page.locator('form[data-testid="profile-form"]');
    await expect(profileForm).toBeVisible();
  });

  test('should handle 404 page', async ({ page }) => {
    // Navigate to non-existent page
    await page.goto('/this-page-does-not-exist');

    // Should show 404 page or redirect to homepage
    const title = await page.title();
    expect(title).toMatch(/404|Not Found|Job Raider/i);
  });
});

test.describe('Job Search Smoke Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/jobs');
  });

  test('should show job search form', async ({ page }) => {
    // Check for search input
    const keywordsInput = page.locator('input[name="keywords"]');
    await expect(keywordsInput).toBeVisible();

    // Check for location input
    const locationInput = page.locator('input[name="locations"]');
    await expect(locationInput).toBeVisible();

    // Check for search button
    const searchButton = page.locator('button[type="submit"]');
    await expect(searchButton).toBeVisible();
  });

  test('should show validation for empty search', async ({ page }) => {
    // Click search without entering keywords
    const searchButton = page.locator('button[type="submit"]');
    await searchButton.click();

    // Should show validation error
    const errorMessage = page.locator('text=keywords required');
    await expect(errorMessage).toBeVisible();
  });

  test('should display job results after search', async ({ page }) => {
    // Enter search keywords
    const keywordsInput = page.locator('input[name="keywords"]');
    await keywordsInput.fill('Software Engineer');

    // Enter location
    const locationInput = page.locator('input[name="locations"]');
    await locationInput.fill('San Francisco, CA');

    // Submit search
    const searchButton = page.locator('button[type="submit"]');
    await searchButton.click();

    // Wait for results to load
    const resultsContainer = page.locator('[data-testid="job-results"]');
    await expect(resultsContainer).toBeVisible({ timeout: 10000 });
  });
});
