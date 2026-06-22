/**
 * Job Raider - E2E API Mock Layer
 *
 * Intercepts every `/api/proxy/**` request made by the browser during E2E
 * tests and fulfills it with synthetic fixture data, so the suite never
 * depends on a live backend (which CI does not start).
 *
 * Interception happens at the Playwright network layer via `page.route()`,
 * so requests are answered before they ever reach the Next.js proxy route
 * handler — the backend is never contacted.
 */

import type { Page, Route } from "@playwright/test";

import { sampleJobs, sampleProfile } from "../../setup/fixtures";

/** Synthetic health payload (shape consumed by `src/app/dashboard/page.tsx`). */
const mockHealth = {
  status: "healthy",
  checks: [{ name: "backend", status: "healthy", message: "ok" }],
};

/** Synthetic metrics-summary payload (shape consumed by the dashboard stat cards). */
const mockMetricsSummary = {
  outcomes: { total_applications: 5, interview_rate: 0.2, offers: 1 },
  cost: { total_usd: 1.23, per_application: 0.25, local_usage_percent: 95 },
};

/** Synthetic pipeline-history payload (shape consumed by the dashboard "Recent Runs" card). */
const mockPipelineHistory = {
  runs: [
    {
      run_id: "r1",
      jobs_scraped: 12,
      jobs_applied: 3,
      created_at: "2026-06-20T10:00:00Z",
      status: "completed",
    },
  ],
};

/**
 * Register route handlers that fulfill `/api/proxy/**` requests with mocked
 * responses. Must be called before the page navigates, so it is applied by
 * the custom `page` fixture in `support/test.ts`.
 *
 * @param page - The Playwright page whose network traffic to mock.
 * @returns A promise that resolves once the catch-all route is registered.
 */
export async function mockApi(page: Page): Promise<void> {
  await page.route("**/api/proxy/**", async (route: Route) => {
    const request = route.request();
    // Strip the `/api/proxy` prefix so the switch reads clean backend paths.
    const path = new URL(request.url()).pathname.replace(/^\/api\/proxy/, "");
    const key = `${request.method()} ${path}`;

    switch (key) {
      case "POST /jobs/search":
        return route.fulfill({
          status: 200,
          json: { total: sampleJobs.length, jobs: sampleJobs },
        });
      case "GET /health":
        return route.fulfill({ status: 200, json: mockHealth });
      case "GET /metrics/summary":
        return route.fulfill({ status: 200, json: mockMetricsSummary });
      case "GET /pipeline/history":
        return route.fulfill({ status: 200, json: mockPipelineHistory });
      case "GET /jobs/sources":
        return route.fulfill({ status: 200, json: { sources: ["linkedin", "jsearch"] } });
      case "GET /profile":
        return route.fulfill({ status: 200, json: sampleProfile });
      default:
        // Safety net: any unmapped proxied call returns an empty 200 so an
        // unanticipated endpoint surfaces as a render gap rather than a crash.
        return route.fulfill({ status: 200, json: {} });
    }
  });
}
