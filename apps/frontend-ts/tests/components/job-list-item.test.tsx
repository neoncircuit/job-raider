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
});
