/**
 * Build a structured cover-letter analysis export payload.
 *
 * Used to compare model runs (JSON primary). Fields mirror the Cover
 * Letter page: job fit, letter text, settings, timing/tokens, proofread,
 * and reviewer feedback.
 */

import type {
  CoverLetterResponse,
  CoverLetterValidation,
} from "@/lib/types/api";
import type { JdMatchResponse } from "@/lib/api/coverLetter";

/** Schema version for analysis export files. */
export const COVER_LETTER_ANALYSIS_SCHEMA_VERSION = 1;

/** Max characters kept from the JD in the export. */
export const JD_SNIPPET_MAX = 500;

export interface CoverLetterAnalysisJob {
  title: string;
  company: string;
  location?: string | null;
  jd_snippet: string;
  job_id?: string | null;
}

export interface CoverLetterAnalysisSettings {
  writer_model: string;
  style: string;
  deep_validation: boolean;
  review_rewrite: boolean;
}

export interface CoverLetterAnalysisExport {
  schema_version: number;
  exported_at: string;
  job: CoverLetterAnalysisJob;
  job_fit: JdMatchResponse | null;
  letter_text: string;
  settings: CoverLetterAnalysisSettings;
  timing: CoverLetterResponse["cover_letter"]["timing"] | null;
  token_usage: CoverLetterResponse["cover_letter"]["token_usage"] | null;
  proofread: {
    score: number;
    structure_score: number;
    content_score: number;
    tone_score: number;
    recommendation: string;
    issues: string[];
    is_valid: boolean;
    word_count: number;
  } | null;
  review: {
    critique: string;
    rewrite_needed: boolean;
    rewrite_count: number;
    model_used: string;
    error?: string | null;
    review_ms?: number | null;
    rewrite_ms?: number | null;
    review_tokens?: number | null;
    rewrite_tokens?: number | null;
  } | null;
}

export interface BuildCoverLetterAnalysisInput {
  title: string;
  company: string;
  description: string;
  location?: string;
  style: string;
  deep: boolean;
  review: boolean;
  writerModelLabel: string;
  letterText: string;
  result: CoverLetterResponse | null;
  validation: CoverLetterValidation | null;
  assessment: JdMatchResponse | null;
  exportedAt?: string;
}

/**
 * Truncate a job description for export payloads.
 *
 * @param description - Full JD text.
 * @param maxChars - Maximum characters to keep.
 * @returns Truncated snippet with an ellipsis when shortened.
 */
export function jdSnippet(
  description: string,
  maxChars: number = JD_SNIPPET_MAX,
): string {
  const text = (description || "").trim();
  if (text.length <= maxChars) return text;
  return `${text.slice(0, maxChars - 1).trimEnd()}…`;
}

/**
 * Build a versioned analysis export object from Cover Letter page state.
 *
 * @param input - Form, generate result, assessment, and letter text.
 * @returns Structured payload ready for JSON/PDF export.
 */
export function buildCoverLetterAnalysisExport(
  input: BuildCoverLetterAnalysisInput,
): CoverLetterAnalysisExport {
  const validation = input.validation ?? input.result?.validation ?? null;
  const details = (validation?.details ?? {}) as Record<string, unknown>;
  const reviewRaw = details.review as
    CoverLetterAnalysisExport["review"] | undefined;

  return {
    schema_version: COVER_LETTER_ANALYSIS_SCHEMA_VERSION,
    exported_at: input.exportedAt ?? new Date().toISOString(),
    job: {
      title: input.title.trim(),
      company: input.company.trim(),
      location: input.location?.trim() || null,
      jd_snippet: jdSnippet(input.description),
      job_id: input.result?.job_id ?? null,
    },
    job_fit: input.assessment
      ? {
          score: input.assessment.score,
          passed_threshold: input.assessment.passed_threshold,
          recommendation: input.assessment.recommendation,
          reasoning: input.assessment.reasoning,
          breakdown: { ...input.assessment.breakdown },
          matched_keywords: [...input.assessment.matched_keywords],
          missing_skills: [...input.assessment.missing_skills],
          scam_risk: input.assessment.scam_risk,
          scam_flags: [...input.assessment.scam_flags],
        }
      : null,
    letter_text: input.letterText,
    settings: {
      writer_model:
        input.result?.cover_letter.model_used || input.writerModelLabel,
      style: input.result?.cover_letter.style || input.style,
      deep_validation: input.deep,
      review_rewrite: input.review,
    },
    timing: input.result?.cover_letter.timing ?? null,
    token_usage: input.result?.cover_letter.token_usage ?? null,
    proofread: validation
      ? {
          score: validation.score,
          structure_score: validation.structure_score,
          content_score: validation.content_score,
          tone_score: validation.tone_score,
          recommendation: validation.recommendation,
          issues: [...validation.issues],
          is_valid: validation.is_valid,
          word_count: validation.word_count,
        }
      : null,
    review: reviewRaw
      ? {
          critique: String(reviewRaw.critique ?? ""),
          rewrite_needed: Boolean(reviewRaw.rewrite_needed),
          rewrite_count: Number(reviewRaw.rewrite_count ?? 0),
          model_used: String(reviewRaw.model_used ?? ""),
          error: reviewRaw.error ?? null,
          review_ms: reviewRaw.review_ms ?? null,
          rewrite_ms: reviewRaw.rewrite_ms ?? null,
          review_tokens: reviewRaw.review_tokens ?? null,
          rewrite_tokens: reviewRaw.rewrite_tokens ?? null,
        }
      : null,
  };
}
