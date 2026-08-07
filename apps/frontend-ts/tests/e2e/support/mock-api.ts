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

import {
  sampleJobs,
  sampleProfile,
  sampleCoverLetter,
  sampleCoverLetterValidation,
} from "../../setup/fixtures";

/** Synthetic resource snapshot for the sidebar meter. */
const mockResources = {
  cpu: { percent: 18.0 },
  ram: { used_mb: 4096.0, total_mb: 16384.0, percent: 25.0 },
  gpu: {
    name: "Mock GPU",
    utilization_percent: 12.0,
    memory_used_mb: 1024,
    memory_total_mb: 8192,
    memory_percent: 12.5,
    temperature_celsius: 45.0,
  },
};

const mockHealth = {
  status: "healthy",
  checks: [{ name: "backend", status: "healthy", message: "ok" }],
};

/** Synthetic metrics-summary payload (shape consumed by the dashboard stat cards). */
const mockMetricsSummary = {
  outcomes: {
    total_applications: 5,
    screening_rate: 0.2,
    offer_rate: 0.1,
    acceptance_rate: 0.05,
  },
  cost: {
    total_usd: 1.23,
    per_application: 0.25,
    local_usage_percent: 95,
    total_calls: 120,
  },
  health: { healthy: 4, degraded: 0, unhealthy: 0 },
  recent_calls: [],
};

/** Synthetic settings payload (shape consumed by `src/app/settings/page.tsx`). */
const mockSettings = {
  routing: {
    default: {
      primary_provider: "ollama",
      primary_model: "qwen2.5:7b",
      fallback_provider: "anthropic",
      fallback_model: "claude-3-5-sonnet-20241022",
    },
  },
  api_config: {
    anthropic_api_key: null,
    gemini_api_key: null,
    cloud_fallback_provider: "anthropic",
    ollama_host: "http://localhost:11434",
  },
  model_params: {
    temperature: 0.7,
    max_tokens: 4096,
    top_p: 0.9,
  },
  cost_limits: {
    max_api_cost_per_run: 5.0,
    enable_cache: true,
    cache_ttl: 3600,
    enable_jd_llm_extract: false,
    enable_prompt_cache: false,
    ollama_keep_alive: null,
  },
  updated_at: "2026-06-28T12:00:00Z",
  version: "0.1.0",
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

    if (key.startsWith("POST /jobs/") && key.endsWith("/cover-letter")) {
      return route.fulfill({
        status: 200,
        json: {
          success: true,
          job_id: path.split("/")[2] ?? "job-1",
          cover_letter: sampleCoverLetter,
          validation: sampleCoverLetterValidation,
        },
      });
    }

    switch (key) {
      case "POST /jobs/search":
        return route.fulfill({
          status: 200,
          json: { total: sampleJobs.length, jobs: sampleJobs },
        });
      case "GET /health":
        return route.fulfill({ status: 200, json: mockHealth });
      case "GET /health/resources":
        return route.fulfill({ status: 200, json: mockResources });
      case "GET /metrics/summary":
        return route.fulfill({ status: 200, json: mockMetricsSummary });
      case "GET /pipeline/history":
        return route.fulfill({ status: 200, json: mockPipelineHistory });
      case "GET /jobs/sources":
        return route.fulfill({
          status: 200,
          json: { sources: ["linkedin", "jsearch"] },
        });
      case "GET /settings":
      case "GET /settings/":
        return route.fulfill({ status: 200, json: mockSettings });
      case "GET /profile":
        return route.fulfill({ status: 200, json: sampleProfile });
      case "POST /profile/analyze-linkedin":
        return route.fulfill({
          status: 200,
          json: {
            overall_score: 76,
            summary: "Strong LinkedIn profile with clear positioning.",
            section_scores: [],
            insights: [],
            keyword_recommendations: ["TypeScript", "React", "FastAPI"],
            action_plan: ["Add more quantified achievements"],
            generated_headline_options: [],
            summary_rewrite_suggestions: [],
            competitive_edge: "Solid technical breadth",
            is_strong_profile: true,
            high_priority_insights: [],
            weighted_overall_score: 76,
            metadata: {},
            analyzed_at: "2026-06-28T12:00:00Z",
          },
        });
      case "POST /profile/search-linkedin":
        return route.fulfill({
          status: 200,
          json: {
            query: { keywords: "engineer" },
            total: 1,
            results: [
              {
                name: "Alex Smith",
                headline: "Senior Engineer",
                profile_url: "https://www.linkedin.com/in/alexsmith",
                location: "Remote",
              },
            ],
          },
        });
      case "GET /assessment/skills":
        return route.fulfill({
          status: 200,
          json: { skills: ["JavaScript", "TypeScript", "React", "Python"] },
        });
      default:
        // Safety net: any unmapped proxied call returns an empty 200 so an
        // unanticipated endpoint surfaces as a render gap rather than a crash.
        return route.fulfill({ status: 200, json: {} });
    }
  });
}
