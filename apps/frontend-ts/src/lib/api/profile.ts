import { request } from "./client";
import type {
  UserProfile,
  ResumeAnalysis,
  LinkedInProfileInput,
  LinkedInProfileAnalysis,
  LinkedInPeopleSearchInput,
  LinkedInPeopleSearchResponse,
} from "@/lib/types/api";

export const profileApi = {
  get: () =>
    request<UserProfile>("GET", "/profile"),

  update: (updates: Partial<UserProfile>) =>
    request<{ message: string }>("PUT", "/profile", { body: updates }),

  export: () =>
    request<UserProfile>("GET", "/profile/export"),

  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    return request<{ profile_id: string; resume_path: string; message: string }>(
      "POST",
      "/profile/upload",
      { formData: fd }
    );
  },

  analyze: (file: File, jobDescription?: string) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    if (jobDescription) fd.append("job_description", jobDescription);
    return request<ResumeAnalysis>("POST", "/profile/analyze", { formData: fd });
  },

  analyzeLinkedIn: (input: LinkedInProfileInput) =>
    request<LinkedInProfileAnalysis>("POST", "/profile/analyze-linkedin", { body: input }),

  searchLinkedInPeople: (input: LinkedInPeopleSearchInput) =>
    request<LinkedInPeopleSearchResponse>("POST", "/profile/search-linkedin", { body: input }),
};
