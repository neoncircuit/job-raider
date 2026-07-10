/**
 * Job Raider - MSW API Mock Handlers
 *
 * Mock Service Worker handlers for API endpoints.
 * Provides realistic API responses for testing without backend dependency.
 *
 * Author: Job Raider
 * Date: 2026-06-08
 */

import { http, HttpResponse } from "msw";

// Base URL for API calls
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Mock job data
const mockJobs = [
  {
    id: "1",
    title: "Senior Software Engineer",
    company: "Tech Corp",
    location: "San Francisco, CA",
    description: "We are looking for a senior software engineer...",
    url: "https://example.com/job/1",
    source: "linkedin",
    posted_date: "2026-06-01",
    salary_range: "$150k-$200k",
    experience_level: "Senior",
    remote: true,
    skills: ["React", "TypeScript", "Node.js"],
    scam_score: 0.1,
    relevance_score: 0.95,
    application_status: null,
    saved: false,
    notes: null,
  },
  {
    id: "2",
    title: "Full Stack Developer",
    company: "StartupXYZ",
    location: "Remote",
    description: "Join our team as a full stack developer...",
    url: "https://example.com/job/2",
    source: "jsearch",
    posted_date: "2026-06-02",
    salary_range: "$120k-$180k",
    experience_level: "Mid Level",
    remote: true,
    skills: ["Python", "React", "AWS"],
    scam_score: 0.2,
    relevance_score: 0.88,
    application_status: null,
    saved: false,
    notes: null,
  },
];

// Mock profile data
const mockProfile = {
  id: "profile-1",
  name: "John Doe",
  email: "john@example.com",
  phone: "+1-555-0123",
  location: "San Francisco, CA",
  linkedin_url: "https://linkedin.com/in/johndoe",
  github_url: "https://github.com/johndoe",
  portfolio_url: "https://johndoe.dev",
  target_keywords: ["Software Engineer", "Full Stack", "React"],
  target_locations: ["San Francisco, CA", "Remote"],
  target_experience: ["Mid Level", "Senior"],
  remote_preference: true,
  salary_min: 150000,
  skills: [
    {
      id: "skill-1",
      name: "React",
      category: "frontend",
      proficiency: "advanced",
    },
    {
      id: "skill-2",
      name: "TypeScript",
      category: "frontend",
      proficiency: "advanced",
    },
    {
      id: "skill-3",
      name: "Python",
      category: "backend",
      proficiency: "intermediate",
    },
  ],
  projects: [
    {
      id: "project-1",
      title: "Job Raider",
      description: "AI-powered job application automation platform",
      technologies: ["React", "TypeScript", "FastAPI", "Python"],
      url: "https://github.com/johndoe/job-raider",
      start_date: "2025-01",
      end_date: null,
    },
  ],
  experience: [
    {
      id: "exp-1",
      title: "Software Engineer",
      company: "Previous Company",
      location: "Remote",
      start_date: "2023-01",
      end_date: null,
      description: "Built and maintained web applications...",
    },
  ],
  education: [
    {
      id: "edu-1",
      degree: "Bachelor of Science in Computer Science",
      school: "University of California, Berkeley",
      location: "Berkeley, CA",
      start_date: "2018-09",
      end_date: "2022-05",
    },
  ],
};

// Mock applications data
const mockApplications = [
  {
    id: "app-1",
    job_id: "1",
    job_title: "Senior Software Engineer",
    company: "Tech Corp",
    status: "applied",
    application_date: "2026-06-01",
    application_method: "easy_apply",
    notes: "Applied via LinkedIn Easy Apply",
    resume_url: null,
    cover_letter_url: null,
  },
  {
    id: "app-2",
    job_id: "2",
    job_title: "Full Stack Developer",
    company: "StartupXYZ",
    status: "saved",
    application_date: null,
    application_method: null,
    notes: "Interesting role, will apply later",
    resume_url: null,
    cover_letter_url: null,
  },
];

// Mock DISC assessment data
const mockDiscAssessment = {
  id: "disc-1",
  completed: true,
  submit_date: "2026-05-15",
  results: {
    D: 25,
    I: 30,
    S: 20,
    C: 25,
    profile_type: "IC",
    description: "Influencing - Optimistic and Outgoing",
  },
};

export const handlers = [
  // Jobs API endpoints
  http.get(`${API_BASE}/api/jobs/search`, () => {
    return HttpResponse.json({
      success: true,
      data: mockJobs,
      total: mockJobs.length,
    });
  }),

  http.get(`${API_BASE}/api/jobs/:jobId`, ({ params }) => {
    const job = mockJobs.find((j) => j.id === params.jobId);
    if (!job) {
      return HttpResponse.json(
        { success: false, error: "Job not found" },
        { status: 404 },
      );
    }
    return HttpResponse.json({ success: true, data: job });
  }),

  http.post(`${API_BASE}/api/jobs/:jobId/save`, () => {
    return HttpResponse.json({ success: true, message: "Job saved" });
  }),

  http.post(`${API_BASE}/api/jobs/:jobId/hide`, () => {
    return HttpResponse.json({ success: true, message: "Job hidden" });
  }),

  http.post(`${API_BASE}/api/jobs/:jobId/apply`, () => {
    return HttpResponse.json({
      success: true,
      message: "Application submitted",
    });
  }),

  http.post(`${API_BASE}/api/jobs/:jobId/cover-letter`, ({ request }) => {
    const url = new URL(request.url);
    const deep = url.searchParams.get("deep") === "true";
    return HttpResponse.json({
      success: true,
      job_id: "job-1",
      cover_letter: {
        content:
          "I am excited about the Senior Software Engineer role at Tech Corp. " +
          "My background in React, TypeScript, and scalable systems makes me a strong fit. " +
          "I would welcome the opportunity to discuss how I can contribute to your team. " +
          "Thank you for considering my application.",
        word_count: 56,
        model_used: "qwen2.5:7b",
        highlighted_experiences: [
          { name: "Job Raider", reason: "Relevant project" },
        ],
      },
      validation: {
        is_valid: true,
        score: deep ? 92 : 85,
        issues: [],
        word_count: 56,
        structure_score: 80,
        content_score: 90,
        tone_score: 85,
        recommendation: "approve",
        details: {
          paragraph_count: 1,
          has_generic_opening: false,
          has_call_to_action: true,
          company_mentioned: true,
          job_title_mentioned: true,
          referenced_projects: ["Job Raider"],
          llm_feedback: deep
            ? ["Strong personalization and clear value proposition."]
            : [],
        },
      },
    });
  }),

  // Profile API endpoints
  http.get(`${API_BASE}/api/profile`, () => {
    return HttpResponse.json({ success: true, data: mockProfile });
  }),

  http.post(`${API_BASE}/api/profile`, async ({ request }) => {
    const updates = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      success: true,
      data: { ...mockProfile, ...updates },
    });
  }),

  http.post(`${API_BASE}/api/profile/upload-resume`, () => {
    return HttpResponse.json({
      success: true,
      message: "Resume uploaded successfully",
    });
  }),

  // Applications API endpoints
  http.get(`${API_BASE}/api/applications`, () => {
    return HttpResponse.json({
      success: true,
      data: mockApplications,
      total: mockApplications.length,
    });
  }),

  http.get(`${API_BASE}/api/applications/:appId`, ({ params }) => {
    const app = mockApplications.find((a) => a.id === params.appId);
    if (!app) {
      return HttpResponse.json(
        { success: false, error: "Application not found" },
        { status: 404 },
      );
    }
    return HttpResponse.json({ success: true, data: app });
  }),

  http.patch(`${API_BASE}/api/applications/:appId/status`, () => {
    return HttpResponse.json({ success: true, message: "Status updated" });
  }),

  // DISC assessment endpoints
  http.get(`${API_BASE}/api/assessment/disc`, () => {
    return HttpResponse.json({ success: true, data: mockDiscAssessment });
  }),

  http.post(`${API_BASE}/api/assessment/disc/submit`, () => {
    return HttpResponse.json({
      success: true,
      data: { ...mockDiscAssessment, completed: true },
    });
  }),

  // Dashboard API endpoints
  http.get(`${API_BASE}/api/dashboard/stats`, () => {
    return HttpResponse.json({
      success: true,
      data: {
        total_applications: 10,
        active_applications: 5,
        saved_jobs: 15,
        interviews: 2,
      },
    });
  }),

  http.get(`${API_BASE}/api/dashboard/applications`, () => {
    return HttpResponse.json({
      success: true,
      data: mockApplications,
      total: mockApplications.length,
    });
  }),
];
