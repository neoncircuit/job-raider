"""
Job Raider - Job Listing Models

This module provides Pydantic models for job listings and related data structures.

Author: Job Raider
Date: 2026-04-20
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator, ConfigDict
from pathlib import Path


class ExperienceLevel(str, Enum):
    """Experience level for job positions."""
    ENTRY = "Entry Level"
    MID = "Mid Level"
    SENIOR = "Senior"
    LEAD = "Lead"
    PRINCIPAL = "Principal"
    EXECUTIVE = "Executive"
    INTERNSHIP = "Internship"
    NOT_SPECIFIED = "Not Specified"


class JobType(str, Enum):
    """Type of employment."""
    FULL_TIME = "Full-time"
    PART_TIME = "Part-time"
    CONTRACT = "Contract"
    INTERNSHIP = "Internship"
    TEMPORARY = "Temporary"
    FREELANCE = "Freelance"
    REMOTE = "Remote"


class WorkMode(str, Enum):
    """Work arrangement mode."""
    ON_SITE = "On-site"
    REMOTE = "Remote"
    HYBRID = "Hybrid"


class SalaryRange(BaseModel):
    """Salary range for a position."""
    min_amount: Optional[float] = Field(default=None, description="Minimum salary")
    max_amount: Optional[float] = Field(default=None, description="Maximum salary")
    currency: str = Field(default="USD", description="Currency code")
    period: str = Field(default="annual", description="Salary period: annual, monthly, hourly")
    is_estimated: bool = Field(default=False, description="True if salary is estimated")

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        """Normalize currency code to uppercase (ISO 4217 standard)."""
        return v.upper() if v else "USD"

    @property
    def is_valid(self) -> bool:
        """Check if salary range has valid values."""
        return self.min_amount is not None or self.max_amount is not None

    def __str__(self) -> str:
        """Return formatted salary range."""
        if not self.is_valid:
            return "Not specified"

        if self.min_amount and self.max_amount:
            return f"{self.currency} {self.min_amount:,.0f} - {self.max_amount:,.0f} ({self.period})"
        elif self.min_amount:
            return f"{self.currency} {self.min_amount:,.0f}+ ({self.period})"
        else:
            return f"Up to {self.currency} {self.max_amount:,.0f} ({self.period})"


class JobRequirement(BaseModel):
    """A specific job requirement."""
    category: Optional[str] = Field(default=None, description="Category of requirement (e.g., 'Skills', 'Education')")
    text: str = Field(description="Requirement text")
    is_required: bool = Field(default=True, description="Whether this is a must-have requirement")
    years_of_experience: Optional[float] = Field(default=None, description="Required years of experience")


class JobResponsibility(BaseModel):
    """A specific job responsibility."""
    category: Optional[str] = Field(default=None, description="Category of responsibility")
    text: str = Field(description="Responsibility text")


class Skill(BaseModel):
    """A skill or competency."""
    name: str = Field(description="Skill name")
    category: Optional[str] = Field(default=None, description="Skill category (technical, soft, language, etc.)")
    proficiency: Optional[str] = Field(default=None, description="Proficiency level if specified")
    is_required: bool = Field(default=True, description="Whether skill is required")


class JobSource(str, Enum):
    """Source of the job listing."""
    LINKEDIN = "linkedin"
    JSEARCH = "jsearch"
    MANUAL = "manual"
    OTHER = "other"


class JobListing(BaseModel):
    """
    Complete job listing model.

    Represents a job posting with all relevant information for
    scoring and matching against user profiles.
    """
    # Basic Information
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    job_id: str = Field(description="Unique identifier for the job listing")
    source: JobSource = Field(description="Source of the listing")
    source_url: Optional[HttpUrl] = Field(default=None, description="URL to original posting")

    # Location & Work Mode
    location: Optional[str] = Field(default=None, description="Job location (city, state, country)")
    work_mode: WorkMode = Field(default=WorkMode.ON_SITE, description="Work arrangement")
    is_remote: bool = Field(default=False, description="Whether position is remote")

    # Employment Details
    job_type: JobType = Field(default=JobType.FULL_TIME, description="Employment type")
    experience_level: ExperienceLevel = Field(default=ExperienceLevel.NOT_SPECIFIED, description="Required experience level")

    # Compensation
    salary_range: Optional[SalaryRange] = Field(default=None, description="Salary information")

    # Job Content
    description: Optional[str] = Field(default=None, description="Full job description")
    requirements: List[JobRequirement] = Field(default_factory=list, description="List of requirements")
    responsibilities: List[JobResponsibility] = Field(default_factory=list, description="List of responsibilities")
    skills: List[Skill] = Field(default_factory=list, description="List of required/preferred skills")

    # Additional Details
    department: Optional[str] = Field(default=None, description="Department or team")
    posted_date: Optional[datetime] = Field(default=None, description="When job was posted")
    application_deadline: Optional[datetime] = Field(default=None, description="Application deadline")
    applicants_count: Optional[int] = Field(default=None, description="Number of applicants if shown")

    # Recruiter Info
    recruiter_name: Optional[str] = Field(default=None, description="Name of recruiter or hiring manager")
    recruiter_email: Optional[str] = Field(default=None, description="Recruiter email")
    recruiter_phone: Optional[str] = Field(default=None, description="Recruiter phone")

    # Application Status
    already_applied: bool = Field(default=False, description="Whether user has already applied to this job")

    # Metadata
    scraped_at: datetime = Field(default_factory=datetime.now, description="When this was scraped")
    raw_html: Optional[str] = Field(default=None, description="Raw HTML for debugging")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("location")
    @classmethod
    def validate_location(cls, v: Optional[str]) -> Optional[str]:
        """Standardize location format."""
        if v and isinstance(v, str):
            return v.strip().title()
        return v

    @property
    def is_entry_level(self) -> bool:
        """Check if this is an entry-level position."""
        return self.experience_level in [ExperienceLevel.ENTRY, ExperienceLevel.INTERNSHIP]

    @property
    def is_senior_level(self) -> bool:
        """Check if this is a senior-level position."""
        return self.experience_level in [ExperienceLevel.SENIOR, ExperienceLevel.LEAD, ExperienceLevel.PRINCIPAL]

    @property
    def days_since_posted(self) -> Optional[int]:
        """Calculate days since job was posted."""
        if not self.posted_date:
            return None
        return (datetime.now() - self.posted_date).days

    @property
    def all_skill_names(self) -> List[str]:
        """Get list of all skill names."""
        return [skill.name for skill in self.skills]

    @property
    def required_skill_names(self) -> List[str]:
        """Get list of required skill names."""
        return [skill.name for skill in self.skills if skill.is_required]

    def matches_keyword(self, keyword: str) -> bool:
        """
        Check if job listing matches a keyword.

        Searches in title, description, requirements, skills, and responsibilities.

        Args:
            keyword: Keyword to search for (case-insensitive)

        Returns:
            True if keyword is found
        """
        keyword_lower = keyword.lower()

        # Check title
        if keyword_lower in self.title.lower():
            return True

        # Check description
        if self.description and keyword_lower in self.description.lower():
            return True

        # Check requirements
        for req in self.requirements:
            if keyword_lower in req.text.lower():
                return True

        # Check skills
        for skill in self.skills:
            if keyword_lower in skill.name.lower():
                return True

        # Check responsibilities
        for resp in self.responsibilities:
            if keyword_lower in resp.text.lower():
                return True

        return False

    model_config = ConfigDict(use_enum_values=True)


class JobListingCollection(BaseModel):
    """Collection of job listings with metadata."""
    listings: List[JobListing] = Field(default_factory=list, description="List of job listings")
    total_count: int = Field(default=0, description="Total number of listings")
    source: Optional[JobSource] = Field(default=None, description="Source of these listings")
    scraped_at: datetime = Field(default_factory=datetime.now, description="When collection was created")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @model_validator(mode="before")
    @classmethod
    def update_total_count(cls, data: Any) -> Any:
        """Ensure total_count matches listings length."""
        if isinstance(data, dict) and "listings" in data:
            data["total_count"] = len(data["listings"])
        return data

    def add(self, listing: JobListing) -> None:
        """Add a job listing to the collection."""
        self.listings.append(listing)
        self.total_count = len(self.listings)

    def extend(self, listings: List[JobListing]) -> None:
        """Add multiple job listings to the collection."""
        self.listings.extend(listings)
        self.total_count = len(self.listings)

    def filter_by_keywords(self, keywords: List[str]) -> "JobListingCollection":
        """
        Filter listings by keywords (OR logic).

        Args:
            keywords: List of keywords to filter by

        Returns:
            New JobListingCollection with filtered listings
        """
        filtered = [
            listing for listing in self.listings
            if any(listing.matches_keyword(keyword) for keyword in keywords)
        ]
        return JobListingCollection(
            listings=filtered,
            source=self.source,
            metadata=self.metadata,
        )

    def filter_by_location(self, locations: List[str]) -> "JobListingCollection":
        """
        Filter listings by location.

        Args:
            locations: List of locations to filter by

        Returns:
            New JobListingCollection with filtered listings
        """
        filtered = [
            listing for listing in self.listings
            if listing.location and any(loc.lower() in listing.location.lower() for loc in locations)
        ]
        return JobListingCollection(
            listings=filtered,
            source=self.source,
            metadata=self.metadata,
        )

    def deduplicate(self) -> "JobListingCollection":
        """
        Remove duplicate listings based on job_id.

        Returns:
            New JobListingCollection with duplicates removed
        """
        seen = set()
        unique_listings = []

        for listing in self.listings:
            if listing.job_id not in seen:
                seen.add(listing.job_id)
                unique_listings.append(listing)

        return JobListingCollection(
            listings=unique_listings,
            source=self.source,
            metadata=self.metadata,
        )
