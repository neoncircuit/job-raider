/**
 * Job Raider - Score Explanation Component Tests
 *
 * Tests the shared strengths/concerns/improvements renderer used by both
 * the job-fit and cover-letter quality panels.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScoreExplanationDisplay } from "@/components/score-explanation";
import type { ScoreExplanation } from "@/lib/api/coverLetter";

const fullExplanation: ScoreExplanation = {
  strengths: ["Strong Python background"],
  concerns: ["No direct AWS experience"],
  improvements: ["Highlight cloud deployment work"],
};

describe("ScoreExplanationDisplay", () => {
  it("renders all three sections when populated", () => {
    render(<ScoreExplanationDisplay explanation={fullExplanation} />);
    expect(screen.getByText("Strengths")).toBeInTheDocument();
    expect(screen.getByText("Strong Python background")).toBeInTheDocument();
    expect(screen.getByText("Concerns")).toBeInTheDocument();
    expect(screen.getByText("No direct AWS experience")).toBeInTheDocument();
    expect(screen.getByText("How to improve")).toBeInTheDocument();
    expect(
      screen.getByText("Highlight cloud deployment work"),
    ).toBeInTheDocument();
  });

  it("omits sections with no items", () => {
    render(
      <ScoreExplanationDisplay
        explanation={{ ...fullExplanation, concerns: [] }}
      />,
    );
    expect(screen.getByText("Strengths")).toBeInTheDocument();
    expect(screen.queryByText("Concerns")).not.toBeInTheDocument();
  });

  it("renders nothing when all sections are empty", () => {
    const { container } = render(
      <ScoreExplanationDisplay
        explanation={{ strengths: [], concerns: [], improvements: [] }}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the explained fit score when present", () => {
    render(
      <ScoreExplanationDisplay
        explanation={{ ...fullExplanation, fit_score: 78 }}
      />,
    );
    expect(screen.getByText("78/100")).toBeInTheDocument();
  });
});
