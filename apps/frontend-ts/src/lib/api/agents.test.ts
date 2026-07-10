/**
 * Job Raider - Agents API Unit Tests
 *
 * Covers the typed Career Coach API helpers with mocked fetch responses.
 *
 * Author: Job Raider
 * Date: 2026-07-10
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { agentsApi } from "./agents";
import type {
  CareerAnalysisRequest,
  CareerAnalysisResult,
  CareerGoalsRequest,
  GapAnalysisRequest,
  UpskillingRoadmapRequest,
} from "@/lib/types/api";

// Spy on global fetch so these tests do not depend on MSW configuration.
const mockFetch = vi.fn();

describe("agentsApi", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  /**
   * Build a mocked ``fetch`` Response for the given JSON body.
   *
   * @param body Serializable response body.
   * @param status HTTP status code; defaults to ``200``.
   * @returns A promise resolving to a minimal ``Response``-like object.
   */
  function mockResponse<T>(body: T, status = 200) {
    return Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      statusText: status === 200 ? "OK" : "Error",
      json: () => Promise.resolve(body),
    } as Response);
  }

  const baseProfile: CareerAnalysisRequest["profile"] = {
    contact_info: {},
    target_job: {
      keywords: ["Software Engineer"],
      locations: ["Remote"],
      experience_levels: ["Senior"],
      remote_preference: true,
      constraint_mode: "boost",
    },
    skills: [],
    work_experience: [],
    education: [],
    projects: [],
  };

  it("submits a career analysis request", async () => {
    const submission = {
      data: {
        task_id: "task-1",
        agent: "career_coach",
        task_type: "career_analysis",
        status: "pending",
      },
    };
    mockFetch.mockReturnValueOnce(mockResponse(submission));

    const request: CareerAnalysisRequest = {
      profile: baseProfile,
      target_jobs: [{ title: "Senior Engineer" }],
    };
    const result = await agentsApi.careerAnalysis(request);

    expect(result).toEqual(submission);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/proxy/agents/career-analysis",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(request),
      }),
    );
  });

  it("submits a gap analysis request", async () => {
    const submission = {
      data: {
        task_id: "task-2",
        agent: "career_coach",
        task_type: "gap_analysis",
        status: "pending",
      },
    };
    mockFetch.mockReturnValueOnce(mockResponse(submission));

    const request: GapAnalysisRequest = {
      profile: baseProfile,
      target_jobs: [{ title: "Senior Engineer" }],
    };
    const result = await agentsApi.gapAnalysis(request);

    expect(result).toEqual(submission);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/proxy/agents/gap-analysis",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(request),
      }),
    );
  });

  it("submits an upskilling roadmap request", async () => {
    const submission = {
      data: {
        task_id: "task-3",
        agent: "career_coach",
        task_type: "upskilling_roadmap",
        status: "pending",
      },
    };
    mockFetch.mockReturnValueOnce(mockResponse(submission));

    const request: UpskillingRoadmapRequest = {
      profile: baseProfile,
      gap_analysis: {
        skills_gap: {},
        experience_gap: {},
        education_gap: {},
        recommendations: [],
      },
    };
    const result = await agentsApi.upskillingRoadmap(request);

    expect(result).toEqual(submission);
  });

  it("submits a career goals request", async () => {
    const submission = {
      data: {
        task_id: "task-4",
        agent: "career_coach",
        task_type: "career_goals",
        status: "pending",
      },
    };
    mockFetch.mockReturnValueOnce(mockResponse(submission));

    const request: CareerGoalsRequest = { profile: baseProfile };
    const result = await agentsApi.careerGoals(request);

    expect(result).toEqual(submission);
  });

  it("polls a task by ID with typed result", async () => {
    const result: CareerAnalysisResult = {
      current_positioning: {
        experience_level: "Senior",
        skill_count: 3,
        primary_skills: ["TypeScript", "React"],
        positioning_score: 80,
      },
      career_trajectory: {
        current_stage: "Senior Engineer",
        next_stage: "Staff Engineer",
        estimated_timeline: "2-3 years",
        required_advancements: ["System design"],
      },
      target_alignment: {},
      strategic_recommendations: [
        {
          category: "leadership",
          title: "Grow leadership scope",
          description: "Look for opportunities to lead projects end-to-end.",
          priority: "high",
          actions: ["Mentor junior engineers"],
        },
      ],
    };

    const taskRecord = {
      data: {
        task_id: "task-1",
        status: "completed" as const,
        result,
        created_at: "2026-07-10T00:00:00Z",
        updated_at: "2026-07-10T00:00:05Z",
      },
    };
    mockFetch.mockReturnValueOnce(mockResponse(taskRecord));

    const response = await agentsApi.getTask<CareerAnalysisResult>("task-1");

    expect(response.data.result).toEqual(result);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/proxy/agents/tasks/task-1",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("passes the abort signal to fetch", async () => {
    mockFetch.mockReturnValueOnce(
      mockResponse({
        data: {
          task_id: "task-signal",
          agent: "career_coach",
          task_type: "career_analysis",
          status: "pending",
        },
      }),
    );

    const controller = new AbortController();
    await agentsApi.careerAnalysis({ profile: baseProfile }, controller.signal);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/proxy/agents/career-analysis",
      expect.objectContaining({ signal: controller.signal }),
    );
  });

  it("throws an ApiError when the response is not OK", async () => {
    mockFetch.mockReturnValueOnce(
      mockResponse({ detail: "Invalid request payload" }, 422),
    );

    await expect(
      agentsApi.careerAnalysis({ profile: baseProfile }),
    ).rejects.toThrow("API 422: Invalid request payload");
  });
});
