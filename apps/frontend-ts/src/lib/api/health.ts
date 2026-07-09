import { request } from "./client";
import type { HealthResponse } from "@/lib/types/api";

export const healthApi = {
  getHealth: () => request<HealthResponse>("GET", "/health"),
  getVersion: () => request<{ version: string; build: string }>("GET", "/version"),
};
