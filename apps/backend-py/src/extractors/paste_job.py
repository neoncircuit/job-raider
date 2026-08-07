"""
Build JobListing objects from messy human-pasted job text.

Any feature that accepts a drag-copied JD (cover letter, resume analysis,
applications track-external, jobs classify/trust/cover-letter, CLI analyze)
must go through this module so scrape and paste share the same cleaning rules.

Scraped listings already run ``normalize_job_description`` at ingest. Paste
paths historically stored the raw blob only. This module closes that gap with
rules only (no LLM) so paste stays fast and offline-friendly.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Mapping, Optional

from ..models.job_listing import JobListing, JobSource
from ..utils.text_normalizer import normalize_job_description
from .jd_extractor import JDExtractor


def clean_pasted_job_description(description: str) -> str:
    """
    Normalize pasted JD text for storage or LLM prompts.

    Use when a feature only needs cleaned text (for example applications
    metadata) and does not need a full ``JobListing``.

    Args:
        description: Raw pasted job description (may include HTML crumbs).

    Returns:
        Cleaned description, or the stripped original when normalize yields empty.
    """
    if not description or not str(description).strip():
        return ""
    normalized = normalize_job_description(str(description))
    return normalized if normalized.strip() else str(description).strip()


def build_job_listing_from_paste(
    title: str,
    company: str,
    description: str,
    *,
    location: Optional[str] = None,
    job_id: Optional[str] = None,
    source: JobSource = JobSource.MANUAL,
) -> JobListing:
    """
    Normalize pasted JD text and fill structured fields via rule-based extract.

    User-provided title, company, and location always win over extractor guesses.
    The full normalized description is kept (not truncated) so writers and
    matchers still see the complete paste.

    Args:
        title: Job title from the form.
        company: Company name from the form.
        description: Raw pasted job description (may include HTML crumbs).
        location: Optional location from the form.
        job_id: Optional stable id; generated when omitted.
        source: Listing source (defaults to MANUAL for paste).

    Returns:
        A ``JobListing`` with normalized description and any
        skills/requirements/responsibilities the rule extractor found.
    """
    cleaned = clean_pasted_job_description(description)

    extractor = JDExtractor(llm_router=None)
    extracted = extractor._extract_rule_based(
        cleaned,
        url=None,
        source=source,
        errors=[],
        warnings=[],
    )

    skills = []
    requirements = []
    responsibilities = []
    experience_level = None
    work_mode = None
    job_type = None
    salary_range = None
    inferred_location = location

    if extracted.success and extracted.job_listing is not None:
        listing = extracted.job_listing
        skills = list(listing.skills)
        requirements = list(listing.requirements)
        responsibilities = list(listing.responsibilities)
        experience_level = listing.experience_level
        work_mode = listing.work_mode
        job_type = listing.job_type
        salary_range = listing.salary_range
        if not inferred_location and listing.location:
            inferred_location = listing.location

    kwargs: Dict[str, Any] = {
        "title": title.strip() or "Unknown",
        "company": company.strip() or "Unknown",
        "job_id": job_id or f"manual-{uuid.uuid4().hex[:12]}",
        "source": source,
        "description": cleaned,
        "location": inferred_location,
        "requirements": requirements,
        "responsibilities": responsibilities,
        "skills": skills,
        "salary_range": salary_range,
    }
    if experience_level is not None:
        kwargs["experience_level"] = experience_level
    if work_mode is not None:
        kwargs["work_mode"] = work_mode
    if job_type is not None:
        kwargs["job_type"] = job_type

    return JobListing(**kwargs)


def build_job_listing_from_job_data(
    job_id: str,
    job_data: Optional[Mapping[str, Any]] = None,
    *,
    default_title: str = "Unknown",
    default_company: str = "Unknown",
) -> JobListing:
    """
    Build a structured listing from API ``job_data`` payloads.

    Used by jobs routes that accept optional title/company/description bodies
    (classify, trust analysis, cover letter). When a description is present it
    is treated as paste text and run through the same normalize + rule extract
    path.

    Args:
        job_id: Job identifier for the listing.
        job_data: Optional dict with title, company, description, location, source.
        default_title: Fallback title when job_data is missing or empty.
        default_company: Fallback company when job_data is missing or empty.

    Returns:
        A ``JobListing`` suitable for classifiers, trust analysis, or writers.
    """
    data = dict(job_data or {})
    description = str(data.get("description") or "")
    title = str(data.get("title") or default_title)
    company = str(data.get("company") or default_company)
    location = data.get("location")
    location_str = str(location) if location else None

    source_raw = data.get("source", "manual")
    try:
        source = JobSource(source_raw) if source_raw else JobSource.MANUAL
    except ValueError:
        source = JobSource.MANUAL

    if description.strip():
        return build_job_listing_from_paste(
            title=title,
            company=company,
            description=description,
            location=location_str,
            job_id=job_id,
            source=source,
        )

    return JobListing(
        title=title.strip() or default_title,
        company=company.strip() or default_company,
        job_id=job_id,
        source=source,
        description="",
        location=location_str,
    )
