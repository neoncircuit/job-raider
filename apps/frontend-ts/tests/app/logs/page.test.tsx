/**
 * Job Raider - Logs Page Tests
 *
 * Tests cover record rendering, filter wiring (level, component, debounced
 * search), the empty state, the error banner, and copy to clipboard.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LogsPage from "@/app/logs/page";
import type { LogsResponse } from "@/lib/types/api";

const mockGet = vi.fn();

vi.mock("@/lib/api/logs", () => ({
  logsApi: { get: (...a: unknown[]) => mockGet(...a) },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const RESPONSE: LogsResponse = {
  capacity: 2000,
  latest_seq: 2,
  loggers: ["job_raider.llm", "job_raider.pipeline"],
  records: [
    {
      seq: 1,
      timestamp: "2026-10-05T10:00:00",
      level: "INFO",
      logger: "job_raider.pipeline",
      message: "stage scrape done",
    },
    {
      seq: 2,
      timestamp: "2026-10-05T10:00:01",
      level: "ERROR",
      logger: "job_raider.llm",
      message: "ollama timeout",
    },
  ],
};

/**
 * Render the page inside a fresh query client.
 *
 * @returns The user-event instance.
 */
function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <LogsPage />
    </QueryClientProvider>,
  );
  return userEvent.setup();
}

/**
 * Return the filters from the most recent ``logsApi.get`` call.
 *
 * @returns The query object.
 */
function lastQuery(): Record<string, unknown> {
  return mockGet.mock.calls.at(-1)?.[0] as Record<string, unknown>;
}

describe("LogsPage", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockGet.mockResolvedValue(RESPONSE);
  });

  it("renders records with level and logger", async () => {
    renderPage();

    expect(await screen.findByText("ollama timeout")).toBeInTheDocument();
    expect(screen.getByText("stage scrape done")).toBeInTheDocument();
    expect(within(screen.getByRole("log")).getByText("ERROR")).toHaveClass(
      "text-destructive",
    );
    expect(lastQuery()).toMatchObject({ level: "INFO", component: "", q: "" });
  });

  it("passes level and component filters to the API", async () => {
    const user = renderPage();
    await screen.findByText("ollama timeout");

    await user.selectOptions(screen.getByLabelText("Lowest level"), "ERROR");
    await waitFor(() => expect(lastQuery()).toMatchObject({ level: "ERROR" }));

    await user.selectOptions(
      screen.getByLabelText("Component"),
      "job_raider.llm",
    );
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ component: "job_raider.llm" }),
    );
  });

  it("debounces the search text", async () => {
    const user = renderPage();
    await screen.findByText("ollama timeout");

    await user.type(screen.getByLabelText("Search"), "timeout");
    await waitFor(() => expect(lastQuery()).toMatchObject({ q: "timeout" }));
    const searchCalls = mockGet.mock.calls.filter(
      (c) => (c[0] as { q: string }).q !== "",
    );
    expect(searchCalls).toHaveLength(1);
  });

  it("shows an empty state when nothing matches", async () => {
    mockGet.mockResolvedValue({ ...RESPONSE, records: [] });
    renderPage();

    expect(
      await screen.findByText("No matching log records"),
    ).toBeInTheDocument();
  });

  it("shows an error banner when loading fails", async () => {
    mockGet.mockRejectedValue(new Error("backend down"));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not load logs: backend down",
    );
  });

  it("copies the visible lines", async () => {
    const user = renderPage();
    const writeText = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockResolvedValue();
    await screen.findByText("ollama timeout");

    await user.click(screen.getByRole("button", { name: /Copy/ }));

    expect(writeText).toHaveBeenCalledWith(
      "2026-10-05T10:00:00 INFO job_raider.pipeline - stage scrape done\n" +
        "2026-10-05T10:00:01 ERROR job_raider.llm - ollama timeout",
    );
  });
});
