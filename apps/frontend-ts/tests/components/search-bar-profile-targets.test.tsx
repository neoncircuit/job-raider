/**
 * Job Raider - SearchBar profile-targets opt-in tests
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SearchBar } from "@/components/jobs/search-bar";

vi.mock("@/lib/hooks/use-profile-targets", () => ({
  useProfileTargets: () => ({
    targets: {
      keywords: ["AI Engineer", "LLM"],
      locations: ["Singapore"],
      experience_levels: ["Entry Level"],
      remote_preference: true,
      constraint_mode: "filter",
      exclude_internships: true,
    },
    hasKeywords: true,
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/lib/api/jobs", () => ({
  jobsApi: {
    getSources: vi.fn().mockResolvedValue({ sources: ["linkedin", "jsearch"] }),
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

function renderBar(onSearch = vi.fn(), onGoogleSearch = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <SearchBar onSearch={onSearch} onGoogleSearch={onGoogleSearch} />
    </QueryClientProvider>,
  );
  return { onSearch, onGoogleSearch };
}

describe("SearchBar use profile targets", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("defaults the profile-targets switch to off", () => {
    renderBar();
    const toggle = screen.getByRole("switch", { name: /Use profile targets/i });
    expect(toggle).not.toBeChecked();
  });

  it("prefills keywords and location when the switch is enabled", async () => {
    const user = userEvent.setup();
    renderBar();

    await user.click(
      screen.getByRole("switch", { name: /Use profile targets/i }),
    );

    expect(screen.getByLabelText("Keywords")).toHaveValue("AI Engineer, LLM");
    expect(screen.getByLabelText("Location")).toHaveValue("Singapore");
  });
});