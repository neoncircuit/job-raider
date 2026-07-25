import { request } from "./client";
import type { HealthResponse, SystemResourcesResponse } from "@/lib/types/api";

export const healthApi = {
  getHealth: () => request<HealthResponse>("GET", "/health"),
  getResources: () =>
    request<SystemResourcesResponse>("GET", "/health/resources"),
  getVersion: () =>
    request<{ version: string; build: string }>("GET", "/version"),
};
