/**
 * Tests for the Metrics page token counts and unknown cost display.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MetricsPage from "@/app/metrics/page";
import type { MetricsSummaryResponse } from "@/lib/types/api";

const mockGetSummary = vi.fn();

vi.mock("@/lib/api/metrics", () => ({
  metricsApi: { getSummary: () => mockGetSummary() },
}));

vi.mock("@/components/agent-system-card", () => ({
  AgentSystemCard: () => null,
}));

vi.mock("@/components/model-compare-card", () => ({
  ModelCompareCard: () => null,
}));

const SUMMARY: MetricsSummaryResponse = {
  cost: {
    total_usd: null,
    per_application: null,
    total_calls: 2,
    local_usage_percent: 100,
    prompt_tokens: 10,
    completion_tokens: 5,
    total_tokens: 15,
    estimated_counts: 1,
    last_run: {
      run_id: "run-42",
      end_time: "2026-10-27T01:00:00Z",
      calls: 2,
      total_tokens: 15,
    },
  },
  outcomes: {
    total_applications: 0,
    screening_rate: 0,
    offer_rate: 0,
    acceptance_rate: 0,
  },
  health: { status: "healthy", healthy: 1, degraded: 0, unhealthy: 0 },
  recent_calls: [
    {
      task_type: "selection",
      provider: "ollama",
      model: "qwen2.5:3b",
      cost_usd: null,
      timestamp: "2026-10-27T01:00:00Z",
      total_tokens: 15,
      tokens_estimated: true,
      cache_hit: false,
      fallback: false,
      error: false,
    },
  ],
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MetricsPage />
    </QueryClientProvider>,
  );
}

describe("MetricsPage", () => {
  beforeEach(() => {
    mockGetSummary.mockReset();
    mockGetSummary.mockResolvedValue(SUMMARY);
  });

  it("shows token counts, last run, and unknown cost", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Total Tokens")).toBeInTheDocument();
    });
    expect(screen.getAllByText("15").length).toBeGreaterThan(0);
    expect(screen.getByText("run-42")).toBeInTheDocument();
    expect(screen.getAllByText("unknown").length).toBeGreaterThan(0);
    expect(screen.getByText("est.")).toBeInTheDocument();
  });
});
