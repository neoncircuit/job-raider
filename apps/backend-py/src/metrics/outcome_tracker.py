"""
Job Raider - Outcome Tracker

This module tracks job application outcomes from submission
through to offer, providing conversion metrics and insights.

Author: Job Raider
Date: 2026-04-21
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.logger import Components, get_logger


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


class OutcomeTracker:
    """
    Track job application outcomes and conversion metrics.

    Provides insights into pipeline effectiveness and
    helps optimize targeting and application strategy.
    """

    def __init__(self, storage_dir: str = "data/applications"):
        """
        Initialize the outcome tracker.

        Args:
            storage_dir: Directory to store application data
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(Components.SCRAPERS)

        # Custom statuses storage
        self.custom_statuses_dir = self.storage_dir / "custom_statuses"
        self.custom_statuses_dir.mkdir(exist_ok=True)

        # Cache
        self._outcomes: Dict[str, ApplicationOutcome] = {}
        self._custom_statuses: Dict[str, CustomApplicationStatus] = {}
        self._load_cache()
        self._load_custom_statuses()

    def track_application(
        self,
        application_id: str,
        job_title: str,
        company: str,
        applied_date: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ApplicationOutcome:
        """
        Create a new application outcome record.

        Args:
            application_id: Unique application ID
            job_title: Job title applied for
            company: Company name
            applied_date: Application date (default: now)
            metadata: Additional metadata

        Returns:
            ApplicationOutcome object
        """
        outcome = ApplicationOutcome(
            application_id=application_id,
            job_title=job_title,
            company=company,
            applied_date=applied_date or datetime.now(),
            current_status=ApplicationStatus.APPLIED,
            final_outcome=Outcome.PENDING,
            metadata=metadata or {},
        )

        self._outcomes[application_id] = outcome
        self._save_outcome(outcome)

        self.logger.info(
            f"Tracking application: {application_id} - {job_title} at {company}"
        )

        return outcome

    def update_status(
        self,
        application_id: str,
        status: ApplicationStatus,
        note: Optional[str] = None,
    ) -> bool:
        """
        Update application status.

        Args:
            application_id: Application ID
            status: New status
            note: Optional note about the change

        Returns:
            True if update successful
        """
        outcome = self._outcomes.get(application_id)
        if not outcome:
            self.logger.warning(f"Application not found: {application_id}")
            return False

        outcome.current_status = status

        if note:
            outcome.timeline_notes.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "note": note,
                }
            )

        # Auto-detect final outcome
        if status == ApplicationStatus.OFFER_ACCEPTED:
            outcome.final_outcome = Outcome.OFFER
        elif status == ApplicationStatus.REJECTED:
            outcome.final_outcome = Outcome.REJECT
        elif status == ApplicationStatus.WITHDRAWN:
            outcome.final_outcome = Outcome.WITHDRAW

        self._save_outcome(outcome)

        self.logger.info(f"Updated application {application_id} to {status.value}")

        return True

    def add_interview(
        self,
        application_id: str,
        stage: InterviewStage,
        scheduled_date: Optional[datetime] = None,
        feedback: Optional[str] = None,
    ) -> bool:
        """
        Add an interview event to an application.

        Args:
            application_id: Application ID
            stage: Interview stage
            scheduled_date: Scheduled date (default: now)
            feedback: Interview feedback

        Returns:
            True if added successfully
        """
        outcome = self._outcomes.get(application_id)
        if not outcome:
            self.logger.warning(f"Application not found: {application_id}")
            return False

        event = InterviewEvent(
            stage=stage,
            scheduled_date=scheduled_date or datetime.now(),
            completed_date=datetime.now() if scheduled_date else None,
            feedback=feedback,
        )

        outcome.interviews.append(event)
        self._save_outcome(outcome)

        self.logger.info(
            f"Added {stage.value} interview to application {application_id}"
        )

        return True

    def complete_interview(
        self,
        application_id: str,
        stage: InterviewStage,
        outcome: str,
        feedback: Optional[str] = None,
    ) -> bool:
        """
        Mark an interview as completed.

        Args:
            application_id: Application ID
            stage: Interview stage
            outcome: Interview outcome
            feedback: Interview feedback

        Returns:
            True if updated successfully
        """
        app_outcome = self._outcomes.get(application_id)
        if not app_outcome:
            self.logger.warning(f"Application not found: {application_id}")
            return False

        # Find the interview
        for interview in app_outcome.interviews:
            if interview.stage == stage and not interview.completed_date:
                interview.completed_date = datetime.now()
                interview.outcome = outcome
                interview.feedback = feedback
                self._save_outcome(app_outcome)

                self.logger.info(
                    f"Completed {stage.value} interview for {application_id}: {outcome}"
                )

                return True

        self.logger.warning(
            f"No pending {stage.value} interview found for {application_id}"
        )
        return False

    def add_offer(
        self,
        application_id: str,
        salary_min: Optional[float] = None,
        salary_max: Optional[float] = None,
        bonus: Optional[float] = None,
        benefits: Optional[List[str]] = None,
        notes: str = "",
    ) -> bool:
        """
        Add offer details to an application.

        Args:
            application_id: Application ID
            salary_min: Minimum salary
            salary_max: Maximum salary
            bonus: Bonus amount
            benefits: List of benefits
            notes: Additional notes

        Returns:
            True if added successfully
        """
        outcome = self._outcomes.get(application_id)
        if not outcome:
            self.logger.warning(f"Application not found: {application_id}")
            return False

        outcome.offer = OfferDetails(
            salary_min=salary_min,
            salary_max=salary_max,
            bonus=bonus,
            benefits=benefits or [],
            notes=notes,
        )

        outcome.final_outcome = Outcome.OFFER
        outcome.current_status = ApplicationStatus.OFFER_RECEIVED

        self._save_outcome(outcome)

        self.logger.info(f"Added offer to application {application_id}")

        return True

    def get_application(self, application_id: str) -> Optional[ApplicationOutcome]:
        """
        Get application outcome by ID.

        Args:
            application_id: Application ID

        Returns:
            ApplicationOutcome or None if not found
        """
        return self._outcomes.get(application_id)

    def get_all_applications(
        self,
        status: Optional[ApplicationStatus] = None,
        company: Optional[str] = None,
        days: Optional[int] = None,
    ) -> List[ApplicationOutcome]:
        """
        Get applications with optional filtering.

        Args:
            status: Filter by status
            company: Filter by company
            days: Filter by days since application

        Returns:
            List of ApplicationOutcome objects
        """
        outcomes = list(self._outcomes.values())

        # Filter by status
        if status:
            outcomes = [o for o in outcomes if o.current_status == status]

        # Filter by company
        if company:
            outcomes = [o for o in outcomes if company.lower() in o.company.lower()]

        # Filter by days
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            outcomes = [o for o in outcomes if o.applied_date >= cutoff]

        return sorted(outcomes, key=lambda x: x.applied_date, reverse=True)

    def get_conversion_metrics(
        self,
        days: int = 90,
    ) -> ConversionMetrics:
        """
        Calculate conversion metrics.

        Args:
            days: Number of days to look back

        Returns:
            ConversionMetrics object
        """
        cutoff = datetime.now() - timedelta(days=days)
        recent_apps = [o for o in self._outcomes.values() if o.applied_date >= cutoff]

        if not recent_apps:
            return ConversionMetrics(
                total_applications=0,
                screening_rate=0.0,
                technical_rate=0.0,
                onsite_rate=0.0,
                offer_rate=0.0,
                acceptance_rate=0.0,
                avg_time_to_offer=0.0,
                avg_time_to_reject=0.0,
            )

        total = len(recent_apps)

        # Calculate rates
        screening = len([o for o in recent_apps if o.has_interview])
        technical = len(
            [
                o
                for o in recent_apps
                if any(i.stage == InterviewStage.TECHNICAL for i in o.interviews)
            ]
        )
        onsite = len(
            [
                o
                for o in recent_apps
                if any(i.stage == InterviewStage.ONSITE for i in o.interviews)
            ]
        )
        offers = len([o for o in recent_apps if o.final_outcome == Outcome.OFFER])
        accepted = len(
            [
                o
                for o in recent_apps
                if o.current_status == ApplicationStatus.OFFER_ACCEPTED
            ]
        )

        # Time to outcome
        time_to_offer = []
        time_to_reject = []

        for o in recent_apps:
            if o.final_outcome == Outcome.OFFER:
                # Find when offer was received
                for note in reversed(o.timeline_notes):
                    if "offer" in note.get("note", "").lower():
                        try:
                            offer_date = datetime.fromisoformat(note["timestamp"])
                            time_to_offer.append((offer_date - o.applied_date).days)
                        except (ValueError, TypeError):
                            pass
                        break

            elif o.final_outcome == Outcome.REJECT:
                # Use last update
                if o.timeline_notes:
                    try:
                        last_date = datetime.fromisoformat(
                            o.timeline_notes[-1]["timestamp"]
                        )
                        time_to_reject.append((last_date - o.applied_date).days)
                    except (ValueError, TypeError):
                        pass

        return ConversionMetrics(
            total_applications=total,
            screening_rate=screening / total if total > 0 else 0,
            technical_rate=technical / total if total > 0 else 0,
            onsite_rate=onsite / total if total > 0 else 0,
            offer_rate=offers / total if total > 0 else 0,
            acceptance_rate=accepted / offers if offers > 0 else 0,
            avg_time_to_offer=(
                sum(time_to_offer) / len(time_to_offer) if time_to_offer else 0
            ),
            avg_time_to_reject=(
                sum(time_to_reject) / len(time_to_reject) if time_to_reject else 0
            ),
        )

    def get_pipeline_effectiveness(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Analyze pipeline effectiveness.

        Args:
            days: Number of days to analyze

        Returns:
            Effectiveness metrics
        """
        metrics = self.get_conversion_metrics(days)

        # Calculate scores
        funnel_score = (
            metrics.screening_rate * 0.2
            + metrics.technical_rate * 0.3
            + metrics.onsite_rate * 0.3
            + metrics.offer_rate * 0.2
        )

        # Get offer details
        offers = [
            o for o in self._outcomes.values() if o.final_outcome == Outcome.OFFER
        ]

        avg_salary = None
        if offers:
            salaries = []
            for o in offers:
                if o.offer and o.offer.salary_min:
                    salaries.append(o.offer.salary_min)
            if salaries:
                avg_salary = sum(salaries) / len(salaries)

        return {
            "period_days": days,
            "total_applications": metrics.total_applications,
            "funnel_score": funnel_score,
            "conversion_rates": {
                "screening": f"{metrics.screening_rate:.1%}",
                "technical": f"{metrics.technical_rate:.1%}",
                "onsite": f"{metrics.onsite_rate:.1%}",
                "offer": f"{metrics.offer_rate:.1%}",
            },
            "time_metrics": {
                "avg_days_to_offer": metrics.avg_time_to_offer,
                "avg_days_to_reject": metrics.avg_time_to_reject,
            },
            "offer_metrics": {
                "total_offers": sum(
                    1
                    for o in self._outcomes.values()
                    if o.final_outcome == Outcome.OFFER
                ),
                "avg_salary": avg_salary,
                "acceptance_rate": f"{metrics.acceptance_rate:.1%}",
            },
        }

    def get_company_stats(
        self,
        min_applications: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Get statistics by company.

        Args:
            min_applications: Minimum applications to include

        Returns:
            List of company statistics
        """
        # Group by company
        company_apps: Dict[str, List[ApplicationOutcome]] = {}
        for outcome in self._outcomes.values():
            company = outcome.company
            if company not in company_apps:
                company_apps[company] = []
            company_apps[company].append(outcome)

        # Calculate stats
        stats = []
        for company, apps in company_apps.items():
            if len(apps) < min_applications:
                continue

            offers = sum(1 for a in apps if a.final_outcome == Outcome.OFFER)
            interviews = sum(1 for a in apps if a.has_interview)

            stats.append(
                {
                    "company": company,
                    "total_applications": len(apps),
                    "interview_count": interviews,
                    "offer_count": offers,
                    "interview_rate": interviews / len(apps) if apps else 0,
                    "offer_rate": offers / len(apps) if apps else 0,
                }
            )

        # Sort by offer rate
        stats.sort(key=lambda x: x["offer_rate"], reverse=True)

        return stats

    def get_streak_metrics(self) -> Dict[str, Any]:
        """
        Get current streak metrics.

        Returns:
            Streak information
        """
        # Sort by date
        sorted_outcomes = sorted(
            self._outcomes.values(),
            key=lambda x: x.applied_date,
            reverse=True,
        )

        current_rejection_streak = 0
        current_interview_streak = 0
        days_since_last_offer = None

        last_offer_date = None
        for outcome in sorted_outcomes:
            if outcome.final_outcome == Outcome.OFFER:
                last_offer_date = outcome.applied_date
                break

        if last_offer_date:
            days_since_last_offer = (datetime.now() - last_offer_date).days

        for outcome in sorted_outcomes:
            if outcome.final_outcome == Outcome.REJECT:
                current_rejection_streak += 1
            else:
                break

        for outcome in sorted_outcomes:
            if outcome.has_interview:
                current_interview_streak += 1
            else:
                break

        return {
            "current_rejection_streak": current_rejection_streak,
            "current_interview_streak": current_interview_streak,
            "days_since_last_offer": days_since_last_offer,
        }

    def _load_custom_statuses(self) -> None:
        """Load custom statuses from storage."""
        for filepath in self.custom_statuses_dir.glob("*.json"):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                status = CustomApplicationStatus(
                    status_id=data["status_id"],
                    name=data["name"],
                    description=data["description"],
                    color=data.get("color", "#6B7280"),
                    icon=data.get("icon"),
                    is_active=data.get("is_active", True),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    user_id=data.get("user_id"),
                    metadata=data.get("metadata", {}),
                )
                self._custom_statuses[status.status_id] = status
            except Exception as e:
                self.logger.warning(f"Failed to load custom status: {e}")

    def _save_custom_status(self, status: CustomApplicationStatus) -> None:
        """Save custom status to file."""
        filepath = self.custom_statuses_dir / f"{status.status_id}.json"
        data = {
            "status_id": status.status_id,
            "name": status.name,
            "description": status.description,
            "color": status.color,
            "icon": status.icon,
            "is_active": status.is_active,
            "created_at": status.created_at.isoformat(),
            "user_id": status.user_id,
            "metadata": status.metadata,
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def create_custom_status(
        self,
        name: str,
        description: str,
        color: str = "#6B7280",
        icon: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> CustomApplicationStatus:
        """
        Create a new custom status.

        Args:
            name: Status name
            description: Status description
            color: Hex color code
            icon: Optional icon name
            user_id: Optional user ID for multi-user support

        Returns:
            CustomApplicationStatus object
        """
        import hashlib

        status_id = f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(name.encode()).hexdigest()[:8]}"

        status = CustomApplicationStatus(
            status_id=status_id,
            name=name,
            description=description,
            color=color,
            icon=icon,
            user_id=user_id,
        )

        self._custom_statuses[status_id] = status
        self._save_custom_status(status)

        self.logger.info(f"Created custom status: {status_id} - {name}")

        return status

    def get_custom_statuses(
        self, active_only: bool = True
    ) -> List[CustomApplicationStatus]:
        """
        Get all custom statuses.

        Args:
            active_only: Only return active statuses

        Returns:
            List of CustomApplicationStatus objects
        """
        statuses = list(self._custom_statuses.values())
        if active_only:
            statuses = [s for s in statuses if s.is_active]
        return statuses

    def delete_custom_status(self, status_id: str, hard_delete: bool = False) -> bool:
        """
        Delete or deactivate a custom status.

        Args:
            status_id: Status ID to delete
            hard_delete: If True, permanently delete; if False, soft delete (set is_active=False)

        Returns:
            True if successful
        """
        status = self._custom_statuses.get(status_id)
        if not status:
            return False

        if hard_delete:
            # Remove from cache and delete file
            del self._custom_statuses[status_id]
            filepath = self.custom_statuses_dir / f"{status_id}.json"
            if filepath.exists():
                filepath.remove()
            self.logger.info(f"Hard deleted custom status: {status_id}")
        else:
            # Soft delete
            status.is_active = False
            self._save_custom_status(status)
            self.logger.info(f"Soft deleted custom status: {status_id}")

        return True

    def save_job(
        self,
        job_id: str,
        job_title: str,
        company: str,
        source_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ApplicationOutcome:
        """
        Save/bookmark a job for later.

        Args:
            job_id: Unique job identifier
            job_title: Job title
            company: Company name
            source_url: Optional source URL
            metadata: Additional metadata

        Returns:
            ApplicationOutcome object
        """
        outcome = ApplicationOutcome(
            application_id=job_id,
            job_title=job_title,
            company=company,
            applied_date=datetime.now(),
            current_status=ApplicationStatus.SAVED_BOOKMARKED,
            final_outcome=None,
            metadata=metadata or {},
            is_bookmarked=True,
            bookmark_date=datetime.now(),
        )

        if source_url:
            outcome.metadata["source_url"] = source_url

        self._outcomes[job_id] = outcome
        self._save_outcome(outcome)

        self.logger.info(f"Saved job: {job_id} - {job_title} at {company}")

        return outcome

    def mark_not_interested(
        self,
        job_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Mark a job as not interested (hides from results).

        Args:
            job_id: Job ID
            reason: Optional reason for not being interested

        Returns:
            True if successful
        """
        outcome = self._outcomes.get(job_id)
        if not outcome:
            return False

        outcome.current_status = ApplicationStatus.NOT_INTERESTED
        outcome.is_hidden = True
        outcome.hidden_date = datetime.now()

        if reason:
            outcome.timeline_notes.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "note": f"Marked not interested: {reason}",
                }
            )

        self._save_outcome(outcome)

        self.logger.info(f"Marked job as not interested: {job_id}")

        return True

    def track_external_application(
        self,
        job_id: str,
        job_title: str,
        company: str,
        application_date: Optional[datetime] = None,
        application_method: str = "manual",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ApplicationOutcome:
        """
        Track an application made outside the system.

        Args:
            job_id: Unique job identifier
            job_title: Job title
            company: Company name
            application_date: When application was made
            application_method: How application was made (manual, referral, etc.)
            metadata: Additional metadata

        Returns:
            ApplicationOutcome object
        """
        outcome = ApplicationOutcome(
            application_id=job_id,
            job_title=job_title,
            company=company,
            applied_date=application_date or datetime.now(),
            current_status=ApplicationStatus.APPLIED_ELSEWHERE,
            final_outcome=Outcome.PENDING,
            metadata=metadata or {},
            external_application_details={
                "application_method": application_method,
                "tracked_at": datetime.now().isoformat(),
            },
        )

        self._outcomes[job_id] = outcome
        self._save_outcome(outcome)

        self.logger.info(
            f"Tracked external application: {job_id} - {job_title} at {company}"
        )

        return outcome

    def set_custom_status(
        self,
        job_id: str,
        custom_status_id: str,
        note: Optional[str] = None,
    ) -> bool:
        """
        Set a custom status for an application.

        Args:
            job_id: Job ID
            custom_status_id: Custom status ID
            note: Optional note

        Returns:
            True if successful
        """
        outcome = self._outcomes.get(job_id)
        if not outcome:
            return False

        if custom_status_id not in self._custom_statuses:
            self.logger.warning(f"Custom status not found: {custom_status_id}")
            return False

        outcome.current_status = ApplicationStatus.CUSTOM
        outcome.custom_status_id = custom_status_id

        if note:
            outcome.timeline_notes.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "note": note,
                }
            )

        self._save_outcome(outcome)

        self.logger.info(f"Set custom status on {job_id}: {custom_status_id}")

        return True

    def get_bookmarked_jobs(self) -> List[ApplicationOutcome]:
        """
        Get all bookmarked/saved jobs.

        Returns:
            List of ApplicationOutcome objects
        """
        return [o for o in self._outcomes.values() if o.is_bookmarked]

    def get_hidden_jobs(self) -> List[ApplicationOutcome]:
        """
        Get all hidden (not interested) jobs.

        Returns:
            List of ApplicationOutcome objects
        """
        return [o for o in self._outcomes.values() if o.is_hidden]

    def get_external_applications(self) -> List[ApplicationOutcome]:
        """
        Get all external applications.

        Returns:
            List of ApplicationOutcome objects
        """
        return [
            o
            for o in self._outcomes.values()
            if o.current_status == ApplicationStatus.APPLIED_ELSEWHERE
        ]

    def unsave_job(self, job_id: str) -> bool:
        """
        Unsave/remove bookmark from a job.

        Args:
            job_id: Job ID

        Returns:
            True if successful
        """
        outcome = self._outcomes.get(job_id)
        if not outcome:
            return False

        outcome.is_bookmarked = False
        outcome.bookmark_date = None
        if outcome.current_status == ApplicationStatus.SAVED_BOOKMARKED:
            outcome.current_status = ApplicationStatus.APPLIED

        self._save_outcome(outcome)

        self.logger.info(f"Unsaved job: {job_id}")

        return True

    def unhide_job(self, job_id: str) -> bool:
        """
        Unhide a job that was marked as not interested.

        Args:
            job_id: Job ID

        Returns:
            True if successful
        """
        outcome = self._outcomes.get(job_id)
        if not outcome:
            return False

        outcome.is_hidden = False
        outcome.hidden_date = None
        if outcome.current_status == ApplicationStatus.NOT_INTERESTED:
            outcome.current_status = ApplicationStatus.APPLIED

        self._save_outcome(outcome)

        self.logger.info(f"Unhid job: {job_id}")

        return True

    def _load_cache(self) -> None:
        """Load outcomes from storage into cache."""
        for filepath in self.storage_dir.glob("*.json"):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)

                outcome = self._deserialize_outcome(data)
                if outcome:
                    self._outcomes[outcome.application_id] = outcome

            except Exception as e:
                self.logger.warning(f"Failed to load outcome from {filepath}: {str(e)}")
                continue

    def _save_outcome(self, outcome: ApplicationOutcome) -> None:
        """Save outcome to file."""
        filepath = self.storage_dir / f"{outcome.application_id}.json"

        data = self._serialize_outcome(outcome)

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _serialize_outcome(self, outcome: ApplicationOutcome) -> Dict[str, Any]:
        """Serialize outcome to dict."""
        return {
            "application_id": outcome.application_id,
            "job_title": outcome.job_title,
            "company": outcome.company,
            "applied_date": outcome.applied_date.isoformat(),
            "current_status": outcome.current_status.value,
            "final_outcome": (
                outcome.final_outcome.value if outcome.final_outcome else None
            ),
            "interviews": [
                {
                    "stage": i.stage.value,
                    "scheduled_date": (
                        i.scheduled_date.isoformat() if i.scheduled_date else None
                    ),
                    "completed_date": (
                        i.completed_date.isoformat() if i.completed_date else None
                    ),
                    "feedback": i.feedback,
                    "outcome": i.outcome,
                }
                for i in outcome.interviews
            ],
            "offer": {
                "salary_min": outcome.offer.salary_min if outcome.offer else None,
                "salary_max": outcome.offer.salary_max if outcome.offer else None,
                "salary_period": (
                    outcome.offer.salary_period if outcome.offer else "annual"
                ),
                "bonus": outcome.offer.bonus if outcome.offer else None,
                "equity": outcome.offer.equity if outcome.offer else None,
                "benefits": outcome.offer.benefits if outcome.offer else [],
                "notes": outcome.offer.notes if outcome.offer else "",
            },
            "timeline_notes": outcome.timeline_notes,
            "metadata": outcome.metadata,
            "custom_status_id": outcome.custom_status_id,
            "external_application_details": outcome.external_application_details,
            "is_bookmarked": outcome.is_bookmarked,
            "is_hidden": outcome.is_hidden,
            "bookmark_date": (
                outcome.bookmark_date.isoformat() if outcome.bookmark_date else None
            ),
            "hidden_date": (
                outcome.hidden_date.isoformat() if outcome.hidden_date else None
            ),
        }

    def _deserialize_outcome(
        self, data: Dict[str, Any]
    ) -> Optional[ApplicationOutcome]:
        """Deserialize dict to outcome."""
        try:
            interviews = []
            for i_data in data.get("interviews", []):
                interviews.append(
                    InterviewEvent(
                        stage=InterviewStage(i_data["stage"]),
                        scheduled_date=(
                            datetime.fromisoformat(i_data["scheduled_date"])
                            if i_data.get("scheduled_date")
                            else None
                        ),
                        completed_date=(
                            datetime.fromisoformat(i_data["completed_date"])
                            if i_data.get("completed_date")
                            else None
                        ),
                        feedback=i_data.get("feedback"),
                        outcome=i_data.get("outcome"),
                    )
                )

            offer_data = data.get("offer", {})
            offer = (
                OfferDetails(
                    salary_min=offer_data.get("salary_min"),
                    salary_max=offer_data.get("salary_max"),
                    salary_period=offer_data.get("salary_period", "annual"),
                    bonus=offer_data.get("bonus"),
                    equity=offer_data.get("equity"),
                    benefits=offer_data.get("benefits", []),
                    notes=offer_data.get("notes", ""),
                )
                if offer_data
                else None
            )

            return ApplicationOutcome(
                application_id=data["application_id"],
                job_title=data["job_title"],
                company=data["company"],
                applied_date=datetime.fromisoformat(data["applied_date"]),
                current_status=ApplicationStatus(data["current_status"]),
                final_outcome=(
                    Outcome(data["final_outcome"])
                    if data.get("final_outcome")
                    else None
                ),
                interviews=interviews,
                offer=offer,
                timeline_notes=data.get("timeline_notes", []),
                metadata=data.get("metadata", {}),
                custom_status_id=data.get("custom_status_id"),
                external_application_details=data.get("external_application_details"),
                is_bookmarked=data.get("is_bookmarked", False),
                is_hidden=data.get("is_hidden", False),
                bookmark_date=(
                    datetime.fromisoformat(data["bookmark_date"])
                    if data.get("bookmark_date")
                    else None
                ),
                hidden_date=(
                    datetime.fromisoformat(data["hidden_date"])
                    if data.get("hidden_date")
                    else None
                ),
            )

        except Exception as e:
            self.logger.error(f"Failed to deserialize outcome: {str(e)}")
            return None
