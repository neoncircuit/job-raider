/**
 * Pipeline Live Monitor shows the Cloud badge when status.cloud_documents > 0.
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
    activeRunId: "run_cloud01",
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
    run_id: "run_cloud01",
    status: "completed",
    stage_progress: 100,
    jobs_scraped: 1,
    jobs_scored: 1,
    jobs_selected: 1,
    applications_submitted: 0,
    stages_planned: ["generate_resumes"],
    stages_completed: ["generate_resumes"],
    cloud_documents: 0,
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

describe("PipelinePage Cloud badge", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", QuietWebSocket);
    mockGetStatus.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows Cloud when cloud_documents is greater than 0", async () => {
    mockGetStatus.mockResolvedValue(status({ cloud_documents: 1 }));
    await openMonitor();
    expect(await screen.findByText("Cloud")).toBeInTheDocument();
  });

  it("hides Cloud when cloud_documents is 0", async () => {
    mockGetStatus.mockResolvedValue(status({ cloud_documents: 0 }));
    await openMonitor();
    expect(await screen.findByText("Complete")).toBeInTheDocument();
    expect(screen.queryByText("Cloud")).not.toBeInTheDocument();
  });
});
