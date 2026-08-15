import type { ApplicationSummary } from "@/lib/types/api";

/** Bookmark-only and hidden rows belong on Saved / Hidden, not All. */
const NON_TRACKED_STATUSES = new Set(["saved_bookmarked", "not_interested"]);

/** Statuses that can advance to the first interview stage. */
const APPLIED_STATUSES = new Set(["applied", "applied_elsewhere"]);

/** Statuses that mean the company has come back and interview prep is relevant. */
const INTERVIEW_STATUSES = new Set([
  "under_review",
  "screening_scheduled",
  "screening_completed",
  "technical_scheduled",
  "technical_completed",
  "onsite_scheduled",
  "onsite_completed",
  "final",
]);

/** Minimum stored JD length required by interview prep. */
export const MIN_JOB_DESCRIPTION_CHARS = 50;

/** Title or company values that should not be shown as real labels. */
const PLACEHOLDER_LABELS = new Set(["", "unknown", "n/a", "none"]);

/**
 * Return whether an application row is an expired catalog listing.
 *
 * Missing listing_status (external or unsynced ids) is not expired.
 *
 * @param app - Dashboard application summary.
 * @returns True when the catalog listing is expired.
 */
export function isExpiredApplication(app: ApplicationSummary): boolean {
  return app.listing_status === "expired";
}

/**
 * Return whether a dashboard row is a real application, not a bookmark or hide.
 *
 * @param app - Dashboard application summary.
 * @returns True for applied, applied_elsewhere, interview, and outcome statuses.
 */
export function isTrackedApplication(app: ApplicationSummary): boolean {
  return !NON_TRACKED_STATUSES.has(app.current_status.toLowerCase());
}

/**
 * Return whether a tracked application can move to the interview stage.
 *
 * Bookmark-only and hidden rows are not eligible.
 *
 * @param status - Current application status.
 * @returns True for applied and applied_elsewhere.
 */
export function canAdvanceToInterview(status: string): boolean {
  return APPLIED_STATUSES.has(status.toLowerCase());
}

/**
 * Return whether a status is an interview stage that can run prep.
 *
 * @param status - Current application status.
 * @returns True for under_review through final interview stages.
 */
export function isInterviewStage(status: string): boolean {
  return INTERVIEW_STATUSES.has(status.toLowerCase());
}

/**
 * Applications that belong on the All Applications tab.
 *
 * @param apps - Dashboard application summaries.
 * @returns Tracked rows in the original order.
 */
export function filterTrackedApplications(
  apps: ApplicationSummary[],
): ApplicationSummary[] {
  return apps.filter(isTrackedApplication);
}

/**
 * Display title for a card when the stored title is empty or a stub.
 *
 * @param title - Stored job title.
 * @returns Title text, or Untitled listing.
 */
export function displayApplicationTitle(
  title: string | null | undefined,
): string {
  const trimmed = title?.trim() ?? "";
  if (!trimmed || PLACEHOLDER_LABELS.has(trimmed.toLowerCase())) {
    return "Untitled listing";
  }
  return trimmed;
}

/**
 * Display company for a card when the stored company is empty or a stub.
 *
 * @param company - Stored company name.
 * @returns Company text, or Unknown company.
 */
export function displayApplicationCompany(
  company: string | null | undefined,
): string {
  const trimmed = company?.trim() ?? "";
  if (!trimmed || PLACEHOLDER_LABELS.has(trimmed.toLowerCase())) {
    return "Unknown company";
  }
  return trimmed;
}

/**
 * Applications whose catalog listing is expired.
 *
 * @param apps - Dashboard application summaries.
 * @returns Expired rows in the original order.
 */
export function filterExpiredApplications(
  apps: ApplicationSummary[],
): ApplicationSummary[] {
  return apps.filter(isExpiredApplication);
}

/**
 * Return an http(s) listing URL for Open listing, or null when none.
 *
 * Empty values are hidden. Scheme-less hosts get https. Non-http schemes
 * are rejected so the card never renders an unsafe href.
 *
 * @param url - Stored or pasted listing URL.
 * @returns Safe href, or null when the control should stay hidden.
 */
export function safeListingUrl(url: string | null | undefined): string | null {
  const trimmed = url?.trim() ?? "";
  if (!trimmed || trimmed.length > 2048) {
    return null;
  }
  const lowered = trimmed.toLowerCase();
  if (
    lowered.startsWith("javascript:") ||
    lowered.startsWith("data:") ||
    lowered.startsWith("file:") ||
    lowered.startsWith("vbscript:")
  ) {
    return null;
  }
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  const schemeEnd = trimmed.indexOf("://");
  if (schemeEnd !== -1 && !trimmed.slice(0, schemeEnd).includes("/")) {
    return null;
  }
  return `https://${trimmed}`;
}
