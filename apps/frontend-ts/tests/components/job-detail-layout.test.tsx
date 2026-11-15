/**
 * Job Raider - Job Detail Layout Tests (responsive-job-detail task)
 *
 * On a laptop window the fixed header and the fixed action footer took all
 * the height of the detail card, so the description was not visible. The
 * card now has one scroll area (header, analysis actions, results, and the
 * description) and only the primary action row stays fixed at the bottom.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { JobDetail } from "@/components/jobs/job-detail";
import type { JobListing } from "@/lib/types/api";

let cachedCoverLetterData: { content: string; validation: null } | null = null;

vi.mock("@/lib/hooks/use-jobs", () => ({
  useClassifyJob: () => ({ mutate: vi.fn(), isPending: false }),
  useAnalyzeTrust: () => ({ mutate: vi.fn(), isPending: false }),
  useGenerateCoverLetter: () => ({ mutate: vi.fn(), isPending: false }),
  useExplainJobFit: () => ({ mutate: vi.fn(), isPending: false }),
  useCachedClassification: () => ({ data: null }),
  useCachedTrustAnalysis: () => ({ data: null }),
  useCachedCoverLetter: () => ({ data: cachedCoverLetterData }),
  useCachedExplainFit: () => ({ data: null }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const job: JobListing = {
  job_id: "job-1",
  title: "Junior Backend Engineer",
  company: "Tech Innovations Inc",
  location: "Singapore",
  description:
    "We are looking for a junior backend engineer to build Python services " +
    "and data APIs with the team.",
  source: "linkedin",
  is_remote: false,
  skills: [],
  relevance_score: 63,
};

const handlers = {
  isSaved: false,
  isAppliedExternally: false,
  onSave: vi.fn(),
  onApply: vi.fn(),
  onMarkAppliedExternally: vi.fn(),
};

/**
 * Render the detail card and return its two regions.
 *
 * @returns The scroll area and the fixed action row.
 */
function renderRegions() {
  render(<JobDetail job={job} {...handlers} />);
  return {
    scroll: screen.getByTestId("job-detail-scroll"),
    actions: screen.getByTestId("job-detail-actions"),
  };
}

describe("JobDetail layout", () => {
  beforeEach(() => {
    cachedCoverLetterData = null;
  });

  it("keeps only the primary actions in the fixed row", () => {
    const { actions } = renderRegions();

    expect(
      within(actions).getByRole("button", { name: /Simulate Apply/i }),
    ).toBeInTheDocument();
    expect(
      within(actions).getByRole("button", { name: "Save" }),
    ).toBeInTheDocument();
    expect(
      within(actions).getByRole("button", { name: /Applied Elsewhere/i }),
    ).toBeInTheDocument();
    expect(
      within(actions).queryByRole("button", { name: /Analyze with AI/i }),
    ).toBeNull();
    expect(
      within(actions).queryByRole("button", { name: /Generate Cover Letter/i }),
    ).toBeNull();
  });

  it("puts the header, the analysis actions, and the description in the scroll area", () => {
    const { scroll } = renderRegions();

    expect(
      within(scroll).getByRole("heading", { name: job.title }),
    ).toBeInTheDocument();
    for (const name of [
      /Analyze with AI/i,
      /Analyze Trust/i,
      /Explain This Match/i,
      /Generate Cover Letter/i,
    ]) {
      expect(within(scroll).getByRole("button", { name })).toBeInTheDocument();
    }
    expect(within(scroll).getByText("Job Description")).toBeInTheDocument();
  });

  it("has no second scroll area inside the description", () => {
    const { scroll } = renderRegions();

    const description = within(scroll).getByText("Job Description");
    expect(description.closest(".overflow-y-auto")).toBe(scroll);
  });

  it("shows a generated cover letter in the scroll area, not the fixed row", () => {
    cachedCoverLetterData = {
      content: "Dear hiring team, I build Python services.",
      validation: null,
    };
    const { scroll, actions } = renderRegions();

    expect(within(scroll).getByText(/Dear hiring team/)).toBeInTheDocument();
    expect(within(actions).queryByText(/Dear hiring team/)).toBeNull();
  });
});
