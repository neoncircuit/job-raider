"""
Job Raider - Outcome Lists

This module defines custom statuses, saved jobs, hidden jobs, and the
removal of applications.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from .outcome_helpers import application_filename_stem
from .outcome_models import (
    ApplicationOutcome,
    ApplicationStatus,
    CustomApplicationStatus,
)
from .outcome_storage import OutcomeStorage


class OutcomeLists(OutcomeStorage):
    """
    Custom statuses, saved jobs, hidden jobs, and removal.
    """

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
                filepath.unlink()
            self.logger.info(f"Hard deleted custom status: {status_id}")
        else:
            # Soft delete
            status.is_active = False
            self._save_custom_status(status)
            self.logger.info(f"Soft deleted custom status: {status_id}")

        return True

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
        self._reload_cache()
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
        self._reload_cache()
        existing = self._outcomes.get(job_id)
        if existing and existing.is_bookmarked:
            # Refresh title/company/url but keep bookmark flags.
            existing.job_title = job_title or existing.job_title
            existing.company = company or existing.company
            if source_url:
                existing.metadata["source_url"] = source_url
            if metadata:
                existing.metadata.update(metadata)
            existing.current_status = ApplicationStatus.SAVED_BOOKMARKED
            existing.is_bookmarked = True
            existing.bookmark_date = existing.bookmark_date or datetime.now()
            self._save_outcome(existing)
            self.logger.info(f"Updated saved job: {job_id} - {job_title} at {company}")
            return existing

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

    def unsave_job(self, job_id: str) -> bool:
        """
        Unsave/remove bookmark from a job.

        Args:
            job_id: Job ID

        Returns:
            True if successful
        """
        self._reload_cache()
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
        self._reload_cache()
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

    def unhide_job(self, job_id: str) -> bool:
        """
        Unhide a job that was marked as not interested.

        Args:
            job_id: Job ID

        Returns:
            True if successful
        """
        self._reload_cache()
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

    def get_bookmarked_jobs(self) -> List[ApplicationOutcome]:
        """
        Get all bookmarked/saved jobs.

        Returns:
            List of ApplicationOutcome objects
        """
        self._reload_cache()
        return [o for o in self._outcomes.values() if o.is_bookmarked]

    def get_hidden_jobs(self) -> List[ApplicationOutcome]:
        """
        Get all hidden (not interested) jobs.

        Returns:
            List of ApplicationOutcome objects
        """
        self._reload_cache()
        return [o for o in self._outcomes.values() if o.is_hidden]

    def get_external_applications(self) -> List[ApplicationOutcome]:
        """
        Get all external applications.

        Returns:
            List of ApplicationOutcome objects
        """
        self._reload_cache()
        return [
            o
            for o in self._outcomes.values()
            if o.current_status == ApplicationStatus.APPLIED_ELSEWHERE
        ]

    def delete_application(self, application_id: str) -> bool:
        """
        Permanently remove an application record from cache and disk.

        Uses the same filename stem as save, so hashed ``id_*.json`` files
        are removed when the logical job id is passed.

        Args:
            application_id: Logical job / application id.

        Returns:
            True if a cache entry or file was removed.
        """
        self._reload_cache()
        existed_in_cache = application_id in self._outcomes
        if existed_in_cache:
            del self._outcomes[application_id]

        filepath = (
            self.storage_dir / f"{application_filename_stem(application_id)}.json"
        )
        existed_on_disk = filepath.exists()
        if existed_on_disk:
            filepath.unlink()

        if existed_in_cache or existed_on_disk:
            self.logger.info(f"Deleted application: {application_id}")
            return True
        return False
