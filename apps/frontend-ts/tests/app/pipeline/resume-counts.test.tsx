/**
 * Pipeline Live Monitor shows the jobs selected for resumes and the resumes
 * generated (monitor resume count, MH-2).
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
    activeRunId: "run_counts01",
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
    run_id: "run_counts01",
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

describe("PipelinePage resume line", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", QuietWebSocket);
    mockGetStatus.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the jobs selected for resumes and the resumes generated", async () => {
    mockGetStatus.mockResolvedValue(
      status({ jobs_for_resumes: 2, resumes_generated: 2 }),
    );
    await openMonitor();
    expect(
      await screen.findByText(
        "Resumes: 2 jobs selected (Max Jobs) · 2 generated",
      ),
    ).toBeInTheDocument();
  });

  it("says job for one job", async () => {
    mockGetStatus.mockResolvedValue(
      status({ jobs_for_resumes: 1, resumes_generated: 0 }),
    );
    await openMonitor();
    expect(
      await screen.findByText(
        "Resumes: 1 job selected (Max Jobs) · 0 generated",
      ),
    ).toBeInTheDocument();
  });

  it("hides the resume line when no job was selected for resumes", async () => {
    mockGetStatus.mockResolvedValue(status({ jobs_for_resumes: 0 }));
    await openMonitor();
    expect(await screen.findByText("Complete")).toBeInTheDocument();
    expect(screen.queryByText(/^Resumes:/)).not.toBeInTheDocument();
  });
});
