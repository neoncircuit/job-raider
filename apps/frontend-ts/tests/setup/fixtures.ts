/**
 * Job Raider - Test Fixtures
 *
 * Reusable test data fixtures for consistent testing.
 * Provides sample data matching real API responses.
 *
 * Author: Job Raider
 * Date: 2026-06-08
 */

import {
  JobListing,
  UserProfile,
  ApplicationDetail,
  CoverLetter,
  CoverLetterValidation,
} from "@/lib/types/api";

/**
 * Sample job fixture
 */
export const sampleJob: JobListing = {
  job_id: "job-1",
  title: "Senior Software Engineer",
  company: "Tech Innovations Inc",
  location: "San Francisco, CA",
  description: `
    <p>We are seeking a talented Senior Software Engineer to join our team.</p>
    <h3>Requirements:</h3>
    <ul>
      <li>5+ years of experience with React and TypeScript</li>
      <li>Strong understanding of software architecture</li>
      <li>Experience with cloud platforms (AWS/GCP)</li>
    </ul>
    <h3>Benefits:</h3>
    <ul>
      <li>Competitive salary ($150k-$200k)</li>
      <li>Remote work options</li>
      <li>Professional development budget</li>
    </ul>
  `,
  source: "linkedin",
  source_url: "https://linkedin.com/jobs/view/123456789",
  is_remote: true,
  apply_method: "easy_apply",
  experience_level: "Senior",
  salary_range: "$150k-$200k",
  skills: [
    { name: "React", is_required: true },
    { name: "TypeScript", is_required: true },
    { name: "Node.js", is_required: false },
  ],
  posted_date: "2026-06-01",
  relevance_score: 0.92,
  scam_score: 0.05,
};

/**
 * Sample profile fixture
 */
export const sampleProfile: UserProfile = {
  contact_info: {
    name: "Alex Chen",
    email: "alex.chen@example.com",
    phone: "+1-555-0199",
    location: "San Francisco, CA",
    linkedin_url: "https://linkedin.com/in/alexchen",
    github_url: "https://github.com/alexchen",
    portfolio_url: "https://alexchen.dev",
  },
  target_job: {
    keywords: ["Senior Software Engineer", "Full Stack", "React"],
    locations: ["San Francisco, CA", "Remote", "New York, NY"],
    experience_levels: ["Senior", "Lead"],
    remote_preference: true,
    constraint_mode: "boost",
  },
  skills: [
    {
      name: "React",
      category: "programming_language",
      proficiency: "Expert",
      years_of_experience: 5,
    },
    {
      name: "TypeScript",
      category: "programming_language",
      proficiency: "Expert",
      years_of_experience: 4,
    },
    {
      name: "Python",
      category: "language",
      proficiency: "Advanced",
      years_of_experience: 3,
    },
  ],
  work_experience: [
    {
      title: "Senior Software Engineer",
      company: "Tech Startup Inc",
      location: "Remote",
      start_date: "2023-01",
      end_date: null,
      current: true,
      description:
        "Led development of microservices architecture serving 1M+ users. Mentored junior developers and introduced best practices.",
      highlights: [
        "Led development of microservices architecture",
        "Mentored junior developers",
      ],
      technologies: ["React", "TypeScript", "Node.js", "Python"],
    },
  ],
  education: [
    {
      degree: "Bachelor of Science in Computer Science",
      institution: "University of California, Berkeley",
      graduation_date: "2020-05",
      gpa: 3.8,
      honors: ["Dean's List"],
    },
  ],
  projects: [
    {
      name: "Job Raider",
      description:
        "AI-powered job application automation platform with intelligent matching and auto-apply capabilities",
      technologies: ["React", "TypeScript", "FastAPI", "Python", "Docker"],
      url: "https://github.com/alexchen/job-raider",
      start_date: "2025-01",
      end_date: null,
      highlights: [
        "Built intelligent job matching system",
        "Implemented auto-apply functionality",
      ],
    },
  ],
  core_skills: ["React", "TypeScript", "Python", "Node.js"],
  summary:
    "Senior Software Engineer with 5+ years of experience building scalable web applications.",
};

/**
 * Sample application fixture
 */
export const sampleApplication: ApplicationDetail = {
  application_id: "app-1",
  job_title: "Senior Software Engineer",
  company: "Tech Innovations Inc",
  applied_date: "2026-06-05",
  current_status: "applied",
  is_bookmarked: true,
  is_hidden: false,
  source_url: "https://linkedin.com/jobs/view/123456789",
  metadata: {
    resume_version: "v2",
    ai_score: 0.95,
    scam_score: 0.05,
  },
  timeline_notes: [],
  interviews: [],
};

/**
 * Sample cover letter fixture
 */
export const sampleCoverLetter: CoverLetter = {
  content:
    "I am excited about the Senior Software Engineer role at Tech Innovations Inc. " +
    "My experience building scalable React applications and leading cross-functional teams " +
    "has prepared me to contribute from day one. I would welcome the opportunity to discuss " +
    "how my background aligns with your goals. Thank you for considering my application.",
  word_count: 58,
  model_used: "qwen2.5:7b",
  highlighted_experiences: [
    { name: "Job Raider", reason: "Relevant full-stack project" },
  ],
  timing: {
    selection_ms: 120.5,
    generation_ms: 8420.0,
    review_ms: 910.2,
    rewrite_ms: 4510.0,
    validation_ms: 12.0,
    total_ms: 13972.7,
  },
};

/**
 * Sample cover letter validation fixture
 */
export const sampleCoverLetterValidation: CoverLetterValidation = {
  is_valid: true,
  score: 88,
  issues: [],
  word_count: 58,
  structure_score: 85,
  content_score: 90,
  tone_score: 88,
  recommendation: "approve",
  details: {
    paragraph_count: 1,
    has_generic_opening: false,
    has_call_to_action: true,
    company_mentioned: true,
    job_title_mentioned: true,
    referenced_projects: ["Job Raider"],
  },
};

/**
 * Sample jobs list fixture
 */
export const sampleJobs: JobListing[] = [
  sampleJob,
  {
    ...sampleJob,
    job_id: "job-2",
    title: "Full Stack Developer",
    company: "CloudTech Solutions",
    location: "Remote",
    salary_range: "$120k-$160k",
    experience_level: "Mid Level",
    is_remote: true,
    source: "jsearch",
    relevance_score: 0.87,
  },
  {
    ...sampleJob,
    job_id: "job-3",
    title: "Lead Software Engineer",
    company: "Enterprise Corp",
    location: "New York, NY",
    salary_range: "$180k-$250k",
    experience_level: "Lead",
    is_remote: false,
    source: "linkedin",
    relevance_score: 0.81,
  },
  {
    ...sampleJob,
    job_id: "job-4",
    title: "Frontend Developer",
    company: "Design Studio",
    location: "Los Angeles, CA",
    salary_range: "$100k-$140k",
    experience_level: "Entry Level",
    is_remote: true,
    source: "jsearch",
    relevance_score: 0.75,
    scam_score: 0.35,
  },
  {
    ...sampleJob,
    job_id: "job-5",
    title: "React Native Developer",
    company: "MobileFirst Inc",
    location: "Austin, TX",
    salary_range: "$130k-$170k",
    experience_level: "Mid Level",
    is_remote: true,
    source: "linkedin",
    relevance_score: 0.9,
  },
];

/**
 * Sample applications list fixture
 */
export const sampleApplications: ApplicationDetail[] = [
  sampleApplication,
  {
    ...sampleApplication,
    application_id: "app-2",
    job_title: "Full Stack Developer",
    company: "CloudTech Solutions",
    current_status: "saved",
    applied_date: null,
  },
  {
    ...sampleApplication,
    application_id: "app-3",
    job_title: "Lead Software Engineer",
    company: "Enterprise Corp",
    current_status: "interviewing",
    applied_date: "2026-06-02",
  },
];

/**
 * Sample search params fixture
 */
export const sampleSearchParams = {
  keywords: ["Software Engineer", "React", "TypeScript"],
  locations: ["San Francisco, CA", "Remote"],
  sources: ["linkedin", "jsearch"],
  limit: 50,
  remote_only: false,
};

/**
 * Sample profile update fixture
 */
export const sampleProfileUpdate = {
  name: "Alex Chen",
  email: "alex.chen.updated@example.com",
  target_keywords: ["Senior Software Engineer", "Staff Engineer", "React"],
  salary_min: 175000,
};
