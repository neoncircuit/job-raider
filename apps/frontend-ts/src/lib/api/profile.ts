import { request } from "./client";
import type {
  UserProfile,
  ResumeAnalysis,
  LinkedInProfileInput,
  LinkedInProfileAnalysis,
  LinkedInPeopleSearchInput,
  LinkedInPeopleSearchResponse,
  ProfileTargetsUpdate,
} from "@/lib/types/api";

export const profileApi = {
  get: () => request<UserProfile>("GET", "/profile"),

  update: (updates: Partial<UserProfile> | ProfileTargetsUpdate) =>
    request<{ message: string }>("PUT", "/profile", { body: updates }),

  export: () => request<UserProfile>("GET", "/profile/export"),

  /**
   * Export the active profile as a summary PDF.
   * Returns a raw Response so the caller can stream the file to disk.
   *
   * @returns Fetch Response with ``application/pdf`` body.
   */
  exportPdf: () =>
    fetch("/api/proxy/profile/export.pdf", {
      method: "GET",
    }),

  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    return request<{
      profile_id: string;
      resume_path: string;
      message: string;
      resume_parse?: {
        parsed_at?: string;
        duration_ms?: number;
        model?: string;
        provider?: string | null;
        method?: string;
      };
    }>("POST", "/profile/upload", { formData: fd });
  },

  analyze: (file: File, jobDescription?: string) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    if (jobDescription) fd.append("job_description", jobDescription);
    return request<ResumeAnalysis>("POST", "/profile/analyze", {
      formData: fd,
    });
  },

  analyzeLinkedIn: (input: LinkedInProfileInput) =>
    request<LinkedInProfileAnalysis>("POST", "/profile/analyze-linkedin", {
      body: input,
    }),

  searchLinkedInPeople: (input: LinkedInPeopleSearchInput) =>
    request<LinkedInPeopleSearchResponse>("POST", "/profile/search-linkedin", {
      body: input,
    }),
};
