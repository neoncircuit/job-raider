import { request } from "./client";
import type { MetricsSummaryResponse } from "@/lib/types/api";

export const metricsApi = {
  getSummary: () =>
    request<MetricsSummaryResponse>("GET", "/metrics/summary"),
};
