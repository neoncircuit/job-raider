/**
 * Job Raider - Local models (Ollama) card tests
 *
 * Tests cover the installed list with in-use guard, unreachable Ollama,
 * pull progress, guard messages from the API, and delete confirmation.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { toast } from "sonner";
import { OllamaModelsCard } from "@/components/settings/ollama-models-card";
import type { OllamaModelList } from "@/lib/types/api";

const mockList = vi.fn();
const mockPull = vi.fn();
const mockStatus = vi.fn();
const mockDelete = vi.fn();

vi.mock("@/lib/api/settings", () => ({
  settingsApi: {
    listOllamaModels: (...a: unknown[]) => mockList(...a),
    pullOllamaModel: (...a: unknown[]) => mockPull(...a),
    getOllamaPullStatus: (...a: unknown[]) => mockStatus(...a),
    deleteOllamaModel: (...a: unknown[]) => mockDelete(...a),
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const LIST: OllamaModelList = {
  host: "host.docker.internal:11434",
  reachable: true,
  in_use: ["qwen2.5:3b", "nomic-embed-text"],
  models: [
    {
      name: "phi3:mini",
      size: 2 * 1024 ** 3,
      parameter_size: "3.8B",
      in_use: false,
    },
    {
      name: "qwen2.5:3b",
      size: 1.9 * 1024 ** 3,
      parameter_size: "3.1B",
      in_use: true,
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
      <OllamaModelsCard />
    </QueryClientProvider>,
  );
  return userEvent.setup();
}

describe("OllamaModelsCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue(LIST);
    mockStatus.mockResolvedValue({ status: "idle" });
  });

  it("lists models and only offers delete for unused ones", async () => {
    renderCard();

    expect(await screen.findByText("phi3:mini")).toBeInTheDocument();
    expect(screen.getByText("2.0 GB")).toBeInTheDocument();
    expect(screen.getByText("In use")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete phi3:mini" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Delete qwen2.5:3b" }),
    ).not.toBeInTheDocument();
  });

  it("shows a banner when Ollama is unreachable", async () => {
    mockList.mockResolvedValue({ ...LIST, reachable: false, models: [] });
    renderCard();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ollama is not reachable",
    );
  });

  it("shows progress while a pull runs", async () => {
    mockStatus.mockResolvedValue({
      status: "pulling",
      model: "gemma3:4b",
      message: "downloading",
      completed: 1024 ** 3,
      total: 2 * 1024 ** 3,
    });
    renderCard();

    expect(
      await screen.findByText(/Pulling gemma3:4b: downloading/),
    ).toBeInTheDocument();
    expect(screen.getByText(/1\.0 GB of 2\.0 GB/)).toBeInTheDocument();
    expect(screen.getByLabelText("Pull a model")).toBeDisabled();
  });

  it("starts a pull with the typed tag", async () => {
    mockPull.mockResolvedValue({ status: "pulling", model: "gemma3:4b" });
    const user = renderCard();

    await user.type(screen.getByLabelText("Pull a model"), "gemma3:4b");
    await user.click(screen.getByRole("button", { name: /Pull/ }));

    await waitFor(() => expect(mockPull).toHaveBeenCalledWith("gemma3:4b"));
  });

  it("shows the API guard message when a pull is refused", async () => {
    mockPull.mockRejectedValue(
      new Error("gemma3:12b is about 12B parameters. Models of 9B ..."),
    );
    const user = renderCard();

    await user.type(screen.getByLabelText("Pull a model"), "gemma3:12b");
    await user.click(screen.getByRole("button", { name: /Pull/ }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        expect.stringContaining("12B parameters"),
      ),
    );
  });

  it("deletes only after confirmation", async () => {
    mockDelete.mockResolvedValue({ deleted: "phi3:mini" });
    const user = renderCard();

    await user.click(
      await screen.findByRole("button", { name: "Delete phi3:mini" }),
    );
    expect(mockDelete).not.toHaveBeenCalled();
    await user.click(await screen.findByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith("phi3:mini"));
  });
});
