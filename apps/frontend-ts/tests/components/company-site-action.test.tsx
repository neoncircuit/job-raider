/**
 * Job detail: the "Find company site" control (company-site-apply, S2).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CompanySiteAction } from "@/components/jobs/company-site-action";
import type { CompanySiteResult, JobListing } from "@/lib/types/api";

const mockGetCompanySite = vi.hoisted(() => vi.fn());
const mockToastError = vi.hoisted(() => vi.fn());
const mockTrackMutate = vi.hoisted(() => vi.fn());

vi.mock("@/lib/hooks/use-jobs", () => ({
  useTrackCompanySiteApplication: () => ({
    mutate: mockTrackMutate,
    isPending: false,
  }),
}));

vi.mock("@/lib/api/jobs", () => ({
  jobsApi: {
    getCompanySite: (...args: unknown[]) => mockGetCompanySite(...args),
  },
}));

vi.mock("sonner", () => ({
  toast: { error: (...args: unknown[]) => mockToastError(...args) },
}));

const job: JobListing = {
  job_id: "job-1",
  title: "Graduate Machine Learning Engineer",
  company: "Lumen Analytics Pte. Ltd.",
  source: "mycareersfuture",
  source_url: "https://www.mycareersfuture.gov.sg/job/it/x",
  is_remote: false,
  skills: [],
};

/**
 * Build a company site result for the mocked API.
 *
 * @param overrides - Fields to change from the default exact result.
 * @returns A CompanySiteResult.
 */
function result(overrides: Partial<CompanySiteResult>): CompanySiteResult {
  return {
    level: "exact",
    url: "https://boards.greenhouse.io/lumenanalytics/jobs/4012345",
    page_title: "Job Application",
    evidence: [],
    checked_at: "2026-11-20T10:00:00+00:00",
    query: "Lumen Analytics",
    cached: false,
    ...overrides,
  };
}

describe("CompanySiteAction", () => {
  beforeEach(() => {
    mockGetCompanySite.mockReset();
    mockToastError.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("finds the company site on click and shows the exact link", async () => {
    mockGetCompanySite.mockResolvedValue(result({}));
    const user = userEvent.setup();
    render(<CompanySiteAction job={job} />);
    await user.click(screen.getByRole("button", { name: "Find company site" }));
    expect(mockGetCompanySite).toHaveBeenCalledWith("job-1", false);
    const link = await screen.findByRole("link", {
      name: "Apply on company site",
    });
    expect(link).toHaveAttribute(
      "href",
      "https://boards.greenhouse.io/lumenanalytics/jobs/4012345",
    );
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("labels a careers page result as a careers page", async () => {
    mockGetCompanySite.mockResolvedValue(
      result({
        level: "careers",
        url: "https://www.marigoldhealth.sg/careers",
      }),
    );
    const user = userEvent.setup();
    render(<CompanySiteAction job={job} />);
    await user.click(screen.getByRole("button", { name: "Find company site" }));
    expect(
      await screen.findByRole("link", { name: "Company careers page" }),
    ).toHaveAttribute("href", "https://www.marigoldhealth.sg/careers");
  });

  it("says that no page was verified and shows no link", async () => {
    mockGetCompanySite.mockResolvedValue(
      result({ level: "none", url: null, evidence: [] }),
    );
    const user = userEvent.setup();
    render(<CompanySiteAction job={job} />);
    await user.click(screen.getByRole("button", { name: "Find company site" }));
    expect(
      await screen.findByText(/No company page was verified/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("shows a working state while the search runs", async () => {
    mockGetCompanySite.mockReturnValue(new Promise(() => {}));
    const user = userEvent.setup();
    render(<CompanySiteAction job={job} />);
    await user.click(screen.getByRole("button", { name: "Find company site" }));
    const busy = await screen.findByRole("button", {
      name: "Searching company site...",
    });
    expect(busy).toBeDisabled();
  });

  it("returns to the idle button and reports an error when the search fails", async () => {
    mockGetCompanySite.mockRejectedValue(new Error("Backend unreachable"));
    const user = userEvent.setup();
    render(<CompanySiteAction job={job} />);
    await user.click(screen.getByRole("button", { name: "Find company site" }));
    await waitFor(() => expect(mockToastError).toHaveBeenCalled());
    expect(
      screen.getByRole("button", { name: "Find company site" }),
    ).toBeEnabled();
  });

  it("tells the user when the search is off in Settings", async () => {
    mockGetCompanySite.mockResolvedValue(
      result({ level: "disabled", url: null }),
    );
    const user = userEvent.setup();
    render(<CompanySiteAction job={job} />);
    await user.click(screen.getByRole("button", { name: "Find company site" }));
    expect(
      await screen.findByText(/Company site search is off/),
    ).toBeInTheDocument();
  });

  it("searches again with refresh on when asked", async () => {
    mockGetCompanySite.mockResolvedValue(result({}));
    const user = userEvent.setup();
    render(<CompanySiteAction job={job} />);
    await user.click(screen.getByRole("button", { name: "Find company site" }));
    await screen.findByRole("link", { name: "Apply on company site" });
    await user.click(screen.getByRole("button", { name: "Search again" }));
    expect(mockGetCompanySite).toHaveBeenLastCalledWith("job-1", true);
  });

  it("offers Applied on company site next to a verified link", async () => {
    mockGetCompanySite.mockResolvedValue(result({}));
    const user = userEvent.setup();
    render(<CompanySiteAction job={job} />);
    await user.click(screen.getByRole("button", { name: "Find company site" }));
    await screen.findByRole("link", { name: "Apply on company site" });
    await user.click(
      screen.getByRole("button", { name: "Applied on company site" }),
    );
    expect(mockTrackMutate).toHaveBeenCalledWith({
      job,
      companyUrl: "https://boards.greenhouse.io/lumenanalytics/jobs/4012345",
      level: "exact",
    });
  });

  it("does not offer Applied on company site when nothing was verified", async () => {
    mockGetCompanySite.mockResolvedValue(
      result({ level: "none", url: null, evidence: [] }),
    );
    const user = userEvent.setup();
    render(<CompanySiteAction job={job} />);
    await user.click(screen.getByRole("button", { name: "Find company site" }));
    await screen.findByText(/No company page was verified/);
    expect(
      screen.queryByRole("button", { name: "Applied on company site" }),
    ).toBeNull();
  });
});
