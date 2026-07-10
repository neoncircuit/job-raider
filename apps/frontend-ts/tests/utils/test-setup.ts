/**
 * Job Raider - Playwright Test Setup
 *
 * Global setup and fixtures for Playwright E2E tests.
 * Provides common test data and helper functions.
 *
 * Author: Job Raider
 * Date: 2026-06-08
 */

import { test as base, type Page } from "@playwright/test";

// Define custom fixtures
export const test = base.extend<{
  authenticatedPage: Page;
}>({
  authenticatedPage: async (
    { page }: { page: Page },
    provide: (page: Page) => Promise<void>,
  ) => {
    // Setup authentication if needed
    // For now, just use the page as-is
    await provide(page);
  },
});

export { expect } from "@playwright/test";

// Common test data
export const testUserData = {
  email: "test@example.com",
  password: "testpass123",
  name: "Test User",
};

export const testJobData = {
  keywords: "Software Engineer",
  location: "San Francisco, CA",
  experience_level: "Mid Level",
};
