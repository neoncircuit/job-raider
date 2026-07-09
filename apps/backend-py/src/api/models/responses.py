"""
Job Raider - API Response Models

Pydantic models for API response formatting.

Author: Job Raider
Date: 2026-04-21
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PipelineStatus(str, Enum):
    """Pipeline execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStatusResponse(BaseModel):
    """Response with current pipeline status."""

    run_id: str
    status: PipelineStatus
    current_stage: Optional[str] = None
    stage_progress: int = 0  # 0-100
    jobs_scraped: int = 0
    jobs_scored: int = 0
    jobs_selected: int = 0
    applications_submitted: int = 0
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None


class PipelineResultResponse(BaseModel):
    """Response with completed pipeline results."""

    run_id: str
    status: PipelineStatus
    success: bool
    duration_seconds: float
    stages_completed: List[str]
    jobs_scraped: int
    jobs_applied: int

    # Scored jobs (top results)
    top_jobs: List[Dict[str, Any]] = Field(default_factory=list)

    # Generated resumes
    generated_resumes: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Mapping of job_id to resume_path",
    )

    # Stage results
    stage_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # Summary
    summary: Dict[str, Any] = Field(default_factory=dict)

    started_at: datetime
    completed_at: datetime


class JobListingResponse(BaseModel):
    """Response with job listing data."""

    job_id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str

    # Scoring data
    relevance_score: Optional[int] = None
    scam_score: Optional[float] = None

    # Job details
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_range: Optional[str] = None
    remote: bool = False
    already_applied: bool = False

    # Metadata
    posted_date: Optional[datetime] = None
    scraped_at: datetime

    # Skills and requirements
    skills: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)

    # Rich classification (if available)
    classification: Optional[Dict[str, Any]] = Field(
        default=None, description="LLM-based job classification"
    )

    # Trust analysis (if available)
    trust_analysis: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Trust analysis with tier, reasons, and category scores",
    )


class ProfileResponse(BaseModel):
    """Response with user profile data."""

    # Contact info
    name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None

    # Target job preferences
    target_keywords: List[str] = Field(default_factory=list)
    target_locations: List[str] = Field(default_factory=list)
    target_experience: List[str] = Field(default_factory=list)
    remote_preference: bool = False
    salary_min: Optional[float] = None

    # Profile data
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)

    # Metadata
    years_of_experience: float = 0.0
    resume_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class HealthCheckResponse(BaseModel):
    """Response with system health status."""

    status: str  # healthy, degraded, unhealthy, unknown
    timestamp: str
    checks: List[Dict[str, Any]]
    summary: Dict[str, int]


class MetricsResponse(BaseModel):
    """Response with metrics data."""

    # Cost metrics
    total_cost_usd: float = 0.0
    cost_per_application: float = 0.0
    api_costs_usd: float = 0.0
    local_model_usage: float = 0.0  # percentage

    # Application metrics
    total_applications: int = 0
    interviews_scheduled: int = 0
    offers_received: int = 0
    rejection_count: int = 0

    # Conversion rates
    interview_rate: float = 0.0  # applications -> interviews
    offer_rate: float = 0.0  # interviews -> offers
    overall_rate: float = 0.0  # applications -> offers

    # Pipeline runs
    pipeline_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0


class ErrorResponse(BaseModel):
    """Response with error information."""

    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class CustomStatusResponse(BaseModel):
    """Response with custom status data."""

    status_id: str
    name: str
    description: str
    color: str
    icon: Optional[str] = None
    is_active: bool
    created_at: datetime
    usage_count: int = 0


class JobActionResponse(BaseModel):
    """Response to job action."""

    success: bool
    job_id: str
    action: str
    new_status: Optional[str] = None
    message: str = ""


class DashboardResponse(BaseModel):
    """Response with dashboard data."""

    applications: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    custom_statuses: List[CustomStatusResponse] = Field(default_factory=list)
    filters_applied: Dict[str, Any] = Field(default_factory=dict)


class ApplicationDetailResponse(BaseModel):
    """Response with detailed application information."""

    application_id: str
    job_title: str
    company: str
    applied_date: datetime
    current_status: str
    custom_status: Optional[CustomStatusResponse] = None
    is_bookmarked: bool
    is_hidden: bool
    external_application_details: Optional[Dict[str, Any]] = None
    final_outcome: Optional[str] = None
    interviews: List[Dict[str, Any]] = Field(default_factory=list)
    offer: Optional[Dict[str, Any]] = None
    timeline_notes: List[Dict[str, str]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SemanticSearchResult(BaseModel):
    """Result for semantic job search."""

    job_id: str
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    similarity_score: float
    description_snippet: str = ""


class SemanticSearchResponse(BaseModel):
    """Response for semantic search endpoint."""

    query: str
    total: int
    results: List[SemanticSearchResult] = Field(default_factory=list)


class JobSimilarityResponse(BaseModel):
    """Response for job similarity scoring."""

    job_id: str
    heuristic_score: Optional[int] = None
    semantic_score: Optional[float] = None
    combined_score: Optional[float] = None
    heuristic_breakdown: Optional[Dict[str, int]] = None
    recommendation: Optional[str] = None
    reasoning: Optional[str] = None


class CoverLetterValidationResponse(BaseModel):
    """Response with cover letter validation results."""

    is_valid: bool
    score: int  # 0-100
    issues: List[str] = Field(default_factory=list)
    word_count: int
    structure_score: int  # 0-100
    content_score: int  # 0-100
    tone_score: int  # 0-100
    recommendation: str  # "approve", "needs_revision", "reject"
    details: Dict[str, Any] = Field(default_factory=dict)


class CoverLetterResponse(BaseModel):
    """Response with generated cover letter and validation results."""

    success: bool
    job_id: str
    cover_letter: Dict[str, Any]
    validation: CoverLetterValidationResponse
