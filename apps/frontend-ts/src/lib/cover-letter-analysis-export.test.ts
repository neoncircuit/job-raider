import { describe, expect, it } from "vitest";
import {
  buildCoverLetterAnalysisExport,
  jdSnippet,
} from "@/lib/cover-letter-analysis-export";
import type { CoverLetterResponse } from "@/lib/types/api";
import type { JdMatchResponse } from "@/lib/api/coverLetter";

const sampleResult: CoverLetterResponse = {
  success: true,
  job_id: "manual-1",
  cover_letter: {
    content: "Letter body",
    word_count: 2,
    model_used: "qwen2.5:7b",
    highlighted_experiences: [],
    style: "modern",
    timing: {
      selection_ms: 10,
      generation_ms: 1000,
      validation_ms: 5,
      total_ms: 1015,
    },
    token_usage: {
      total_tokens: 400,
      prompt_tokens: 300,
      completion_tokens: 100,
    },
  },
  validation: {
    is_valid: true,
    score: 90,
    issues: [],
    word_count: 2,
    structure_score: 90,
    content_score: 90,
    tone_score: 90,
    recommendation: "approve",
    details: {
      review: {
        critique: "Looks good.",
        rewrite_needed: false,
        rewrite_count: 0,
        model_used: "qwen2.5:3b",
      },
    },
  },
};

const sampleAssessment: JdMatchResponse = {
  score: 72,
  passed_threshold: true,
  recommendation: "maybe",
  reasoning: "Decent overlap.",
  breakdown: {
    keyword: 18,
    skills: 25,
    experience: 12,
    location: 8,
    projects: 5,
    education: 4,
  },
  matched_keywords: ["Python"],
  missing_skills: ["Go"],
  scam_risk: "low",
  scam_flags: [],
};

describe("cover-letter-analysis-export", () => {
  it("truncates long JD snippets", () => {
    const snippet = jdSnippet("x".repeat(600), 40);
    expect(snippet.endsWith("…")).toBe(true);
    expect(snippet.length).toBe(40);
  });

  it("builds a complete analysis payload for model-run diffs", () => {
    const payload = buildCoverLetterAnalysisExport({
      title: "Backend Engineer",
      company: "Harbor Labs",
      description: "Build APIs with Python and FastAPI.",
      location: "Singapore",
      style: "modern",
      deep: true,
      review: true,
      writerModelLabel: "qwen2.5:7b",
      letterText: "Edited letter body",
      result: sampleResult,
      validation: sampleResult.validation,
      assessment: sampleAssessment,
      exportedAt: "2026-08-25T12:00:00.000Z",
    });

    expect(payload.schema_version).toBe(1);
    expect(payload.exported_at).toBe("2026-08-25T12:00:00.000Z");
    expect(payload.job.title).toBe("Backend Engineer");
    expect(payload.job.jd_snippet).toContain("FastAPI");
    expect(payload.job_fit?.breakdown.skills).toBe(25);
    expect(payload.job_fit?.missing_skills).toEqual(["Go"]);
    expect(payload.letter_text).toBe("Edited letter body");
    expect(payload.settings).toEqual({
      writer_model: "qwen2.5:7b",
      style: "modern",
      deep_validation: true,
      review_rewrite: true,
    });
    expect(payload.timing?.generation_ms).toBe(1000);
    expect(payload.token_usage?.total_tokens).toBe(400);
    expect(payload.proofread?.score).toBe(90);
    expect(payload.review?.critique).toBe("Looks good.");
    expect(payload.review?.rewrite_needed).toBe(false);
  });

  it("allows null job_fit when assessment is missing", () => {
    const payload = buildCoverLetterAnalysisExport({
      title: "Role",
      company: "Co",
      description: "A".repeat(60),
      style: "classic",
      deep: false,
      review: false,
      writerModelLabel: "settings-default",
      letterText: "Body",
      result: sampleResult,
      validation: null,
      assessment: null,
    });
    expect(payload.job_fit).toBeNull();
    expect(payload.proofread?.score).toBe(90);
  });
});
