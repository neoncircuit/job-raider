"""
Job Raider - Models Module

This module provides Pydantic models for job listings and user profiles.

Author: Job Raider
Date: 2026-04-20
"""

from .assessment import (
    Answer,
    AnswerFormat,
    AssessmentMode,
    AssessmentSession,
    DifficultyLevel,
    MultipleChoiceOption,
    Question,
    QuestionScore,
    QuestionType,
    SessionStatus,
)
from .job_listing import (
    ExperienceLevel,
    JobListing,
    JobListingCollection,
    JobRequirement,
    JobResponsibility,
    JobSource,
    JobType,
    SalaryRange,
    Skill,
    WorkMode,
)
from .resume_analysis import (
    AnalysisFocus,
    ExperienceInsight,
    ProjectInsight,
    ResumeAnalysis,
    SkillAssessment,
)
from .user_profile import (
    Certification,
    ContactInfo,
    Education,
    ProficiencyLevel,
    Project,
)
from .user_profile import Skill as UserSkill
from .user_profile import (
    SkillCategory,
    TargetJob,
    UserProfile,
    WorkExperience,
)

__all__ = [
    # Job Listing
    "JobListing",
    "JobListingCollection",
    "JobRequirement",
    "JobResponsibility",
    "Skill",
    "SalaryRange",
    "ExperienceLevel",
    "JobType",
    "WorkMode",
    "JobSource",
    # User Profile
    "UserProfile",
    "ContactInfo",
    "UserSkill",
    "SkillCategory",
    "ProficiencyLevel",
    "Project",
    "WorkExperience",
    "Education",
    "Certification",
    "TargetJob",
    # Resume Analysis
    "ResumeAnalysis",
    "SkillAssessment",
    "ExperienceInsight",
    "ProjectInsight",
    "AnalysisFocus",
    # Assessment
    "AssessmentMode",
    "QuestionType",
    "AnswerFormat",
    "DifficultyLevel",
    "SessionStatus",
    "MultipleChoiceOption",
    "Question",
    "Answer",
    "QuestionScore",
    "AssessmentSession",
]
