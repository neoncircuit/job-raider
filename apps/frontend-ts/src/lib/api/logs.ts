import { request } from "./client";
import type { LogLevel, LogsResponse } from "@/lib/types/api";

/** Filters for ``GET /api/logs``. */
export interface LogsQuery {
  level: LogLevel;
  component?: string;
  q?: string;
  limit?: number;
}

export const logsApi = {
  /**
   * Read recent API log records (already redacted), oldest first.
   *
   * @param query - Level, logger prefix, text search, and limit.
   * @param signal - Optional abort signal.
   * @returns Records plus the logger names present in the buffer.
   */
  get: (query: LogsQuery, signal?: AbortSignal) =>
    request<LogsResponse>("GET", "/logs", {
      params: {
        level: query.level,
        component: query.component || undefined,
        q: query.q || undefined,
        limit: query.limit ?? 500,
      },
      signal,
    }),
};
