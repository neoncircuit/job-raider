import type { ApplicationSummary } from "@/lib/types/api";

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
