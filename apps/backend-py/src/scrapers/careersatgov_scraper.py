"""
Job Raider - Careers@Gov delayed-catalog scraper

Public HTTP adapter for the OpenGovSG published Careers@Gov dump.
This is not live search. The dump is a daily (or twice-daily) snapshot
of jobs.careers.gov.sg listings. No login, no Playwright, no OData
secrets. Disable with CAREERSATGOV_ENABLED=0. Default is off because
the feed is delayed.

Author: Job Raider
Date: 2026-08-15
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..models.job_listing import (
    ExperienceLevel,
    JobListing,
    JobListingCollection,
    JobRequirement,
    JobResponsibility,
    JobSource,
    JobType,
    WorkMode,
)
from ..utils.source_geography import singapore_board_applies
from .base import BaseScraper, ScrapingException, SearchParams

logger = logging.getLogger(__name__)

# Public processed dump. Do not use CAREERSGOVSG_JOB_HEADER / DETAILS
# (those OData URLs are treated as secrets by the dump publisher).
CAG_DUMP_URL = (
    "https://raw.githubusercontent.com/opengovsg/careersgovsg-jobs-data"
    "/main/data/job-listings.json"
)
CAG_PUBLIC_JOB_BASE = "https://jobs.careers.gov.sg/jobs"
CAG_WORKABLE_JOB_BASE = "https://apply.workable.com/j"

MAX_RESULTS = 60
MAX_DUMP_BYTES = 30 * 1024 * 1024
DUMP_CACHE_TTL_SECONDS = 6 * 3600
DUMP_FETCH_TIMEOUT = 60

_cache_lock = threading.Lock()
_dump_cache: Optional[Tuple[datetime, datetime, List[Dict[str, Any]]]] = None


def careersatgov_enabled() -> bool:
    """
    Return whether the Careers@Gov delayed-catalog adapter is enabled.

    Default is off. The feed is a delayed dump, not live search.

    Args:
        None.

    Returns:
        True only when ``CAREERSATGOV_ENABLED`` is a truthy value
        (``1``, ``true``, ``yes``, ``on``).
    """
    raw = os.environ.get("CAREERSATGOV_ENABLED", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def clear_dump_cache() -> None:
    """
    Clear the in-process dump cache.

    Args:
        None.

    Returns:
        None.
    """
    global _dump_cache
    with _cache_lock:
        _dump_cache = None


class CareersAtGovScraper(BaseScraper):
    """
    Filter the public OpenGovSG Careers@Gov dump into JobListing rows.

    Downloads ``job-listings.json`` from the published GitHub repository,
    filters locally by keywords, and caps results. Rows are marked as a
    delayed catalog. ``last_seen_at`` uses the dump snapshot time, not
    wall-clock now, so stale dumps do not look like live scrapes.
    """

    def __init__(self, **kwargs: Any):
        """
        Initialize the Careers@Gov delayed-catalog scraper.

        Args:
            **kwargs: Forwarded to ``BaseScraper`` (rate_limit, timeout, …).
        """
        kwargs.setdefault("rate_limit", 1.5)
        kwargs.setdefault("timeout", DUMP_FETCH_TIMEOUT)
        super().__init__(**kwargs)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": (
                    "JobRaider/1.0 (personal-use; Careers@Gov delayed dump)"
                ),
            }
        )

    @property
    def source_name(self) -> JobSource:
        """Return the JobSource enum for Careers@Gov."""
        return JobSource.CAREERSATGOV

    @property
    def base_url(self) -> str:
        """Return the public dump URL host path."""
        return CAG_DUMP_URL

    def build_search_url(self, params: SearchParams) -> str:
        """
        Not used. Search filters a bulk dump.

        Args:
            params: Search parameters (ignored).

        Returns:
            The public dump URL.

        Raises:
            None.
        """
        return CAG_DUMP_URL

    def parse_job_listings(self, html: str) -> List[JobListing]:
        """
        HTML parsing is out of scope for this adapter.

        Args:
            html: Page HTML (unused).

        Returns:
            Never returns.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            "CareersAtGovScraper parses the published JSON dump, not HTML"
        )

    def search(self, params: SearchParams) -> JobListingCollection:
        """
        Filter the delayed Careers@Gov dump for jobs matching the keywords.

        Args:
            params: Keywords, optional location, and result limit.

        Returns:
            JobListingCollection of mapped dump rows.

        Raises:
            ScrapingException: When the adapter is disabled or the dump
                download fails.
        """
        if not careersatgov_enabled():
            raise ScrapingException(
                "Careers@Gov adapter is disabled (CAREERSATGOV_ENABLED is off)"
            )

        if not singapore_board_applies(params.location, remote=params.remote):
            logger.info(
                "Skipping Careers@Gov: location %r is outside Singapore/remote",
                params.location,
            )
            return JobListingCollection(
                listings=[],
                source=self.source_name,
                metadata={
                    "search_params": params.model_dump(),
                    "skipped": True,
                    "skip_reason": "location_outside_singapore",
                    "catalog_kind": "delayed_dump",
                    "searched_at": datetime.now().isoformat(),
                },
            )

        limit = max(1, min(params.limit or MAX_RESULTS, MAX_RESULTS))
        rows, snapshot_at = self._load_dump()
        matched = self._filter_rows(rows, params.keywords)[:limit]
        listings: List[JobListing] = []
        for raw in matched:
            try:
                listings.append(self._parse_job(raw, snapshot_at=snapshot_at))
            except Exception as exc:  # noqa: BLE001 — skip bad rows
                logger.warning("Skipping Careers@Gov dump row: %s", exc)

        logger.info(
            "Careers@Gov dump matched %d/%d rows (snapshot=%s)",
            len(listings),
            len(rows),
            snapshot_at.isoformat(),
        )
        return JobListingCollection(
            listings=listings,
            source=self.source_name,
            metadata={
                "search_params": params.model_dump(),
                "catalog_kind": "delayed_dump",
                "dump_url": CAG_DUMP_URL,
                "dump_snapshot_at": snapshot_at.isoformat(),
                "dump_row_count": len(rows),
                "matched_count": len(listings),
                "freshness_note": (
                    "Delayed OpenGovSG dump, not live Careers@Gov search. "
                    "Snapshot time is dump_snapshot_at."
                ),
                "searched_at": datetime.now().isoformat(),
            },
        )

    def get_job_details(self, job_id: str) -> Optional[JobListing]:
        """
        Resolve one dump row by Job Raider job id.

        Args:
            job_id: Prefixed id such as ``cag-hrp-17060737-<postingNo>``.

        Returns:
            JobListing or None when not found / disabled.
        """
        if not careersatgov_enabled():
            return None
        try:
            rows, snapshot_at = self._load_dump()
        except ScrapingException:
            return None
        for raw in rows:
            try:
                generated = self._stable_id(
                    str(raw.get("platform") or ""),
                    str(raw.get("jobId") or ""),
                    str(raw.get("postingNo") or ""),
                )
            except ValueError:
                continue
            if generated == job_id:
                try:
                    return self._parse_job(raw, snapshot_at=snapshot_at)
                except Exception:  # noqa: BLE001
                    return None
        return None

    def _load_dump(self) -> Tuple[List[Dict[str, Any]], datetime]:
        """
        Return dump rows and snapshot time, using the in-process cache.

        Args:
            None.

        Returns:
            Tuple of row list and naive snapshot datetime.

        Raises:
            ScrapingException: On HTTP or parse failure.
        """
        global _dump_cache
        now = datetime.now()
        with _cache_lock:
            cached = _dump_cache
        if cached is not None:
            fetched_at, snapshot_at, rows = cached
            age = (now - fetched_at).total_seconds()
            if age < DUMP_CACHE_TTL_SECONDS:
                return rows, snapshot_at

        self._rate_limit_wait()
        rows, snapshot_at = self._fetch_dump()
        with _cache_lock:
            _dump_cache = (datetime.now(), snapshot_at, rows)
        return rows, snapshot_at

    def _fetch_dump(self) -> Tuple[List[Dict[str, Any]], datetime]:
        """
        Download the public OpenGovSG JSON dump.

        Args:
            None.

        Returns:
            Tuple of row list and snapshot datetime from Last-Modified
            when present, else fetch time.

        Raises:
            ScrapingException: On HTTP, size, or JSON failure.
        """
        try:
            response = self._session.get(CAG_DUMP_URL, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise ScrapingException(f"Careers@Gov dump unreachable: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise ScrapingException(
                f"Careers@Gov dump request timed out: {exc}"
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", "?")
            text = exc.response.text[:200] if exc.response is not None else ""
            raise ScrapingException(
                f"Careers@Gov dump returned HTTP {status}: {text}"
            ) from exc

        if len(response.content) > MAX_DUMP_BYTES:
            raise ScrapingException(f"Careers@Gov dump exceeds {MAX_DUMP_BYTES} bytes")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ScrapingException(
                f"Careers@Gov dump is not valid JSON: {exc}"
            ) from exc
        if not isinstance(payload, list):
            raise ScrapingException("Careers@Gov dump is not a JSON array")

        rows = [row for row in payload if isinstance(row, dict)]
        snapshot_at = (
            self._parse_last_modified(response.headers.get("Last-Modified"))
            or datetime.now()
        )
        return rows, snapshot_at

    def _parse_job(self, raw: Dict[str, Any], *, snapshot_at: datetime) -> JobListing:
        """
        Map one dump row into a JobListing.

        Args:
            raw: One object from the published JSON array.
            snapshot_at: Dump Last-Modified (or fetch time).

        Returns:
            Populated JobListing.

        Raises:
            ValueError: When platform or jobId is missing.
        """
        platform = str(raw.get("platform") or "").strip()
        job_id = str(raw.get("jobId") or "").strip()
        posting_no = str(raw.get("postingNo") or "").strip()
        if not platform or not job_id:
            raise ValueError("Careers@Gov dump row missing platform or jobId")

        title = (str(raw.get("jobTitle") or "Unknown")).strip() or "Unknown"
        company = (str(raw.get("agency") or "Unknown")).strip() or "Unknown"
        location = (str(raw.get("location") or "")).strip() or "Singapore"

        description_parts: List[str] = []
        for field_name, heading in (
            ("jobDescription", None),
            ("jobResponsibilities", "Responsibilities"),
            ("jobRequirements", "Requirements"),
        ):
            cleaned = self._clean_description(str(raw.get(field_name) or ""))
            if not cleaned:
                continue
            if heading:
                description_parts.append(f"{heading}:\n\n{cleaned}")
            else:
                description_parts.append(cleaned)
        description = "\n\n".join(description_parts)
        if len(description) > 10000:
            description = description[:10000]

        requirements: List[JobRequirement] = []
        req_text = self._clean_description(str(raw.get("jobRequirements") or ""))
        if req_text:
            requirements.append(
                JobRequirement(category="Requirements", text=req_text[:2000])
            )
        responsibilities: List[JobResponsibility] = []
        resp_text = self._clean_description(str(raw.get("jobResponsibilities") or ""))
        if resp_text:
            responsibilities.append(
                JobResponsibility(category="Responsibilities", text=resp_text[:2000])
            )

        work_mode, is_remote = self._map_work_arrangement(
            str(raw.get("workArrangement") or "")
        )
        job_type = self._map_employment_type(
            str(raw.get("employmentType") or ""), title
        )
        experience_level = self._map_experience(
            str(raw.get("experienceRequired") or ""),
            raw.get("experienceYearsMin"),
            title,
        )

        return JobListing(
            title=title,
            company=company,
            job_id=self._stable_id(platform, job_id, posting_no),
            source=self.source_name,
            source_url=self._public_url(platform, job_id, posting_no),
            location=location,
            work_mode=work_mode,
            is_remote=is_remote,
            job_type=job_type,
            experience_level=experience_level,
            description=description or None,
            requirements=requirements,
            responsibilities=responsibilities,
            department=str(raw.get("field") or raw.get("functionalArea") or "") or None,
            posted_date=self._parse_unix_ms(raw.get("startDate")),
            application_deadline=self._parse_unix_ms(raw.get("closingDate")),
            scraped_at=datetime.now(),
            last_seen_at=snapshot_at,
            metadata={
                "catalog_kind": "delayed_dump",
                "dump_snapshot_at": snapshot_at.isoformat(),
                "freshness_note": (
                    "Delayed OpenGovSG dump; not a live Careers@Gov posting time."
                ),
                "cag_platform": platform,
                "cag_job_id": job_id,
                "cag_posting_no": posting_no,
                "cag_employment_type": str(raw.get("employmentType") or ""),
                "cag_closing_date_text": str(raw.get("closingDateText") or ""),
            },
        )

    @staticmethod
    def _stable_id(platform: str, job_id: str, posting_no: str) -> str:
        """
        Build a stable Job Raider id from dump identifiers.

        Args:
            platform: Dump ``platform`` (hrp, greenhouse, workable).
            job_id: Dump ``jobId``.
            posting_no: Dump ``postingNo`` (may be empty).

        Returns:
            Prefixed job id.

        Raises:
            ValueError: When platform or job_id is empty.
        """
        if not platform or not job_id:
            raise ValueError("platform and jobId are required")
        parts = ["cag", platform, job_id]
        if posting_no:
            parts.append(posting_no)
        return "-".join(parts)

    @staticmethod
    def _public_url(platform: str, job_id: str, posting_no: str) -> str:
        """
        Build the public listing URL for a dump row.

        Args:
            platform: Dump ``platform``.
            job_id: Dump ``jobId``.
            posting_no: Dump ``postingNo``.

        Returns:
            Public apply / listing URL.
        """
        if platform == "workable" and posting_no:
            return f"{CAG_WORKABLE_JOB_BASE}/{posting_no}"
        if platform == "greenhouse":
            return f"{CAG_PUBLIC_JOB_BASE}/greenhouse/{job_id}?gh_jid={job_id}"
        if posting_no:
            return f"{CAG_PUBLIC_JOB_BASE}/{platform}/{job_id}/{posting_no}"
        return f"{CAG_PUBLIC_JOB_BASE}/{platform}/{job_id}"

    @staticmethod
    def _filter_rows(
        rows: List[Dict[str, Any]], keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Keep dump rows whose searchable text contains every keyword.

        Title matches sort first. This is local filter of a bulk dump,
        not a live search API.

        Args:
            rows: Dump objects.
            keywords: Search keywords.

        Returns:
            Matching rows, title hits first, capped later by the caller.
        """
        tokens = [k.strip().lower() for k in keywords if k and k.strip()]
        if not tokens:
            tokens = ["software"]

        scored: List[Tuple[int, Dict[str, Any]]] = []
        for raw in rows:
            haystack = " ".join(
                str(raw.get(key) or "")
                for key in (
                    "jobTitle",
                    "agency",
                    "field",
                    "functionalArea",
                    "jobDescription",
                    "jobResponsibilities",
                    "jobRequirements",
                    "location",
                )
            ).lower()
            if not all(token in haystack for token in tokens):
                continue
            title = str(raw.get("jobTitle") or "").lower()
            score = 0 if all(token in title for token in tokens) else 1
            scored.append((score, raw))
        scored.sort(key=lambda item: item[0])
        return [raw for _, raw in scored]

    @staticmethod
    def _map_work_arrangement(text: str) -> Tuple[WorkMode, bool]:
        """
        Map dump workArrangement to WorkMode.

        Args:
            text: Dump workArrangement string.

        Returns:
            Tuple of work mode and remote flag.
        """
        lower = text.lower()
        if "remote" in lower:
            return WorkMode.REMOTE, True
        if "hybrid" in lower:
            return WorkMode.HYBRID, False
        return WorkMode.ON_SITE, False

    @staticmethod
    def _map_employment_type(text: str, title: str) -> JobType:
        """
        Map dump employment type and title to JobType.

        Args:
            text: Dump employmentType string.
            title: Job title.

        Returns:
            JobType.
        """
        blob = f"{text} {title}".lower()
        if "intern" in blob:
            return JobType.INTERNSHIP
        if "part" in blob:
            return JobType.PART_TIME
        if "contract" in blob or "fixed term" in blob or "temporary" in blob:
            return JobType.CONTRACT
        return JobType.FULL_TIME

    @staticmethod
    def _map_experience(required: str, years_min: Any, title: str) -> ExperienceLevel:
        """
        Map dump experience fields to ExperienceLevel.

        Args:
            required: Human-readable experienceRequired.
            years_min: Numeric minimum years.
            title: Job title.

        Returns:
            ExperienceLevel.
        """
        blob = f"{required} {title}".lower()
        if "intern" in blob:
            return ExperienceLevel.INTERNSHIP
        if "entry" in blob:
            return ExperienceLevel.ENTRY
        years: Optional[float] = None
        if isinstance(years_min, (int, float)):
            years = float(years_min)
        if years is not None:
            if years < 1:
                return ExperienceLevel.ENTRY
            if years < 3:
                return ExperienceLevel.MID
            if years < 7:
                return ExperienceLevel.SENIOR
            return ExperienceLevel.LEAD
        return ExperienceLevel.NOT_SPECIFIED

    @staticmethod
    def _parse_unix_ms(value: Any) -> Optional[datetime]:
        """
        Parse dump Unix timestamps stored in milliseconds.

        Args:
            value: Number, numeric string, or None.

        Returns:
            Naive UTC datetime, or None.
        """
        if value is None or value == "":
            return None
        try:
            millis = float(value)
        except (TypeError, ValueError):
            return None
        if millis > 1e12:
            millis = millis / 1000.0
        try:
            return datetime.fromtimestamp(millis, tz=timezone.utc).replace(tzinfo=None)
        except (OSError, OverflowError, ValueError):
            return None

    @staticmethod
    def _parse_last_modified(header: Optional[str]) -> Optional[datetime]:
        """
        Parse an HTTP Last-Modified header to naive UTC datetime.

        Args:
            header: Last-Modified value or None.

        Returns:
            Naive datetime or None.
        """
        if not header:
            return None
        try:
            parsed = parsedate_to_datetime(header)
        except (TypeError, ValueError, IndexError):
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
