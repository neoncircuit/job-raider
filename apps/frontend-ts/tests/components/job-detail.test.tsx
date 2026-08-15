/**
 * Job Raider - Job Detail Panel Tests
 *
 * Tests the relevance-score display and on-demand "Explain this match"
 * job-fit explanation wiring in the Jobs detail panel.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { JobDetail } from "@/components/jobs/job-detail";
import type { JobListing } from "@/lib/types/api";
import type { ScoreExplanation } from "@/lib/api/coverLetter";

const mockExplainMutate = vi.hoisted(() => vi.fn());
const mockClassifyMutate = vi.hoisted(() => vi.fn());
const mockAnalyzeTrustMutate = vi.hoisted(() => vi.fn());
const mockGenerateCoverLetterMutate = vi.hoisted(() => vi.fn());

let explainFitState = { isPending: false };
let generateCoverLetterState = { isPending: false };
let cachedExplainFitData: ScoreExplanation | null = null;

vi.mock("@/lib/hooks/use-jobs", () => ({
  useClassifyJob: () => ({
    mutate: mockClassifyMutate,
    isPending: false,
  }),
  useAnalyzeTrust: () => ({
    mutate: mockAnalyzeTrustMutate,
    isPending: false,
  }),
  useGenerateCoverLetter: () => ({
    mutate: mockGenerateCoverLetterMutate,
    isPending: generateCoverLetterState.isPending,
  }),
  useExplainJobFit: () => ({
    mutate: mockExplainMutate,
    isPending: explainFitState.isPending,
  }),
  useCachedClassification: () => ({ data: null }),
  useCachedTrustAnalysis: () => ({ data: null }),
  useCachedCoverLetter: () => ({ data: null }),
  useCachedExplainFit: () => ({ data: cachedExplainFitData }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const baseJob: JobListing = {
  job_id: "job-1",
  title: "Senior Software Engineer",
  company: "Tech Innovations Inc",
  location: "San Francisco, CA",
  description:
    "We are seeking a talented Senior Software Engineer with 5+ years " +
    "of experience in React and TypeScript to join our growing team.",
  source: "linkedin",
  is_remote: true,
  skills: [],
  relevance_score: 85,
};

const noopHandlers = {
  isSaved: false,
  isAppliedExternally: false,
  onSave: vi.fn(),
  onApply: vi.fn(),
  onMarkAppliedExternally: vi.fn(),
};

describe("JobDetail explain-fit wiring", () => {
  beforeEach(() => {
    mockExplainMutate.mockReset();
    explainFitState = { isPending: false };
    generateCoverLetterState = { isPending: false };
    cachedExplainFitData = null;
  });

  it("renders the relevance score badge when present", () => {
    render(<JobDetail job={baseJob} {...noopHandlers} />);
    expect(screen.getByText("Relevance Score")).toBeInTheDocument();
    expect(screen.getByText("85/100")).toBeInTheDocument();
  });

  it("disables the explain button when the description is too short", () => {
    const job: JobListing = { ...baseJob, description: "Too short." };
    render(<JobDetail job={job} {...noopHandlers} />);
    expect(screen.getByText("Explain This Match")).toBeDisabled();
    expect(
      screen.getByText(
        "Job description needs at least 50 characters to explain.",
      ),
    ).toBeInTheDocument();
  });

  it("labels dry-run apply as Simulate Apply", () => {
    render(<JobDetail job={baseJob} {...noopHandlers} />);
    expect(screen.getByText("Simulate Apply")).toBeInTheDocument();
    expect(screen.queryByText("Auto Apply")).not.toBeInTheDocument();
  });

  it("calls the mutation with the job's fields when clicked", async () => {
    const user = userEvent.setup();
    render(<JobDetail job={baseJob} {...noopHandlers} />);

    await user.click(screen.getByText("Explain This Match"));

    expect(mockExplainMutate).toHaveBeenCalledWith({
      id: baseJob.job_id,
      job: baseJob,
    });
  });

  it("shows the loading state while the explanation is pending", () => {
    explainFitState = { isPending: true };
    render(<JobDetail job={baseJob} {...noopHandlers} />);
    expect(screen.getByText("Explaining...")).toBeDisabled();
  });

  it("renders the explanation once cached, hiding the explain button", () => {
    cachedExplainFitData = {
      strengths: ["Matches required skills"],
      concerns: [],
      improvements: [],
    };
    render(<JobDetail job={baseJob} {...noopHandlers} />);

    expect(screen.getByText("Why This Match")).toBeInTheDocument();
    expect(screen.getByText("Matches required skills")).toBeInTheDocument();
    expect(screen.queryByText("Explain This Match")).not.toBeInTheDocument();
  });

  it("shows an indeterminate wait bar while generating a cover letter", () => {
    generateCoverLetterState = { isPending: true };
    render(<JobDetail job={baseJob} {...noopHandlers} />);

    expect(screen.getByText("Writing cover letter…")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).not.toHaveAttribute(
      "aria-valuenow",
    );
    expect(screen.getByRole("button", { name: /generating/i })).toBeDisabled();
  });
});
