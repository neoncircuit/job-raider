import type { JobListing } from "@/lib/types/api";

export interface JobLifecycleFilterOptions {
  /** When false, listings with listing_status expired are omitted. */
  showExpired: boolean;
  /** When true, only listings last seen on the current calendar day remain. */
  scrapedTodayOnly: boolean;
}

/**
 * Filter Jobs-page listings by expiry and scraped-today flags.
 *
 * Missing listing_status is treated as active so older API payloads still
 * appear. Missing scraped_today is treated as not-today.
 *
 * @param jobs - Listings from search or the discover shortlist.
 * @param options - Show-expired and scraped-today-only toggles.
 * @returns Filtered listings in the original order.
 */
export function filterJobsByLifecycle(
  jobs: JobListing[],
  options: JobLifecycleFilterOptions,
): JobListing[] {
  return jobs.filter((job) => {
    const expired = job.listing_status === "expired";
    if (expired && !options.showExpired) {
      return false;
    }
    if (options.scrapedTodayOnly && job.scraped_today !== true) {
      return false;
    }
    return true;
  });
}
