/**
 * Job Raider - Cover Letter Page Tests
 *
 * Tests the dedicated Cover Letter page:
 * - Form rendering and validation
 * - Successful generation from pasted job details
 * - Deep validation toggle
 * - DOCX/PDF export
 * - Copy-to-clipboard
 *
 * Author: Job Raider
 * Date: 2026-06-29
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CoverLetterPage from "@/app/cover-letter/page";
import {
  sampleCoverLetter,
  sampleCoverLetterValidation,
} from "../../setup/fixtures";
import type { CoverLetterResponse } from "@/lib/types/api";

const mockGenerate = vi.hoisted(() => vi.fn());
const mockExport = vi.hoisted(() => vi.fn());
const mockAssess = vi.hoisted(() => vi.fn());
const mockValidate = vi.hoisted(() => vi.fn());
const mockParseJd = vi.hoisted(() => vi.fn());
const mockDownloadFile = vi.hoisted(() => vi.fn());
const mockExportAnalysis = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/coverLetter", () => ({
  coverLetterApi: {
    generate: (...args: unknown[]) => mockGenerate(...args),
    export: (...args: unknown[]) => mockExport(...args),
    exportAnalysis: (...args: unknown[]) => mockExportAnalysis(...args),
    assess: (...args: unknown[]) => mockAssess(...args),
    validate: (...args: unknown[]) => mockValidate(...args),
    parseJd: (...args: unknown[]) => mockParseJd(...args),
    detectInstructions: vi.fn().mockResolvedValue({
      why_interest: null,
      inclusions: [],
      short_answer_mode: false,
      has_inclusions: false,
    }),
  },
  downloadFile: (...args: unknown[]) => mockDownloadFile(...args),
}));

vi.mock("@/lib/api/profile", () => ({
  profileApi: {
    get: vi.fn().mockResolvedValue({
      contact_info: { name: "Test User", email: "test@example.com" },
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
    }),
  },
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

/** Accessible name for the JD textarea (not the upload file input). */
function getJdTextarea() {
  return screen.getByRole("textbox", { name: /^job description$/i });
}

const sampleResponse: CoverLetterResponse = {
  success: true,
  job_id: "manual-test-123",
  cover_letter: sampleCoverLetter,
  validation: sampleCoverLetterValidation,
};

describe("CoverLetterPage", () => {
  beforeEach(() => {
    mockGenerate.mockReset();
    mockExport.mockReset();
    mockExportAnalysis.mockReset();
    mockAssess.mockReset();
    mockValidate.mockReset();
    mockParseJd.mockReset();
    mockDownloadFile.mockReset();

    mockGenerate.mockResolvedValue(sampleResponse);
    mockExport.mockResolvedValue(
      new Response(new Blob(["mock"]), { status: 200 }),
    );
    mockExportAnalysis.mockResolvedValue(
      new Response(new Blob(["{}"]), { status: 200 }),
    );
    mockAssess.mockResolvedValue({
      score: 75,
      passed_threshold: true,
      recommendation: "maybe",
      reasoning: "Solid match.",
      breakdown: { keyword_match: 40 },
      matched_keywords: ["React"],
      missing_skills: [],
      scam_risk: "low",
      scam_flags: [],
    });
    mockValidate.mockResolvedValue({
      ...sampleCoverLetterValidation,
      score: 82,
    });
    mockParseJd.mockResolvedValue({
      text:
        "We are seeking a talented Senior Software Engineer to join our team. " +
        "Requirements include 5+ years of React and TypeScript experience.",
      filename: "sample-jd.pdf",
      char_count: 140,
      warnings: [],
    });
    mockDownloadFile.mockResolvedValue(undefined);
  });

  it("renders the form and disables generate until required fields are filled", () => {
    renderWithClient(<CoverLetterPage />);

    expect(
      screen.getByRole("heading", { name: /cover letter/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/job title/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/company/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/location \(optional\)/i)).toBeInTheDocument();
    expect(getJdTextarea()).toBeInTheDocument();
    expect(
      screen.getByLabelText(/upload job description \(pdf or docx\)/i),
    ).toBeInTheDocument();

    const generateButton = screen.getByRole("button", {
      name: /generate cover letter/i,
    });
    expect(generateButton).toBeDisabled();
  });

  it("fills the JD textarea from an uploaded document without auto-generating", async () => {
    const user = userEvent.setup();
    renderWithClient(<CoverLetterPage />);

    const file = new File(
      [new Blob(["fake pdf bytes"], { type: "application/pdf" })],
      "sample-jd.pdf",
      { type: "application/pdf" },
    );
    const input = screen.getByLabelText(
      /upload job description \(pdf or docx\)/i,
    );
    await user.upload(input, file);

    await waitFor(() => {
      expect(mockParseJd).toHaveBeenCalledTimes(1);
    });
    expect(mockParseJd).toHaveBeenCalledWith(file);

    await waitFor(() => {
      expect((getJdTextarea() as HTMLTextAreaElement).value).toContain(
        "Senior Software Engineer",
      );
    });
    expect(
      screen.getByText(/source file: sample-jd\.pdf/i),
    ).toBeInTheDocument();
    expect(mockGenerate).not.toHaveBeenCalled();

    const generateButton = screen.getByRole("button", {
      name: /generate cover letter/i,
    });
    // Title and company still required — Generate stays disabled.
    expect(generateButton).toBeDisabled();
  });

  it("generates a cover letter and shows the validation panel", async () => {
    const user = userEvent.setup();
    renderWithClient(<CoverLetterPage />);

    await user.type(
      screen.getByLabelText(/job title/i),
      "Senior Software Engineer",
    );
    await user.type(screen.getByLabelText(/company/i), "Tech Innovations Inc");
    await user.type(screen.getByLabelText(/location \(optional\)/i), "Remote");
    await user.type(
      getJdTextarea(),
      "We are seeking a talented Senior Software Engineer to join our team. " +
        "Requirements include 5+ years of React and TypeScript experience and strong architecture skills.",
    );

    const generateButton = screen.getByRole("button", {
      name: /generate cover letter/i,
    });
    await waitFor(() => expect(generateButton).not.toBeDisabled());
    await user.click(generateButton);

    await waitFor(() => {
      expect(mockGenerate).toHaveBeenCalledTimes(1);
    });
    expect(mockGenerate).toHaveBeenCalledWith(
      {
        title: "Senior Software Engineer",
        company: "Tech Innovations Inc",
        description: expect.stringContaining(
          "We are seeking a talented Senior Software Engineer",
        ),
        location: "Remote",
        style: "modern",
        writer_model: undefined,
      },
      false,
      false,
    );

    expect(
      await screen.findByDisplayValue(sampleCoverLetter.content),
    ).toBeInTheDocument();
    expect(screen.getByText(/ready to send/i)).toBeInTheDocument();
    expect(screen.getByText("88/100")).toBeInTheDocument();
    expect(screen.getByText(/Tokens:/i)).toBeInTheDocument();
    expect(screen.getByText(/2,200/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /export full analysis/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /export cover letter pdf/i }),
    ).toBeInTheDocument();
  });

  it("hides Sources when mission_context has no citations", async () => {
    const user = userEvent.setup();
    mockGenerate.mockResolvedValue({
      ...sampleResponse,
      mission_context: { status: "disabled" },
    });
    renderWithClient(<CoverLetterPage />);

    await user.type(screen.getByLabelText(/job title/i), "Engineer");
    await user.type(screen.getByLabelText(/company/i), "Acme");
    await user.type(
      getJdTextarea(),
      "We are seeking an engineer with Python experience for a remote role.",
    );
    await user.click(
      screen.getByRole("button", { name: /generate cover letter/i }),
    );
    await screen.findByDisplayValue(sampleCoverLetter.content);
    expect(
      screen.queryByTestId("cover-letter-sources"),
    ).not.toBeInTheDocument();
  });

  it("shows a single Sources card when one mission citation is present", async () => {
    const user = userEvent.setup();
    mockGenerate.mockResolvedValue({
      ...sampleResponse,
      mission_context: {
        status: "pass",
        brief: "Acme builds tools.",
        source_url: "https://www.acme.example/about",
        sources: [
          {
            index: 1,
            url: "https://www.acme.example/about",
            title: "About Acme",
            domain: "acme.example",
            snippet: "Acme builds developer tools.",
            kind: "company_mission",
          },
        ],
      },
    });
    renderWithClient(<CoverLetterPage />);

    await user.type(screen.getByLabelText(/job title/i), "Engineer");
    await user.type(screen.getByLabelText(/company/i), "Acme");
    await user.type(
      getJdTextarea(),
      "We are seeking an engineer with Python experience for a remote role.",
    );
    await user.click(
      screen.getByRole("button", { name: /generate cover letter/i }),
    );
    await screen.findByTestId("cover-letter-sources");
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /about acme/i })).toHaveAttribute(
      "href",
      "https://www.acme.example/about",
    );
  });

  it("shows a collapsible Sources panel for multiple citations", async () => {
    const user = userEvent.setup();
    mockGenerate.mockResolvedValue({
      ...sampleResponse,
      mission_context: {
        status: "pass",
        sources: [
          {
            index: 1,
            url: "https://www.acme.example/about",
            title: "About",
            domain: "acme.example",
          },
          {
            index: 2,
            url: "https://careers.acme.example/mission",
            title: "Mission",
            domain: "acme.example",
          },
        ],
      },
    });
    renderWithClient(<CoverLetterPage />);

    await user.type(screen.getByLabelText(/job title/i), "Engineer");
    await user.type(screen.getByLabelText(/company/i), "Acme");
    await user.type(
      getJdTextarea(),
      "We are seeking an engineer with Python experience for a remote role.",
    );
    await user.click(
      screen.getByRole("button", { name: /generate cover letter/i }),
    );
    const panel = await screen.findByTestId("cover-letter-sources");
    expect(panel).toHaveTextContent(/Sources \(2\)/);
    await user.click(screen.getByText(/Sources \(2\)/i));
    // Accessible name includes title plus domain (and icon text nodes).
    expect(
      await screen.findByRole("link", { name: /about/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /mission/i })).toBeInTheDocument();
  });

  it("toggles deep validation and sends deep=true", async () => {
    const user = userEvent.setup();
    renderWithClient(<CoverLetterPage />);

    await user.type(
      screen.getByLabelText(/job title/i),
      "Senior Software Engineer",
    );
    await user.type(screen.getByLabelText(/company/i), "Tech Innovations Inc");
    await user.type(
      getJdTextarea(),
      "We are seeking a talented Senior Software Engineer with React and TypeScript experience.",
    );

    const deepSwitch = screen.getByRole("switch", { name: /deep validation/i });
    await user.click(deepSwitch);
    expect(deepSwitch).toHaveAttribute("aria-checked", "true");

    const generateButton = screen.getByRole("button", {
      name: /generate cover letter/i,
    });
    await waitFor(() => expect(generateButton).not.toBeDisabled());
    await user.click(generateButton);

    await waitFor(() => {
      expect(mockGenerate).toHaveBeenCalledTimes(1);
    });
    expect(mockGenerate).toHaveBeenCalledWith(expect.any(Object), true, false);
  });

  it("exports the generated cover letter as DOCX", async () => {
    const user = userEvent.setup();
    renderWithClient(<CoverLetterPage />);

    await user.type(
      screen.getByLabelText(/job title/i),
      "Senior Software Engineer",
    );
    await user.type(screen.getByLabelText(/company/i), "Tech Innovations Inc");
    await user.type(
      getJdTextarea(),
      "We are seeking a talented Senior Software Engineer with React and TypeScript experience.",
    );

    await user.click(
      screen.getByRole("button", { name: /generate cover letter/i }),
    );
    await screen.findByDisplayValue(sampleCoverLetter.content);

    await user.click(
      screen.getByRole("button", { name: /export cover letter pdf/i }),
    );

    await waitFor(() => {
      expect(mockExport).toHaveBeenCalledTimes(1);
    });
    expect(mockExport).toHaveBeenCalledWith({
      content: sampleCoverLetter.content,
      format: "pdf",
      company: "Tech Innovations Inc",
      title: "Senior Software Engineer",
    });
    expect(mockDownloadFile).toHaveBeenCalledTimes(1);
  });

  it("exports full analysis JSON after generate", async () => {
    const user = userEvent.setup();
    renderWithClient(<CoverLetterPage />);

    await user.type(
      screen.getByLabelText(/job title/i),
      "Senior Software Engineer",
    );
    await user.type(screen.getByLabelText(/company/i), "Tech Innovations Inc");
    await user.type(
      getJdTextarea(),
      "We are seeking a talented Senior Software Engineer with React and TypeScript experience.",
    );

    await user.click(
      screen.getByRole("button", { name: /generate cover letter/i }),
    );
    await screen.findByDisplayValue(sampleCoverLetter.content);

    await user.click(
      screen.getByRole("button", { name: /export full analysis/i }),
    );

    await waitFor(() => {
      expect(mockExportAnalysis).toHaveBeenCalledTimes(1);
    });
    const call = mockExportAnalysis.mock.calls[0][0] as {
      format: string;
      analysis: {
        job: { company: string };
        settings: { writer_model: string };
      };
    };
    expect(call.format).toBe("json");
    expect(call.analysis.job.company).toBe("Tech Innovations Inc");
    expect(call.analysis.settings.writer_model).toBeTruthy();
    expect(mockDownloadFile).toHaveBeenCalled();
  });

  it("copies the generated cover letter to clipboard", async () => {
    const user = userEvent.setup();
    renderWithClient(<CoverLetterPage />);

    await user.type(
      screen.getByLabelText(/job title/i),
      "Senior Software Engineer",
    );
    await user.type(screen.getByLabelText(/company/i), "Tech Innovations Inc");
    await user.type(
      getJdTextarea(),
      "We are seeking a talented Senior Software Engineer with React and TypeScript experience.",
    );

    await user.click(
      screen.getByRole("button", { name: /generate cover letter/i }),
    );
    await screen.findByDisplayValue(sampleCoverLetter.content);

    // jsdom may not expose navigator.clipboard until after rendering, so mock it lazily.
    if (!navigator.clipboard) {
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText: vi.fn() },
        configurable: true,
        writable: true,
      });
    }
    const writeText = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockResolvedValue(undefined);

    await user.click(screen.getByRole("button", { name: /copy$/i }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(sampleCoverLetter.content);
    });
    expect(screen.getByRole("button", { name: /copied/i })).toBeInTheDocument();
  });

  it("shows validation issues when the result needs revision", async () => {
    const user = userEvent.setup();
    const issuesResponse: CoverLetterResponse = {
      ...sampleResponse,
      validation: {
        ...sampleCoverLetterValidation,
        is_valid: false,
        recommendation: "needs_revision",
        score: 62,
        issues: ["too_short", "missing_call_to_action"],
        details: {
          ...sampleCoverLetterValidation.details,
          has_call_to_action: false,
        },
      },
    };
    mockGenerate.mockResolvedValueOnce(issuesResponse);
    renderWithClient(<CoverLetterPage />);

    await user.type(
      screen.getByLabelText(/job title/i),
      "Senior Software Engineer",
    );
    await user.type(screen.getByLabelText(/company/i), "Tech Innovations Inc");
    await user.type(
      getJdTextarea(),
      "We are seeking a talented Senior Software Engineer with React and TypeScript experience.",
    );

    await user.click(
      screen.getByRole("button", { name: /generate cover letter/i }),
    );

    expect(await screen.findByText(/needs revision/i)).toBeInTheDocument();
    expect(screen.getByText(/too short/i)).toBeInTheDocument();
  });

  it("re-checks quality on demand after editing the letter", async () => {
    const user = userEvent.setup();
    renderWithClient(<CoverLetterPage />);

    await user.type(
      screen.getByLabelText(/job title/i),
      "Senior Software Engineer",
    );
    await user.type(screen.getByLabelText(/company/i), "Tech Innovations Inc");
    await user.type(
      getJdTextarea(),
      "We are seeking a talented Senior Software Engineer with React and TypeScript experience.",
    );

    const generateButton = screen.getByRole("button", {
      name: /generate cover letter/i,
    });
    await waitFor(() => expect(generateButton).not.toBeDisabled());
    await user.click(generateButton);

    const textarea = await screen.findByDisplayValue(sampleCoverLetter.content);
    expect(textarea).toBeInTheDocument();

    await user.clear(textarea);
    await user.type(textarea, "Edited cover letter content");

    const reCheckButton = screen.getByRole("button", {
      name: /re-check quality/i,
    });
    await waitFor(() => expect(reCheckButton).not.toBeDisabled());
    await user.click(reCheckButton);

    await waitFor(() => {
      expect(mockValidate).toHaveBeenCalledTimes(1);
    });
    expect(mockValidate).toHaveBeenCalledWith(
      expect.objectContaining({
        content: "Edited cover letter content",
        title: "Senior Software Engineer",
        company: "Tech Innovations Inc",
      }),
      expect.any(AbortSignal),
    );
    expect(await screen.findByText("82/100")).toBeInTheDocument();
  });

  it("shows an indeterminate wait bar while generating", async () => {
    mockGenerate.mockReturnValue(new Promise(() => {}));
    const user = userEvent.setup();
    renderWithClient(<CoverLetterPage />);

    await user.type(
      screen.getByLabelText(/job title/i),
      "Senior Software Engineer",
    );
    await user.type(screen.getByLabelText(/company/i), "Tech Innovations Inc");
    await user.type(
      getJdTextarea(),
      "We are seeking a talented Senior Software Engineer to join our team. " +
        "Requirements include 5+ years of React and TypeScript experience and strong architecture skills.",
    );

    const generateButton = screen.getByRole("button", {
      name: /generate cover letter/i,
    });
    await waitFor(() => expect(generateButton).not.toBeDisabled());
    await user.click(generateButton);

    const labels = await screen.findAllByText(/writing cover letter/i);
    expect(labels.length).toBeGreaterThan(0);
    const bars = screen.getAllByRole("progressbar");
    expect(bars.length).toBeGreaterThan(0);
    bars.forEach((bar) => {
      expect(bar).not.toHaveAttribute("aria-valuenow");
    });
    expect(generateButton).toBeDisabled();
  });
});
