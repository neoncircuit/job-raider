"""
Job Raider - Notice for a run that scraped no jobs

When Scrape returns no listings, the run stops after Scrape and shows a
notice. The notice tells the two causes apart (no-jobs-notice task): a job
source that did not answer (for example MyCareersFuture HTTP 504 "Endpoint
request timed out") and searches that ran but found nothing. Other keywords
do not help when the source timed out.

Author: Job Raider
Date: 2026-11-20
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping

# Shown when Scrape finds no listings and no search failed.
NO_JOBS_WARNING = (
    "No jobs found for these keywords and sources. The run stopped after "
    "Scrape. Try other keywords, fewer keywords, or another source."
)

# Source IDs to the names that the app shows.
SOURCE_NAMES: Dict[str, str] = {
    "mycareersfuture": "MyCareersFuture",
    "linkedin": "LinkedIn",
    "jobstreet": "JobStreet",
    "careersatgov": "Careers@Gov",
    "jsearch": "JSearch",
    "indeed": "Indeed",
}
HTTP_STATUS_RE = re.compile(r"\bHTTP\s+(\d{3})\b")
TIMEOUT_RE = re.compile(r"timed?\s*out|timeout", re.IGNORECASE)


def _source_name(source: Any) -> str:
    """
    Return the display name of a job source.

    Args:
        source: The source ID, for example "mycareersfuture".

    Returns:
        The display name; the ID in title case when it is not known.
    """
    key = str(source or "").strip().lower()
    return SOURCE_NAMES.get(key, key.title() or "The job source")


def _reason(error: str) -> str:
    """
    Turn a search error into a short reason, without the raw response text.

    Args:
        error: The error text of one search.

    Returns:
        For example "timed out (HTTP 504)", "HTTP 503", "timed out", or
        "an error".
    """
    status = HTTP_STATUS_RE.search(error)
    timed_out = bool(TIMEOUT_RE.search(error))
    if status and timed_out:
        return f"timed out (HTTP {status.group(1)})"
    if status:
        return f"HTTP {status.group(1)}"
    return "timed out" if timed_out else "an error"


def _failures(rows: List[Mapping[str, Any]]) -> List[str]:
    """
    List each failed source once, with its first reason.

    Args:
        rows: The search rows that have an error.

    Returns:
        Texts such as "MyCareersFuture timed out (HTTP 504)", in order.
    """
    seen: Dict[str, str] = {}
    for row in rows:
        name = _source_name(row.get("source"))
        seen.setdefault(name, f"{name} {_reason(str(row.get('error')))}")
    return list(seen.values())


def no_jobs_warning(scrape_metadata: Mapping[str, Any]) -> str:
    """
    Build the notice for a run whose Scrape returned no listings.

    Args:
        scrape_metadata: The Scrape stage metadata; ``searches`` holds one
            row per search with ``source``, ``count``, and ``error``.

    Returns:
        A source notice when every search failed, a mixed notice when some
        failed, and ``NO_JOBS_WARNING`` when none failed or no row exists.
    """
    rows = [
        row
        for row in (scrape_metadata or {}).get("searches") or []
        if isinstance(row, Mapping)
    ]
    failed = [row for row in rows if row.get("error")]
    if not failed:
        return NO_JOBS_WARNING
    reasons = "; ".join(_failures(failed))
    if len(failed) == len(rows):
        return (
            f"No jobs came in because the job source did not answer: {reasons}. "
            "The run stopped after Scrape. Try again later."
        )
    return (
        f"No jobs found, and some searches failed: {reasons}. The run "
        "stopped after Scrape. Try again later, or try other keywords."
    )
