/**
 * Job Raider - E2E Custom Test Fixture
 *
 * Extends Playwright's base `test` so that the built-in `page` fixture
 * automatically has the `/api/proxy/**` mock layer (see `./mock-api`)
 * applied before it is handed to any spec. Specs import `test` and
 * `expect` from here instead of from `@playwright/test`.
 *
 * A spec that needs a different response for a specific endpoint can call
 * `page.route(...)` itself; the most recently registered handler wins, so a
 * spec-level route overrides the catch-all mock for that test.
 */

import { test as base, expect } from "@playwright/test";

import { mockApi } from "./mock-api";

export const test = base.extend({
  // Override the framework `page` fixture to install the mock first.
  // The callback param is named `provide` (not `use`) to avoid a
  // react-hooks/rules-of-hooks false positive — the linter treats an argument
  // literally named `use` as a React Hook call. Same convention as
  // tests/utils/test-setup.ts.
  page: async ({ page }, provide) => {
    await mockApi(page);
    page.on("console", (msg) => {
      console.log(`[PAGE] ${msg.type()}: ${msg.text()}`);
    });
    await provide(page);
  },
});

export { expect };
