/**
 * Job detail: the application files (apply pack) list (company-site-apply, S2).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApplicationFiles } from "@/components/jobs/application-files";
import type { ApplicationFilesResponse, JobListing } from "@/lib/types/api";

const mockGetFiles = vi.hoisted(() => vi.fn());
const mockDownload = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/jobs", () => ({
  jobsApi: {
    getApplicationFiles: (...args: unknown[]) => mockGetFiles(...args),
    downloadApplicationFile: (...args: unknown[]) => mockDownload(...args),
  },
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const job: JobListing = {
  job_id: "job-1",
  title: "Graduate Machine Learning Engineer",
  company: "Lumen Analytics Pte. Ltd.",
  source: "mycareersfuture",
  is_remote: false,
  skills: [],
};

const someFiles: ApplicationFilesResponse = {
  files: [
    {
      kind: "cv_pdf",
      label: "CV (PDF)",
      filename: "job-1.pdf",
      available: true,
      download_path: "/jobs/job-1/application-files/cv_pdf",
    },
    {
      kind: "cv_docx",
      label: "CV (DOCX)",
      filename: "job-1.docx",
      available: true,
      download_path: "/jobs/job-1/application-files/cv_docx",
    },
    {
      kind: "cover_letter",
      label: "Cover letter",
      filename: "job-1.txt",
      available: false,
      download_path: "/jobs/job-1/application-files/cover_letter",
    },
  ],
};

describe("ApplicationFiles", () => {
  beforeEach(() => {
    mockGetFiles.mockReset();
    mockDownload.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("lists the generated files with a download button each", async () => {
    mockGetFiles.mockResolvedValue(someFiles);
    render(<ApplicationFiles job={job} />);
    expect(
      await screen.findByRole("button", { name: "Download CV (PDF)" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Download CV (DOCX)" }),
    ).toBeEnabled();
  });

  it("marks a file that was not generated as not generated yet", async () => {
    mockGetFiles.mockResolvedValue(someFiles);
    render(<ApplicationFiles job={job} />);
    expect(
      await screen.findByText(
        "Cover letter: not generated yet. Letters that need review are on the Cover Letter page.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Download Cover letter" }),
    ).toBeNull();
  });

  it("downloads the file the user chose", async () => {
    mockGetFiles.mockResolvedValue(someFiles);
    mockDownload.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ApplicationFiles job={job} />);
    await user.click(
      await screen.findByRole("button", { name: "Download CV (PDF)" }),
    );
    expect(mockDownload).toHaveBeenCalledWith("job-1", "cv_pdf", "job-1.pdf");
  });

  it("says so when no file has been generated", async () => {
    mockGetFiles.mockResolvedValue({
      files: someFiles.files.map((f) => ({ ...f, available: false })),
    });
    render(<ApplicationFiles job={job} />);
    expect(
      await screen.findByText("No application files yet"),
    ).toBeInTheDocument();
  });
});
