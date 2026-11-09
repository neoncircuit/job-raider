/**
 * Settings: the GPU memory budget field (Step 6, MH-4).
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
 * @returns AppSettings for the Settings page.
 */
function settings(hardware?: AppSettings["hardware"]): AppSettings {
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

describe("Settings GPU memory budget", () => {
  beforeEach(() => {
    mockUpdate.mockImplementation((s: AppSettings) => Promise.resolve(s));
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the stored value and saves a new one", async () => {
    mockGet.mockResolvedValue(settings({ vram_headroom_percent: 80 }));
    const user = userEvent.setup();
    renderPage();

    const field = await screen.findByLabelText("GPU memory budget (%)");
    expect(field).toHaveValue(80);
    await user.clear(field);
    await user.type(field, "60");
    await user.click(screen.getByRole("button", { name: "Save Settings" }));

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled());
    expect(mockUpdate.mock.calls[0][0].hardware).toEqual({
      vram_headroom_percent: 60,
    });
  });

  it("uses 75 when the backend sends no hardware section", async () => {
    mockGet.mockResolvedValue(settings());
    renderPage();

    expect(await screen.findByLabelText("GPU memory budget (%)")).toHaveValue(
      75,
    );
  });

  it("refuses a value below 30", async () => {
    mockGet.mockResolvedValue(settings({ vram_headroom_percent: 75 }));
    const user = userEvent.setup();
    renderPage();

    const field = await screen.findByLabelText("GPU memory budget (%)");
    await user.clear(field);
    await user.type(field, "20");
    await user.click(screen.getByRole("button", { name: "Save Settings" }));

    // The browser's own check (min=30) stops the submit; zod is a second guard.
    expect(field).toBeInvalid();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(mockUpdate).not.toHaveBeenCalled();
  });
});
