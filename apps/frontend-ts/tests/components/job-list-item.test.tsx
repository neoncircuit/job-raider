/**
 * Tests for the score badge on a job row.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { JobListItem } from "@/components/jobs/job-list-item";
import type { JobListing } from "@/lib/types/api";

const job: JobListing = {
  job_id: "job-1",
  title: "Machine Learning Engineer",
  company: "Example Labs",
  location: "Singapore",
  description: "Build machine learning services.",
  source: "other",
  is_remote: false,
  skills: [],
  relevance_score: 80.22549940382058,
};

describe("JobListItem", () => {
  it("shows a whole relevance score", () => {
    render(
      <JobListItem
        job={job}
        isSelected={false}
        isSaved={false}
        isAppliedExternally={false}
        onClick={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByText("80/100")).toBeInTheDocument();
  });

  it("shows the required years and the fresh grad label", () => {
    render(
      <JobListItem
        job={{ ...job, required_years: 4, fresh_grad_friendly: true }}
        isSelected={false}
        isSaved={false}
        isAppliedExternally={false}
        onClick={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByText("4+ yrs")).toBeInTheDocument();
    expect(screen.getByText("Fresh grad friendly")).toBeInTheDocument();
  });

  it("hides both labels when the job states neither", () => {
    render(
      <JobListItem
        job={{ ...job, required_years: null, fresh_grad_friendly: false }}
        isSelected={false}
        isSaved={false}
        isAppliedExternally={false}
        onClick={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.queryByText(/yrs$/)).not.toBeInTheDocument();
    expect(screen.queryByText("Fresh grad friendly")).not.toBeInTheDocument();
  });

  it("shows the stated range when the posting gives one", () => {
    render(
      <JobListItem
        job={{ ...job, required_years: 1, required_years_max: 5 }}
        isSelected={false}
        isSaved={false}
        isAppliedExternally={false}
        onClick={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByText("1-5 yrs")).toBeInTheDocument();
    expect(screen.queryByText("1+ yrs")).not.toBeInTheDocument();
  });
});
