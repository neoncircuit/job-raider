/**
 * Hardware fit helpers (Step 6, MH-4).
 *
 * The backend labels each local model against the user's safety budget of
 * GPU memory (``GET /api/hardware/fit``). These helpers turn a label into the
 * badge text and colour, and read the 409 answer of an over-budget pull.
 */

import { ApiError } from "@/lib/api/client";
import type {
  FitLabel,
  InstalledFit,
  OverBudgetDetails,
} from "@/lib/types/api";

/** Badge text for each fit label. */
export const FIT_LABEL_TEXT: Record<FitLabel, string> = {
  fits: "Fits",
  over_budget: "Over budget",
  too_large: "Too large",
  unknown: "Unknown",
};

const FIT_LABEL_CLASS: Record<FitLabel, string> = {
  fits: "bg-success/10 text-success",
  over_budget: "bg-warning/10 text-warning",
  too_large: "bg-destructive/10 text-destructive",
  unknown: "bg-muted text-muted-foreground",
};

/**
 * Badge colour classes for a fit label.
 *
 * @param label - Fit label from the backend.
 * @returns Tailwind classes for the badge.
 */
export function fitBadgeClass(label: FitLabel): string {
  return FIT_LABEL_CLASS[label];
}

/**
 * Hover text that says how much memory a model needs and where the number
 * comes from.
 *
 * @param fit - Fit of one installed model.
 * @returns Text such as ``Needs about 5.4 GB (llmfit plan)``.
 */
export function fitTitle(fit: InstalledFit): string {
  if (fit.need_gb == null) return "No estimate for this model";
  const source =
    fit.source === "llmfit_plan" ? "llmfit plan" : "rough estimate from size";
  return `Needs about ${fit.need_gb.toFixed(1)} GB (${source})`;
}

/**
 * Read the over-budget details of a refused pull.
 *
 * @param error - Error from ``settingsApi.pullOllamaModel``.
 * @returns The details when the backend asks the user to confirm, else null.
 */
export function overBudgetDetails(error: unknown): OverBudgetDetails | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const details = error.details;
  if (!details || details.code !== "over_budget") return null;
  if (typeof details.tag !== "string") return null;
  return details as unknown as OverBudgetDetails;
}
