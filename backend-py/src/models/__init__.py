"""
Job Raider - Models Module

This module provides Pydantic models for job listings and user profiles.

Author: Job Raider
Date: 2026-04-20
"""

from .job_listing import (
    JobListing,
    JobListingCollection,
    JobRequirement,
    JobResponsibility,
    Skill,
    SalaryRange,
    ExperienceLevel,
    JobType,
    WorkMode,
    JobSource,
)

from .user_profile import (
    UserProfile,
    ContactInfo,
    Skill as UserSkill,
    SkillCategory,
    ProficiencyLevel,
    Project,
    WorkExperience,
    Education,
    Certification,
    TargetJob,
)

from .resume_analysis import (
    ResumeAnalysis,
    SkillAssessment,
    ExperienceInsight,
    ProjectInsight,
    AnalysisFocus,
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
]
