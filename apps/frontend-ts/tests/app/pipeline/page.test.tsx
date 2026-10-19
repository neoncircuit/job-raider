/**
 * Job Raider - Pipeline Page Start Form Tests
 *
 * Tests cover the advanced options payload:
 * - Discover defaults (no stop stage, no submission pacing)
 * - Fresh graduate scoring and stop stage
 * - Full-mode submission delay and hourly cap
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PipelinePage from "@/app/pipeline/page";

const mockStart = vi.fn();

vi.mock("@/lib/api/pipeline", () => ({
  pipelineApi: {
    start: (...args: unknown[]) => mockStart(...args),
    getStatus: vi.fn(),
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
  useAppState: () => ({ activeRunId: null, setActiveRunId: vi.fn() }),
}));

vi.mock("@/lib/hooks/use-profile-targets", () => ({
  useProfileTargets: () => ({ targets: null, hasKeywords: false }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

/**
 * Render the Pipeline page inside a fresh query client.
 *
 * @returns The user-event instance for interactions.
 */
function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <PipelinePage />
    </QueryClientProvider>,
  );
  return userEvent.setup();
}

/**
 * Return the payload of the first ``pipelineApi.start`` call.
 *
 * @returns The request object sent to the API.
 */
async function startPayload(): Promise<Record<string, unknown>> {
  await waitFor(() => expect(mockStart).toHaveBeenCalled());
  return mockStart.mock.calls[0][0] as Record<string, unknown>;
}

describe("PipelinePage start form", () => {
  beforeEach(() => {
    mockStart.mockReset();
    mockStart.mockResolvedValue({ run_id: "run-1234567890" });
  });

  it("sends discover defaults without submission pacing", async () => {
    const user = renderPage();
    await user.type(screen.getByPlaceholderText(/Python, FastAPI/), "Python");
    await user.click(screen.getByRole("button", { name: /Start Discover/i }));

    const payload = await startPayload();
    expect(payload).toMatchObject({
      mode: "discover",
      fresh_grad_mode: false,
      stop_at: null,
      dry_run: true,
    });
    expect(payload).not.toHaveProperty("submission_delay");
    expect(payload).not.toHaveProperty("max_submissions_per_hour");
  });

  it("keeps multi-word keywords and locations whole", async () => {
    const user = renderPage();
    await user.type(
      screen.getByPlaceholderText(/Python, FastAPI/),
      "python engineer, machine learning",
    );
    const locations = screen.getByPlaceholderText(/Singapore, Remote/);
    await user.clear(locations);
    await user.type(locations, "New York, Remote");
    await user.click(screen.getByRole("button", { name: /Start Discover/i }));

    expect(await startPayload()).toMatchObject({
      keywords: ["python engineer", "machine learning"],
      locations: ["New York", "Remote"],
    });
  });

  it("offers only discover stages in discover mode", () => {
    renderPage();
    const select = screen.getByLabelText("Stop after stage");
    const values = Array.from(
      select.querySelectorAll("option"),
      (o) => o.value,
    );
    expect(values).toContain("rag_rank");
    expect(values).not.toContain("submit_applications");
  });

  it("sends fresh graduate scoring and the chosen stop stage", async () => {
    const user = renderPage();
    await user.type(screen.getByPlaceholderText(/Python, FastAPI/), "Python");
    await user.click(
      screen.getByRole("switch", { name: /Fresh graduate scoring/i }),
    );
    await user.selectOptions(
      screen.getByLabelText("Stop after stage"),
      "score_and_rank",
    );
    await user.click(screen.getByRole("button", { name: /Start Discover/i }));

    expect(await startPayload()).toMatchObject({
      fresh_grad_mode: true,
      stop_at: "score_and_rank",
    });
  });

  it("sends submission delay and hourly cap in full mode", async () => {
    const user = renderPage();
    await user.type(screen.getByPlaceholderText(/Python, FastAPI/), "Python");
    await user.click(screen.getByLabelText(/Full pipeline/i));

    const delay = screen.getByLabelText(/Delay between submissions/i);
    await user.clear(delay);
    await user.type(delay, "5");
    const cap = screen.getByLabelText(/Max submissions per hour/i);
    await user.clear(cap);
    await user.type(cap, "7");
    await user.click(
      screen.getByRole("button", { name: /Start Full Pipeline/i }),
    );

    expect(await startPayload()).toMatchObject({
      mode: "full",
      submission_delay: 5,
      max_submissions_per_hour: 7,
    });
  });

  it("blocks submit when the hourly cap is out of range", async () => {
    const user = renderPage();
    await user.type(screen.getByPlaceholderText(/Python, FastAPI/), "Python");
    await user.click(screen.getByLabelText(/Full pipeline/i));

    const cap = screen.getByLabelText(/Max submissions per hour/i);
    await user.clear(cap);
    await user.type(cap, "500");
    await user.click(
      screen.getByRole("button", { name: /Start Full Pipeline/i }),
    );

    await new Promise((r) => setTimeout(r, 50));
    expect(mockStart).not.toHaveBeenCalled();
  });
});
