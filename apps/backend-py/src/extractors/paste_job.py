"""
Build JobListing objects from messy human-pasted job text.

Paste paths (cover letter, resume analysis, etc.) historically stored the raw
blob only. Scraped listings already run ``normalize_job_description`` and
optional structure extraction. This module closes that gap with rules only
(no LLM) so paste stays fast and offline-friendly.
"""

from __future__ import annotations

import uuid
from typing import Optional

from ..models.job_listing import JobListing, JobSource
from ..utils.text_normalizer import normalize_job_description
from .jd_extractor import JDExtractor


def build_job_listing_from_paste(
    title: str,
    company: str,
    description: str,
    *,
    location: Optional[str] = None,
    job_id: Optional[str] = None,
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

    Returns:
        A ``JobListing`` with ``source=MANUAL``, normalized description, and
        any skills/requirements/responsibilities the rule extractor found.
    """
    normalized = normalize_job_description(description)
    cleaned = normalized if normalized.strip() else description.strip()

    extractor = JDExtractor(llm_router=None)
    extracted = extractor._extract_rule_based(
        cleaned,
        url=None,
        source=JobSource.MANUAL,
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

    kwargs = {
        "title": title.strip(),
        "company": company.strip(),
        "job_id": job_id or f"manual-{uuid.uuid4().hex[:12]}",
        "source": JobSource.MANUAL,
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
