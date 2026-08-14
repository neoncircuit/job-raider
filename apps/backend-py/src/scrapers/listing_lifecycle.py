"""
Job Raider - Listing lifecycle helpers

Compute active/expired status from last-seen timestamps and application
deadlines. Status is derived at read time so stored JSON does not need a
stale status field.

Author: Job Raider
Date: 2026-08-13
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from ..models.job_listing import JobListing

DEFAULT_MAX_AGE_DAYS = 30


class ListingStatus(str, Enum):
    """Lifecycle status for a stored job listing."""

    ACTIVE = "active"
    EXPIRED = "expired"


def as_naive_datetime(value: datetime) -> datetime:
    """
    Return a timezone-naive datetime for age comparisons.

    Args:
        value: Aware or naive datetime.

    Returns:
        The same instant with tzinfo removed.
    """
    if value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def parse_optional_datetime(value: Any) -> Optional[datetime]:
    """
    Parse a datetime from a model field or ISO string.

    Args:
        value: datetime, ISO-8601 string, or None.

    Returns:
        Parsed datetime, or None when missing/invalid.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def resolve_seen_at(
    *,
    last_seen_at: Optional[datetime] = None,
    scraped_at: Optional[datetime] = None,
) -> Optional[datetime]:
    """
    Return the best last-seen timestamp for a listing.

    Prefers ``last_seen_at``. Falls back to ``scraped_at``. Does not default
    to ``datetime.now()`` so loading old JSON cannot un-expire stale rows.

    Args:
        last_seen_at: Explicit last-seen time.
        scraped_at: Original scrape time.

    Returns:
        Last-seen datetime, or None when both are missing.
    """
    return last_seen_at or scraped_at


def resolve_listing_status(
    listing: Optional[JobListing] = None,
    *,
    last_seen_at: Optional[datetime] = None,
    scraped_at: Optional[datetime] = None,
    application_deadline: Optional[datetime] = None,
    now: Optional[datetime] = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> ListingStatus:
    """
    Classify a listing as active or expired.

    Expired when the application deadline has passed, or when the last-seen
    timestamp is at least ``max_age_days`` old. A posting with an old
    ``posted_date`` stays active if it was seen recently.

    Missing dates do not expire the listing.

    Args:
        listing: Optional JobListing; field kwargs override its values.
        last_seen_at: Explicit last-seen time.
        scraped_at: Original scrape time.
        application_deadline: Application close datetime.
        now: Clock override for tests.
        max_age_days: Stale last-seen threshold.

    Returns:
        ``ListingStatus.ACTIVE`` or ``ListingStatus.EXPIRED``.
    """
    clock = now or datetime.now()
    deadline = application_deadline
    seen = last_seen_at
    scraped = scraped_at
    if listing is not None:
        if deadline is None:
            deadline = listing.application_deadline
        if seen is None:
            seen = listing.last_seen_at
        if scraped is None:
            scraped = listing.scraped_at

    if deadline is not None and as_naive_datetime(deadline) < as_naive_datetime(clock):
        return ListingStatus.EXPIRED

    seen_at = resolve_seen_at(last_seen_at=seen, scraped_at=scraped)
    if seen_at is None:
        return ListingStatus.ACTIVE

    age_days = (as_naive_datetime(clock) - as_naive_datetime(seen_at)).days
    if age_days >= max_age_days:
        return ListingStatus.EXPIRED
    return ListingStatus.ACTIVE


def is_scraped_today(
    listing: Optional[JobListing] = None,
    *,
    last_seen_at: Optional[datetime] = None,
    scraped_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> bool:
    """
    Return True when the listing was last seen on the current local calendar day.

    Args:
        listing: Optional JobListing; field kwargs override its values.
        last_seen_at: Explicit last-seen time.
        scraped_at: Original scrape time.
        now: Clock override for tests.

    Returns:
        True when last-seen date equals today.
    """
    clock = now or datetime.now()
    seen = last_seen_at
    scraped = scraped_at
    if listing is not None:
        if seen is None:
            seen = listing.last_seen_at
        if scraped is None:
            scraped = listing.scraped_at
    seen_at = resolve_seen_at(last_seen_at=seen, scraped_at=scraped)
    if seen_at is None:
        return False
    return as_naive_datetime(seen_at).date() == as_naive_datetime(clock).date()


def days_since_posted(
    posted_date: Optional[datetime],
    *,
    now: Optional[datetime] = None,
) -> Optional[int]:
    """
    Return whole days since the posting date.

    Args:
        posted_date: When the job was posted.
        now: Clock override for tests.

    Returns:
        Non-negative day count, or None when posted_date is missing.
    """
    if posted_date is None:
        return None
    clock = now or datetime.now()
    delta = as_naive_datetime(clock) - as_naive_datetime(posted_date)
    return max(delta.days, 0)


def lifecycle_fields(
    listing: Optional[JobListing] = None,
    *,
    last_seen_at: Optional[datetime] = None,
    scraped_at: Optional[datetime] = None,
    application_deadline: Optional[datetime] = None,
    posted_date: Optional[datetime] = None,
    now: Optional[datetime] = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> Dict[str, Any]:
    """
    Build API lifecycle fields for a listing or stored job dict.

    Args:
        listing: Optional JobListing; field kwargs override its values.
        last_seen_at: Explicit last-seen time.
        scraped_at: Original scrape time.
        application_deadline: Application close datetime.
        posted_date: When the job was posted.
        now: Clock override for tests.
        max_age_days: Stale last-seen threshold.

    Returns:
        Dict with listing_status, last_seen_at, scraped_today, days_since_posted.
    """
    clock = now or datetime.now()
    seen = last_seen_at
    scraped = scraped_at
    deadline = application_deadline
    posted = posted_date
    if listing is not None:
        if seen is None:
            seen = listing.last_seen_at
        if scraped is None:
            scraped = listing.scraped_at
        if deadline is None:
            deadline = listing.application_deadline
        if posted is None:
            posted = listing.posted_date

    seen_at = resolve_seen_at(last_seen_at=seen, scraped_at=scraped)
    status = resolve_listing_status(
        last_seen_at=seen,
        scraped_at=scraped,
        application_deadline=deadline,
        now=clock,
        max_age_days=max_age_days,
    )
    return {
        "listing_status": status.value,
        "last_seen_at": seen_at.isoformat() if seen_at else None,
        "scraped_today": is_scraped_today(
            last_seen_at=seen,
            scraped_at=scraped,
            now=clock,
        ),
        "days_since_posted": days_since_posted(posted, now=clock),
    }


def attach_lifecycle_fields(
    job: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> Dict[str, Any]:
    """
    Mutate an API job dict with current lifecycle fields.

    Safe for old shortlist JSON that has no ``listing_status``. Missing
    status is treated as unknown dates rather than expired.

    Args:
        job: Serialized job dict.
        now: Clock override for tests.
        max_age_days: Stale last-seen threshold.

    Returns:
        The same dict, updated in place.
    """
    job.update(
        lifecycle_fields(
            last_seen_at=parse_optional_datetime(job.get("last_seen_at")),
            scraped_at=parse_optional_datetime(job.get("scraped_at")),
            application_deadline=parse_optional_datetime(
                job.get("application_deadline")
            ),
            posted_date=parse_optional_datetime(job.get("posted_date")),
            now=now,
            max_age_days=max_age_days,
        )
    )
    return job


def listing_status_for_job_id(
    job_id: str,
    catalog: Dict[str, JobListing],
    *,
    now: Optional[datetime] = None,
) -> Optional[str]:
    """
    Return catalog listing status for an application job id.

    Applications use ``application_id`` equal to the listing ``job_id``.
    External or unknown ids are not in the catalog and must not be
    treated as expired.

    Args:
        job_id: Application / listing identifier.
        catalog: Canonical listings keyed by job_id.
        now: Clock override for tests.

    Returns:
        ``active`` or ``expired``, or None when the id is not in the catalog.
    """
    if not job_id:
        return None
    listing = catalog.get(job_id)
    if listing is None:
        return None
    return resolve_listing_status(listing, now=now).value
