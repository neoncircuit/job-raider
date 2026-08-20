"""
Job Raider - Unified Applied Guard

Cross-source guard that blocks re-applying to the same real listing
across boards (LinkedIn, MCF, JobStreet, JSearch, etc.).

Match order mirrors ``find_matching_application``: job id, listing URL,
then company+title when URL identity is missing on either side.

Author: Job Raider
Date: 2026-08-18
"""

from __future__ import annotations

from typing import List, Optional, Set, Tuple

from ..metrics.outcome_tracker import (
    ApplicationStatus,
    OutcomeTracker,
    _usable_match_label,
    normalize_match_label,
    normalize_match_url,
)
from ..models.job_listing import JobListing
from ..utils.logger import Components, get_logger
from .applied_tracker import AppliedJobsTracker

# Bookmark / hide only — not a real application track.
_EXCLUDED_STATUSES = frozenset(
    {
        ApplicationStatus.SAVED_BOOKMARKED,
        ApplicationStatus.NOT_INTERESTED,
    }
)

CompanyTitleKey = Tuple[str, str]


class AppliedGuard:
    """
    Cross-source guard against re-applying to the same listing.

    Indexes outcome rows (excluding bookmark/hide) and AppliedJobsTracker
    entries by job id, listing URL, and company+title when URL identity
    is missing.
    """

    def __init__(
        self,
        outcome_tracker: Optional[OutcomeTracker] = None,
        applied_tracker: Optional[AppliedJobsTracker] = None,
    ) -> None:
        """
        Initialize the guard and build indexes from disk.

        Args:
            outcome_tracker: Applications store; defaults to OutcomeTracker().
            applied_tracker: LinkedIn-oriented applied IDs; defaults to
                AppliedJobsTracker().
        """
        self.logger = get_logger(Components.SUBMISSION)
        self._outcome_tracker = outcome_tracker or OutcomeTracker()
        self._applied_tracker = applied_tracker or AppliedJobsTracker()
        self._job_ids: Set[str] = set()
        self._urls: Set[str] = set()
        self._company_title_no_url: Set[CompanyTitleKey] = set()
        self._company_title_with_url: Set[CompanyTitleKey] = set()
        self.refresh()

    def refresh(self) -> None:
        """
        Rebuild indexes from outcome storage and AppliedJobsTracker.
        """
        self._job_ids = set()
        self._urls = set()
        self._company_title_no_url = set()
        self._company_title_with_url = set()

        self._outcome_tracker._reload_cache()
        for outcome in self._outcome_tracker._outcomes.values():
            if outcome.current_status in _EXCLUDED_STATUSES:
                continue
            self._index_record(
                job_id=outcome.application_id,
                title=outcome.job_title or "",
                company=outcome.company or "",
                source_url=(outcome.metadata or {}).get("source_url"),
            )

        for job_id in self._applied_tracker.get_all_applied_ids():
            data = self._applied_tracker.get_applied_data(job_id) or {}
            self._index_record(
                job_id=job_id,
                title=str(data.get("title") or ""),
                company=str(data.get("company") or ""),
                source_url=None,
            )

    def _index_record(
        self,
        job_id: str,
        title: str,
        company: str,
        source_url: Optional[str],
    ) -> None:
        """
        Add one applied record to the in-memory indexes.

        Args:
            job_id: Application or listing id.
            title: Job title.
            company: Company name.
            source_url: Optional listing URL from metadata.
        """
        if job_id:
            self._job_ids.add(job_id)

        existing_url = normalize_match_url(
            source_url if isinstance(source_url, str) else None
        )
        if existing_url:
            self._urls.add(existing_url)

        if not _usable_match_label(company) or not _usable_match_label(title):
            return
        key: CompanyTitleKey = (
            normalize_match_label(company),
            normalize_match_label(title),
        )
        if existing_url:
            self._company_title_with_url.add(key)
        else:
            self._company_title_no_url.add(key)

    def is_applied(
        self,
        job_id: str,
        title: str = "",
        company: str = "",
        source_url: Optional[str] = None,
    ) -> bool:
        """
        Return whether the listing matches an already-applied record.

        Match order: job id, cleaned listing URL, then company+title when
        URL identity is missing on either side (same rules as
        ``find_matching_application``).

        Args:
            job_id: Incoming job id.
            title: Incoming job title.
            company: Incoming company name.
            source_url: Optional listing URL.

        Returns:
            True when the user should not apply again.
        """
        if job_id and job_id in self._job_ids:
            return True

        incoming_url = normalize_match_url(source_url)
        if incoming_url and incoming_url in self._urls:
            return True

        if not _usable_match_label(company) or not _usable_match_label(title):
            return False
        key: CompanyTitleKey = (
            normalize_match_label(company),
            normalize_match_label(title),
        )
        # Both sides have URLs: never match on company+title alone
        # (different postings at the same company stay separate).
        if incoming_url:
            return key in self._company_title_no_url
        return key in self._company_title_no_url or key in self._company_title_with_url

    def _listing_source_url(self, listing: JobListing) -> Optional[str]:
        """
        Extract a string source URL from a listing.

        Args:
            listing: Job listing.

        Returns:
            URL string, or None.
        """
        if not listing.source_url:
            return None
        return str(listing.source_url)

    def annotate_listings(self, listings: List[JobListing]) -> List[JobListing]:
        """
        Set ``already_applied=True`` on matches via model_copy.

        Args:
            listings: Incoming job listings.

        Returns:
            New list; matched rows are copies with already_applied set.
        """
        result: List[JobListing] = []
        for listing in listings:
            if listing.already_applied:
                result.append(listing)
                continue
            source_url = self._listing_source_url(listing)
            if self.is_applied(
                job_id=listing.job_id or "",
                title=listing.title or "",
                company=listing.company or "",
                source_url=source_url,
            ):
                result.append(listing.model_copy(update={"already_applied": True}))
            else:
                result.append(listing)
        return result

    def filter_unapplied(
        self, listings: List[JobListing]
    ) -> tuple[list[JobListing], int]:
        """
        Keep listings that are not already applied.

        Args:
            listings: Job listings (preferably after annotate_listings).

        Returns:
            Tuple of (kept listings, removed_count).
        """
        kept: List[JobListing] = []
        removed = 0
        for listing in listings:
            source_url = self._listing_source_url(listing)
            if listing.already_applied or self.is_applied(
                job_id=listing.job_id or "",
                title=listing.title or "",
                company=listing.company or "",
                source_url=source_url,
            ):
                removed += 1
                continue
            kept.append(listing)
        return kept, removed

    def annotate_job_dicts(self, jobs: List[dict]) -> List[dict]:
        """
        Set already_applied / apply_method on serialized Jobs API dicts.

        Args:
            jobs: Serialized job dicts (shortlist or search shape).

        Returns:
            Same list object with matching rows updated in place.
        """
        for job in jobs:
            if not isinstance(job, dict):
                continue
            if job.get("already_applied"):
                job["apply_method"] = "already_applied"
                continue
            source_url = job.get("source_url") or job.get("url")
            url_str = source_url if isinstance(source_url, str) else None
            if self.is_applied(
                job_id=str(job.get("job_id") or ""),
                title=str(job.get("title") or ""),
                company=str(job.get("company") or ""),
                source_url=url_str,
            ):
                job["already_applied"] = True
                job["apply_method"] = "already_applied"
        return jobs
