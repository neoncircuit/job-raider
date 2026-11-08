"""
Job Raider - Outcome Models

This module defines the application statuses, interview stages, outcomes,
and the dataclasses that the outcome tracker stores.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ApplicationStatus(str, Enum):
    """Status of a job application."""

    APPLIED = "applied"
    UNDER_REVIEW = "under_review"
    SCREENING_SCHEDULED = "screening_scheduled"
    SCREENING_COMPLETED = "screening_completed"
    TECHNICAL_SCHEDULED = "technical_scheduled"
    TECHNICAL_COMPLETED = "technical_completed"
    ONSITE_SCHEDULED = "onsite_scheduled"
    ONSITE_COMPLETED = "onsite_completed"
    OFFER_RECEIVED = "offer_received"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_DECLINED = "offer_declined"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    SAVED_BOOKMARKED = "saved_bookmarked"
    APPLIED_ELSEWHERE = "applied_elsewhere"
    NOT_INTERESTED = "not_interested"
    CUSTOM = "custom"


class InterviewStage(str, Enum):
    """Stages of the interview process."""

    SCREENING = "screening"
    TECHNICAL = "technical"
    ONSITE = "onsite"
    FINAL = "final"


class Outcome(str, Enum):
    """Final outcome of an application."""

    OFFER = "offer"
    REJECT = "reject"
    WITHDRAW = "withdraw"
    PENDING = "pending"


@dataclass
class InterviewEvent:
    """Record of an interview event."""

    stage: InterviewStage
    scheduled_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    feedback: Optional[str] = None
    outcome: Optional[str] = None


@dataclass
class OfferDetails:
    """Details of a job offer."""

    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_period: str = "annual"
    bonus: Optional[float] = None
    equity: Optional[str] = None
    benefits: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class CustomApplicationStatus:
    """User-defined application status."""

    status_id: str
    name: str
    description: str
    color: str = "#6B7280"
    icon: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApplicationOutcome:
    """Complete outcome tracking for an application."""

    application_id: str
    job_title: str
    company: str
    applied_date: datetime
    current_status: ApplicationStatus
    final_outcome: Optional[Outcome] = None
    interviews: List[InterviewEvent] = field(default_factory=list)
    offer: Optional[OfferDetails] = None
    timeline_notes: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    custom_status_id: Optional[str] = None
    external_application_details: Optional[Dict[str, Any]] = None
    is_bookmarked: bool = False
    is_hidden: bool = False
    bookmark_date: Optional[datetime] = None
    hidden_date: Optional[datetime] = None
    status_history: List[str] = field(default_factory=list)

    @property
    def previous_status(self) -> Optional[str]:
        """Last status before the current one, if a revert is possible."""
        if not self.status_history:
            return None
        return self.status_history[-1]

    @property
    def days_since_application(self) -> int:
        """Days since application was submitted."""
        return (datetime.now() - self.applied_date).days

    @property
    def has_interview(self) -> bool:
        """Whether any interviews occurred."""
        return len(self.interviews) > 0

    @property
    def interview_count(self) -> int:
        """Number of interviews completed."""
        return len([i for i in self.interviews if i.completed_date])

    @property
    def reached_stage(self) -> Optional[InterviewStage]:
        """Latest stage reached."""
        if not self.interviews:
            return None
        return self.interviews[-1].stage


@dataclass
class ConversionMetrics:
    """Conversion metrics for applications."""

    total_applications: int
    screening_rate: float  # % that got screening
    technical_rate: float  # % that got technical
    onsite_rate: float  # % that got onsite
    offer_rate: float  # % that got offers
    acceptance_rate: float  # % of offers accepted
    avg_time_to_offer: float  # days
    avg_time_to_reject: float  # days
