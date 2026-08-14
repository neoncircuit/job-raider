import { describe, expect, it } from "vitest";
import { filterJobsByLifecycle } from "@/lib/jobs-filters";
import type { JobListing } from "@/lib/types/api";

function job(
  overrides: Partial<JobListing> & Pick<JobListing, "job_id">,
): JobListing {
  return {
    title: "Engineer",
    company: "Acme",
    source: "linkedin",
    is_remote: false,
    skills: [],
    ...overrides,
  };
}

describe("filterJobsByLifecycle", () => {
  const active = job({
    job_id: "a",
    listing_status: "active",
    scraped_today: true,
  });
  const expired = job({
    job_id: "e",
    listing_status: "expired",
    scraped_today: false,
  });
  const legacy = job({ job_id: "l" });

  it("hides expired listings unless showExpired is true", () => {
    const hidden = filterJobsByLifecycle([active, expired, legacy], {
      showExpired: false,
      scrapedTodayOnly: false,
    });
    expect(hidden.map((item) => item.job_id)).toEqual(["a", "l"]);

    const shown = filterJobsByLifecycle([active, expired, legacy], {
      showExpired: true,
      scrapedTodayOnly: false,
    });
    expect(shown.map((item) => item.job_id)).toEqual(["a", "e", "l"]);
  });

  it("keeps only scraped-today listings when that filter is on", () => {
    const todayExpired = job({
      job_id: "te",
      listing_status: "expired",
      scraped_today: true,
    });
    const filtered = filterJobsByLifecycle(
      [active, expired, legacy, todayExpired],
      { showExpired: false, scrapedTodayOnly: true },
    );
    expect(filtered.map((item) => item.job_id)).toEqual(["a"]);
  });
});
