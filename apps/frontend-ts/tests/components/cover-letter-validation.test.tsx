/**
 * Job Raider - Cover Letter Validation Component Tests
 *
 * Tests the proofread result display for each recommendation tier,
 * score rendering, issue labels, and detail chips.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  CoverLetterValidationDisplay,
  CoverLetterRecommendationBadge,
} from "@/components/cover-letter-validation";
import type { CoverLetterValidation } from "@/lib/types/api";

const baseValidation: CoverLetterValidation = {
  is_valid: true,
  score: 70,
  issues: [],
  word_count: 120,
  structure_score: 75,
  content_score: 70,
  tone_score: 65,
  recommendation: "approve",
  details: {
    paragraph_count: 3,
    company_mentioned: true,
    job_title_mentioned: true,
    has_call_to_action: true,
    referenced_projects: ["Job Raider"],
  },
};

describe("CoverLetterValidationDisplay", () => {
  it("renders approve recommendation and overall score", () => {
    render(<CoverLetterValidationDisplay validation={baseValidation} />);
    expect(screen.getByText("Ready to send")).toBeInTheDocument();
    expect(screen.getByText("70/100")).toBeInTheDocument();
    expect(screen.getByText("120 words")).toBeInTheDocument();
  });

  it("renders needs_revision recommendation in amber", () => {
    const validation: CoverLetterValidation = {
      ...baseValidation,
      recommendation: "needs_revision",
      issues: ["too_short", "missing_call_to_action"],
      details: { ...baseValidation.details, has_call_to_action: false },
    };
    render(<CoverLetterValidationDisplay validation={validation} />);
    expect(screen.getByText("Needs revision")).toBeInTheDocument();
    expect(screen.getByText("Too Short")).toBeInTheDocument();
    expect(screen.getByText("Missing Call To Action")).toBeInTheDocument();
    expect(screen.getByText("Missing closing")).toBeInTheDocument();
  });

  it("renders reject recommendation and issues list", () => {
    const validation: CoverLetterValidation = {
      ...baseValidation,
      recommendation: "reject",
      score: 45,
      issues: ["missing_company", "missing_job_title", "generic_opening"],
      details: {
        ...baseValidation.details,
        company_mentioned: false,
        job_title_mentioned: false,
      },
    };
    render(<CoverLetterValidationDisplay validation={validation} />);
    expect(screen.getByText("Major issues")).toBeInTheDocument();
    expect(screen.getByText("Missing Company")).toBeInTheDocument();
    expect(screen.getByText("Missing Job Title")).toBeInTheDocument();
    expect(screen.getByText("Generic Opening")).toBeInTheDocument();
    expect(screen.getByText("Missing company")).toBeInTheDocument();
    expect(screen.getByText("Missing role")).toBeInTheDocument();
  });

  it("renders dimension score bars", () => {
    render(<CoverLetterValidationDisplay validation={baseValidation} />);
    expect(screen.getByText("Structure")).toBeInTheDocument();
    expect(screen.getByText("Content")).toBeInTheDocument();
    expect(screen.getByText("Tone")).toBeInTheDocument();
  });

  it("renders LLM feedback when present", () => {
    const validation: CoverLetterValidation = {
      ...baseValidation,
      details: {
        ...baseValidation.details,
        llm_feedback: ["Strong opening paragraph.", "Add more metrics."],
      },
    };
    render(<CoverLetterValidationDisplay validation={validation} />);
    expect(screen.getByText("AI Feedback")).toBeInTheDocument();
    expect(screen.getByText("Strong opening paragraph.")).toBeInTheDocument();
    expect(screen.getByText("Add more metrics.")).toBeInTheDocument();
  });

  it("shows a no-issues message when there are no issues or feedback", () => {
    render(<CoverLetterValidationDisplay validation={baseValidation} />);
    expect(
      screen.getByText("No issues detected. The cover letter looks good."),
    ).toBeInTheDocument();
  });

  it("renders reviewer feedback when present", () => {
    const validation: CoverLetterValidation = {
      ...baseValidation,
      details: {
        ...baseValidation.details,
        review: {
          critique: "Tighten the opening paragraph.",
          rewrite_needed: true,
          rewrite_count: 1,
          model_used: "qwen2.5:3b",
          review_ms: 820.4,
          rewrite_ms: 4510.0,
        },
      },
    };
    render(<CoverLetterValidationDisplay validation={validation} />);
    expect(screen.getByText("Reviewer Feedback")).toBeInTheDocument();
    expect(
      screen.getByText("Tighten the opening paragraph."),
    ).toBeInTheDocument();
    expect(screen.getByText("Rewritten once")).toBeInTheDocument();
    expect(screen.getByText("Rewrite requested")).toBeInTheDocument();
    expect(screen.getByText(/Model: qwen2\.5:3b/)).toBeInTheDocument();
    expect(screen.getByText(/Review: 820 ms/)).toBeInTheDocument();
    expect(screen.getByText(/Rewrite: 4\.5 s/)).toBeInTheDocument();
  });

  it("hides the no-issues message when LLM feedback is present", () => {
    const validation: CoverLetterValidation = {
      ...baseValidation,
      details: {
        ...baseValidation.details,
        llm_feedback: ["Good overall structure."],
      },
    };
    render(<CoverLetterValidationDisplay validation={validation} />);
    expect(screen.getByText("AI Feedback")).toBeInTheDocument();
    expect(
      screen.queryByText("No issues detected. The cover letter looks good."),
    ).not.toBeInTheDocument();
  });

  it("falls back to needs_revision styling for an unrecognized recommendation", () => {
    const validation: CoverLetterValidation = {
      ...baseValidation,
      recommendation: "unknown" as CoverLetterValidation["recommendation"],
    };
    render(<CoverLetterValidationDisplay validation={validation} />);
    expect(screen.getByText("Needs revision")).toBeInTheDocument();
  });
});

describe("CoverLetterRecommendationBadge", () => {
  it.each([
    ["approve", "Ready to send"],
    ["needs_revision", "Needs revision"],
    ["reject", "Major issues"],
  ] as const)(
    "renders the %s recommendation label",
    (recommendation, label) => {
      render(
        <CoverLetterRecommendationBadge recommendation={recommendation} />,
      );
      expect(screen.getByText(label)).toBeInTheDocument();
    },
  );
});
