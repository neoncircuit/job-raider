import { request } from "./client";
import type {
  AssessmentSession,
  ProgressStats,
  DISCSession,
  DISCResult,
  DISCAnswer,
} from "@/lib/types/api";

export interface StartAssessmentRequest {
  mode: "job_targeted" | "skill_based";
  target_job_ids?: string[];
  target_skills?: string[];
  difficulty?: "beginner" | "intermediate" | "advanced" | "expert";
  question_count?: number;
}

export interface SubmitAnswerRequest {
  question_id: string;
  selected_option?: string;
  freeform_text?: string;
  time_taken_seconds?: number;
}

export interface AnswerResponse {
  score: {
    question_id: string;
    score: number;
    is_correct?: boolean | null;
    feedback: string;
    strengths: string[];
    improvements: string[];
    model_answer: string;
  };
  session_completed: boolean;
  overall_score: number | null;
}

export const assessmentApi = {
  start: (req: StartAssessmentRequest) =>
    request<AssessmentSession>("POST", "/assessment/", { body: req }),

  list: () => request<AssessmentSession[]>("GET", "/assessment/"),

  get: (id: string) => request<AssessmentSession>("GET", `/assessment/${id}`),

  nextQuestions: (id: string) =>
    request<AssessmentSession>("POST", `/assessment/${id}/next`),

  submitAnswer: (id: string, answer: SubmitAnswerRequest) =>
    request<AnswerResponse>("POST", `/assessment/${id}/answer`, {
      body: answer,
    }),

  complete: (id: string) =>
    request<AssessmentSession>("POST", `/assessment/${id}/complete`),

  delete: (id: string) =>
    request<{ success: boolean; message: string }>(
      "DELETE",
      `/assessment/${id}`,
    ),

  progress: () => request<ProgressStats>("GET", "/assessment/progress"),

  availableSkills: () =>
    request<{ skills: string[] }>("GET", "/assessment/skills"),

  availableJobs: () =>
    request<{
      jobs: Array<{ job_id: string; title: string; company: string }>;
    }>("GET", "/assessment/jobs"),
};

export interface DISCSubmitRequest {
  session_id: string;
  answers: DISCAnswer[];
}

export const discApi = {
  start: () => request<DISCSession>("POST", "/assessment/disc/start"),

  submit: (req: DISCSubmitRequest) =>
    request<DISCResult>("POST", "/assessment/disc/submit", { body: req }),

  getProfile: () => request<DISCResult>("GET", "/assessment/disc/profile"),
};
