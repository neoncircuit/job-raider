import { request } from "./client";
import type {
  ApplicationDashboardResponse,
  ApplicationDetail,
  CustomStatus,
} from "@/lib/types/api";

export type JobAction = "save" | "unsave" | "hide" | "unhide";

export interface DashboardFilters {
  status?: string;
  company?: string;
  days?: number;
  include_hidden?: boolean;
  include_bookmarked?: boolean;
  include_external?: boolean;
}

export const applicationsApi = {
  action: (
    jobId: string,
    action: JobAction,
    opts?: { note?: string; metadata?: Record<string, unknown> },
  ) =>
    request<{
      success: boolean;
      job_id: string;
      action: string;
      new_status?: string;
      message: string;
    }>("POST", "/applications/actions", {
      body: { job_id: jobId, action, ...opts },
    }),

  getDashboard: (filters: DashboardFilters = {}) =>
    request<ApplicationDashboardResponse>("GET", "/applications/dashboard", {
      params: filters as Record<
        string,
        string | number | boolean | undefined | null
      >,
    }),

  getDetail: (jobId: string) =>
    request<ApplicationDetail>("GET", `/applications/${jobId}`),

  trackExternal: (data: {
    job_id: string;
    job_title: string;
    company: string;
    application_date?: string;
    application_method?: string;
    metadata?: Record<string, unknown>;
  }) =>
    request<{
      success: boolean;
      application_id: string;
      status: string;
      message: string;
    }>("POST", "/applications/external", { body: data }),

  markAppliedExternally: (jobId: string, jobTitle?: string, company?: string) =>
    request<{ success: boolean; message: string }>(
      "POST",
      "/applications/external",
      {
        body: {
          job_id: jobId,
          job_title: jobTitle || "Unknown",
          company: company || "Unknown",
          application_method: "External site",
        },
      },
    ),

  createCustomStatus: (data: {
    name: string;
    description: string;
    color?: string;
    icon?: string;
  }) =>
    request<CustomStatus>("POST", "/applications/statuses/custom", {
      body: data,
    }),

  getCustomStatuses: (activeOnly = true) =>
    request<CustomStatus[]>("GET", "/applications/statuses/custom", {
      params: { active_only: activeOnly },
    }),

  setCustomStatus: (jobId: string, customStatusId: string, note?: string) =>
    request<{ success: boolean }>("POST", "/applications/statuses/set", {
      body: { job_id: jobId, custom_status_id: customStatusId, note },
    }),

  updateStatus: (jobId: string, status: string, note?: string) =>
    request<{ success: boolean }>("PUT", "/applications/status", {
      body: { job_id: jobId, status, note },
    }),
};
