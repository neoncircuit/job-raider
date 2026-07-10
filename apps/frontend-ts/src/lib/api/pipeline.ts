import { request } from "./client";
import type {
  PipelineStartRequest,
  PipelineStatusResponse,
  PipelineResultResponse,
  PipelineHistoryResponse,
} from "@/lib/types/api";

export const pipelineApi = {
  start: (req: PipelineStartRequest, signal?: AbortSignal) =>
    request<{ run_id: string }>("POST", "/pipeline/start", {
      body: req,
      signal,
    }),

  getStatus: (runId: string, signal?: AbortSignal) =>
    request<PipelineStatusResponse>("GET", `/pipeline/status/${runId}`, {
      signal,
    }),

  getResults: (runId: string) =>
    request<PipelineResultResponse>("GET", `/pipeline/results/${runId}`),

  cancel: (runId: string) =>
    request<{ run_id: string; status: string }>("DELETE", `/pipeline/${runId}`),

  getHistory: (limit = 20) =>
    request<PipelineHistoryResponse>("GET", "/pipeline/history", {
      params: { limit },
    }),
};
