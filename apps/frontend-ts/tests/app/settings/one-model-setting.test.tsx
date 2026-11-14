/**
 * Settings: the "One local model at a time" switch (one-model-at-a-time task).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SettingsPage from "@/app/settings/page";
import type { AppSettings } from "@/lib/types/api";

const mockGet = vi.fn();
const mockUpdate = vi.fn();

vi.mock("@/lib/api/settings", () => ({
  settingsApi: {
    get: (...args: unknown[]) => mockGet(...args),
    update: (...args: unknown[]) => mockUpdate(...args),
    reset: vi.fn(),
    validate: vi.fn(),
    getModels: vi.fn().mockResolvedValue({
      ollama: ["qwen2.5:3b", "qwen2.5:7b"],
      ollama_installed: ["qwen2.5:3b", "qwen2.5:7b"],
      recommended: { small: "qwen2.5:3b", large: "qwen2.5:7b" },
    }),
    applyOllamaDefaults: vi.fn(),
    deleteApiKey: vi.fn(),
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
 * Minimal settings payload.
 *
 * @param hardware - Hardware section, or undefined for an old backend.
 * @param oneModel - The one-model setting, or undefined for an old backend.
 * @returns AppSettings for the Settings page.
 */
function settings(
  hardware?: AppSettings["hardware"],
  oneModel?: boolean,
): AppSettings {
  return {
    routing: {
      default: {
        primary_provider: "ollama",
        primary_model: "qwen2.5:7b",
        fallback_provider: null,
        fallback_model: null,
      },
    },
    api_config: {
      has_anthropic_key: false,
      has_gemini_key: false,
      cloud_fallback_provider: "none",
      ollama_host: "http://localhost:11434",
    },
    model_params: { temperature: 0.7, max_tokens: 4096, top_p: 0.9 },
    cost_limits: {
      max_api_cost_per_run: 5,
      enable_cache: true,
      cache_ttl: 3600,
      ...(oneModel === undefined
        ? {}
        : { ollama_one_model_at_a_time: oneModel }),
    },
    ...(hardware ? { hardware } : {}),
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

describe("Settings one local model at a time", () => {
  beforeEach(() => {
    mockUpdate.mockImplementation((s: AppSettings) => Promise.resolve(s));
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("is on when the backend sends no value", async () => {
    mockGet.mockResolvedValue(settings());
    renderPage();
    const toggle = await screen.findByRole("switch", {
      name: "One local model at a time",
    });
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("shows a stored off value", async () => {
    mockGet.mockResolvedValue(settings(undefined, false));
    renderPage();
    const toggle = await screen.findByRole("switch", {
      name: "One local model at a time",
    });
    expect(toggle).toHaveAttribute("aria-checked", "false");
  });

  it("saves the switch turned off", async () => {
    mockGet.mockResolvedValue(settings(undefined, true));
    const user = userEvent.setup();
    renderPage();
    await user.click(
      await screen.findByRole("switch", { name: "One local model at a time" }),
    );
    await user.click(screen.getByRole("button", { name: "Save Settings" }));
    await waitFor(() => expect(mockUpdate).toHaveBeenCalled());
    expect(
      mockUpdate.mock.calls[0][0].cost_limits.ollama_one_model_at_a_time,
    ).toBe(false);
  });
});
