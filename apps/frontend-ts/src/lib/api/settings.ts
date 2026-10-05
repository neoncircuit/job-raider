import { request } from "./client";
import type {
  AppSettings,
  AvailableModelsResponse,
  OllamaModelList,
  OllamaPullState,
} from "@/lib/types/api";

export const settingsApi = {
  get: () => request<AppSettings>("GET", "/settings/"),

  update: (settings: AppSettings) =>
    request<AppSettings>("PUT", "/settings/", { body: settings }),

  reset: () => request<AppSettings>("POST", "/settings/reset"),

  validate: (settings: AppSettings) =>
    request<{ valid: boolean; errors: string[]; warnings: string[] }>(
      "POST",
      "/settings/validate",
      { body: settings },
    ),

  getModels: () => request<AvailableModelsResponse>("GET", "/settings/models"),

  applyOllamaDefaults: (smallModel: string, largeModel: string) =>
    request<AppSettings>("POST", "/settings/ollama-defaults", {
      body: { small_model: smallModel, large_model: largeModel },
    }),

  /** List installed Ollama models with size and in-use flags. */
  listOllamaModels: () =>
    request<OllamaModelList>("GET", "/settings/ollama/models"),

  /**
   * Start pulling an Ollama model (one at a time; 9B+ refused).
   *
   * @param model - Model tag such as ``qwen2.5:3b``.
   */
  pullOllamaModel: (model: string) =>
    request<OllamaPullState>("POST", "/settings/ollama/pull", {
      body: { model },
    }),

  /** Read progress of the current or last pull. */
  getOllamaPullStatus: () =>
    request<OllamaPullState>("GET", "/settings/ollama/pull/status"),

  /**
   * Delete an installed model that routing and RAG do not use.
   *
   * @param model - Model tag to delete.
   */
  deleteOllamaModel: (model: string) =>
    request<{ deleted: string }>(
      "DELETE",
      `/settings/ollama/models/${encodeURIComponent(model)}`,
    ),
};
