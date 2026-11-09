/**
 * Job Raider - Local models table on a phone.
 *
 * On a narrow screen the table hides the Parameters column, keeps the size
 * on one line, and lets a long model name wrap, so the Fit badge and the
 * delete button stay on the screen. The layout itself is checked by the
 * Mobile Chrome E2E test in tests/e2e/hardware-fit.spec.ts.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { OllamaModelsCard } from "@/components/settings/ollama-models-card";
import type { OllamaModelList } from "@/lib/types/api";

const mockList = vi.fn();

vi.mock("@/lib/api/settings", () => ({
  settingsApi: {
    listOllamaModels: (...a: unknown[]) => mockList(...a),
    pullOllamaModel: vi.fn(),
    getOllamaPullStatus: vi.fn().mockResolvedValue({ status: "idle" }),
    deleteOllamaModel: vi.fn(),
    getHardwareFit: vi.fn().mockRejectedValue(new Error("no llmfit")),
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
      name: "qwen2.5-coder-7b-16k:latest",
      size: 4_680_000_000,
      parameter_size: "7.6B",
      in_use: false,
    },
  ],
};

describe("OllamaModelsCard on a phone", () => {
  beforeEach(() => {
    mockList.mockResolvedValue(LIST);
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <OllamaModelsCard />
      </QueryClientProvider>,
    );
  });

  it("hides the Parameters column below the sm breakpoint", async () => {
    await screen.findByText("qwen2.5-coder-7b-16k:latest");
    const header = screen.getByRole("columnheader", { name: "Parameters" });
    expect(header).toHaveClass("hidden", "sm:table-cell");
    expect(screen.getByText("7.6B").closest("td")).toHaveClass(
      "hidden",
      "sm:table-cell",
    );
  });

  it("keeps the size on one line and lets a long name wrap", async () => {
    const name = await screen.findByText("qwen2.5-coder-7b-16k:latest");
    expect(name.closest("td")).toHaveClass("break-all");
    expect(screen.getByText("4.4 GB").closest("td")).toHaveClass(
      "whitespace-nowrap",
    );
  });
});
