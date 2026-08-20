import { request } from "./client";
import type {
  CoverLetterResponse,
  CoverLetterValidation,
} from "@/lib/types/api";

export interface ManualCoverLetterRequest {
  title: string;
  company: string;
  description: string;
  location?: string;
  /** modern = achievement-led; classic = traditional letter structure */
  style?: "modern" | "classic";
  /** Optional one-shot cover_letter_writing model override */
  writer_model?: string;
}

export interface CoverLetterExportRequest {
  content: string;
  format: "docx" | "pdf";
  company: string;
  title: string;
}

export interface JdMatchResponse {
  score: number;
  passed_threshold: boolean;
  recommendation: "apply" | "maybe" | "skip";
  reasoning: string;
  breakdown: Record<string, number>;
  matched_keywords: string[];
  missing_skills: string[];
  scam_risk: "low" | "medium" | "high";
  scam_flags: string[];
}

export interface PrepSheetResponse {
  success: boolean;
  likely_questions: string[];
  gaps_to_address: string[];
  talking_points: string[];
}

export interface ScoreExplanation {
  strengths: string[];
  concerns: string[];
  improvements: string[];
  /** Heuristic score the explanation was grounded on, when returned. */
  fit_score?: number | null;
}

export interface ParseJdDocumentResponse {
  text: string;
  filename: string;
  char_count: number;
  warnings: string[];
}

export interface ValidateCoverLetterRequest extends ManualCoverLetterRequest {
  content: string;
  deep?: boolean;
}

export interface DetectInstructionsResponse {
  why_interest: {
    min_n: number;
    /** Null when the JD only set a floor (e.g. "minimum 50 words"). */
    max_n: number | null;
    unit: string;
    matched_span: string;
  } | null;
  inclusions: Array<{ kind: string; matched_span: string }>;
  short_answer_mode: boolean;
  has_inclusions: boolean;
}

export const coverLetterApi = {
  /**
   * Generate a tailored cover letter from a manually pasted job description.
   */
  generate: (req: ManualCoverLetterRequest, deep = false, review = false) => {
    const params: Record<string, boolean> = {};
    if (deep) params.deep = true;
    if (review) params.review = true;
    return request<CoverLetterResponse>("POST", "/cover-letter/manual", {
      body: req,
      params: Object.keys(params).length > 0 ? params : undefined,
    });
  },

  /**
   * Extract plain text from an uploaded JD PDF or DOCX.
   * Does not generate a letter or call assess/prep.
   */
  parseJd: (file: File) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    return request<ParseJdDocumentResponse>("POST", "/cover-letter/parse-jd", {
      formData: fd,
    });
  },

  /**
   * Scan pasted JD text for length-constrained why-interest asks and
   * inclusion asks (no LLM). Safe to call while typing.
   */
  detectInstructions: (description: string, signal?: AbortSignal) =>
    request<DetectInstructionsResponse>(
      "POST",
      "/cover-letter/detect-instructions",
      {
        body: { description },
        signal,
      },
    ),

  /**
   * Score a pasted job description against the stored profile without
   * generating a letter. Supports aborting stale requests while typing.
   */
  assess: (req: ManualCoverLetterRequest, signal?: AbortSignal) =>
    request<JdMatchResponse>("POST", "/cover-letter/assess", {
      body: req,
      signal,
    }),

  /**
   * Generate an interview prep sheet (likely questions, gaps, talking
   * points) for a pasted job description.
   */
  prep: (req: ManualCoverLetterRequest) =>
    request<PrepSheetResponse>("POST", "/cover-letter/prep", { body: req }),

  /**
   * Re-validate an edited cover letter and return fresh quality metrics.
   * Fast deterministic checks unless `deep` is set. Supports aborting stale
   * requests while the user types.
   */
  validate: (req: ValidateCoverLetterRequest, signal?: AbortSignal) =>
    request<CoverLetterValidation>("POST", "/cover-letter/validate", {
      body: req,
      signal,
    }),

  /**
   * Generate a plain-language explanation of the job-fit score (strengths,
   * concerns, improvements). On-demand LLM call.
   */
  explainFit: (req: ManualCoverLetterRequest) =>
    request<ScoreExplanation>("POST", "/cover-letter/explain-fit", {
      body: req,
    }),

  /**
   * Generate a plain-language explanation of the cover letter's quality
   * (strengths, concerns, improvements). On-demand LLM call.
   */
  explainLetter: (req: ValidateCoverLetterRequest) =>
    request<ScoreExplanation>("POST", "/cover-letter/explain-letter", {
      body: req,
    }),

  /**
   * Export an existing cover letter to DOCX or PDF.
   * Returns a raw Response so the caller can stream the file to disk.
   */
  export: (req: CoverLetterExportRequest) =>
    fetch("/api/proxy/cover-letter/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    }),
};

/**
 * Trigger a browser download from a fetch Response.
 */
export async function downloadFile(
  res: Response,
  fallbackName: string,
): Promise<void> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const json = await res.json();
      detail = json?.detail ?? json?.message ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(`Export failed: ${detail}`);
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);

  const header = res.headers.get("content-disposition");
  let filename = fallbackName;
  if (header) {
    const match = header.match(/filename="?([^";]+)"?/);
    if (match?.[1]) filename = match[1];
  }

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
