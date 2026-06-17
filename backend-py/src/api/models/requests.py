"""
Job Raider - API Request Models

Pydantic models for API request validation and parsing.

Author: Job Raider
Date: 2026-04-21
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class PipelineStartRequest(BaseModel):
    """Request to start a new pipeline run."""

    # Search parameters
    keywords: List[str] = Field(..., description="Job keywords to search for")
    locations: List[str] = Field(..., description="Job locations to search in")
    sources: Optional[List[str]] = Field(
        default=None,
        description="Job sources (linkedin, jsearch)",
    )

    # Pipeline options
    dry_run: bool = Field(default=True, description="Run in dry-run mode")
    skip_submission: bool = Field(default=False, description="Skip submission stage")
    min_score: int = Field(
        default=60, ge=0, le=100, description="Minimum relevance score"
    )
    scam_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Scam detection threshold",
    )
    max_jobs: int = Field(
        default=20, ge=1, le=100, description="Maximum jobs to present"
    )

    # Stage control
    start_from: Optional[str] = Field(
        default=None,
        description="Resume from this stage",
    )
    stop_at: Optional[str] = Field(
        default=None,
        description="Stop at this stage",
    )

    # Profile (optional - will use existing if not provided)
    profile_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="User profile data (if not using stored profile)",
    )

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate sources are known values."""
        if v is not None:
            valid_sources = {"linkedin", "jsearch"}
            invalid = set(v) - valid_sources
            if invalid:
                raise ValueError(f"Invalid sources: {invalid}")
        return v

    @field_validator("start_from", "stop_at")
    @classmethod
    def validate_stages(cls, v: Optional[str]) -> Optional[str]:
        """Validate stage names."""
        valid_stages = {
            "scrape",
            "deduplicate",
            "filter_scams",
            "filter_by_profile",
            "score_and_rank",
            "rag_rank",
            "detect_auto_submit",
            "present_selection",
            "generate_resumes",
            "submit_applications",
        }
        if v is not None and v not in valid_stages:
            raise ValueError(f"Invalid stage: {v}")
        return v


class JobSearchRequest(BaseModel):
    """Request to search for jobs without running full pipeline."""

    keywords: List[str] = Field(
        ..., description="Job keywords to search for", min_length=1
    )
    locations: List[str] = Field(..., description="Job locations to search in")
    sources: Optional[List[str]] = Field(
        default=None,
        description="Job sources (linkedin, jsearch)",
    )
    limit: int = Field(default=50, ge=1, le=200, description="Maximum results")
    remote_only: bool = Field(default=False, description="Remote positions only")
    experience_levels: Optional[List[str]] = Field(
        default=None,
        description="Filter by experience level (Entry Level, Mid Level, Senior, etc.)",
    )
    fresh_grad_mode: bool = Field(
        default=False,
        description="Enable fresh graduate scoring mode (prioritizes projects/education over experience)",
    )

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v: List[str]) -> List[str]:
        """Validate that keywords are not empty strings."""
        if not v or all(k.strip() == "" for k in v):
            raise ValueError(
                "Keywords cannot be empty. Please provide at least one valid keyword."
            )
        # Filter out empty strings
        return [k for k in v if k.strip()]


class ProfileUpdateRequest(BaseModel):
    """Request to update user profile."""

    # Contact info
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None

    # Target job preferences
    target_keywords: Optional[List[str]] = None
    target_locations: Optional[List[str]] = None
    target_experience: Optional[List[str]] = None
    remote_preference: Optional[bool] = None
    salary_min: Optional[float] = None
    constraint_mode: Optional[str] = None

    # Apprenticeship/Traineeship contract (optional)
    apprenticeship_field: Optional[str] = None
    apprenticeship_duration_months: Optional[int] = None
    apprenticeship_employer: Optional[str] = None
    apprenticeship_start_date: Optional[str] = None
    apprenticeship_end_date: Optional[str] = None
    apprenticeship_is_active: Optional[bool] = None

    # Skills (would normally be more complex)
    skills: Optional[List[Dict[str, Any]]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None


class BulkApplyRequest(BaseModel):
    """Request to apply to multiple jobs."""

    job_ids: List[str] = Field(..., description="Job IDs to apply to")
    dry_run: bool = Field(
        default=True, description="Generate resumes without submitting"
    )


class JobActionRequest(BaseModel):
    """Request to perform quick action on a job."""

    job_id: str = Field(..., description="Job ID")
    action: str = Field(..., description="Action: save, unsave, hide, unhide")
    note: Optional[str] = Field(None, description="Optional note")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate action is a known value."""
        valid_actions = {"save", "unsave", "hide", "unhide"}
        if v not in valid_actions:
            raise ValueError(f"Invalid action: {v}. Must be one of {valid_actions}")
        return v


class TrackExternalApplicationRequest(BaseModel):
    """Request to track external application."""

    job_id: str = Field(..., description="Unique job ID")
    job_title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    application_date: Optional[str] = Field(
        None, description="Application date (ISO format)"
    )
    application_method: str = Field(
        default="manual", description="How application was made"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class CreateCustomStatusRequest(BaseModel):
    """Request to create custom status."""

    name: str = Field(..., description="Status name", min_length=1, max_length=50)
    description: str = Field(
        ..., description="Status description", min_length=1, max_length=200
    )
    color: str = Field(default="#6B7280", description="Hex color code")
    icon: Optional[str] = Field(None, description="Icon name")


class SetCustomStatusRequest(BaseModel):
    """Request to set custom status on application."""

    job_id: str = Field(..., description="Job ID")
    custom_status_id: str = Field(..., description="Custom status ID")
    note: Optional[str] = Field(None, description="Optional note")


class UpdateApplicationStatusRequest(BaseModel):
    """Request to update application status."""

    job_id: str = Field(..., description="Job ID")
    status: str = Field(..., description="New status")
    note: Optional[str] = Field(None, description="Optional note about the change")


class DashboardQueryRequest(BaseModel):
    """Request to query dashboard data."""

    status_filter: Optional[List[str]] = Field(None, description="Filter by statuses")
    company_filter: Optional[List[str]] = Field(None, description="Filter by companies")
    days: Optional[int] = Field(
        None, ge=1, description="Filter by days since application"
    )
    include_hidden: bool = Field(default=False, description="Include hidden jobs")
    include_bookmarked: bool = Field(
        default=True, description="Include bookmarked jobs"
    )
    include_external: bool = Field(
        default=True, description="Include external applications"
    )


class SemanticSearchRequest(BaseModel):
    """Request for semantic job search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language search query",
    )
    n_results: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum results to return",
    )
    min_similarity: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold",
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata filters",
    )
