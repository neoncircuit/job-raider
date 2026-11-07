/**
 * Tests for the onboarding checklist on the dashboard page (Step 4, MH-5).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "@/app/dashboard/page";

vi.mock("@/components/onboarding-checklist", () => ({
  OnboardingChecklist: () => <p>the checklist</p>,
}));
vi.mock("@/lib/api/health", () => ({
  healthApi: { getHealth: vi.fn().mockResolvedValue({ status: "healthy" }) },
}));
vi.mock("@/lib/api/metrics", () => ({
  metricsApi: { getSummary: vi.fn().mockReturnValue(new Promise(() => {})) },
}));
vi.mock("@/lib/api/pipeline", () => ({
  pipelineApi: {
    getHistory: vi.fn().mockResolvedValue({ runs: [], total: 0 }),
  },
}));

/**
 * Render the dashboard with a new query client.
 *
 * @returns The render result.
 */
function show() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <DashboardPage />
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("shows the checklist to a real user", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "");

    show();

    expect(await screen.findByText("the checklist")).toBeInTheDocument();
  });

  it("leaves the checklist out of the demo", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "1");

    show();

    await waitFor(() =>
      expect(screen.getByText("healthy")).toBeInTheDocument(),
    );
    expect(screen.queryByText("the checklist")).not.toBeInTheDocument();
  });
});
