import { request } from "./client";
import type { AppSettings, AvailableModelsResponse } from "@/lib/types/api";

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

  getModels: () =>
    request<AvailableModelsResponse>("GET", "/settings/models"),

  applyOllamaDefaults: (smallModel: string, largeModel: string) =>
    request<AppSettings>("POST", "/settings/ollama-defaults", {
      body: { small_model: smallModel, large_model: largeModel },
    }),
};
