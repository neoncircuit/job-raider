"use client";

import { useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { jobsApi } from "@/lib/api/jobs";
import { pipelineApi } from "@/lib/api/pipeline";
import { applicationsApi } from "@/lib/api/applications";
import { coverLetterApi } from "@/lib/api/coverLetter";
import type { JobSearchRequest } from "@/lib/api/jobs";
import type { ScoreExplanation } from "@/lib/api/coverLetter";
import type {
  JobListing,
  JobClassification,
  TrustAnalysis,
  CoverLetterValidation,
  DiscoverShortlistResponse,
} from "@/lib/types/api";

const DASHBOARD_QUERY_KEY = ["applications", "dashboard"] as const;

interface UseJobSearchResult {
  /** Matching jobs, or undefined while loading. */
  data: { jobs: JobListing[] } | undefined;
  /** True during the first fetch. */
  isLoading: boolean;
  /** Truthy if the query encountered an error. */
  error: Error | null;
}

/**
 * Search for jobs using committed query parameters.
 *
 * The query is disabled until a non-null request is provided, so the page
 * controls when a search actually runs.
 *
 * @param params - Backend search request, or null to keep the query idle.
 * @returns The query result for the search request.
 */
export function useJobSearch(
  params: JobSearchRequest | null,
): UseJobSearchResult {
  const { data, isLoading, error } = useQuery({
    queryKey: ["jobs", "search", params],
    queryFn: ({ signal }) => jobsApi.search(params!, signal),
    enabled: params !== null,
    staleTime: 5 * 60 * 1000,
  });

  return { data, isLoading, error };
}

interface UseLatestShortlistResult {
  /** Latest discover shortlist payload, or undefined while loading. */
  data: DiscoverShortlistResponse | undefined;
  /** True during the first fetch. */
  isLoading: boolean;
  /** Truthy if the query encountered an error. */
  error: Error | null;
  /** Refetch the shortlist (e.g. after a new discover run). */
  refetch: () => void;
}

/**
 * Load the latest pipeline discover shortlist for Jobs review.
 *
 * @returns Query result for ``GET /pipeline/shortlist/latest``.
 */
export function useLatestShortlist(): UseLatestShortlistResult {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["pipeline", "shortlist", "latest"],
    queryFn: ({ signal }) => pipelineApi.getLatestShortlist(signal),
    staleTime: 30_000,
  });

  return {
    data,
    isLoading,
    error:
      error instanceof Error ? error : error ? new Error(String(error)) : null,
    refetch: () => {
      void refetch();
    },
  };
}

interface UseSavedAndExternalJobIdsResult {
  /** Set of saved/bookmarked application IDs. */
  savedIds: Set<string>;
  /** Set of externally-applied application IDs. */
  externalIds: Set<string>;
  /** True during the first dashboard fetch. */
  isLoading: boolean;
  /** Truthy if the dashboard query encountered an error. */
  error: Error | null;
}

/**
 * Derive saved and externally-applied job IDs from the applications dashboard.
 *
 * A single dashboard query feeds both derived sets, avoiding multiple round-trips.
 *
 * @returns Memoized sets of saved and externally-applied IDs plus query status.
 */
export function useSavedAndExternalJobIds(): UseSavedAndExternalJobIdsResult {
  const { data, isLoading, error } = useQuery({
    queryKey: DASHBOARD_QUERY_KEY,
    queryFn: () => applicationsApi.getDashboard({ include_hidden: false }),
    staleTime: 30_000,
  });

  return useMemo(() => {
    const applications = data?.applications ?? [];
    const savedIds = new Set<string>(
      applications.filter((a) => a.is_bookmarked).map((a) => a.application_id),
    );
    const externalIds = new Set<string>(
      applications
        .filter((a) => a.current_status === "applied_elsewhere")
        .map((a) => a.application_id),
    );

    return { savedIds, externalIds, isLoading, error };
  }, [data, isLoading, error]);
}

/**
 * Toggle the saved/bookmarked state for a job.
 *
 * Invalidates the applications dashboard so saved/external IDs refresh everywhere.
 *
 * @returns Mutation helpers for toggling the saved state.
 */
export function useSaveJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, saved }: { id: string; saved: boolean }) =>
      applicationsApi.action(id, saved ? "unsave" : "save"),
    onSuccess: (_, { saved }) => {
      toast.success(saved ? "Removed from saved" : "Job saved");
      queryClient.invalidateQueries({ queryKey: ["applications"] });
    },
    onError: () => {
      toast.error("Action failed");
    },
  });
}

/**
 * Track that a job was applied to on an external site.
 *
 * @returns Mutation helpers for marking a job as applied externally.
 */
export function useMarkAppliedElsewhere() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      title,
      company,
    }: {
      id: string;
      title: string;
      company: string;
    }) => applicationsApi.markAppliedExternally(id, title, company),
    onSuccess: () => {
      toast.success("Marked as applied externally");
      void queryClient.invalidateQueries({ queryKey: ["applications"] });
    },
    onError: (error: Error) => {
      toast.error(
        error.message
          ? `Failed to mark as applied externally: ${error.message}`
          : "Failed to mark as applied externally",
      );
    },
  });
}

/**
 * Trigger a simulated (dry-run) apply for a job.
 *
 * Real non-dry-run submission is not exposed yet; the API always runs
 * with ``dry_run=true`` from this hook.
 *
 * @returns Mutation helpers for simulating an application.
 */
export function useApplyJob() {
  return useMutation({
    mutationFn: (id: string) => jobsApi.apply(id, true),
    onSuccess: (data) => {
      toast.success(data.message || "Application simulated (dry run only)");
    },
    onError: (error: Error) => {
      toast.error(`Simulate apply failed: ${error.message}`);
    },
  });
}

/**
 * Cache key helpers for per-job analysis results.
 */
const classificationKey = (jobId: string) => ["jobs", jobId, "classification"];
const trustKey = (jobId: string) => ["jobs", jobId, "trust-analysis"];
const coverLetterKey = (jobId: string, deep: boolean) =>
  ["jobs", jobId, "cover-letter", { deep }] as const;
const explainFitKey = (jobId: string) => ["jobs", jobId, "explain-fit"];

/**
 * Classify a job and cache the result against the job ID.
 *
 * @returns Mutation helpers for running classification.
 */
export function useClassifyJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, job }: { id: string; job: JobListing }) =>
      jobsApi.classify(id, {
        title: job.title,
        company: job.company,
        description: job.description ?? undefined,
        location: job.location ?? undefined,
        source: job.source,
      }),
    onSuccess: (data, { id }) => {
      queryClient.setQueryData<JobClassification>(
        classificationKey(id),
        data.classification,
      );
      toast.success("Job classified successfully");
    },
    onError: () => {
      toast.error("Failed to classify job");
    },
  });
}

/**
 * Analyze trust for a job and cache the result against the job ID.
 *
 * @returns Mutation helpers for running trust analysis.
 */
export function useAnalyzeTrust() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      job,
      deep = false,
    }: {
      id: string;
      job: JobListing;
      deep?: boolean;
    }) =>
      jobsApi.trustAnalysis(
        id,
        {
          title: job.title,
          company: job.company,
          description: job.description ?? undefined,
          location: job.location ?? undefined,
          source: job.source,
        },
        deep,
      ),
    onSuccess: (data, { id }) => {
      queryClient.setQueryData<TrustAnalysis>(
        trustKey(id),
        data.trust_analysis,
      );
      toast.success("Trust analysis complete");
    },
    onError: () => {
      toast.error("Failed to analyze trust");
    },
  });
}

interface CoverLetterData {
  content: string;
  validation: CoverLetterValidation;
}

/**
 * Generate a cover letter for a job and cache the result against the job ID.
 *
 * @returns Mutation helpers for generating a cover letter.
 */
export function useGenerateCoverLetter() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      job,
      deep = false,
    }: {
      id: string;
      job: JobListing;
      deep?: boolean;
    }) =>
      jobsApi.generateCoverLetter(
        id,
        {
          title: job.title,
          company: job.company,
          description: job.description ?? undefined,
          location: job.location ?? undefined,
          source: job.source,
        },
        deep,
      ),
    onSuccess: (data, { id, deep }) => {
      queryClient.setQueryData<CoverLetterData>(
        coverLetterKey(id, deep ?? false),
        { content: data.cover_letter.content, validation: data.validation },
      );
      toast.success("Cover letter generated");
    },
    onError: () => {
      toast.error("Failed to generate cover letter. Upload a resume first.");
    },
  });
}

/**
 * Explain, in plain language, why a job's heuristic fit score was given.
 *
 * Reuses `POST /cover-letter/explain-fit`, which computes and explains a
 * fresh fit score from the supplied job fields — no server-side job lookup
 * by ID exists, matching the same pattern as {@link useClassifyJob}.
 *
 * @returns Mutation helpers for running the fit explanation.
 */
export function useExplainJobFit() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ job }: { id: string; job: JobListing }) =>
      coverLetterApi.explainFit({
        title: job.title,
        company: job.company,
        description: job.description ?? "",
        location: job.location ?? undefined,
      }),
    onSuccess: (data, { id }) => {
      queryClient.setQueryData<ScoreExplanation>(explainFitKey(id), data);
      toast.success("Fit explanation generated");
    },
    onError: () => {
      toast.error("Failed to explain fit");
    },
  });
}

/**
 * Read a cached classification result for a job.
 *
 * The query is disabled because it is only populated by {@link useClassifyJob}.
 *
 * @param jobId - Job ID to look up.
 * @returns The cached classification, or null when absent.
 */
export function useCachedClassification(jobId: string) {
  return useQuery<JobClassification | null>({
    queryKey: classificationKey(jobId),
    queryFn: () => null,
    enabled: false,
  });
}

/**
 * Read a cached trust-analysis result for a job.
 *
 * @param jobId - Job ID to look up.
 * @returns The cached trust analysis, or null when absent.
 */
export function useCachedTrustAnalysis(jobId: string) {
  return useQuery<TrustAnalysis | null>({
    queryKey: trustKey(jobId),
    queryFn: () => null,
    enabled: false,
  });
}

/**
 * Read a cached cover letter for a job and deep-check mode.
 *
 * @param jobId - Job ID to look up.
 * @param deep - Whether the deep-check variant was requested.
 * @returns The cached cover letter data, or null when absent.
 */
export function useCachedCoverLetter(jobId: string, deep: boolean) {
  return useQuery<CoverLetterData | null>({
    queryKey: coverLetterKey(jobId, deep),
    queryFn: () => null,
    enabled: false,
  });
}

/**
 * Read a cached job-fit explanation for a job.
 *
 * The query is disabled because it is only populated by {@link useExplainJobFit}.
 *
 * @param jobId - Job ID to look up.
 * @returns The cached explanation, or null when absent.
 */
export function useCachedExplainFit(jobId: string) {
  return useQuery<ScoreExplanation | null>({
    queryKey: explainFitKey(jobId),
    queryFn: () => null,
    enabled: false,
  });
}
