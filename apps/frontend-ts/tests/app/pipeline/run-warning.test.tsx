/**
 * Pipeline page: the run warning box and the Request Cancel button
 * (scrape-keyword-search task).
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
    getSources: vi.fn().mockResolvedValue({ sources: ["mycareersfuture"] }),
  },
}));

vi.mock("@/app/providers", () => ({
  useAppState: () => ({
    activeRunId: "run_warn0001",
    setActiveRunId: vi.fn(),
  }),
}));

vi.mock("@/lib/hooks/use-profile-targets", () => ({
  useProfileTargets: () => ({ targets: null, hasKeywords: false }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

/** WebSocket stand-in that never connects. */
class QuietWebSocket {
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  /** Ignore close. */
  close(): void {}
}

/**
 * Build a status poll response.
 *
 * @param overrides - Fields to change.
 * @returns A status response.
 */
function status(
  overrides: Partial<PipelineStatusResponse>,
): PipelineStatusResponse {
  return {
    run_id: "run_warn0001",
    status: "completed",
    stage_progress: 100,
    jobs_scraped: 60,
    jobs_scored: 20,
    jobs_selected: 20,
    applications_submitted: 0,
    stages_planned: ["generate_resumes"],
    stages_completed: ["generate_resumes"],
    cloud_documents: 0,
    jobs_for_resumes: 0,
    resumes_generated: 0,
    ...overrides,
  };
}

/**
 * Open the Live Monitor tab.
 *
 * @returns Resolves when the monitor is open.
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

describe("PipelinePage run warning and cancel button", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", QuietWebSocket);
    mockGetStatus.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the run warning", async () => {
    mockGetStatus.mockResolvedValue(
      status({
        warning_message: "No jobs found for these keywords and sources.",
      }),
    );
    await openMonitor();
    const box = await screen.findByRole("status");
    expect(box).toHaveTextContent(
      "No jobs found for these keywords and sources.",
    );
  });

  it("shows Request Cancel while the run is running", async () => {
    mockGetStatus.mockResolvedValue(
      status({ status: "running", stage_progress: 40 }),
    );
    await openMonitor();
    expect(
      await screen.findByRole("button", { name: /Request Cancel/ }),
    ).toBeInTheDocument();
  });

  it("hides Request Cancel when the run is complete", async () => {
    mockGetStatus.mockResolvedValue(status({ status: "completed" }));
    await openMonitor();
    expect(await screen.findByText("Complete")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Request Cancel/ }),
    ).not.toBeInTheDocument();
  });
});
