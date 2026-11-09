/**
 * Job Raider - hardware fit in the Local models card (Step 6, MH-4).
 *
 * Tests cover the fit badges, the budget line, the install hint without
 * llmfit, a pull from the suggestions, the over-budget confirm dialog, and
 * the refresh button. The hardware is made up (an 8 GB GPU).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { toast } from "sonner";

import { OllamaModelsCard } from "@/components/settings/ollama-models-card";
import { ApiError } from "@/lib/api/client";
import type { HardwareFitReport, OllamaModelList } from "@/lib/types/api";

const mockList = vi.fn();
const mockPull = vi.fn();
const mockStatus = vi.fn();
const mockDelete = vi.fn();
const mockFit = vi.fn();

vi.mock("@/lib/api/settings", () => ({
  settingsApi: {
    listOllamaModels: (...a: unknown[]) => mockList(...a),
    pullOllamaModel: (...a: unknown[]) => mockPull(...a),
    getOllamaPullStatus: (...a: unknown[]) => mockStatus(...a),
    deleteOllamaModel: (...a: unknown[]) => mockDelete(...a),
    getHardwareFit: (...a: unknown[]) => mockFit(...a),
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const LIST: OllamaModelList = {
  host: "localhost:11434",
  reachable: true,
  in_use: [],
  models: [
    {
      name: "examplechat:7b",
      size: 4_680_000_000,
      parameter_size: "7B",
      quantization: "Q4_K_M",
      in_use: false,
    },
    {
      name: "examplereason:8b",
      size: 5_230_000_000,
      parameter_size: "8B",
      quantization: "Q4_K_M",
      in_use: false,
    },
  ],
};

const FIT: HardwareFitReport = {
  available: true,
  llmfit_version: "1.1.20",
  hardware: {
    has_gpu: true,
    gpu_name: "Example GPU",
    gpu_vram_gb: 8,
    total_ram_gb: 32,
  },
  headroom_percent: 75,
  budget_gb: 6,
  ollama_reachable: true,
  installed: [
    {
      name: "examplechat:7b",
      quantization: "Q4_K_M",
      need_gb: 5.35,
      label: "fits",
      source: "llmfit_plan",
    },
    {
      name: "examplereason:8b",
      quantization: "Q4_K_M",
      need_gb: 6.2,
      label: "over_budget",
      source: "llmfit_plan",
    },
  ],
  suggestions: [
    {
      ollama_name: "examplebig:8b",
      category: "General",
      params_b: 8,
      memory_required_gb: 5.9,
      score: 84,
    },
  ],
};

const OVER_BUDGET = new ApiError(
  409,
  "examplebig:8b needs about 6.4 GB of GPU memory, above your safety budget of 6.0 GB (75% of 8.0 GB). Confirm to pull it anyway.",
  {
    code: "over_budget",
    tag: "examplebig:8b",
    quantization: "Q4_K_M",
    label: "over_budget",
    need_gb: 6.4,
    budget_gb: 6,
    total_vram_gb: 8,
    headroom_percent: 75,
  },
);

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
      <OllamaModelsCard />
    </QueryClientProvider>,
  );
  return userEvent.setup();
}

/**
 * Find the table row of one model.
 *
 * @param name - Model tag.
 * @returns The row element.
 */
async function rowOf(name: string): Promise<HTMLElement> {
  const cell = await screen.findByText(name);
  return cell.closest("tr") as HTMLElement;
}

describe("OllamaModelsCard hardware fit", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue(LIST);
    mockStatus.mockResolvedValue({ status: "idle" });
    mockFit.mockResolvedValue(FIT);
  });

  it("labels each model and shows the budget", async () => {
    renderCard();

    const chat = within(await rowOf("examplechat:7b"));
    const reason = within(await rowOf("examplereason:8b"));
    expect(await chat.findByText("Fits")).toHaveAttribute(
      "title",
      "Needs about 5.3 GB (llmfit plan)",
    );
    expect(reason.getByText("Over budget")).toBeInTheDocument();
    const panel = screen.getByLabelText("Hardware fit");
    expect(panel).toHaveTextContent("Safety budget 6.0 GB of 8.0 GB");
    expect(panel).toHaveTextContent("(75%) on Example GPU");
    expect(panel).toHaveTextContent("llmfit 1.1.20");
  });

  it("explains how to install llmfit when it is missing", async () => {
    mockFit.mockResolvedValue({
      available: false,
      reason: "llmfit is not installed",
      install_hint: "Run ./setup.sh, or pip install llmfit==1.1.20",
      headroom_percent: 75,
      budget_gb: 0,
      ollama_reachable: true,
      installed: [],
      suggestions: [],
    } satisfies HardwareFitReport);
    renderCard();

    const panel = await screen.findByLabelText("Hardware fit");
    expect(panel).toHaveTextContent("optional and recommended");
    expect(panel).toHaveTextContent("llmfit is not installed");
    expect(panel).toHaveTextContent("pip install llmfit==1.1.20");
    // The models still list, with no fit label.
    const chat = within(await rowOf("examplechat:7b"));
    expect(chat.getByText("—")).toBeInTheDocument();
  });

  it("pulls a suggested model", async () => {
    mockPull.mockResolvedValue({ status: "pulling", model: "examplebig:8b" });
    const user = renderCard();

    await user.click(
      await screen.findByRole("button", { name: "Pull examplebig:8b" }),
    );

    await waitFor(() => expect(mockPull).toHaveBeenCalledWith("examplebig:8b"));
  });

  it("asks to confirm an over-budget pull, then pulls", async () => {
    mockPull
      .mockRejectedValueOnce(OVER_BUDGET)
      .mockResolvedValueOnce({ status: "pulling", model: "examplebig:8b" });
    const user = renderCard();

    await user.click(
      await screen.findByRole("button", { name: "Pull examplebig:8b" }),
    );
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("Pull examplebig:8b anyway?");
    expect(dialog).toHaveTextContent("safety budget of 6.0 GB");
    expect(toast.error).not.toHaveBeenCalled();

    await user.click(
      within(dialog).getByRole("button", { name: "Pull anyway" }),
    );

    await waitFor(() =>
      expect(mockPull).toHaveBeenLastCalledWith("examplebig:8b", true),
    );
  });

  it("does not pull when the user cancels", async () => {
    mockPull.mockRejectedValueOnce(OVER_BUDGET);
    const user = renderCard();

    await user.click(
      await screen.findByRole("button", { name: "Pull examplebig:8b" }),
    );
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() =>
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument(),
    );
    expect(mockPull).toHaveBeenCalledTimes(1);
  });

  it("runs llmfit again on refresh", async () => {
    const user = renderCard();

    await user.click(
      await screen.findByRole("button", { name: "Refresh hardware fit" }),
    );

    await waitFor(() => expect(mockFit).toHaveBeenCalledWith(true));
  });
});
