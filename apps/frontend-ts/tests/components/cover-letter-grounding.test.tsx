/**
 * Cover letter validation UI — ungrounded sentence surfacing.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CoverLetterValidationDisplay } from "@/components/cover-letter-validation";
import type { CoverLetterValidation } from "@/lib/types/api";

const baseValidation: CoverLetterValidation = {
  is_valid: true,
  score: 88,
  issues: [],
  word_count: 58,
  structure_score: 85,
  content_score: 90,
  tone_score: 88,
  recommendation: "approve",
  details: {},
};

describe("CoverLetterValidationDisplay grounding", () => {
  it("lists ungrounded sentences for manual review", () => {
    const validation: CoverLetterValidation = {
      ...baseValidation,
      issues: ["ungrounded_claims"],
      details: {
        ungrounded_sentences: [
          "I look forward to shipping deployed production solutions",
        ],
      },
    };
    render(<CoverLetterValidationDisplay validation={validation} />);
    expect(screen.getByText("Review before sending")).toBeInTheDocument();
    expect(
      screen.getByText(
        "I look forward to shipping deployed production solutions",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Ungrounded Claims")).toBeInTheDocument();
  });

  it("lists scope and technique claim overclaims", () => {
    const validation: CoverLetterValidation = {
      ...baseValidation,
      issues: ["scope_inflation", "technique_mismatch"],
      details: {
        claim_overclaims: [
          {
            sentence: "Leading the development of Job Raider with FastAPI.",
            flags: [
              "Scope inflation: 'leading the' implies leadership/ownership beyond an individual contribution",
            ],
          },
          {
            sentence:
              "On Job Raider I improved scam detection using retrieval methods.",
            flags: [
              "Technique mismatch: 'retrieval' not verified for Job Raider",
            ],
          },
        ],
      },
    };
    render(<CoverLetterValidationDisplay validation={validation} />);
    expect(screen.getByText("Review before sending")).toBeInTheDocument();
    expect(screen.getByText("Scope Inflation")).toBeInTheDocument();
    expect(screen.getByText("Technique Mismatch")).toBeInTheDocument();
    expect(
      screen.getByText(/Technique mismatch: 'retrieval'/),
    ).toBeInTheDocument();
  });

  it("shows severity-weighted grounding penalty breakdown", () => {
    const validation: CoverLetterValidation = {
      ...baseValidation,
      issues: ["ungrounded_claims", "scope_inflation"],
      details: {
        ungrounded_sentences: ["I am excited to contribute meaningfully"],
        claim_overclaims: [
          {
            sentence: "Leading the development of Job Raider with FastAPI.",
            flags: ["Scope inflation: 'leading the'"],
          },
        ],
        grounding_penalty: {
          soft_ungrounded: 1,
          hard_ungrounded: 0,
          scope_inflation: 1,
          technique_mismatch: 0,
          capped_penalty: 15,
          weights: {
            soft_ungrounded: 3,
            hard_ungrounded: 10,
            scope_inflation: 12,
            technique_mismatch: 10,
          },
        },
      },
    };
    render(<CoverLetterValidationDisplay validation={validation} />);
    expect(
      screen.getByText(/Content score deducted 15 by severity/),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 soft/)).toBeInTheDocument();
    expect(screen.getByText(/1 scope/)).toBeInTheDocument();
  });
});
