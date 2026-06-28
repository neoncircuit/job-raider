// TypeScript interfaces mirroring backend Pydantic models.
// Source of truth: backend-py/src/api/models/responses.py and backend-py/src/models/

// ── Enums ─────────────────────────────────────────────────────────────────────

export type PipelineStatus = "pending" | "running" | "completed" | "failed" | "cancelled";
export type ExperienceLevel =
  | "Entry Level"
  | "Mid Level"
  | "Senior"
  | "Lead"
  | "Principal"
  | "Executive"
  | "Internship"
  | "Not Specified";
export type JobType =
  | "Full-time"
  | "Part-time"
  | "Contract"
  | "Internship"
  | "Temporary"
  | "Freelance"
  | "Remote";
export type WorkMode = "On-site" | "Remote" | "Hybrid";
export type SkillCategory =
  | "programming_language"
  | "framework"
  | "tool"
  | "cloud"
  | "database"
  | "language"
  | "soft_skill"
  | "domain"
  | "other";
export type ProficiencyLevel = "Beginner" | "Intermediate" | "Advanced" | "Expert";

// ── Health ────────────────────────────────────────────────────────────────────

export interface HealthCheck {
  name: string;
  status: "healthy" | "degraded" | "unhealthy" | "unknown";
  message: string;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy" | "unknown";
  timestamp: string;
  checks: HealthCheck[];
  summary: Record<string, number>;
}

// ── Pipeline ──────────────────────────────────────────────────────────────────

export interface PipelineStartRequest {
  keywords: string[];
  locations: string[];
  sources?: string[] | null;
  dry_run: boolean;
  skip_submission?: boolean;
  min_score: number;
  scam_threshold: number;
  max_jobs: number;
}

export interface PipelineStatusResponse {
  run_id: string;
  status: PipelineStatus;
  current_stage?: string | null;
  stage_progress: number;
  jobs_scraped: number;
  jobs_scored: number;
  jobs_selected: number;
  applications_submitted: number;
  started_at?: string | null;
  estimated_completion?: string | null;
  error_message?: string | null;
}

export interface PipelineRun {
  run_id: string;
  status: PipelineStatus;
  created_at: string;
  completed_at?: string | null;
  jobs_scraped?: number;
  jobs_applied?: number;
  stages_completed?: string[];
}

export interface PipelineHistoryResponse {
  runs: PipelineRun[];
  total: number;
}

export interface PipelineResultResponse {
  run_id: string;
  status: PipelineStatus;
  success: boolean;
  duration_seconds: number;
  stages_completed: string[];
  jobs_scraped: number;
  jobs_applied: number;
  stage_results: Record<string, Record<string, unknown>>;
  started_at: string;
  completed_at: string;
}

// ── Jobs ──────────────────────────────────────────────────────────────────────

export interface SalaryRange {
  min_amount?: number | null;
  max_amount?: number | null;
  currency: string;
  period: string;
  is_estimated: boolean;
}

export interface JobSkill {
  name: string;
  category?: SkillCategory | null;
  proficiency?: ProficiencyLevel | null;
  is_required: boolean;
}

export interface JobRequirement {
  category?: string | null;
  text: string;
  is_required: boolean;
  years_of_experience?: number | null;
}

export interface JobListing {
  job_id: string;
  title: string;
  company: string;
  location?: string | null;
  description?: string | null;
  source: string;
  source_url?: string | null;
  work_mode?: WorkMode;
  is_remote: boolean;
  already_applied?: boolean;
  apply_method?: "easy_apply" | "external_site" | "already_applied" | null;
  job_type?: JobType | string | null;
  experience_level?: ExperienceLevel | string | null;
  salary_range?: SalaryRange | string | null;
  skills: JobSkill[];
  requirements?: JobRequirement[];
  posted_date?: string | null;
  scraped_at?: string | null;
  relevance_score?: number | null;
  scam_score?: number | null;
  classification?: JobClassification | null;
  trust_analysis?: TrustAnalysis | null;
}

export interface JobClassification {
  industry: string;
  role_category: string;
  company_size: string;
  company_stage?: string | null;
  work_pace: string;
  team_structure: string;
  technical_skills: SkillRequirement[];
  soft_skills: SkillRequirement[];
  domain_skills: SkillRequirement[];
  experience_level_confidence: number;
  actual_experience_years?: [number, number] | null;
  management_level?: string | null;
  impact_scope?: string | null;
  classification_confidence: number;
  tags: string[];
  red_flags: string[];
}

export interface SkillRequirement {
  name: string;
  category: string;
  proficiency: string;
  is_required: boolean;
  confidence: number;
}

export type TrustTier =
  | "legitimate"
  | "low_risk"
  | "moderate_risk"
  | "suspicious"
  | "likely_scam";

export interface TrustAnalysis {
  tier: TrustTier;
  tier_display: string;
  confidence: number;
  risk_score: number;
  is_scam: boolean;
  category_scores: Record<string, number>;
  indicators: string[];
  reasons: string[];
  llm_summary?: string | null;
  llm_indicators?: string[];
}

export interface JobSearchResponse {
  total: number;
  jobs: JobListing[];
}

export interface SemanticSearchResult {
  job_id: string;
  title?: string | null;
  company?: string | null;
  location?: string | null;
  similarity_score: number;
  description_snippet: string;
}

export interface SemanticSearchResponse {
  query: string;
  total: number;
  results: SemanticSearchResult[];
}

export interface JobSimilarityResponse {
  job_id: string;
  heuristic_score?: number | null;
  semantic_score?: number | null;
  combined_score?: number | null;
  heuristic_breakdown?: Record<string, number> | null;
  recommendation?: string | null;
  reasoning?: string | null;
}

export type CoverLetterIssue =
  | "missing_company"
  | "missing_job_title"
  | "missing_contact_info"
  | "too_short"
  | "too_long"
  | "generic_opening"
  | "missing_call_to_action"
  | "missing_experience_match"
  | "tone_too_informal"
  | "tone_too_formal"
  | "grammar_errors"
  | "spelling_errors"
  | "poor_formatting";

export type CoverLetterRecommendation = "approve" | "needs_revision" | "reject";

export interface HighlightedExperience {
  name: string;
  reason: string;
}

export interface CoverLetterValidation {
  is_valid: boolean;
  score: number;
  issues: CoverLetterIssue[];
  word_count: number;
  structure_score: number;
  content_score: number;
  tone_score: number;
  recommendation: CoverLetterRecommendation;
  details: Record<string, unknown>;
}

export interface CoverLetter {
  content: string;
  word_count: number;
  model_used: string;
  highlighted_experiences: HighlightedExperience[];
}

export interface CoverLetterResponse {
  success: boolean;
  job_id: string;
  cover_letter: CoverLetter;
  validation: CoverLetterValidation;
}

// ── Profile ───────────────────────────────────────────────────────────────────

export interface ContactInfo {
  name?: string;
  email?: string;
  phone?: string | null;
  location?: string | null;
  linkedin_url?: string | null;
  github_url?: string | null;
  portfolio_url?: string | null;
  website_url?: string | null;
}

export interface Certification {
  name: string;
  issuer: string;
  issue_date?: string | null;
  expiration_date?: string | null;
  credential_id?: string | null;
}

export interface ProfileSkill {
  name: string;
  category: SkillCategory;
  proficiency?: ProficiencyLevel | null;
  years_of_experience?: number | null;
}

export interface WorkExperience {
  title: string;
  company: string;
  location?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  current: boolean;
  description?: string | null;
  highlights: string[];
  technologies: string[];
}

export interface Education {
  degree: string;
  field_of_study?: string | null;
  institution: string;
  graduation_date?: string | null;
  gpa?: number | null;
  honors: string[];
  coursework?: string[];
}

export interface Project {
  name: string;
  description?: string | null;
  technologies: string[];
  url?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  highlights: string[];
  role?: string | null;
}

export interface ApprenticeshipContract {
  field: string;
  duration_months?: number | null;
  employer?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  is_active: boolean;
}

export interface TargetJob {
  keywords: string[];
  locations: string[];
  experience_levels: ExperienceLevel[];
  remote_preference: boolean;
  constraint_mode: "boost" | "filter";
}

export interface UserProfile {
  contact_info: ContactInfo;
  summary?: string | null;
  core_skills?: string[];
  target_job: TargetJob;
  apprenticeship?: ApprenticeshipContract | null;
  skills: ProfileSkill[];
  work_experience: WorkExperience[];
  education: Education[];
  projects: Project[];
  certifications?: Certification[];
  languages?: string[];
  years_of_experience?: number | null;
  // Application-specific fields
  visa_status?: VisaStatus | null;
  visa_expiration_date?: string | null;
  salary_expectation_min?: number | null;
  salary_expectation_max?: number | null;
  salary_currency?: string;
  notice_period_weeks?: number | null;
  willing_to_relocate?: boolean;
  preferred_work_locations?: string[];
}

export type VisaStatus =
  | "citizen"
  | "permanent_resident"
  | "h1b"
  | "other_visa"
  | "need_sponsorship"
  | "student_visa"
  | "not_specified";

// ── Applications ──────────────────────────────────────────────────────────────

export interface CustomStatus {
  status_id: string;
  name: string;
  description: string;
  color: string;
  icon?: string | null;
  is_active: boolean;
  created_at: string;
  usage_count: number;
}

export interface ApplicationSummary {
  application_id: string;
  job_title: string;
  company: string;
  applied_date?: string | null;
  current_status: string;
  custom_status?: CustomStatus | null;
  is_bookmarked: boolean;
  is_hidden: boolean;
  days_since_application?: number | null;
  source_url?: string | null;
}

export interface ApplicationDetail extends ApplicationSummary {
  external_application_details?: Record<string, unknown> | null;
  final_outcome?: string | null;
  interviews: Array<Record<string, unknown>>;
  offer?: Record<string, unknown> | null;
  timeline_notes: Array<Record<string, string>>;
  metadata: Record<string, unknown>;
}

export interface DashboardSummary {
  total_applications: number;
  bookmarked: number;
  hidden: number;
  external: number;
  by_status: Record<string, number>;
}

export interface ApplicationDashboardResponse {
  applications: ApplicationSummary[];
  summary: DashboardSummary;
  custom_statuses: CustomStatus[];
  filters_applied: Record<string, unknown>;
}

// ── Metrics ───────────────────────────────────────────────────────────────────

export interface CostMetrics {
  total_usd: number;
  per_application: number;
  total_calls: number;
  local_usage_percent: number;
}

export interface OutcomeMetrics {
  total_applications: number;
  interviews: number;
  offers: number;
  rejection_count?: number;
  interview_rate: number;
  offer_rate: number;
  overall_rate: number;
}

export interface HealthMetrics {
  status: string;
  healthy: number;
  degraded: number;
  unhealthy: number;
}

export interface LLMCall {
  task_type: string;
  provider: string;
  model: string;
  cost_usd: number;
  timestamp: string;
}

export interface MetricsSummaryResponse {
  cost: CostMetrics;
  outcomes: OutcomeMetrics;
  health: HealthMetrics;
  recent_calls: LLMCall[];
}

// ── Settings ──────────────────────────────────────────────────────────────────

export interface ModelRouting {
  primary_provider: string;
  primary_model: string;
  fallback_provider: string;
  fallback_model: string;
}

export interface ApiConfig {
  anthropic_api_key?: string | null;
  ollama_host: string;
}

export interface ModelParams {
  temperature: number;
  max_tokens: number;
  top_p: number;
}

export interface CostLimits {
  max_api_cost_per_run: number;
  enable_cache: boolean;
  cache_ttl: number;
}

export interface AppSettings {
  routing: Record<string, ModelRouting>;
  api_config: ApiConfig;
  model_params: ModelParams;
  cost_limits: CostLimits;
  updated_at?: string;
  version?: string;
}

// ── Resume Analysis ───────────────────────────────────────────────────────────

export interface SkillAssessment {
  skill_name: string;
  proficiency_level: string;
  years_experience?: number | null;
  is_industry_relevant: boolean;
  improvement_suggestions: string[];
}

export interface ExperienceInsight {
  company: string;
  title: string;
  period: string;
  strengths: string[];
  gaps: string[];
  achievements_to_highlight: string[];
}

export interface ProjectInsight {
  name: string;
  technologies: string[];
  impact_score: number;
  strengths: string[];
  improvements: string[];
}

export interface ResumeAnalysis {
  analyzed_at: string;
  analysis_type: "general" | "job_specific";
  overall_score: number;
  summary: string;
  key_strengths: string[];
  key_improvements: string[];
  skills_assessment: SkillAssessment[];
  experience_insights: ExperienceInsight[];
  project_insights: ProjectInsight[];
  resume_improvements: string[];
  skill_gaps: string[];
  next_steps: string[];
  target_alignment_score?: number | null;
  competitive_advantages: string[];
  competitive_gaps: string[];
  competitive_edge: string;
}

// ── Assessment ─────────────────────────────────────────────────────────────────

export type AssessmentMode = "job_targeted" | "skill_based";
export type QuestionType = "conceptual" | "scenario" | "coding" | "system_design";
export type AnswerFormat = "freeform" | "multiple_choice";
export type DifficultyLevel = "beginner" | "intermediate" | "advanced" | "expert";
export type SessionStatus = "in_progress" | "completed" | "abandoned";

export interface MultipleChoiceOption {
  label: string;
  text: string;
  is_correct?: boolean;
}

export interface AssessmentQuestion {
  question_id: string;
  question_type: QuestionType;
  answer_format: AnswerFormat;
  difficulty: DifficultyLevel;
  topic: string;
  question_text: string;
  options: MultipleChoiceOption[];
  time_limit_seconds?: number | null;
  order_index: number;
}

export interface QuestionScore {
  question_id: string;
  score: number;
  is_correct?: boolean | null;
  feedback: string;
  strengths: string[];
  improvements: string[];
  model_answer: string;
}

export interface AssessmentSession {
  session_id: string;
  mode: AssessmentMode;
  status: SessionStatus;
  difficulty: DifficultyLevel;
  target_job_ids: string[];
  target_skills: string[];
  questions: AssessmentQuestion[];
  answers: Array<{
    question_id: string;
    selected_option?: string | null;
    freeform_text?: string | null;
    answered_at: string;
    time_taken_seconds?: number | null;
  }>;
  scores: QuestionScore[];
  overall_score: number | null;
  topic_breakdown: Record<string, number>;
  current_difficulty: DifficultyLevel;
  difficulty_history: Array<{
    from: string;
    to: string;
    avg_score: number;
    triggered_at: number;
  }>;
  created_at: string;
  completed_at: string | null;
  question_count: number;
}

export interface ProgressStats {
  total_sessions: number;
  completed_sessions: number;
  average_score: number;
  score_trend: Array<{ date: string; score: number }>;
  strongest_topics: Array<[string, number]>;
  weakest_topics: Array<[string, number]>;
}

// ── DISC Assessment ───────────────────────────────────────────────────────────────

export type DISCTrait = "D" | "I" | "S" | "C";
export type DISCCategory = "leadership" | "communication" | "work_style" | "problem_solving";

export interface DISCQuestionOption {
  label: string;
  text: string;
  scores: Record<DISCTrait, number>;
}

export interface DISCQuestion {
  id: string;
  category: DISCCategory;
  question: string;
  options: DISCQuestionOption[];
}

export interface DISCAnswer {
  question_id: string;
  most_like: string;
  least_like: string;
  answered_at?: string;
}

export interface DISCScore {
  trait: DISCTrait;
  raw_score: number;
  percentage: number;
}

export interface DISCJobMatch {
  job_type: string;
  match_score: number;
  description: string;
  ideal_profile: Record<DISCTrait, number>;
}

export interface DISCResult {
  session_id: string;
  answers: DISCAnswer[];
  scores: DISCScore[];
  profile: Record<DISCTrait, number>;
  primary_type: DISCTrait;
  secondary_type?: DISCTrait | null;
  completed_at: string;
  job_matches: DISCJobMatch[];
}

export interface DISCSession {
  session_id: string;
  questions: DISCQuestion[];
}

// ── LinkedIn Profile Analysis ─────────────────────────────────────────────────

export interface LinkedInExperienceEntry {
  title?: string;
  company?: string;
  description?: string;
  dates?: string;
}

export interface LinkedInEducationEntry {
  school?: string;
  degree?: string;
  field?: string;
  dates?: string;
}

export interface LinkedInProfileInput {
  profile_url?: string | null;
  raw_text?: string | null;
  headline?: string | null;
  summary?: string | null;
  experience_entries?: LinkedInExperienceEntry[];
  education_entries?: LinkedInEducationEntry[];
  skills?: string[];
  industry?: string | null;
  career_goals?: string | null;
  target_roles?: string[];
}

export interface LinkedInPeopleSearchInput {
  keywords?: string | null;
  name?: string | null;
  title?: string | null;
  company?: string | null;
  location?: string | null;
  limit?: number;
}

export interface LinkedInPeopleSearchResult {
  name: string;
  headline: string;
  profile_url: string;
  location?: string | null;
}

export interface LinkedInPeopleSearchResponse {
  query: Record<string, unknown>;
  total: number;
  results: LinkedInPeopleSearchResult[];
}

export interface ProfileSectionScore {
  section_name: string;
  score: number;
  weight: number;
  feedback: string;
}

export interface InboundAttractionInsight {
  category: string;
  observation: string;
  recommendation: string;
  priority: "critical" | "high" | "medium" | "low";
}

export interface LinkedInProfileAnalysis {
  analyzed_at: string;
  overall_score: number;
  summary: string;
  section_scores: ProfileSectionScore[];
  insights: InboundAttractionInsight[];
  keyword_recommendations: string[];
  action_plan: string[];
  generated_headline_options: string[];
  summary_rewrite_suggestions: string[];
  competitive_edge: string;
  metadata?: Record<string, unknown> | null;
}
