import { request } from "./client";
import type {
  CoverLetterResponse,
  JobSearchResponse,
  SemanticSearchResponse,
  JobSimilarityResponse,
  JobClassification,
  TrustAnalysis,
} from "@/lib/types/api";

export interface JobSearchRequest {
  keywords: string[];
  locations: string[];
  sources?: string[];
  limit?: number;
  remote_only?: boolean;
}

export interface SemanticSearchRequest {
  query: string;
  n_results?: number;
  min_similarity?: number;
}

export const jobsApi = {
  getSources: () => request<{ sources: string[] }>("GET", "/jobs/sources"),

  search: (req: JobSearchRequest, signal?: AbortSignal) =>
    request<JobSearchResponse>("POST", "/jobs/search", { body: req, signal }),

  semanticSearch: (req: SemanticSearchRequest, signal?: AbortSignal) =>
    request<SemanticSearchResponse>("POST", "/jobs/search/semantic", {
      body: req,
      signal,
    }),

  getSimilarity: (jobId: string) =>
    request<JobSimilarityResponse>("GET", `/jobs/${jobId}/similarity`),

  score: (jobId: string) =>
    request<{ total_score: number; details?: Record<string, unknown> }>(
      "POST",
      `/jobs/${jobId}/score`,
    ),

  classify: (
    jobId: string,
    jobData: {
      title: string;
      company: string;
      description?: string;
      location?: string;
      source?: string;
    },
  ) =>
    request<{
      success: boolean;
      job_id: string;
      classification: JobClassification;
      warnings?: string[];
    }>("POST", `/jobs/${jobId}/classify`, {
      body: jobData,
    }),

  trustAnalysis: (
    jobId: string,
    jobData: {
      title: string;
      company: string;
      description?: string;
      location?: string;
      source?: string;
    },
    deep = false,
  ) =>
    request<{
      success: boolean;
      job_id: string;
      trust_analysis: TrustAnalysis;
    }>("POST", `/jobs/${jobId}/trust-analysis`, {
      body: jobData,
      params: deep ? { deep: true } : undefined,
    }),

  apply: (jobId: string, dryRun = true) =>
    request<{
      success: boolean;
      job_id: string;
      dry_run: boolean;
      message: string;
      application_id?: string;
      status?: string;
      next_steps?: string[];
    }>("POST", `/jobs/${jobId}/apply`, {
      params: { dry_run: dryRun },
    }),

  generateCoverLetter: (
    jobId: string,
    jobData: {
      title: string;
      company: string;
      description?: string;
      location?: string;
      source?: string;
    },
    deep = false,
  ) =>
    request<CoverLetterResponse>("POST", `/jobs/${jobId}/cover-letter`, {
      body: jobData,
      params: deep ? { deep: true } : undefined,
    }),
};
