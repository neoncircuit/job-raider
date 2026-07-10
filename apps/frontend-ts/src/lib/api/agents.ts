import { request } from "./client";
import type {
  CareerAnalysisRequest,
  CareerAnalysisResult,
  CareerGoalsRequest,
  CareerGoalsResult,
  GapAnalysisRequest,
  GapAnalysisResult,
  TaskRecord,
  TaskSubmissionResponse,
  UpskillingRoadmapRequest,
  UpskillingRoadmapResult,
} from "@/lib/types/api";

/**
 * API helpers for the multi-agent system.
 *
 * All agent tasks are asynchronous. Each submission returns a task ID that
 * can be polled via ``getTask`` until the task reaches ``completed`` or
 * ``failed``.
 */
export const agentsApi = {
  /**
   * Trigger a career-path analysis for the given profile.
   *
   * @param req Career analysis request payload.
   * @returns Task submission envelope containing the task ID.
   */
  careerAnalysis: (req: CareerAnalysisRequest, signal?: AbortSignal) =>
    request<{ data: TaskSubmissionResponse }>(
      "POST",
      "/agents/career-analysis",
      {
        body: req,
        signal,
      },
    ),

  /**
   * Trigger a skill-gap analysis against one or more target jobs.
   *
   * @param req Gap analysis request payload.
   * @returns Task submission envelope containing the task ID.
   */
  gapAnalysis: (req: GapAnalysisRequest, signal?: AbortSignal) =>
    request<{ data: TaskSubmissionResponse }>("POST", "/agents/gap-analysis", {
      body: req,
      signal,
    }),

  /**
   * Generate an upskilling roadmap from a gap-analysis result.
   *
   * @param req Upskilling roadmap request payload.
   * @returns Task submission envelope containing the task ID.
   */
  upskillingRoadmap: (req: UpskillingRoadmapRequest, signal?: AbortSignal) =>
    request<{ data: TaskSubmissionResponse }>(
      "POST",
      "/agents/upskilling-roadmap",
      {
        body: req,
        signal,
      },
    ),

  /**
   * Generate SMART career goals from the given profile.
   *
   * @param req Career goals request payload.
   * @returns Task submission envelope containing the task ID.
   */
  careerGoals: (req: CareerGoalsRequest, signal?: AbortSignal) =>
    request<{ data: TaskSubmissionResponse }>("POST", "/agents/career-goals", {
      body: req,
      signal,
    }),

  /**
   * Poll for the status and result of a previously submitted agent task.
   *
   * The backend returns ``202`` while the task is still pending. This helper
   * resolves with whatever payload is returned; callers should inspect
   * ``data.status`` to decide whether to keep polling.
   *
   * @param taskId Task identifier returned by a submission endpoint.
   * @returns Task record containing status, result, or error.
   */
  getTask: <T = Record<string, unknown>>(
    taskId: string,
    signal?: AbortSignal,
  ) =>
    request<{ data: TaskRecord<T> }>(
      "GET",
      `/agents/tasks/${encodeURIComponent(taskId)}`,
      {
        signal,
      },
    ),
};

/** Convenience alias for the common Career Coach submission response. */
export type CareerCoachSubmissionResponse = { data: TaskSubmissionResponse };

/** Convenience aliases for typed task records. */
export type CareerAnalysisTaskRecord = TaskRecord<CareerAnalysisResult>;
export type GapAnalysisTaskRecord = TaskRecord<GapAnalysisResult>;
export type UpskillingRoadmapTaskRecord = TaskRecord<UpskillingRoadmapResult>;
export type CareerGoalsTaskRecord = TaskRecord<CareerGoalsResult>;
