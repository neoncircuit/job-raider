"""
Job Raider - Outcome Tracker

This module tracks job application outcomes from submission
through to offer, providing conversion metrics and insights.

Author: Job Raider
Date: 2026-04-21

The class joins mixin modules: ``outcome_storage``, ``outcome_analytics``,
``outcome_lists``, and ``outcome_external``. The models are in
``outcome_models`` and the pure functions in ``outcome_helpers``. This
module re-exports their public names, so existing imports do not change.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.logger import Components, get_logger
from .outcome_analytics import OutcomeAnalytics
from .outcome_external import OutcomeExternal
from .outcome_helpers import (
    INBOUND_APPLICATION_METHOD,
    _usable_match_label,
    application_filename_stem,
    normalize_match_label,
    normalize_match_url,
)
from .outcome_lists import OutcomeLists
from .outcome_models import (
    ApplicationOutcome,
    ApplicationStatus,
    ConversionMetrics,
    CustomApplicationStatus,
    InterviewEvent,
    InterviewStage,
    OfferDetails,
    Outcome,
)

__all__ = [
    "INBOUND_APPLICATION_METHOD",
    "ApplicationOutcome",
    "ApplicationStatus",
    "ConversionMetrics",
    "CustomApplicationStatus",
    "InterviewEvent",
    "InterviewStage",
    "OfferDetails",
    "Outcome",
    "OutcomeTracker",
    "_usable_match_label",
    "application_filename_stem",
    "normalize_match_label",
    "normalize_match_url",
]


class OutcomeTracker(OutcomeAnalytics, OutcomeLists, OutcomeExternal):
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
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update application status.

        Reloads from disk first so a peer API worker can update a record
        that another worker created.

        Args:
            application_id: Application ID
            status: New status
            note: Optional note about the change
            metadata: Optional metadata keys to merge (for example a JD)

        Returns:
            True if update successful
        """
        self._reload_cache()
        outcome = self._outcomes.get(application_id)
        if not outcome:
            self.logger.warning(f"Application not found: {application_id}")
            return False

        if outcome.current_status != status:
            outcome.status_history.append(outcome.current_status.value)
            outcome.current_status = status
            self._sync_final_outcome(outcome)

        if metadata:
            outcome.metadata.update(metadata)

        if note:
            outcome.timeline_notes.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "note": note,
                }
            )

        self._save_outcome(outcome)

        self.logger.info(f"Updated application {application_id} to {status.value}")

        return True

    def revert_status(self, application_id: str) -> Optional[ApplicationStatus]:
        """
        Restore the previous application status from stored history.

        Reloads from disk first so a peer API worker sees the latest stack.
        Same-status metadata updates do not write history, so a job-description
        paste cannot invent a revert target.

        Args:
            application_id: Application ID

        Returns:
            Restored status, or None when the row is missing or has no history
        """
        self._reload_cache()
        outcome = self._outcomes.get(application_id)
        if not outcome or not outcome.status_history:
            self.logger.warning(
                f"Cannot revert application {application_id}: no status history"
            )
            return None

        previous = outcome.status_history.pop()
        try:
            outcome.current_status = ApplicationStatus(previous)
        except ValueError:
            outcome.status_history.append(previous)
            self.logger.warning(
                f"Cannot revert application {application_id}: invalid status {previous}"
            )
            return None

        self._sync_final_outcome(outcome)
        self._save_outcome(outcome)

        self.logger.info(
            f"Reverted application {application_id} to {outcome.current_status.value}"
        )
        return outcome.current_status

    def _sync_final_outcome(self, outcome: ApplicationOutcome) -> None:
        """
        Keep final_outcome aligned with the current status.

        Terminal statuses set a matching outcome. All other statuses return
        to pending so a revert away from rejected or withdrawn is usable.

        Args:
            outcome: Application record to update
        """
        status = outcome.current_status
        if status == ApplicationStatus.OFFER_ACCEPTED:
            outcome.final_outcome = Outcome.OFFER
        elif status == ApplicationStatus.REJECTED:
            outcome.final_outcome = Outcome.REJECT
        elif status == ApplicationStatus.WITHDRAWN:
            outcome.final_outcome = Outcome.WITHDRAW
        else:
            outcome.final_outcome = Outcome.PENDING

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

    def get_all_applications(
        self,
        status: Optional[ApplicationStatus] = None,
        company: Optional[str] = None,
        days: Optional[int] = None,
    ) -> List[ApplicationOutcome]:
        """
        Get applications with optional filtering.

        Reloads from disk first so multi-worker API processes see peer writes.

        Args:
            status: Filter by status
            company: Filter by company
            days: Filter by days since application

        Returns:
            List of ApplicationOutcome objects
        """
        self._reload_cache()
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
