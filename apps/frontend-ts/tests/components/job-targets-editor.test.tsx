/**
 * Job Raider - JobTargetsEditor tests
 *
 * Covers the experimental profile preference editor save payload.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { JobTargetsEditor } from "@/components/job-targets-editor";
import type { TargetJob } from "@/lib/types/api";

const mockUpdate = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/profile", () => ({
  profileApi: {
    update: (...args: unknown[]) => mockUpdate(...args),
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const targets: TargetJob = {
  keywords: ["AI Engineer"],
  locations: ["Remote"],
  experience_levels: ["Entry Level"],
  remote_preference: false,
  constraint_mode: "boost",
  exclude_internships: false,
};

function renderEditor() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <JobTargetsEditor targetJob={targets} />
    </QueryClientProvider>,
  );
}

describe("JobTargetsEditor", () => {
  beforeEach(() => {
    mockUpdate.mockReset();
    mockUpdate.mockResolvedValue({ message: "ok" });
  });

  it("renders the experimental helper copy", () => {
    renderEditor();
    expect(screen.getByText(/Optional hunt helper/i)).toBeInTheDocument();
  });

  it("saves profile target fields via the flat update API", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(
      screen.getByRole("switch", { name: /Exclude internships/i }),
    );
    await user.click(screen.getByText("Filter (hard)"));
    await user.click(screen.getByText("Save job targets"));

    expect(mockUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        target_keywords: ["AI Engineer"],
        target_locations: ["Remote"],
        target_experience: ["Entry Level"],
        exclude_internships: true,
        constraint_mode: "filter",
      }),
    );
  });
});
