import { request } from "./client";
import type { CompareReport, CompareState } from "@/lib/types/api";

export const evaluationApi = {
  /**
   * Start the cover-letter model compare (default allow-list models).
   *
   * @returns The compare state after it starts.
   */
  startCompare: () =>
    request<CompareState>("POST", "/evaluation/cover-letter-compare", {
      body: {},
    }),

  /**
   * Read the progress of the current or last compare.
   *
   * @param signal - Optional abort signal.
   * @returns Compare state.
   */
  getCompareStatus: (signal?: AbortSignal) =>
    request<CompareState>("GET", "/evaluation/cover-letter-compare/status", {
      signal,
    }),

  /**
   * Read the last saved compare report (from the app or the CLI).
   *
   * @param signal - Optional abort signal.
   * @returns Wrapper with the report, or null when none exists.
   */
  getLatestCompare: (signal?: AbortSignal) =>
    request<{ report: CompareReport | null }>(
      "GET",
      "/evaluation/cover-letter-compare/latest",
      { signal },
    ),
};
