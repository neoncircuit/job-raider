import { request } from "./client";
import type { AppSettings } from "@/lib/types/api";

export const settingsApi = {
  get: () =>
    request<AppSettings>("GET", "/settings/"),

  update: (settings: AppSettings) =>
    request<AppSettings>("PUT", "/settings/", { body: settings }),

  reset: () =>
    request<AppSettings>("POST", "/settings/reset"),

  validate: (settings: AppSettings) =>
    request<{ valid: boolean; errors: string[]; warnings: string[] }>(
      "POST",
      "/settings/validate",
      { body: settings }
    ),

  getModels: () =>
    request<Record<string, string[]>>("GET", "/settings/models"),
};
