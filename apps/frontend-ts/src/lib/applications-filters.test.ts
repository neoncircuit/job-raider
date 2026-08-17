import { describe, expect, it } from "vitest";

import type { ApplicationSummary } from "@/lib/types/api";
import {
  canAdvanceToInterview,
  canRevertStatus,
  displayApplicationCompany,
  displayApplicationMethod,
  displayApplicationTitle,
  filterExpiredApplications,
  filterTrackedApplications,
  isExpiredApplication,
  isInboundApplicationMethod,
  isInterviewStage,
  isTrackedApplication,
  safeListingUrl,
} from "./applications-filters";

function app(overrides: Partial<ApplicationSummary> = {}): ApplicationSummary {
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

describe("filterTrackedApplications", () => {
  it("keeps applied and applied_elsewhere, drops bookmarks and hidden", () => {
    const applied = app({
      application_id: "a1",
      current_status: "applied",
      is_bookmarked: false,
    });
    const elsewhere = app({
      application_id: "a2",
      current_status: "applied_elsewhere",
      is_bookmarked: false,
    });
    const bookmark = app({
      application_id: "b1",
      current_status: "saved_bookmarked",
      is_bookmarked: true,
    });
    const hidden = app({
      application_id: "h1",
      current_status: "not_interested",
      is_bookmarked: false,
      is_hidden: true,
    });
    expect(
      filterTrackedApplications([applied, elsewhere, bookmark, hidden]),
    ).toEqual([applied, elsewhere]);
  });

  it("keeps a bookmarked row that was also marked applied elsewhere", () => {
    const both = app({
      application_id: "both",
      current_status: "applied_elsewhere",
      is_bookmarked: true,
    });
    expect(isTrackedApplication(both)).toBe(true);
    expect(filterTrackedApplications([both])).toEqual([both]);
  });
});

describe("interview eligibility", () => {
  it("lets applied and applied_elsewhere advance to interview", () => {
    expect(canAdvanceToInterview("applied")).toBe(true);
    expect(canAdvanceToInterview("applied_elsewhere")).toBe(true);
    expect(canAdvanceToInterview("saved_bookmarked")).toBe(false);
    expect(canAdvanceToInterview("not_interested")).toBe(false);
    expect(canAdvanceToInterview("screening_scheduled")).toBe(false);
  });

  it("treats screening_scheduled as interview-prep eligible", () => {
    expect(isInterviewStage("screening_scheduled")).toBe(true);
    expect(isInterviewStage("applied_elsewhere")).toBe(false);
    expect(isInterviewStage("applied")).toBe(false);
    expect(isInterviewStage("saved_bookmarked")).toBe(false);
  });

  it("allows revert from interview or rejected when history exists", () => {
    expect(canRevertStatus("screening_scheduled", "applied")).toBe(true);
    expect(canRevertStatus("screening_scheduled", "applied_elsewhere")).toBe(
      true,
    );
    expect(canRevertStatus("rejected", "applied")).toBe(true);
    expect(canRevertStatus("rejected", "applied_elsewhere")).toBe(true);
    expect(canRevertStatus("rejected", "screening_scheduled")).toBe(true);
    expect(canRevertStatus("applied", "screening_scheduled")).toBe(false);
    expect(canRevertStatus("screening_scheduled", null)).toBe(false);
    expect(canRevertStatus("saved_bookmarked", "applied")).toBe(false);
  });
});

describe("displayApplicationTitle and company", () => {
  it("replaces empty and Unknown stubs", () => {
    expect(displayApplicationTitle("")).toBe("Untitled listing");
    expect(displayApplicationTitle("Unknown")).toBe("Untitled listing");
    expect(displayApplicationTitle("  AI Engineer  ")).toBe("AI Engineer");
    expect(displayApplicationCompany(undefined)).toBe("Unknown company");
    expect(displayApplicationCompany("Unknown")).toBe("Unknown company");
    expect(displayApplicationCompany("Acme")).toBe("Acme");
  });
});

describe("application method labels", () => {
  it("labels inbound recruiter methods and hides generic apply methods", () => {
    expect(displayApplicationMethod("inbound/recruiter")).toBe(
      "Inbound / recruiter",
    );
    expect(isInboundApplicationMethod("inbound/recruiter")).toBe(true);
    expect(displayApplicationMethod("External site")).toBeNull();
    expect(displayApplicationMethod("referral")).toBe("referral");
    expect(isInboundApplicationMethod("External site")).toBe(false);
  });
});

describe("safeListingUrl", () => {
  it("hides empty values and unsafe schemes", () => {
    expect(safeListingUrl(undefined)).toBeNull();
    expect(safeListingUrl("")).toBeNull();
    expect(safeListingUrl("   ")).toBeNull();
    expect(safeListingUrl("javascript:alert(1)")).toBeNull();
    expect(safeListingUrl("data:text/html,hi")).toBeNull();
  });

  it("keeps http(s) and adds https for scheme-less hosts", () => {
    expect(safeListingUrl("https://example.com/job")).toBe(
      "https://example.com/job",
    );
    expect(safeListingUrl("  example.com/job  ")).toBe(
      "https://example.com/job",
    );
  });
});
