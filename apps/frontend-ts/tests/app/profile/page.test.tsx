/**
 * Job Raider - Profile Page Tests
 *
 * Covers Download PDF action for the active profile summary export.
 *
 * Author: Job Raider
 * Date: 2026-08-25
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ProfilePage from "@/app/profile/page";

const mockExportPdf = vi.hoisted(() => vi.fn());
const mockDownloadFile = vi.hoisted(() => vi.fn());
const mockGet = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/coverLetter", () => ({
  downloadFile: (...args: unknown[]) => mockDownloadFile(...args),
}));

vi.mock("@/lib/api/profile", () => ({
  profileApi: {
    get: (...args: unknown[]) => mockGet(...args),
    exportPdf: (...args: unknown[]) => mockExportPdf(...args),
    upload: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock("@/components/profile-visualizations", () => ({
  SkillsRadar: () => null,
  ExperienceTimeline: () => null,
  StrengthAssessment: () => null,
}));

vi.mock("@/components/application-settings-modal", () => ({
  ApplicationSettingsModal: () => null,
}));

vi.mock("@/components/job-targets-editor", () => ({
  JobTargetsEditor: () => null,
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("ProfilePage PDF export", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockExportPdf.mockReset();
    mockDownloadFile.mockReset();

    mockGet.mockResolvedValue({
      contact_info: {
        name: "Alex Chen",
        email: "alex@example.com",
        location: "Remote",
      },
      summary: "Software engineer.",
      target_job: {
        keywords: [],
        locations: [],
        experience_levels: [],
        remote_preference: false,
        constraint_mode: "boost",
      },
      skills: [],
      work_experience: [],
      education: [],
      projects: [],
      core_skills: [],
      certifications: [],
    });
    mockExportPdf.mockResolvedValue(
      new Response(new Blob(["%PDF"]), { status: 200 }),
    );
    mockDownloadFile.mockResolvedValue(undefined);
  });

  it("shows Download PDF and streams the profile export", async () => {
    const user = userEvent.setup();
    renderWithClient(<ProfilePage />);

    const button = await screen.findByRole("button", {
      name: /download pdf/i,
    });
    await user.click(button);

    await waitFor(() => {
      expect(mockExportPdf).toHaveBeenCalledTimes(1);
      expect(mockDownloadFile).toHaveBeenCalledTimes(1);
    });
  });
});
