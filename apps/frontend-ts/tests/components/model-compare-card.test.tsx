/**
 * Job Raider - Model comparison card tests
 *
 * Tests cover the empty state, the saved report with winner and MLflow link,
 * the GPU confirmation before a run, running progress, and API errors.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { toast } from "sonner";
import { ModelCompareCard } from "@/components/model-compare-card";
import type { CompareReport } from "@/lib/types/api";

const mockStart = vi.fn();
const mockStatus = vi.fn();
const mockLatest = vi.fn();

vi.mock("@/lib/api/evaluation", () => ({
  evaluationApi: {
    startCompare: (...a: unknown[]) => mockStart(...a),
    getCompareStatus: (...a: unknown[]) => mockStatus(...a),
    getLatestCompare: (...a: unknown[]) => mockLatest(...a),
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const REPORT: CompareReport = {
  generated_at: "2026-10-05T12:00:00",
  winner: "qwen2.5:7b",
  mlflow: {
    run_id: "r1",
    experiment_id: "7",
    ui_url: "http://localhost:5000/#/experiments/7/runs/r1",
  },
  reports: [
    {
      model: "qwen2.5:7b",
      mean_score: 82.5,
      cases: [
        {
          case_id: "a",
          score: 85,
          is_valid: true,
          elapsed_ms: 3000,
          word_count: 250,
          preview: "",
        },
        {
          case_id: "b",
          score: 80,
          is_valid: false,
          elapsed_ms: 5000,
          word_count: 240,
          preview: "",
        },
      ],
    },
  ],
};

/**
 * Render the card inside a fresh query client.
 *
 * @returns The user-event instance.
 */
function renderCard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ModelCompareCard />
    </QueryClientProvider>,
  );
  return userEvent.setup();
}

describe("ModelCompareCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStatus.mockResolvedValue({ status: "idle" });
    mockLatest.mockResolvedValue({ report: null });
  });

  it("shows an empty state before any compare", async () => {
    renderCard();
    expect(
      await screen.findByText("No compare has run yet."),
    ).toBeInTheDocument();
  });

  it("shows the saved report, winner, and MLflow link", async () => {
    mockLatest.mockResolvedValue({ report: REPORT });
    renderCard();

    const table = await screen.findByRole("table");
    const row = within(table).getByText("qwen2.5:7b").closest("tr")!;
    expect(row).toHaveTextContent("Winner");
    expect(row).toHaveTextContent("82.5");
    expect(row).toHaveTextContent("1 of 2");
    expect(row).toHaveTextContent("4.0 s");
    expect(
      screen.getByRole("link", { name: /open in mlflow/i }),
    ).toHaveAttribute("href", REPORT.mlflow!.ui_url);
  });

  it("asks for confirmation before starting a run", async () => {
    mockStart.mockResolvedValue({ status: "running", total: null });
    const user = renderCard();
    await screen.findByText("No compare has run yet.");

    await user.click(screen.getByRole("button", { name: /run compare/i }));
    expect(mockStart).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent(/GPU/);

    await user.click(
      within(dialog).getByRole("button", { name: /run compare/i }),
    );
    await waitFor(() => expect(mockStart).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Starting…")).toBeInTheDocument();
  });

  it("shows progress and disables the button while running", async () => {
    mockStatus.mockResolvedValue({
      status: "running",
      current_model: "qwen3.5:4b",
      current_case: "backend_python",
      done: 4,
      total: 6,
    });
    renderCard();

    expect(
      await screen.findByText(
        "Running qwen3.5:4b, case backend_python (5 of 6)",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run compare/i })).toBeDisabled();
  });

  it("shows the API guard message when start fails", async () => {
    mockStart.mockRejectedValue(new Error("Not installed: qwen3.5:4b"));
    const user = renderCard();
    await screen.findByText("No compare has run yet.");

    await user.click(screen.getByRole("button", { name: /run compare/i }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(
      within(dialog).getByRole("button", { name: /run compare/i }),
    );

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        expect.stringContaining("qwen3.5:4b"),
      ),
    );
  });

  it("shows the last failure", async () => {
    mockStatus.mockResolvedValue({ status: "failed", error: "gpu gone" });
    renderCard();
    expect(await screen.findByRole("alert")).toHaveTextContent("gpu gone");
  });
});
