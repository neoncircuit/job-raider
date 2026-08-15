"""
Job Raider - JobStreet Singapore scraper

Public JSON HTTP adapter for JobStreet Singapore (sg.jobstreet.com).
No login, no Playwright. Cap pages aggressively; disable with
JOBSTREET_ENABLED=0. Do not call my.jobstreet.com, ph.jobstreet.com,
or id.jobstreet.com.

Author: Job Raider
Date: 2026-08-15
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from ..models.job_listing import (
    ExperienceLevel,
    JobListing,
    JobListingCollection,
    JobRequirement,
    JobSource,
    JobType,
    SalaryRange,
    WorkMode,
)
from ..utils.source_geography import singapore_board_applies
from .base import BaseScraper, ScrapingException, SearchParams

logger = logging.getLogger(__name__)

# www.jobstreet.com.sg/api/jobsearch/v5/search returns Australian inventory
# and ignores where/keywords. The Singapore site host is required.
JOBSTREET_API_HOST = "https://sg.jobstreet.com"
JOBSTREET_SEARCH_PATH = "/api/jobsearch/v5/search"
JOBSTREET_GRAPHQL_PATH = "/graphql"
JOBSTREET_PUBLIC_JOB_BASE = "https://www.jobstreet.com.sg/job"

DEFAULT_PAGE_SIZE = 20
MAX_PAGES = 3
MAX_RESULTS = 60

_SALARY_RANGE_RE = re.compile(
    r"\$?\s*([\d,]+)\s*[–\-]\s*\$?\s*([\d,]+)\s*per\s+(month|year|hour)",
    re.IGNORECASE,
)
_SALARY_SINGLE_RE = re.compile(
    r"\$?\s*([\d,]+)\s*per\s+(month|year|hour)",
    re.IGNORECASE,
)


def jobstreet_enabled() -> bool:
    """
    Return whether the JobStreet Singapore adapter is enabled.

    Args:
        None.

    Returns:
        True unless ``JOBSTREET_ENABLED`` is set to a falsey value
        (``0``, ``false``, ``no``, ``off``).
    """
    raw = os.environ.get("JOBSTREET_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


class JobStreetScraper(BaseScraper):
    """
    Search JobStreet Singapore via its public v5 JSON search endpoint.

    Uses ``sg.jobstreet.com/api/jobsearch/v5/search``. This is not a
    formally documented developer API; treat as personal-use tooling
    with rate limits and hard result caps. Official SEEK partner
    GraphQL requires a partnership and is out of scope.
    """

    def __init__(self, **kwargs: Any):
        """
        Initialize the JobStreet Singapore scraper.

        Args:
            **kwargs: Forwarded to ``BaseScraper`` (rate_limit, timeout, …).
        """
        kwargs.setdefault("rate_limit", 1.5)
        kwargs.setdefault("timeout", 30)
        super().__init__(**kwargs)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "JobRaider/1.0 (personal-use; JobStreet SG adapter)",
                "Origin": "https://sg.jobstreet.com",
                "Referer": "https://sg.jobstreet.com/",
            }
        )

    @property
    def source_name(self) -> JobSource:
        """Return the JobSource enum for JobStreet Singapore."""
        return JobSource.JOBSTREET

    @property
    def base_url(self) -> str:
        """Return the JobStreet Singapore API host."""
        return JOBSTREET_API_HOST

    def build_search_url(self, params: SearchParams) -> str:
        """
        Not used for JSON API scrapers.

        Args:
            params: Search parameters (ignored).

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            "JobStreetScraper uses search() directly, not build_search_url()"
        )

    def parse_job_listings(self, html: str) -> List[JobListing]:
        """
        Not used for JSON API scrapers.

        Args:
            html: Raw HTML (ignored).

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("JobStreetScraper parses JSON responses, not HTML")

    def search(self, params: SearchParams) -> JobListingCollection:
        """
        Search JobStreet Singapore for jobs matching the keywords.

        Args:
            params: Keywords, optional location, and result limit.

        Returns:
            JobListingCollection of mapped JobStreet SG listings.

        Raises:
            ScrapingException: When the adapter is disabled or the HTTP call fails.
        """
        if not jobstreet_enabled():
            raise ScrapingException(
                "JobStreet adapter is disabled (JOBSTREET_ENABLED=0)"
            )

        if not singapore_board_applies(params.location, remote=params.remote):
            logger.info(
                "Skipping JobStreet: location %r is outside Singapore/remote",
                params.location,
            )
            return JobListingCollection(
                listings=[],
                source=self.source_name,
                metadata={
                    "search_params": params.model_dump(),
                    "skipped": True,
                    "skip_reason": "location_outside_singapore",
                    "searched_at": datetime.now().isoformat(),
                },
            )

        query = " ".join(params.keywords).strip() or "software"
        limit = max(1, min(params.limit or MAX_RESULTS, MAX_RESULTS))
        page_size = min(DEFAULT_PAGE_SIZE, limit)
        max_pages = min(MAX_PAGES, (limit + page_size - 1) // page_size)

        listings: List[JobListing] = []
        total: Optional[int] = None
        pages_fetched = 0

        for page in range(1, max_pages + 1):
            if len(listings) >= limit:
                break
            self._rate_limit_wait()
            payload = self._fetch_page(query=query, page=page, page_size=page_size)
            pages_fetched += 1
            if total is None:
                total = payload.get("totalCount")
            results = payload.get("data") or []
            if not results:
                break
            for raw in results:
                if len(listings) >= limit:
                    break
                try:
                    job = self._parse_job(raw)
                except Exception as exc:  # noqa: BLE001 — skip bad rows
                    logger.warning("Skipping JobStreet job parse error: %s", exc)
                    continue
                if job is None:
                    continue
                listings.append(job)
            if len(results) < page_size:
                break

        logger.info(
            "JobStreet returned %d jobs for query=%r (total=%s)",
            len(listings),
            query,
            total,
        )
        return JobListingCollection(
            listings=listings,
            source=self.source_name,
            metadata={
                "search_params": params.model_dump(),
                "jobstreet_query": query,
                "searched_at": datetime.now().isoformat(),
                "total_results": total,
                "pages_fetched": pages_fetched,
            },
        )

    def get_job_details(self, job_id: str) -> Optional[JobListing]:
        """
        Fetch one job description via public GraphQL when available.

        Args:
            job_id: JobStreet numeric id (or ``js-<id>`` prefixed id).

        Returns:
            JobListing or None when not found / disabled.
        """
        if not jobstreet_enabled():
            return None
        numeric_id = job_id.removeprefix("js-")
        self._rate_limit_wait()
        query = (
            "query { jobDetails(id: %s) { job { id title content abstract } } }"
            % json_string(numeric_id)
        )
        try:
            response = self._session.post(
                f"{JOBSTREET_API_HOST}{JOBSTREET_GRAPHQL_PATH}",
                json={"query": query},
                timeout=self.timeout,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.warning("JobStreet job-details failed for %s: %s", job_id, exc)
            return None
        body = response.json()
        job = ((body.get("data") or {}).get("jobDetails") or {}).get("job")
        if not isinstance(job, dict) or not job.get("id"):
            return None
        content = job.get("content") or job.get("abstract") or ""
        description = self._clean_description(str(content)) if content else None
        if description and len(description) > 10000:
            description = description[:10000]
        return JobListing(
            title=(job.get("title") or "Unknown").strip() or "Unknown",
            company="Unknown",
            job_id=f"js-{job['id']}",
            source=self.source_name,
            source_url=f"{JOBSTREET_PUBLIC_JOB_BASE}/{job['id']}",
            location="Singapore",
            description=description,
            job_type=JobType.FULL_TIME,
            experience_level=ExperienceLevel.NOT_SPECIFIED,
            scraped_at=datetime.now(),
            last_seen_at=datetime.now(),
            metadata={"jobstreet_id": str(job["id"])},
        )

    def _fetch_page(self, *, query: str, page: int, page_size: int) -> Dict[str, Any]:
        """
        Fetch one page of JobStreet Singapore search results.

        Args:
            query: Keyword search string.
            page: One-based page index.
            page_size: Results per page.

        Returns:
            Parsed JSON body.

        Raises:
            ScrapingException: On HTTP or network failure.
        """
        try:
            response = self._session.get(
                f"{JOBSTREET_API_HOST}{JOBSTREET_SEARCH_PATH}",
                params={
                    "siteKey": "SG-Main",
                    "sourcesystem": "houston",
                    "keywords": query,
                    "where": "Singapore",
                    "page": page,
                    "pageSize": page_size,
                    "locale": "en-SG",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise ScrapingException(f"JobStreet API unreachable: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise ScrapingException(f"JobStreet API request timed out: {exc}") from exc
        except requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", "?")
            text = exc.response.text[:200] if exc.response is not None else ""
            raise ScrapingException(
                f"JobStreet API returned HTTP {status}: {text}"
            ) from exc
        payload = response.json()
        if not isinstance(payload, dict):
            raise ScrapingException("JobStreet API returned a non-object JSON body")
        return payload

    def _parse_job(self, raw: Dict[str, Any]) -> Optional[JobListing]:
        """
        Map one JobStreet search card into a JobListing.

        Args:
            raw: One object from ``data``.

        Returns:
            Populated JobListing, or None when the card is not Singapore.

        Raises:
            ValueError: When the card has no id.
        """
        job_id = str(raw.get("id") or "").strip()
        if not job_id:
            raise ValueError("JobStreet job missing id")

        loc0 = (raw.get("locations") or [{}])[0] if raw.get("locations") else {}
        country = str(loc0.get("countryCode") or "").upper()
        if country and country != "SG":
            return None

        title = (raw.get("title") or "Unknown").strip() or "Unknown"
        company = (
            (raw.get("companyName") or "")
            or ((raw.get("advertiser") or {}).get("description") or "")
            or ((raw.get("employer") or {}).get("name") or "")
            or "Unknown"
        ).strip() or "Unknown"

        location_label = (loc0.get("label") or "").strip()
        location = (
            self._with_singapore(location_label) if location_label else "Singapore"
        )

        description = self._card_description(raw)
        work_mode, is_remote = self._map_work_arrangements(
            raw.get("workArrangements") or {}
        )
        job_type = self._map_work_types(raw.get("workTypes") or [], title)
        salary_range = self._parse_salary_label(raw.get("salaryLabel") or "")

        return JobListing(
            title=title,
            company=company,
            job_id=f"js-{job_id}",
            source=self.source_name,
            source_url=f"{JOBSTREET_PUBLIC_JOB_BASE}/{job_id}",
            location=location,
            work_mode=work_mode,
            is_remote=is_remote,
            job_type=job_type,
            experience_level=ExperienceLevel.NOT_SPECIFIED,
            salary_range=salary_range,
            description=description,
            requirements=self._bullet_requirements(raw.get("bulletPoints") or []),
            posted_date=self._parse_date(raw.get("listingDate")),
            scraped_at=datetime.now(),
            last_seen_at=datetime.now(),
            metadata={
                "jobstreet_id": job_id,
                "jobstreet_role_id": raw.get("roleId"),
                "jobstreet_display_type": raw.get("displayType"),
                "sg_board_overseas": False,
            },
        )

    def _card_description(self, raw: Dict[str, Any]) -> Optional[str]:
        """
        Build a search-card description from teaser and bullet points.

        Full HTML JDs are not in the v5 search payload. ``get_job_details``
        can load GraphQL ``content`` later.

        Args:
            raw: Search card object.

        Returns:
            Cleaned description or None.
        """
        parts: List[str] = []
        teaser = (raw.get("teaser") or "").strip()
        if teaser:
            parts.append(teaser)
        bullets = [
            str(item).strip()
            for item in (raw.get("bulletPoints") or [])
            if str(item).strip()
        ]
        if bullets:
            parts.append("\n".join(f"- {item}" for item in bullets[:8]))
        if not parts:
            return None
        cleaned = self._clean_description("\n\n".join(parts))
        if len(cleaned) > 10000:
            cleaned = cleaned[:10000]
        return cleaned or None

    @staticmethod
    def _bullet_requirements(bullets: List[Any]) -> List[JobRequirement]:
        """
        Map search-card bullet points to requirements.

        Args:
            bullets: JobStreet ``bulletPoints`` list.

        Returns:
            Up to eight JobRequirement rows.
        """
        requirements: List[JobRequirement] = []
        for item in bullets[:8]:
            text = str(item).strip()
            if text:
                requirements.append(
                    JobRequirement(category="Highlights", text=text[:2000])
                )
        return requirements

    @staticmethod
    def _with_singapore(text: str) -> str:
        """
        Append Singapore for display. Geography matching uses source policy.

        Args:
            text: District or region label.

        Returns:
            Location string that includes Singapore when missing.
        """
        cleaned = text.strip()
        if "singapore" in cleaned.lower():
            return cleaned
        return f"{cleaned}, Singapore"

    @staticmethod
    def _map_work_arrangements(arrangements: Dict[str, Any]) -> tuple[WorkMode, bool]:
        """
        Map JobStreet workArrangements to WorkMode.

        Args:
            arrangements: JobStreet workArrangements object.

        Returns:
            Tuple of work mode and remote flag.
        """
        labels = " ".join(
            str((item.get("label") or {}).get("text") or item)
            for item in (arrangements.get("data") or [])
            if item
        ).lower()
        if "remote" in labels:
            return WorkMode.REMOTE, True
        if "hybrid" in labels:
            return WorkMode.HYBRID, False
        return WorkMode.ON_SITE, False

    @staticmethod
    def _map_work_types(types: List[Any], title: str) -> JobType:
        """
        Map JobStreet workTypes to JobType.

        Args:
            types: JobStreet workTypes list.
            title: Job title (internship hint).

        Returns:
            Best-effort JobType.
        """
        labels = " ".join(str(item) for item in types).lower()
        title_l = title.lower()
        if "intern" in labels or "intern" in title_l:
            return JobType.INTERNSHIP
        if "part" in labels:
            return JobType.PART_TIME
        if "contract" in labels or "temp" in labels or "casual" in labels:
            return JobType.CONTRACT
        if "full" in labels:
            return JobType.FULL_TIME
        return JobType.FULL_TIME

    @staticmethod
    def _parse_salary_label(label: str) -> Optional[SalaryRange]:
        """
        Parse a JobStreet salaryLabel into SGD SalaryRange.

        Args:
            label: Display salary string.

        Returns:
            SalaryRange or None when the label is empty or unparsed.
        """
        text = (label or "").strip()
        if not text:
            return None
        match = _SALARY_RANGE_RE.search(text)
        if match:
            minimum, maximum, period_raw = match.groups()
            return SalaryRange(
                min_amount=float(minimum.replace(",", "")),
                max_amount=float(maximum.replace(",", "")),
                currency="SGD",
                period=_salary_period(period_raw),
            )
        match = _SALARY_SINGLE_RE.search(text)
        if match:
            amount, period_raw = match.groups()
            return SalaryRange(
                min_amount=float(amount.replace(",", "")),
                currency="SGD",
                period=_salary_period(period_raw),
            )
        return None

    @staticmethod
    def _parse_date(value: Any) -> Optional[datetime]:
        """
        Parse JobStreet listingDate strings.

        Args:
            value: ISO datetime string or None.

        Returns:
            Naive datetime or None.
        """
        if not value or not isinstance(value, str):
            return None
        text = value.strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        except ValueError:
            return None


def _salary_period(raw: str) -> str:
    """
    Map a JobStreet period word to SalaryRange.period.

    Args:
        raw: month, year, or hour.

    Returns:
        monthly, annual, or hourly.
    """
    token = raw.lower()
    if token.startswith("year"):
        return "annual"
    if token.startswith("hour"):
        return "hourly"
    return "monthly"


def json_string(value: str) -> str:
    """
    Quote a string for embedding in a GraphQL query.

    Args:
        value: Raw job id.

    Returns:
        Double-quoted JSON string.
    """
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
