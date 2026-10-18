/**
 * Job Raider - Pipeline Live Monitor Tests
 *
 * Before 2026-10-19 a failed run showed a green "Complete" badge and no
 * error, and the stage list stayed still. These tests render the monitor
 * for a run whose status poll reports failure or progress.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PipelinePage from "@/app/pipeline/page";
import type { PipelineStatusResponse } from "@/lib/types/api";

const mockGetStatus = vi.fn();

vi.mock("@/lib/api/pipeline", () => ({
  pipelineApi: {
    start: vi.fn(),
    getStatus: (...args: unknown[]) => mockGetStatus(...args),
    getHistory: vi.fn().mockResolvedValue({ runs: [] }),
    cancel: vi.fn(),
  },
}));

vi.mock("@/lib/api/jobs", () => ({
  jobsApi: {
    getSources: vi.fn().mockResolvedValue({ sources: ["linkedin"] }),
  },
}));

vi.mock("@/app/providers", () => ({
  useAppState: () => ({
    activeRunId: "run_monitor01",
    setActiveRunId: vi.fn(),
  }),
}));

vi.mock("@/lib/hooks/use-profile-targets", () => ({
  useProfileTargets: () => ({ targets: null, hasKeywords: false }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

/** WebSocket stand-in that never connects, so tests rely on the status poll. */
class QuietWebSocket {
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  /** Ignore close requests. */
  close(): void {}
}

/**
 * Build a status poll response for the monitored run.
 *
 * @param overrides - Fields to change from a running run.
 * @returns A status response.
 */
function status(
  overrides: Partial<PipelineStatusResponse>,
): PipelineStatusResponse {
  return {
    run_id: "run_monitor01",
    status: "running",
    stage_progress: 0,
    jobs_scraped: 0,
    jobs_scored: 0,
    jobs_selected: 0,
    applications_submitted: 0,
    stages_planned: ["scrape", "deduplicate", "filter_scams"],
    stages_completed: [],
    ...overrides,
  };
}

/**
 * Render the page and open the Live Monitor tab.
 *
 * @returns Resolves when the monitor tab is open.
 */
async function openMonitor(): Promise<void> {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <PipelinePage />
    </QueryClientProvider>,
  );
  await userEvent
    .setup()
    .click(screen.getByRole("tab", { name: /Live Monitor/ }));
}

describe("Pipeline Live Monitor", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", QuietWebSocket);
    mockGetStatus.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows a failed run as Failed with the backend error", async () => {
    mockGetStatus.mockResolvedValue(
      status({
        status: "failed",
        current_stage: "deduplicate",
        stages_completed: ["scrape"],
        stage_progress: 33,
        error_message: "Stage 'deduplicate' failed: scraper timed out",
      }),
    );

    await openMonitor();

    expect(await screen.findByText("Failed")).toBeInTheDocument();
    expect(screen.queryByText("Complete")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Stage 'deduplicate' failed: scraper timed out",
    );
    expect(screen.queryByText("Review on Jobs")).not.toBeInTheDocument();
  });

  it("moves the stage list and progress from the status poll", async () => {
    mockGetStatus.mockResolvedValue(
      status({
        current_stage: "deduplicate",
        stages_completed: ["scrape"],
        stage_progress: 33,
      }),
    );

    await openMonitor();

    const scrape = await screen.findByText("Scrape Jobs");
    expect(scrape.closest("[data-state]")).toHaveAttribute(
      "data-state",
      "done",
    );
    expect(
      screen.getByText("Deduplicate").closest("[data-state]"),
    ).toHaveAttribute("data-state", "active");
    expect(
      screen.getByText("Filter Scams").closest("[data-state]"),
    ).toHaveAttribute("data-state", "pending");

    expect(
      screen.getByRole("progressbar", { name: "Pipeline progress" }),
    ).toHaveAttribute("aria-valuenow", "33");
  });
});
