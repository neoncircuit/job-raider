/**
 * DISC assessment intro framing and results labels.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DISCAssessment } from "@/components/disc-assessment";

vi.mock("@/lib/api/assessment", () => ({
  discApi: {
    getProfile: vi.fn(async () => {
      throw new Error("not found");
    }),
    start: vi.fn(),
    submit: vi.fn(),
  },
}));

/**
 * Wrap the assessment in a QueryClient for intro rendering.
 *
 * @returns Rendered DISC intro under a fresh query client.
 */
function renderIntro() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <DISCAssessment />
    </QueryClientProvider>,
  );
}

describe("DISCAssessment current-state framing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("frames DISC as work-style practice, not a full personality inventory", async () => {
    renderIntro();
    expect(
      await screen.findByText("DISC Work Style Assessment"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/not a full personality inventory/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/heuristic job-type match suggestions/i),
    ).toBeInTheDocument();
  });
});
