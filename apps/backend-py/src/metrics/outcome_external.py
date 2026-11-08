"""
Job Raider - External Applications

This module defines the tracking of applications made outside Job Raider,
and the match of a new record to an existing application.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from .outcome_helpers import (
    _GENERIC_APPLICATION_METHODS,
    _KEEP_STATUS_ON_RETRACK,
    _MIN_PREP_DESCRIPTION_CHARS,
    INBOUND_APPLICATION_METHOD,
    _usable_match_label,
    normalize_match_label,
    normalize_match_url,
)
from .outcome_models import (
    ApplicationOutcome,
    ApplicationStatus,
    Outcome,
)
from .outcome_storage import OutcomeStorage


class OutcomeExternal(OutcomeStorage):
    """
    Track applications made outside Job Raider.
    """

    def update_status(
        self,
        application_id: str,
        status: ApplicationStatus,
        note: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update application status. ``OutcomeTracker`` implements this.

        Args:
            application_id: Application ID.
            status: New status.
            note: Optional note for the status history.
            metadata: Optional metadata for the status history.

        Returns:
            True if the application exists and was updated.

        Raises:
            NotImplementedError: Always. The subclass gives the real method.
        """
        raise NotImplementedError

    def find_matching_application(
        self,
        job_id: str,
        job_title: str,
        company: str,
        source_url: Optional[str] = None,
    ) -> Optional[ApplicationOutcome]:
        """
        Find an existing application that is the same listing.

        Match order: real job id, cleaned listing URL, then company+title
        when a URL identity is missing.

        Args:
            job_id: Incoming job / application id.
            job_title: Incoming job title.
            company: Incoming company name.
            source_url: Optional cleaned listing URL.

        Returns:
            Matching ApplicationOutcome, or None.
        """
        self._reload_cache()
        if job_id:
            by_id = self._outcomes.get(job_id)
            if by_id is not None:
                return by_id

        incoming_url = normalize_match_url(source_url)
        if incoming_url:
            for outcome in self._outcomes.values():
                existing_url = normalize_match_url(
                    (outcome.metadata or {}).get("source_url")
                )
                if existing_url and existing_url == incoming_url:
                    return outcome

        if not _usable_match_label(company) or not _usable_match_label(job_title):
            return None
        company_key = normalize_match_label(company)
        title_key = normalize_match_label(job_title)
        for outcome in self._outcomes.values():
            if normalize_match_label(outcome.company) != company_key:
                continue
            if normalize_match_label(outcome.job_title) != title_key:
                continue
            existing_url = normalize_match_url(
                (outcome.metadata or {}).get("source_url")
            )
            # Company+title is the fallback when URL identity is missing.
            # If the incoming row has a URL, only merge into a row that has none
            # so two different listing URLs at the same company stay separate.
            if incoming_url and existing_url:
                continue
            return outcome
        return None

    def _merge_track_metadata(
        self,
        existing: ApplicationOutcome,
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """
        Attach missing job-description and listing URL onto an existing row.

        Args:
            existing: Stored application to update.
            metadata: Incoming metadata mapping.
        """
        if not metadata:
            return
        for key, value in metadata.items():
            if key == "description":
                current = existing.metadata.get("description")
                has_prep = (
                    isinstance(current, str)
                    and len(current.strip()) >= _MIN_PREP_DESCRIPTION_CHARS
                )
                if has_prep:
                    continue
                if isinstance(value, str) and value.strip():
                    existing.metadata["description"] = value
                continue
            if key == "source_url":
                current_url = existing.metadata.get("source_url")
                if isinstance(current_url, str) and current_url.strip():
                    continue
                if value:
                    existing.metadata["source_url"] = value
                continue
            existing.metadata[key] = value

    def _resolve_track_method(
        self,
        inbound: bool,
        application_method: str,
        existing: Optional[ApplicationOutcome],
    ) -> str:
        """
        Choose the application_method label for a track or merge.

        Inbound-only rows use ``inbound/recruiter``. Rows that already recorded
        an apply keep that method so inbound merge does not erase it.

        Args:
            inbound: True when the user was approached without applying.
            application_method: Method from the request.
            existing: Matching stored row, if any.

        Returns:
            Method string to persist.
        """
        requested = (application_method or "").strip() or "manual"
        existing_method = ""
        if existing and existing.external_application_details:
            existing_method = str(
                existing.external_application_details.get("application_method") or ""
            ).strip()
        applied_statuses = {
            ApplicationStatus.APPLIED,
            ApplicationStatus.APPLIED_ELSEWHERE,
        }
        if (
            existing
            and existing.current_status in applied_statuses
            and existing_method
            and existing_method.lower() != INBOUND_APPLICATION_METHOD
        ):
            return existing_method
        if inbound and requested.lower() in _GENERIC_APPLICATION_METHODS:
            return INBOUND_APPLICATION_METHOD
        return requested

    def track_external_application(
        self,
        job_id: str,
        job_title: str,
        company: str,
        application_date: Optional[datetime] = None,
        application_method: str = "manual",
        metadata: Optional[Dict[str, Any]] = None,
        inbound: bool = False,
        interview_invite: bool = False,
    ) -> ApplicationOutcome:
        """
        Track an application made outside the system.

        Duplicate listings (same real job id, listing URL, or company+title)
        merge into the existing row. Inbound recruiter approaches land on
        ``screening_scheduled`` and do not write ``applied_elsewhere`` when
        the user never applied.

        Args:
            job_id: Unique job identifier
            job_title: Job title
            company: Company name
            application_date: When application was made
            application_method: How application was made (manual, referral, etc.)
            metadata: Additional metadata
            inbound: True when a recruiter approached with no prior apply
            interview_invite: True when the user already has an interview invite

        Returns:
            ApplicationOutcome object (existing row when a duplicate is merged)
        """
        # Pick up any record saved by another API worker (e.g. prior Save).
        self._reload_cache()
        source_url = None
        if metadata:
            raw_url = metadata.get("source_url")
            source_url = raw_url if isinstance(raw_url, str) else None
        existing = self.find_matching_application(
            job_id=job_id,
            job_title=job_title,
            company=company,
            source_url=source_url,
        )
        advance_to_interview = inbound or interview_invite
        method = self._resolve_track_method(inbound, application_method, existing)
        details = {
            "application_method": method,
            "tracked_at": datetime.now().isoformat(),
        }
        if inbound:
            details["origin"] = "inbound"

        if existing:
            existing.job_title = job_title or existing.job_title
            existing.company = company or existing.company
            existing.applied_date = application_date or existing.applied_date
            self._merge_track_metadata(existing, metadata)
            if existing.external_application_details:
                existing.external_application_details["tracked_at"] = details[
                    "tracked_at"
                ]
                existing.external_application_details["application_method"] = method
                if method == INBOUND_APPLICATION_METHOD:
                    existing.external_application_details["origin"] = "inbound"
            else:
                existing.external_application_details = details
            if advance_to_interview and existing.is_hidden:
                existing.is_hidden = False
                existing.hidden_date = None
            # Keep interview and outcome stages. Re-track must not reset them.
            pre_apply = {
                ApplicationStatus.SAVED_BOOKMARKED,
                ApplicationStatus.NOT_INTERESTED,
                ApplicationStatus.APPLIED_ELSEWHERE,
            }
            if (
                not advance_to_interview
                and existing.current_status in pre_apply
                and existing.current_status not in _KEEP_STATUS_ON_RETRACK
            ):
                existing.current_status = ApplicationStatus.APPLIED_ELSEWHERE
            self._save_outcome(existing)
            if (
                advance_to_interview
                and existing.current_status not in _KEEP_STATUS_ON_RETRACK
            ):
                self.update_status(
                    existing.application_id,
                    ApplicationStatus.SCREENING_SCHEDULED,
                )
                existing = self.get_application(existing.application_id) or existing
            self.logger.info(
                "Updated external application: "
                f"{existing.application_id} - {job_title} at {company}"
            )
            return existing

        initial_status = (
            ApplicationStatus.SCREENING_SCHEDULED
            if inbound
            else ApplicationStatus.APPLIED_ELSEWHERE
        )
        outcome = ApplicationOutcome(
            application_id=job_id,
            job_title=job_title,
            company=company,
            applied_date=application_date or datetime.now(),
            current_status=initial_status,
            final_outcome=Outcome.PENDING,
            metadata=metadata or {},
            external_application_details=details,
        )

        self._outcomes[job_id] = outcome
        self._save_outcome(outcome)

        if (
            interview_invite
            and not inbound
            and outcome.current_status != ApplicationStatus.SCREENING_SCHEDULED
        ):
            self.update_status(job_id, ApplicationStatus.SCREENING_SCHEDULED)
            outcome = self.get_application(job_id) or outcome

        self.logger.info(
            f"Tracked external application: {job_id} - {job_title} at {company}"
        )

        return outcome
