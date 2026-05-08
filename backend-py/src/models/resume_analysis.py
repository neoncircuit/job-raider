"""
Job Raider - Resume Analysis Models

This module provides Pydantic models for resume analysis results.

Author: Job Raider
Date: 2026-04-23
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class AnalysisFocus(str, Enum):
    """Focus areas for resume analysis."""
    GENERAL = "general"
    TECHNICAL = "technical"
    LEADERSHIP = "leadership"
    INDUSTRY_SPECIFIC = "industry_specific"
    CAREER_TRANSITION = "career_transition"


class SkillAssessment(BaseModel):
    """Assessment of a specific skill."""
    skill_name: str = Field(description="Name of the skill")
    proficiency_level: str = Field(description="Assessed proficiency level")
    years_experience: Optional[float] = Field(default=None, description="Years of experience")
    is_industry_relevant: bool = Field(default=True, description="If skill is relevant to target industry")
    improvement_suggestions: List[str] = Field(default_factory=list, description="Suggestions for improvement")


class ExperienceInsight(BaseModel):
    """Insight about work experience."""
    company: str = Field(description="Company name")
    title: str = Field(description="Job title")
    period: str = Field(description="Employment period")
    strengths: List[str] = Field(default_factory=list, description="What's strong about this experience")
    gaps: List[str] = Field(default_factory=list, description="Potential gaps")
    achievements_to_highlight: List[str] = Field(default_factory=list, description="Key achievements to emphasize")


class ProjectInsight(BaseModel):
    """Insight about a project."""
    name: str = Field(description="Project name")
    technologies: List[str] = Field(default_factory=list, description="Technologies used")
    impact_score: float = Field(description="Impact score (0-100)")
    strengths: List[str] = Field(default_factory=list, description="What's strong about this project")
    improvements: List[str] = Field(default_factory=list, description="Potential improvements")


class ResumeAnalysis(BaseModel):
    """
    Complete resume analysis result.

    Represents the output of a resume analysis including
    assessments, insights, and recommendations.
    """
    # Analysis Metadata
    analyzed_at: datetime = Field(default_factory=datetime.now, description="When analysis was performed")
    resume_path: str = Field(description="Path to analyzed resume")
    analysis_type: Literal["general", "job_specific"] = Field(
        default="general",
        description="Type of analysis performed"
    )

    # Overall Assessment
    overall_score: float = Field(description="Overall resume strength score (0-100)")
    summary: str = Field(description="Executive summary of the resume")
    key_strengths: List[str] = Field(default_factory=list, description="Top 3-5 key strengths")
    key_improvements: List[str] = Field(default_factory=list, description="Top 3-5 key improvements")

    # Detailed Sections
    skills_assessment: List[SkillAssessment] = Field(
        default_factory=list,
        description="Assessment of each skill"
    )
    experience_insights: List[ExperienceInsight] = Field(
        default_factory=list,
        description="Insights from work experience"
    )
    project_insights: List[ProjectInsight] = Field(
        default_factory=list,
        description="Insights from projects"
    )

    # Recommendations
    resume_improvements: List[str] = Field(
        default_factory=list,
        description="Specific resume improvements"
    )
    skill_gaps: List[str] = Field(default_factory=list, description="Missing skills to consider developing")
    next_steps: List[str] = Field(default_factory=list, description="Immediate next steps")

    # Target Job Alignment (job-specific only)
    target_alignment_score: Optional[float] = Field(
        default=None,
        description="Alignment with target jobs (0-100)",
        ge=0,
        le=100
    )
    competitive_advantages: List[str] = Field(
        default_factory=list,
        description="Competitive advantages"
    )
    competitive_gaps: List[str] = Field(
        default_factory=list,
        description="Areas where competition might be stronger"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    @field_validator('overall_score')
    @classmethod
    def validate_score(cls, v: float) -> float:
        """Ensure score is between 0 and 100."""
        if not 0 <= v <= 100:
            raise ValueError('Overall score must be between 0 and 100')
        return v

    @property
    def is_strong_resume(self) -> bool:
        """Check if resume is considered strong (score >= 70)."""
        return self.overall_score >= 70

    @property
    def competitive_edge(self) -> str:
        """Get competitive edge assessment."""
        if self.overall_score >= 85:
            return "Strong competitive edge"
        elif self.overall_score >= 70:
            return "Good competitive edge"
        elif self.overall_score >= 50:
            return "Moderate competitive edge"
        else:
            return "Needs improvement for competitiveness"

    model_config = ConfigDict(use_enum_values=True)
