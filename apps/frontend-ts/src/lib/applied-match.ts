/**
 * Cross-source applied matching for Jobs UI.
 *
 * Mirrors backend ``find_matching_application`` / AppliedGuard:
 * job id → cleaned listing URL → company+title when URL identity is missing.
 */

import { isTrackedApplication } from "@/lib/applications-filters";
import type { ApplicationSummary, JobListing } from "@/lib/types/api";

/** Labels too weak to match on company or title alone. */
const PLACEHOLDER_LABELS = new Set([
  "",
  "unknown",
  "n/a",
  "none",
  "untitled listing",
]);

/**
 * Normalize a listing URL for duplicate matching.
 *
 * @param raw - Stored or pasted listing URL.
 * @returns Lowercased http(s) URL without a trailing slash, or null.
 */
export function normalizeMatchUrl(
  raw: string | null | undefined,
): string | null {
  if (typeof raw !== "string") {
    return null;
  }
  let url = raw.trim();
  if (!url || url.length > 2048) {
    return null;
  }
  let lowered = url.toLowerCase();
  if (
    lowered.startsWith("javascript:") ||
    lowered.startsWith("data:") ||
    lowered.startsWith("file:") ||
    lowered.startsWith("vbscript:")
  ) {
    return null;
  }
  if (!lowered.startsWith("http://") && !lowered.startsWith("https://")) {
    const schemeEnd = url.indexOf("://");
    if (schemeEnd !== -1 && !url.slice(0, schemeEnd).includes("/")) {
      return null;
    }
    url = `https://${url}`;
    lowered = url.toLowerCase();
  }
  return lowered.replace(/\/$/, "");
}

/**
 * Normalize a company or title string for duplicate matching.
 *
 * @param value - Company name or job title.
 * @returns Lowercased value with collapsed whitespace.
 */
export function normalizeMatchLabel(value: string | null | undefined): string {
  return (value ?? "")
    .toLowerCase()
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

/**
 * Return whether a company or title is strong enough to match on.
 *
 * @param value - Company name or job title.
 * @returns True when the normalized label is not empty or a placeholder.
 */
function usableMatchLabel(value: string | null | undefined): boolean {
  return !PLACEHOLDER_LABELS.has(normalizeMatchLabel(value));
}

/** Minimal job fields needed for applied matching. */
export interface AppliedMatchJob {
  job_id?: string | null;
  title?: string | null;
  company?: string | null;
  source_url?: string | null;
  url?: string | null;
}

/** Minimal application fields needed for applied matching. */
export interface AppliedMatchApplication {
  application_id: string;
  job_title: string;
  company: string;
  source_url?: string | null;
  current_status: string;
}

/**
 * Return whether a listing matches any tracked application.
 *
 * Match order: real job id, cleaned listing URL, then company+title when
 * URL identity is missing on either side. Bookmark/hide rows should be
 * filtered out by the caller (or use ``isListingAlreadyTracked``).
 *
 * @param job - Listing from Jobs search or shortlist.
 * @param applications - Tracked application rows (not bookmark/hide).
 * @returns True when the user should not apply again.
 */
export function isListingAlreadyTracked(
  job: AppliedMatchJob,
  applications: AppliedMatchApplication[],
): boolean {
  const jobId = (job.job_id ?? "").trim();
  if (jobId) {
    for (const app of applications) {
      if (app.application_id === jobId) {
        return true;
      }
    }
  }

  const incomingUrl = normalizeMatchUrl(job.source_url ?? job.url);
  if (incomingUrl) {
    for (const app of applications) {
      const existingUrl = normalizeMatchUrl(app.source_url);
      if (existingUrl && existingUrl === incomingUrl) {
        return true;
      }
    }
  }

  if (!usableMatchLabel(job.company) || !usableMatchLabel(job.title)) {
    return false;
  }
  const companyKey = normalizeMatchLabel(job.company);
  const titleKey = normalizeMatchLabel(job.title);

  for (const app of applications) {
    if (normalizeMatchLabel(app.company) !== companyKey) {
      continue;
    }
    if (normalizeMatchLabel(app.job_title) !== titleKey) {
      continue;
    }
    const existingUrl = normalizeMatchUrl(app.source_url);
    // Company+title is the fallback when URL identity is missing.
    // If both sides have a URL, different postings stay separate.
    if (incomingUrl && existingUrl) {
      continue;
    }
    return true;
  }
  return false;
}

/**
 * Return whether a JobListing matches any tracked dashboard application.
 *
 * Filters out bookmark/hide statuses before matching.
 *
 * @param job - Jobs UI listing.
 * @param applications - Full dashboard application list.
 * @returns True when Apply / Applied Elsewhere should be disabled.
 */
export function isJobAlreadyApplied(
  job: JobListing,
  applications: ApplicationSummary[],
): boolean {
  if (job.already_applied) {
    return true;
  }
  const tracked = applications.filter(isTrackedApplication);
  return isListingAlreadyTracked(job, tracked);
}
