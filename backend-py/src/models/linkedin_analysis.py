"""
Job Raider - LinkedIn Profile Analysis Models

This module provides Pydantic models for LinkedIn profile analysis results,
focused on inbound attraction: making the profile discoverable to recruiters
and hiring managers.

Author: Job Raider
Date: 2026-06-25
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LinkedInProfileInput(BaseModel):
    """
    Input data for LinkedIn profile analysis.

    Accepts a LinkedIn profile URL, raw pasted text, structured fields,
    or any combination of the above. At least one of profile_url, raw_text,
    or a structured field must be provided.
    """

    profile_url: Optional[str] = Field(
        default=None, description="LinkedIn profile URL to fetch and analyze"
    )
    raw_text: Optional[str] = Field(
        default=None, description="Raw pasted LinkedIn profile text"
    )
    headline: Optional[str] = Field(
        default=None, description="Current LinkedIn headline"
    )
    summary: Optional[str] = Field(
        default=None, description="LinkedIn About / summary section"
    )
    experience_entries: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of experience entries (title, company, description, dates)",
    )
    education_entries: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of education entries (school, degree, field, dates)",
    )
    skills: List[str] = Field(
        default_factory=list, description="List of skills listed on the profile"
    )
    industry: Optional[str] = Field(
        default=None, description="Industry or field of work"
    )
    career_goals: Optional[str] = Field(
        default=None, description="Stated career goals or aspirations"
    )
    target_roles: List[str] = Field(
        default_factory=list, description="Target job titles or roles"
    )

    @model_validator(mode="after")
    def validate_input_present(self) -> "LinkedInProfileInput":
        """Require profile_url, raw_text, or at least one structured field."""
        has_url = self.profile_url is not None and (self.profile_url or "").strip()
        has_raw = self.raw_text is not None and (self.raw_text or "").strip()
        has_structured = any(
            [
                self.headline,
                self.summary,
                self.experience_entries,
                self.education_entries,
                self.skills,
                self.industry,
                self.career_goals,
                self.target_roles,
            ]
        )
        if not has_url and not has_raw and not has_structured:
            raise ValueError(
                "At least one of profile_url, raw_text, or a structured "
                "field must be provided."
            )
        return self

    model_config = ConfigDict(use_enum_values=True)


class ProfileSectionScore(BaseModel):
    """
    Score and feedback for a specific LinkedIn profile section.
    """

    section_name: str = Field(description="Name of the profile section")
    score: float = Field(description="Score for this section (0-100)", ge=0, le=100)
    weight: float = Field(
        description="Weight of this section in the overall score (0-1)",
        ge=0,
        le=1,
    )
    feedback: str = Field(description="Actionable feedback for improving this section")

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: float) -> float:
        """Ensure score is between 0 and 100."""
        if not 0 <= v <= 100:
            raise ValueError("Score must be between 0 and 100")
        return v

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        """Ensure weight is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Weight must be between 0 and 1")
        return v


class InboundAttractionInsight(BaseModel):
    """
    Insight about how to improve inbound attraction on LinkedIn.
    """

    category: str = Field(
        description="Category of insight (e.g., 'headline', 'keywords', 'content')"
    )
    observation: str = Field(description="What was observed about the current profile")
    recommendation: str = Field(
        description="Specific recommendation to improve inbound attraction"
    )
    priority: Literal["critical", "high", "medium", "low"] = Field(
        description="Priority level of this recommendation"
    )


class LinkedInPeopleSearchInput(BaseModel):
    """
    Input data for LinkedIn people search.

    Search is performed by keywords and optional filters. At least one
    of keywords, name, title, company, or location should be provided.
    """

    keywords: Optional[str] = Field(
        default=None, description="Free-form keywords to search for"
    )
    name: Optional[str] = Field(default=None, description="Person name")
    title: Optional[str] = Field(default=None, description="Job title")
    company: Optional[str] = Field(default=None, description="Company name")
    location: Optional[str] = Field(default=None, description="Location")
    limit: int = Field(
        default=10, ge=1, le=50, description="Maximum number of results to return"
    )


class LinkedInPeopleSearchResult(BaseModel):
    """
    Single result from a LinkedIn people search.
    """

    name: str = Field(description="Person's display name")
    headline: str = Field(description="LinkedIn headline")
    profile_url: str = Field(description="LinkedIn profile URL")
    location: Optional[str] = Field(default=None, description="Location if available")


class LinkedInPeopleSearchResponse(BaseModel):
    """
    Response from a LinkedIn people search.
    """

    query: Dict[str, Any] = Field(description="Query parameters used for search")
    total: int = Field(description="Total number of results returned")
    results: List[LinkedInPeopleSearchResult] = Field(
        default_factory=list, description="List of matching people"
    )


class LinkedInProfileAnalysis(BaseModel):
    """
    Complete LinkedIn profile analysis result.

    Represents the output of a LinkedIn profile analysis including
    section scores, insights, and actionable recommendations for
    inbound attraction.
    """

    # Analysis Metadata
    analyzed_at: datetime = Field(
        default_factory=datetime.now, description="When analysis was performed"
    )

    # Overall Assessment
    overall_score: float = Field(
        description="Overall LinkedIn profile strength score (0-100)", ge=0, le=100
    )
    summary: str = Field(
        description="Executive summary of the LinkedIn profile analysis"
    )

    # Detailed Sections
    section_scores: List[ProfileSectionScore] = Field(
        default_factory=list,
        description="Scores and feedback for each profile section",
    )
    insights: List[InboundAttractionInsight] = Field(
        default_factory=list,
        description="Prioritized insights for inbound attraction",
    )

    # Recommendations
    keyword_recommendations: List[str] = Field(
        default_factory=list,
        description="Keywords to add or emphasize for recruiter discovery",
    )
    action_plan: List[str] = Field(
        default_factory=list,
        description="Step-by-step action plan to improve the profile",
    )

    # Content Generation
    generated_headline_options: List[str] = Field(
        default_factory=list,
        description="Suggested headline options optimized for search",
    )
    summary_rewrite_suggestions: List[str] = Field(
        default_factory=list,
        description="Suggested rewrites for the About/summary section",
    )

    # Competitive Positioning
    competitive_edge: str = Field(
        default="", description="Assessment of competitive positioning"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @field_validator("overall_score")
    @classmethod
    def validate_overall_score(cls, v: float) -> float:
        """Ensure overall score is between 0 and 100."""
        if not 0 <= v <= 100:
            raise ValueError("Overall score must be between 0 and 100")
        return v

    @property
    def is_strong_profile(self) -> bool:
        """Check if profile is considered strong (score >= 70)."""
        return self.overall_score >= 70

    @property
    def high_priority_insights(self) -> List[InboundAttractionInsight]:
        """Get only high-priority insights."""
        return [i for i in self.insights if i.priority == "high"]

    @property
    def weighted_overall_score(self) -> float:
        """
        Compute weighted overall score from section scores.

        If section_scores is empty, returns overall_score as-is.
        """
        if not self.section_scores:
            return self.overall_score

        total_weight = sum(s.weight for s in self.section_scores)
        if total_weight == 0:
            return self.overall_score

        weighted = sum(s.score * s.weight for s in self.section_scores) / total_weight
        return round(weighted, 2)

    model_config = ConfigDict(use_enum_values=True)
