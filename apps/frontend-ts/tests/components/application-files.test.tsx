/**
 * Job detail: the application files (apply pack) list (company-site-apply, S2).
 */

import { Component, type ReactNode } from "react";
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

  it("shows nothing, without an error, when the reply has no file list", async () => {
    // An older backend, or the E2E mock's default reply, answers with {}.
    mockGetFiles.mockResolvedValue({});
    const quiet = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <CrashCatcher>
        <ApplicationFiles job={job} />
      </CrashCatcher>,
    );
    await vi.waitFor(() => expect(mockGetFiles).toHaveBeenCalled());
    await new Promise((resolve) => setTimeout(resolve, 0));
    quiet.mockRestore();

    expect(screen.queryByText("crashed")).toBeNull();
    expect(screen.queryByTestId("application-files")).toBeNull();
  });
});

/** Props of {@link CrashCatcher}. */
interface CrashCatcherProps {
  /** The component under test. */
  children: ReactNode;
}

/**
 * Render "crashed" when a child throws, so a crash fails the test.
 */
class CrashCatcher extends Component<CrashCatcherProps, { crashed: boolean }> {
  state = { crashed: false };

  /**
   * Record that a child threw.
   *
   * @returns The new state.
   */
  static getDerivedStateFromError(): { crashed: boolean } {
    return { crashed: true };
  }

  /**
   * Render the children, or "crashed" after an error.
   *
   * @returns The element.
   */
  render(): ReactNode {
    return this.state.crashed ? <p>crashed</p> : this.props.children;
  }
}
