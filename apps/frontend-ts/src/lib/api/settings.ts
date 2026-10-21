import { request } from "./client";
import type {
  AppSettings,
  AvailableModelsResponse,
  OllamaModelList,
  OllamaPullState,
} from "@/lib/types/api";

/**
 * Strip blank API key fields so PUT does not send empty strings.
 *
 * Only include a key when the user typed a non-empty value. The backend
 * keeps the stored key when the field is omitted or null.
 *
 * @param settings - Full settings payload about to be saved or validated.
 * @returns A shallow-copied settings object with blank keys removed.
 */
export function omitBlankApiKeys(settings: AppSettings): AppSettings {
  const api = { ...settings.api_config };
  const anthropic = api.anthropic_api_key?.trim();
  const gemini = api.gemini_api_key?.trim();
  if (anthropic) {
    api.anthropic_api_key = anthropic;
  } else {
    delete api.anthropic_api_key;
  }
  if (gemini) {
    api.gemini_api_key = gemini;
  } else {
    delete api.gemini_api_key;
  }
  return { ...settings, api_config: api };
}

export const settingsApi = {
  get: () => request<AppSettings>("GET", "/settings/"),

  update: (settings: AppSettings) =>
    request<AppSettings>("PUT", "/settings/", {
      body: omitBlankApiKeys(settings),
    }),

  reset: () => request<AppSettings>("POST", "/settings/reset"),

  /**
   * Clear a stored cloud API key (``anthropic`` or ``gemini``).
   *
   * @param provider - Which saved key to remove.
   * @returns Updated settings after the key is cleared.
   */
  deleteApiKey: (provider: "anthropic" | "gemini") =>
    request<AppSettings>(
      "DELETE",
      `/settings/api-keys/${encodeURIComponent(provider)}`,
    ),

  validate: (settings: AppSettings) =>
    request<{ valid: boolean; errors: string[]; warnings: string[] }>(
      "POST",
      "/settings/validate",
      { body: omitBlankApiKeys(settings) },
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
