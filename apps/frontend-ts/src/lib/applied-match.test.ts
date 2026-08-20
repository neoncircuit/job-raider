import { describe, expect, it } from "vitest";
import {
  isListingAlreadyTracked,
  normalizeMatchLabel,
  normalizeMatchUrl,
} from "@/lib/applied-match";
import type { ApplicationSummary } from "@/lib/types/api";

function app(
  overrides: Partial<ApplicationSummary> &
    Pick<ApplicationSummary, "application_id" | "current_status">,
): ApplicationSummary {
  return {
    job_title: "Engineer",
    company: "Acme",
    is_bookmarked: false,
    is_hidden: false,
    ...overrides,
  };
}

describe("normalizeMatchUrl", () => {
  it("lowercases and strips trailing slash", () => {
    expect(normalizeMatchUrl("HTTPS://Example.com/Jobs/1/")).toBe(
      "https://example.com/jobs/1",
    );
  });

  it("rejects unsafe schemes", () => {
    expect(normalizeMatchUrl("javascript:alert(1)")).toBeNull();
  });
});

describe("normalizeMatchLabel", () => {
  it("collapses whitespace and lowercases", () => {
    expect(normalizeMatchLabel("  Foo   Bar ")).toBe("foo bar");
  });
});

describe("isListingAlreadyTracked", () => {
  it("matches by application id", () => {
    const applications = [
      app({ application_id: "job-1", current_status: "applied_elsewhere" }),
    ];
    expect(
      isListingAlreadyTracked(
        { job_id: "job-1", title: "X", company: "Y" },
        applications,
      ),
    ).toBe(true);
  });

  it("matches by URL across different ids", () => {
    const applications = [
      app({
        application_id: "a",
        current_status: "applied",
        source_url: "https://jobs.example.com/post/9",
        job_title: "Old",
        company: "OldCo",
      }),
    ];
    expect(
      isListingAlreadyTracked(
        {
          job_id: "b",
          title: "New",
          company: "NewCo",
          source_url: "https://jobs.example.com/post/9/",
        },
        applications,
      ),
    ).toBe(true);
  });

  it("does not match same company+title when both have different URLs", () => {
    const applications = [
      app({
        application_id: "li",
        current_status: "applied_elsewhere",
        job_title: "Software Engineer",
        company: "Acme",
        source_url: "https://linkedin.com/jobs/view/1",
      }),
    ];
    expect(
      isListingAlreadyTracked(
        {
          job_id: "mcf",
          title: "Software Engineer",
          company: "Acme",
          source_url: "https://mycareersfuture.gov.sg/jobs/2",
        },
        applications,
      ),
    ).toBe(false);
  });

  it("matches company+title when one side has no URL", () => {
    const applications = [
      app({
        application_id: "manual",
        current_status: "screening_scheduled",
        job_title: "Backend Engineer",
        company: "StackInc",
      }),
    ];
    expect(
      isListingAlreadyTracked(
        {
          job_id: "board",
          title: "Backend Engineer",
          company: "StackInc",
          source_url: "https://jsearch.example/99",
        },
        applications,
      ),
    ).toBe(true);
  });
});
