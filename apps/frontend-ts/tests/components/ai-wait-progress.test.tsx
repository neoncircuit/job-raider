/**
 * Job Raider - AI wait progress tests
 *
 * Covers the shared long-wait bar: honest stage labels, indeterminate
 * (no invented percent), and determinate values when the caller has them.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AiWaitProgress } from "@/components/ai-wait-progress";

describe("AiWaitProgress", () => {
  it("renders an indeterminate progressbar with the stage label", () => {
    render(<AiWaitProgress label="Writing cover letter…" />);

    expect(screen.getByText("Writing cover letter…")).toBeInTheDocument();
    const bar = screen.getByRole("progressbar");
    expect(bar).toBeInTheDocument();
    expect(bar).not.toHaveAttribute("aria-valuenow");
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("marks the wait region as busy", () => {
    render(<AiWaitProgress label="Analyzing profile…" />);

    expect(
      screen.getByText("Analyzing profile…").parentElement,
    ).toHaveAttribute("aria-busy", "true");
  });

  it("renders a hint without claiming a percent", () => {
    render(
      <AiWaitProgress
        label="Parsing resume…"
        hint="This can take 30–60 seconds"
      />,
    );

    expect(screen.getByText("This can take 30–60 seconds")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).not.toHaveAttribute(
      "aria-valuenow",
    );
  });

  it("uses a determinate bar only when a real value is provided", () => {
    const { container } = render(
      <AiWaitProgress label="Scoring jobs…" value={40} />,
    );

    expect(screen.getByText("Scoring jobs…")).toBeInTheDocument();
    const determinate = container.querySelector('[data-slot="progress"]');
    expect(determinate).toBeInTheDocument();
    expect(
      container.querySelector('[data-slot="ai-wait-track"]'),
    ).not.toBeInTheDocument();
  });
});
