"""
Job Raider - User Profile Models

This module provides Pydantic models for user profiles including
skills, projects, experience, and education.

Author: Job Raider
Date: 2026-04-20
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, EmailStr, field_validator, model_validator, ConfigDict
from pathlib import Path

# Import ExperienceLevel from job_listing module
from .job_listing import ExperienceLevel


class SkillCategory(str, Enum):
    """Categories of skills."""
    PROGRAMMING_LANGUAGE = "programming_language"
    FRAMEWORK = "framework"
    TOOL = "tool"
    CLOUD = "cloud"
    DATABASE = "database"
    LANGUAGE = "language"
    SOFT_SKILL = "soft_skill"
    DOMAIN = "domain"
    OTHER = "other"


class ProficiencyLevel(str, Enum):
    """Proficiency level for skills."""
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    EXPERT = "Expert"


class Skill(BaseModel):
    """A skill or competency."""
    name: str = Field(description="Skill name")
    category: SkillCategory = Field(default=SkillCategory.OTHER, description="Skill category")
    proficiency: Optional[ProficiencyLevel] = Field(default=None, description="Proficiency level")
    years_of_experience: Optional[float] = Field(default=None, description="Years of experience with this skill")
    last_used: Optional[datetime] = Field(default=None, description="When this skill was last used")

    @property
    def is_recent(self) -> bool:
        """Check if skill was used in the last 2 years."""
        if not self.last_used:
            return False
        return (datetime.now() - self.last_used).days <= 730


class Project(BaseModel):
    """A project the user has worked on."""
    name: str = Field(description="Project name")
    description: str = Field(description="Brief project description (1-2 sentences)")
    long_description: Optional[str] = Field(default=None, description="Detailed project description")
    technologies: List[str] = Field(default_factory=list, description="Technologies used")
    url: Optional[HttpUrl] = Field(default=None, description="Project URL (GitHub, demo, etc.)")
    start_date: Optional[datetime] = Field(default=None, description="Project start date")
    end_date: Optional[datetime] = Field(default=None, description="Project end date (None if ongoing)")
    highlights: List[str] = Field(default_factory=list, description="Key achievements/impact")
    role: Optional[str] = Field(default=None, description="User's role in the project")

    @property
    def is_ongoing(self) -> bool:
        """Check if project is ongoing."""
        return self.end_date is None

    @property
    def duration_months(self) -> Optional[int]:
        """Calculate project duration in months."""
        if not self.start_date:
            return None

        end = self.end_date or datetime.now()
        return ((end.year - self.start_date.year) * 12 + end.month - self.start_date.month)


class WorkExperience(BaseModel):
    """Work experience entry."""
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    location: Optional[str] = Field(default=None, description="Job location")
    start_date: datetime = Field(description="Employment start date")
    end_date: Optional[datetime] = Field(default=None, description="Employment end date (None if current)")
    current: bool = Field(default=False, description="Whether this is current position")
    description: Optional[str] = Field(default=None, description="Role description")
    highlights: List[str] = Field(default_factory=list, description="Key achievements and responsibilities")
    technologies: List[str] = Field(default_factory=list, description="Technologies used")

    @model_validator(mode="before")
    @classmethod
    def set_current_if_no_end_date(cls, data: Any) -> Any:
        """Set current=True if no end_date provided."""
        if isinstance(data, dict):
            if data.get("end_date") is None and "current" not in data:
                data["current"] = True
        return data

    @property
    def duration_months(self) -> int:
        """Calculate employment duration in months."""
        end = self.end_date or datetime.now()
        return (end.year - self.start_date.year) * 12 + end.month - self.start_date.month

    @property
    def duration_years(self) -> float:
        """Calculate employment duration in years."""
        return round(self.duration_months / 12, 1)


class Education(BaseModel):
    """Education entry."""
    degree: str = Field(description="Degree name (e.g., 'Bachelor of Science in Computer Science')")
    school: str = Field(description="School/university name")
    location: Optional[str] = Field(default=None, description="School location")
    start_date: Optional[datetime] = Field(default=None, description="Start date")
    end_date: Optional[datetime] = Field(default=None, description="Graduation date")
    gpa: Optional[float] = Field(default=None, ge=0.0, le=4.0, description="GPA (0-4 scale)")
    honors: List[str] = Field(default_factory=list, description="Honors and awards")
    coursework: List[str] = Field(default_factory=list, description="Relevant coursework")
    description: Optional[str] = Field(default=None, description="Additional details")

    @property
    def is_completed(self) -> bool:
        """Check if degree is completed."""
        return self.end_date is not None and self.end_date < datetime.now()


class Certification(BaseModel):
    """Professional certification."""
    name: str = Field(description="Certification name")
    issuer: str = Field(description="Issuing organization")
    issue_date: Optional[datetime] = Field(default=None, description="Issue date")
    expiration_date: Optional[datetime] = Field(default=None, description="Expiration date")
    credential_id: Optional[str] = Field(default=None, description="Credential ID")
    url: Optional[HttpUrl] = Field(default=None, description="Verification URL")

    @property
    def is_valid(self) -> bool:
        """Check if certification is currently valid."""
        if not self.expiration_date:
            return True
        return datetime.now() < self.expiration_date


class ContactInfo(BaseModel):
    """Contact information."""
    email: EmailStr = Field(description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    location: str = Field(description="Location (city, state, country)")
    linkedin: Optional[HttpUrl] = Field(default=None, description="LinkedIn profile URL")
    github: Optional[HttpUrl] = Field(default=None, description="GitHub profile URL")
    portfolio: Optional[HttpUrl] = Field(default=None, description="Portfolio website URL")
    website: Optional[HttpUrl] = Field(default=None, description="Personal website URL")


class ApprenticeshipContract(BaseModel):
    """Apprenticeship or traineeship contract obligation.

    Represents a contractual requirement to work in a specific field
    for a set duration, typically arising from sponsored training
    or apprenticeship programs.
    """
    field: str = Field(description="Required field of work (e.g. 'AI/ML', 'Healthcare')")
    duration_months: Optional[int] = Field(default=None, description="Remaining contract duration in months")
    employer: Optional[str] = Field(default=None, description="Sponsoring employer or organization name")
    start_date: Optional[datetime] = Field(default=None, description="Contract start date")
    end_date: Optional[datetime] = Field(default=None, description="Contract end date")
    is_active: bool = Field(default=True, description="Whether the contract obligation is still active")

    @property
    def remaining_months(self) -> Optional[int]:
        """Calculate remaining contract months from end_date."""
        if not self.end_date or not self.is_active:
            return self.duration_months
        delta = (self.end_date - datetime.now()).days // 30
        return max(delta, 0)


class TargetJob(BaseModel):
    """User's target job criteria."""
    keywords: List[str] = Field(default_factory=list, description="Target job keywords")
    locations: List[str] = Field(default_factory=list, description="Preferred locations")
    experience_levels: List[ExperienceLevel] = Field(default_factory=list, description="Target experience levels")
    remote_preference: bool = Field(default=False, description="Preference for remote work")
    salary_min: Optional[float] = Field(default=None, description="Minimum acceptable salary (annual)")
    industries: List[str] = Field(default_factory=list, description="Target industries")
    company_sizes: List[str] = Field(default_factory=list, description="Preferred company sizes")
    constraint_mode: str = Field(default="boost", description="How apprenticeship constraints apply: 'filter' excludes non-matching jobs, 'boost' raises matching job scores")


class VisaStatus(str, Enum):
    """Work authorization status."""
    CITIZEN = "citizen"
    PERMANENT_RESIDENT = "permanent_resident"
    H1B = "h1b"
    OTHER_VISA = "other_visa"
    NEED_SPONSORSHIP = "need_sponsorship"
    STUDENT_VISA = "student_visa"
    NOT_SPECIFIED = "not_specified"


class UserProfile(BaseModel):
    """
    Complete user profile model.

    Represents a user's professional profile including skills,
    experience, projects, and job preferences.
    """
    # Basic Information
    name: str = Field(description="Full name")
    contact: ContactInfo = Field(description="Contact information")

    # Professional Summary
    summary: Optional[str] = Field(default=None, description="Professional summary (2-3 sentences)")

    # Skills
    skills: List[Skill] = Field(default_factory=list, description="List of skills")
    core_skills: List[str] = Field(default_factory=list, description="Core skills to emphasize")

    # Experience
    experience: List[WorkExperience] = Field(default_factory=list, description="Work experience")
    projects: List[Project] = Field(default_factory=list, description="Projects")
    education: List[Education] = Field(default_factory=list, description="Education")

    # Additional
    certifications: List[Certification] = Field(default_factory=list, description="Certifications")
    languages: List[str] = Field(default_factory=list, description="Languages spoken")

    # Job Search Targets
    targets: TargetJob = Field(default_factory=TargetJob, description="Target job criteria")

    # Contractual Obligations
    apprenticeship: Optional[ApprenticeshipContract] = Field(default=None, description="Apprenticeship/traineeship contract obligation (if applicable)")

    # Application-Specific Fields (for auto-apply)
    visa_status: Optional[VisaStatus] = Field(default=None, description="Work authorization status")
    visa_expiration_date: Optional[datetime] = Field(default=None, description="Visa expiration date (if applicable)")
    salary_expectation_min: Optional[float] = Field(default=None, description="Minimum salary expectation (annual)")
    salary_expectation_max: Optional[float] = Field(default=None, description="Maximum salary expectation (annual)")
    salary_currency: str = Field(default="USD", description="Currency for salary expectations")
    notice_period_weeks: Optional[int] = Field(default=None, ge=0, le=52, description="Notice period in weeks")
    willing_to_relocate: bool = Field(default=False, description="Willingness to relocate for work")
    preferred_work_locations: List[str] = Field(default_factory=list, description="Preferred work locations beyond targets")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now, description="Profile creation date")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update date")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("updated_at")
    @classmethod
    def touch_updated_at(cls, v: datetime) -> datetime:
        """Ensure updated_at is current."""
        return datetime.now()

    @field_validator("salary_currency")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        """Normalize currency code to uppercase (ISO 4217 standard)."""
        return v.upper() if v else "USD"

    @property
    def years_of_experience(self) -> float:
        """Calculate total years of work experience."""
        if not self.experience:
            return 0.0

        total_months = sum(exp.duration_months for exp in self.experience)
        return round(total_months / 12, 1)

    @property
    def current_position(self) -> Optional[WorkExperience]:
        """Get current/latest position."""
        if not self.experience:
            return None

        # Get most recent experience
        sorted_exp = sorted(self.experience, key=lambda e: e.start_date, reverse=True)
        return sorted_exp[0]

    @property
    def all_skills_names(self) -> List[str]:
        """Get list of all skill names."""
        return [skill.name for skill in self.skills]

    @property
    def all_technologies(self) -> List[str]:
        """Get list of all technologies from experience and projects."""
        technologies = set()

        for exp in self.experience:
            technologies.update(exp.technologies)

        for project in self.projects:
            technologies.update(project.technologies)

        return sorted(list(technologies))

    @property
    def recent_projects(self, n: int = 3) -> List[Project]:
        """
        Get N most recent projects.

        Args:
            n: Number of projects to return

        Returns:
            List of recent projects
        """
        dated_projects = [p for p in self.projects if p.start_date]
        sorted_projects = sorted(dated_projects, key=lambda p: p.start_date, reverse=True)
        return sorted_projects[:n]

    def has_skill(self, skill_name: str) -> bool:
        """
        Check if user has a specific skill.

        Args:
            skill_name: Skill name to check (case-insensitive)

        Returns:
            True if skill is found
        """
        skill_lower = skill_name.lower()
        return any(skill.name.lower() == skill_lower for skill in self.skills)

    def get_skill(self, skill_name: str) -> Optional[Skill]:
        """
        Get a skill by name.

        Args:
            skill_name: Skill name to get (case-insensitive)

        Returns:
            Skill if found, None otherwise
        """
        skill_lower = skill_name.lower()
        for skill in self.skills:
            if skill.name.lower() == skill_lower:
                return skill
        return None

    def matches_keyword(self, keyword: str) -> bool:
        """
        Check if profile matches a keyword.

        Searches in skills, experience, projects, and education.

        Args:
            keyword: Keyword to search for (case-insensitive)

        Returns:
            True if keyword is found
        """
        keyword_lower = keyword.lower()

        # Check skills
        if any(keyword_lower in skill.name.lower() for skill in self.skills):
            return True

        # Check experience titles and companies
        for exp in self.experience:
            if keyword_lower in exp.title.lower() or keyword_lower in exp.company.lower():
                return True

        # Check projects
        for project in self.projects:
            if keyword_lower in project.name.lower():
                return True

        # Check education
        for edu in self.education:
            if keyword_lower in edu.degree.lower() or keyword_lower in edu.school.lower():
                return True

        return False

    model_config = ConfigDict(use_enum_values=True)
