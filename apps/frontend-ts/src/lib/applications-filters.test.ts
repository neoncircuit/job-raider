import { describe, expect, it } from "vitest";

import type { ApplicationSummary } from "@/lib/types/api";
import {
  filterExpiredApplications,
  isExpiredApplication,
} from "./applications-filters";

function app(
  overrides: Partial<ApplicationSummary> = {},
): ApplicationSummary {
  return {
    application_id: "job-1",
    job_title: "Engineer",
    company: "Acme",
    current_status: "saved_bookmarked",
    is_bookmarked: true,
    is_hidden: false,
    ...overrides,
  };
}

describe("filterExpiredApplications", () => {
  it("keeps only catalog-expired rows", () => {
    const expired = app({
      application_id: "stale",
      listing_status: "expired",
    });
    const active = app({
      application_id: "fresh",
      listing_status: "active",
    });
    const unknown = app({ application_id: "ext-1" });
    expect(filterExpiredApplications([expired, active, unknown])).toEqual([
      expired,
    ]);
  });

  it("does not treat missing listing_status as expired", () => {
    expect(isExpiredApplication(app({}))).toBe(false);
  });
});
