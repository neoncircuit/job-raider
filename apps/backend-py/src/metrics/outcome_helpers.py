"""
Job Raider - Outcome Helpers

This module defines the constants and pure functions of the outcome tracker:
safe file names, and the URL and label forms used to match applications.
"""

import hashlib
import re
from typing import Optional

from .outcome_models import ApplicationStatus

# Linux NAME_MAX is 255; keep a margin for ``.json`` and Windows MAX_PATH.
_MAX_APPLICATION_FILENAME_STEM = 180
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_PLACEHOLDER_LABELS = frozenset(
    {"", "unknown", "n/a", "none", "untitled listing", "confidential"}
)
INBOUND_APPLICATION_METHOD = "inbound/recruiter"
_GENERIC_APPLICATION_METHODS = frozenset({"", "manual", "external site"})
_MIN_PREP_DESCRIPTION_CHARS = 50

# Keep these on re-track. Inbound/invite may still advance earlier statuses.
_KEEP_STATUS_ON_RETRACK = {
    ApplicationStatus.UNDER_REVIEW,
    ApplicationStatus.SCREENING_SCHEDULED,
    ApplicationStatus.SCREENING_COMPLETED,
    ApplicationStatus.TECHNICAL_SCHEDULED,
    ApplicationStatus.TECHNICAL_COMPLETED,
    ApplicationStatus.ONSITE_SCHEDULED,
    ApplicationStatus.ONSITE_COMPLETED,
    ApplicationStatus.OFFER_RECEIVED,
    ApplicationStatus.OFFER_ACCEPTED,
    ApplicationStatus.OFFER_DECLINED,
    ApplicationStatus.CUSTOM,
}


def application_filename_stem(application_id: str) -> str:
    """
    Return a filesystem-safe stem for an application JSON file.

    Long or unsafe job IDs (JSearch base64, characters like ``:``) are
    hashed. The original id stays in the JSON ``application_id`` field.

    Args:
        application_id: Job / application id used as the logical key.

    Returns:
        Filename stem without ``.json``.
    """
    if (
        application_id
        and _SAFE_FILENAME_RE.match(application_id)
        and len(application_id) <= _MAX_APPLICATION_FILENAME_STEM
    ):
        return application_id
    digest = hashlib.sha256(application_id.encode("utf-8")).hexdigest()
    return f"id_{digest}"


def normalize_match_url(raw: Optional[str]) -> Optional[str]:
    """
    Normalize a listing URL for duplicate matching.

    Args:
        raw: Stored or pasted listing URL.

    Returns:
        Lowercased http(s) URL without a trailing slash, or None.
    """
    if not isinstance(raw, str):
        return None
    url = raw.strip()
    if not url or len(url) > 2048:
        return None
    lowered = url.lower()
    if lowered.startswith(("javascript:", "data:", "file:", "vbscript:")):
        return None
    if not lowered.startswith(("http://", "https://")):
        if "://" in url.split("/", 1)[0]:
            return None
        url = f"https://{url}"
        lowered = url.lower()
    return lowered.rstrip("/")


def normalize_match_label(value: str) -> str:
    """
    Normalize a company or title string for duplicate matching.

    Args:
        value: Company name or job title.

    Returns:
        Lowercased value with collapsed whitespace.
    """
    return " ".join((value or "").lower().split())


def _usable_match_label(value: str) -> bool:
    """
    Return whether a company or title is strong enough to match on.

    Args:
        value: Company name or job title.

    Returns:
        True when the normalized label is not empty or a placeholder.
    """
    return normalize_match_label(value) not in _PLACEHOLDER_LABELS
