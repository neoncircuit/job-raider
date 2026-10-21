/**
 * Settings: Remove saved key calls settingsApi.deleteApiKey.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SettingsPage from "@/app/settings/page";
import type { AppSettings } from "@/lib/types/api";

const mockDeleteApiKey = vi.fn();
const mockGet = vi.fn();

vi.mock("@/lib/api/settings", () => ({
  settingsApi: {
    get: (...args: unknown[]) => mockGet(...args),
    update: vi.fn(),
    reset: vi.fn(),
    validate: vi.fn(),
    getModels: vi.fn().mockResolvedValue({
      ollama: ["qwen2.5:3b", "qwen2.5:7b"],
      ollama_installed: ["qwen2.5:3b", "qwen2.5:7b"],
      recommended: { small: "qwen2.5:3b", large: "qwen2.5:7b" },
    }),
    applyOllamaDefaults: vi.fn(),
    listOllamaModels: vi.fn().mockResolvedValue({ models: [] }),
    pullOllamaModel: vi.fn(),
    getOllamaPullStatus: vi.fn().mockResolvedValue({ status: "idle" }),
    deleteOllamaModel: vi.fn(),
    deleteApiKey: (...args: unknown[]) => mockDeleteApiKey(...args),
  },
  omitBlankApiKeys: (s: AppSettings) => s,
}));

vi.mock("@/components/settings/cinematic-atmosphere-toggle", () => ({
  CinematicAtmosphereToggle: () => null,
}));

vi.mock("@/components/settings/ollama-models-card", () => ({
  OllamaModelsCard: () => null,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

/**
 * Minimal settings payload with a saved Anthropic key.
 *
 * @returns AppSettings for the Settings page.
 */
function settingsWithAnthropicKey(): AppSettings {
  return {
    routing: {
      default: {
        primary_provider: "ollama",
        primary_model: "qwen2.5:7b",
        fallback_provider: "anthropic",
        fallback_model: "claude-3-5-sonnet-20241022",
      },
    },
    api_config: {
      has_anthropic_key: true,
      has_gemini_key: false,
      cloud_fallback_provider: "anthropic",
      ollama_host: "http://localhost:11434",
    },
    model_params: { temperature: 0.7, max_tokens: 4096, top_p: 0.9 },
    cost_limits: {
      max_api_cost_per_run: 5,
      enable_cache: true,
      cache_ttl: 3600,
    },
    updated_at: "2026-10-21T00:00:00Z",
    version: "0.1.0",
  };
}

/**
 * Render the Settings page under a fresh query client.
 *
 * @returns Testing Library render result.
 */
function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SettingsPage />
    </QueryClientProvider>,
  );
}

describe("Settings remove saved API key", () => {
  beforeEach(() => {
    mockGet.mockResolvedValue(settingsWithAnthropicKey());
    mockDeleteApiKey.mockResolvedValue({
      ...settingsWithAnthropicKey(),
      api_config: {
        ...settingsWithAnthropicKey().api_config,
        has_anthropic_key: false,
      },
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("calls deleteApiKey(anthropic) when Remove saved key is clicked", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Key saved");
    await user.click(screen.getByRole("button", { name: "Remove saved key" }));

    await waitFor(() => {
      expect(mockDeleteApiKey).toHaveBeenCalledWith("anthropic");
    });
  });
});
