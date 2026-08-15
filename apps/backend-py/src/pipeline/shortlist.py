"""
Job Raider - Discover shortlist persistence

Persists the scored pipeline shortlist so the Jobs page can review
discover runs without re-scraping.

Author: Job Raider
Date: 2026-07-25
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ..models.job_listing import JobListing, JobSource
from ..rag.ranker import RAGMatchScore
from ..scoring.matcher import MatchScore
from ..scrapers.listing_lifecycle import attach_lifecycle_fields, lifecycle_fields
from ..utils.location_normalizer import normalize_all_locations

ScoredItem = Union[Tuple[JobListing, MatchScore], RAGMatchScore]


def default_shortlist_path(results_dir: str | Path = "data/results") -> Path:
    """
    Return the path of the latest discover shortlist artifact.

    Args:
        results_dir: Pipeline results directory.

    Returns:
        Path to ``latest_shortlist.json``.
    """
    return Path(results_dir) / "latest_shortlist.json"


def _apply_method(source: str, already_applied: bool) -> str:
    """
    Map source + applied flag to the Jobs UI apply_method string.

    Args:
        source: Job source key.
        already_applied: Whether the user already applied.

    Returns:
        apply_method discriminator string.
    """
    if already_applied:
        return "already_applied"
    if source in {"jsearch", "mycareersfuture", "jobstreet", "careersatgov"}:
        return "external_site"
    return "easy_apply"


def _job_and_score(
    item: ScoredItem,
) -> Tuple[JobListing, Optional[MatchScore], Optional[float]]:
    """
    Normalize heuristic or RAG-ranked shortlist entries.

    Args:
        item: Tuple of (job, MatchScore) or RAGMatchScore.

    Returns:
        Tuple of job, optional MatchScore, optional display score (0-100).
    """
    if isinstance(item, RAGMatchScore):
        display = (
            item.combined_score * 100.0
            if getattr(item, "combined_score", None) is not None
            else float(getattr(item, "heuristic_score", 0) or 0)
        )
        return item.job, None, display
    job, score = item
    return job, score, float(score.total_score) if score else None


def serialize_listing(listing: JobListing) -> Dict[str, Any]:
    """
    Serialize a job listing into the Jobs API response shape.

    Includes lifecycle fields (status, last-seen, scraped-today). Score
    fields are added by ``serialize_scored_job``.

    Args:
        listing: Job listing to serialize.

    Returns:
        Dict compatible with frontend ``JobListing``.
    """
    source = (
        listing.source.value
        if isinstance(listing.source, JobSource)
        else str(listing.source)
    )
    job_data: Dict[str, Any] = {
        "job_id": listing.job_id or f"{source}_{hash(str(listing.source_url))}",
        "title": listing.title,
        "company": listing.company,
        "location": normalize_all_locations(listing.location),
        "description": (listing.description or "")[:5000],
        "url": str(listing.source_url) if listing.source_url else None,
        "source_url": str(listing.source_url) if listing.source_url else None,
        "source": source,
        "apply_method": _apply_method(source, listing.already_applied),
        "job_type": (
            listing.job_type.value
            if hasattr(listing.job_type, "value")
            else listing.job_type if listing.job_type else None
        ),
        "experience_level": (
            listing.experience_level.value
            if hasattr(listing.experience_level, "value")
            else listing.experience_level if listing.experience_level else None
        ),
        "salary_range": listing.salary_range,
        "remote": listing.is_remote,
        "is_remote": listing.is_remote,
        "already_applied": listing.already_applied,
        "skills": [
            s.model_dump() if hasattr(s, "model_dump") else s
            for s in (listing.skills or [])
        ],
        "posted_date": (
            listing.posted_date.isoformat() if listing.posted_date else None
        ),
        "application_deadline": (
            listing.application_deadline.isoformat()
            if listing.application_deadline
            else None
        ),
        "scraped_at": (
            listing.scraped_at.isoformat()
            if hasattr(listing, "scraped_at") and listing.scraped_at
            else None
        ),
    }
    job_data.update(lifecycle_fields(listing))
    return job_data


def serialize_scored_job(item: ScoredItem) -> Dict[str, Any]:
    """
    Serialize one scored listing into the Jobs API response shape.

    Args:
        item: Heuristic or RAG-ranked scored entry.

    Returns:
        Dict compatible with frontend ``JobListing``.
    """
    listing, score_result, display_score = _job_and_score(item)
    job_data = serialize_listing(listing)
    if display_score is not None:
        job_data["relevance_score"] = display_score
    if score_result:
        job_data["match_breakdown"] = score_result.breakdown
        job_data["recommendation"] = score_result.recommendation
        job_data["reasoning"] = score_result.reasoning
        job_data["matched_keywords"] = score_result.matched_keywords
        job_data["missing_skills"] = score_result.missing_skills
        job_data["passed_threshold"] = score_result.passed_threshold
    elif isinstance(item, RAGMatchScore):
        job_data["recommendation"] = item.recommendation
        job_data["reasoning"] = item.reasoning
        job_data["matched_keywords"] = item.matched_keywords
        job_data["missing_skills"] = item.missing_skills
        job_data["passed_threshold"] = item.passed_threshold
        if item.heuristic_breakdown:
            job_data["match_breakdown"] = item.heuristic_breakdown
    return job_data


def _job_from_scored(item: ScoredItem) -> JobListing:
    """
    Return the JobListing embedded in a scored shortlist entry.

    Args:
        item: Heuristic or RAG-ranked scored entry.

    Returns:
        The underlying job listing.
    """
    job, _, _ = _job_and_score(item)
    return job


def enrich_shortlist_descriptions(
    scored_listings: Optional[List[ScoredItem]],
) -> int:
    """
    Backfill LinkedIn descriptions for shortlisted jobs missing them.

    Search-time enrichment is capped and can fail silently (auth wall /
    selector drift). Re-fetch detail pages for the much smaller shortlist
    before persistence so Jobs review has usable JDs.

    Args:
        scored_listings: Scored or RAG-ranked listings (mutated in place).

    Returns:
        Count of listings that gained a description.
    """
    if not scored_listings:
        return 0
    from ..scrapers.linkedin_scraper import LinkedInScraper

    jobs = [_job_from_scored(item) for item in scored_listings]
    return LinkedInScraper().fill_missing_descriptions(jobs)


def enrich_shortlist_payload_descriptions(
    payload: Dict[str, Any],
    *,
    results_dir: str | Path = "data/results",
    persist: bool = True,
) -> Dict[str, Any]:
    """
    Backfill empty descriptions on a saved shortlist JSON payload.

    Args:
        payload: Loaded ``latest_shortlist.json`` dict.
        results_dir: Directory to rewrite when ``persist`` is true.
        persist: When true and any JD was filled, rewrite the artifact.

    Returns:
        Updated payload (same object, mutated).
    """
    jobs = payload.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        return payload

    from ..scrapers.linkedin_scraper import LinkedInScraper

    scraper = LinkedInScraper()
    filled = 0
    for job in jobs:
        if not isinstance(job, dict):
            continue
        desc = (job.get("description") or "").strip()
        if len(desc) > 50:
            continue
        if str(job.get("source") or "").lower() != "linkedin":
            continue
        job_id = job.get("job_id")
        if not job_id:
            continue
        try:
            detailed = scraper.get_job_details(str(job_id))
        except Exception:
            continue
        if detailed and detailed.description:
            job["description"] = detailed.description[:5000]
            filled += 1

    if filled and persist:
        path = default_shortlist_path(results_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
    return payload


def save_latest_shortlist(
    *,
    run_id: str,
    mode: str,
    keywords: List[str],
    locations: List[str],
    scored_listings: Optional[List[ScoredItem]],
    results_dir: str | Path = "data/results",
    jobs_scraped: int = 0,
) -> Path:
    """
    Persist the latest discover shortlist for the Jobs review page.

    Args:
        run_id: Pipeline run identifier.
        mode: Pipeline mode (``discover`` or ``full``).
        keywords: Search keywords used for the run.
        locations: Search locations used for the run.
        scored_listings: Scored or RAG-ranked listings (may be empty).
        results_dir: Directory for the artifact.
        jobs_scraped: Raw scrape count for the banner.

    Returns:
        Path written.
    """
    path = default_shortlist_path(results_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    jobs = [serialize_scored_job(item) for item in (scored_listings or [])]
    payload = {
        "run_id": run_id,
        "mode": mode,
        "created_at": datetime.now().isoformat(),
        "keywords": keywords,
        "locations": locations,
        "jobs_scraped": jobs_scraped,
        "total": len(jobs),
        "jobs": jobs,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)
    return path


def load_latest_shortlist(
    results_dir: str | Path = "data/results",
) -> Optional[Dict[str, Any]]:
    """
    Load the latest discover shortlist artifact if present.

    Args:
        results_dir: Directory containing the artifact.

    Returns:
        Shortlist dict, or ``None`` when missing/invalid.
    """
    path = default_shortlist_path(results_dir)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or "jobs" not in data:
            return None
        jobs = data.get("jobs") or []
        if isinstance(jobs, list):
            for job in jobs:
                if isinstance(job, dict):
                    attach_lifecycle_fields(job)
        return data
    except (OSError, json.JSONDecodeError):
        return None
