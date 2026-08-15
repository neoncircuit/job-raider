"""
Job Raider - MyCareersFuture scraper

Public JSON HTTP adapter for Singapore's MyCareersFuture portal.
No login, no Playwright. Cap pages aggressively; disable with MCF_ENABLED=0.

Author: Job Raider
Date: 2026-08-14
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
    Skill,
    WorkMode,
)
from ..utils.source_geography import singapore_board_applies
from .base import BaseScraper, ScrapingException, SearchParams

logger = logging.getLogger(__name__)

MCF_API_BASE = "https://api.mycareersfuture.gov.sg/v2"
MCF_PUBLIC_JOB_BASE = "https://www.mycareersfuture.gov.sg/job"

# Careful caps: never unbounded dump of the portal inventory.
DEFAULT_PAGE_SIZE = 20
MAX_PAGES = 3
MAX_RESULTS = 60


def mcf_enabled() -> bool:
    """
    Return whether the MyCareersFuture adapter is enabled.

    Args:
        None.

    Returns:
        True unless ``MCF_ENABLED`` is set to a falsey value
        (``0``, ``false``, ``no``, ``off``).
    """
    raw = os.environ.get("MCF_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


class MyCareersFutureScraper(BaseScraper):
    """
    Search MyCareersFuture via its public JSON jobs endpoint.

    Uses ``api.mycareersfuture.gov.sg/v2/jobs``. This is not a formally
    documented developer API; treat as personal-use tooling with rate
    limits and hard result caps.
    """

    def __init__(self, **kwargs: Any):
        """
        Initialize the MCF scraper.

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
                "User-Agent": "JobRaider/1.0 (personal-use; MyCareersFuture adapter)",
            }
        )

    @property
    def source_name(self) -> JobSource:
        """Return the JobSource enum for MyCareersFuture."""
        return JobSource.MYCAREERSFUTURE

    @property
    def base_url(self) -> str:
        """Return the MCF API base URL."""
        return MCF_API_BASE

    def build_search_url(self, params: SearchParams) -> str:
        """
        Not used for JSON API scrapers.

        Args:
            params: Search parameters (ignored).

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            "MyCareersFutureScraper uses search() directly, not build_search_url()"
        )

    def parse_job_listings(self, html: str) -> List[JobListing]:
        """
        Not used for JSON API scrapers.

        Args:
            html: Raw HTML (ignored).

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            "MyCareersFutureScraper parses JSON responses, not HTML"
        )

    def search(self, params: SearchParams) -> JobListingCollection:
        """
        Search MyCareersFuture for jobs matching the keywords.

        Args:
            params: Keywords, optional location, and result limit.

        Returns:
            JobListingCollection of mapped MCF listings.

        Raises:
            ScrapingException: When the adapter is disabled or the HTTP call fails.
        """
        if not mcf_enabled():
            raise ScrapingException(
                "MyCareersFuture adapter is disabled (MCF_ENABLED=0)"
            )

        if not singapore_board_applies(params.location, remote=params.remote):
            logger.info(
                "Skipping MyCareersFuture: location %r is outside Singapore/remote",
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

        for page in range(max_pages):
            if len(listings) >= limit:
                break
            self._rate_limit_wait()
            payload = self._fetch_page(query=query, page=page, page_size=page_size)
            pages_fetched += 1
            if total is None:
                total = payload.get("total")
            results = payload.get("results") or []
            if not results:
                break
            for raw in results:
                if len(listings) >= limit:
                    break
                try:
                    listings.append(self._parse_job(raw))
                except Exception as exc:  # noqa: BLE001 — skip bad rows
                    logger.warning("Skipping MCF job parse error: %s", exc)

        logger.info(
            "MyCareersFuture returned %d jobs for query=%r (total=%s)",
            len(listings),
            query,
            total,
        )
        return JobListingCollection(
            listings=listings,
            source=self.source_name,
            metadata={
                "search_params": params.model_dump(),
                "mcf_query": query,
                "searched_at": datetime.now().isoformat(),
                "total_results": total,
                "pages_fetched": pages_fetched,
            },
        )

    def get_job_details(self, job_id: str) -> Optional[JobListing]:
        """
        Fetch one job by MCF uuid when available.

        Args:
            job_id: MCF job uuid (or ``mcf-<uuid>`` prefixed id).

        Returns:
            JobListing or None when not found / disabled.
        """
        if not mcf_enabled():
            return None
        uuid = job_id.removeprefix("mcf-")
        self._rate_limit_wait()
        try:
            response = self._session.get(
                f"{MCF_API_BASE}/jobs/{uuid}",
                timeout=self.timeout,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.warning("MCF job-details failed for %s: %s", job_id, exc)
            return None
        body = response.json()
        # Detail endpoint may return the job object directly or wrapped.
        raw = body.get("result") or body.get("data") or body
        if not isinstance(raw, dict) or not raw.get("uuid"):
            return None
        return self._parse_job(raw)

    def _fetch_page(self, *, query: str, page: int, page_size: int) -> Dict[str, Any]:
        """
        Fetch one page of MCF search results.

        Args:
            query: Keyword search string.
            page: Zero-based page index.
            page_size: Results per page.

        Returns:
            Parsed JSON body.

        Raises:
            ScrapingException: On HTTP or network failure.
        """
        try:
            response = self._session.get(
                f"{MCF_API_BASE}/jobs",
                params={
                    "search": query,
                    "limit": page_size,
                    "page": page,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise ScrapingException(f"MyCareersFuture API unreachable: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise ScrapingException(
                f"MyCareersFuture API request timed out: {exc}"
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", "?")
            text = exc.response.text[:200] if exc.response is not None else ""
            raise ScrapingException(
                f"MyCareersFuture API returned HTTP {status}: {text}"
            ) from exc
        return response.json()

    def _parse_job(self, raw: Dict[str, Any]) -> JobListing:
        """
        Map one MCF JSON job into a JobListing.

        Args:
            raw: One object from ``results``.

        Returns:
            Populated JobListing.
        """
        uuid = str(raw.get("uuid") or "")
        if not uuid:
            raise ValueError("MCF job missing uuid")

        metadata = raw.get("metadata") or {}
        company_obj = raw.get("postedCompany") or {}
        title = (raw.get("title") or "Unknown").strip() or "Unknown"
        company = (company_obj.get("name") or "Unknown").strip() or "Unknown"

        source_url = metadata.get("jobDetailsUrl")
        if not source_url:
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "job"
            source_url = f"{MCF_PUBLIC_JOB_BASE}/{slug}/{uuid}"

        address = raw.get("address") or {}
        location = self._format_location(address)
        description = raw.get("description") or ""
        other_req = (raw.get("otherRequirements") or "").strip()
        description_parts: List[str] = []
        if description:
            cleaned = self._clean_description(description)
            if cleaned:
                description_parts.append(cleaned)
        if other_req:
            cleaned_req = self._clean_description(other_req)
            if cleaned_req:
                description_parts.append("Requirements:\n\n" + cleaned_req)
        description = "\n\n".join(description_parts)
        if description:
            description = self._clean_description(description)
        if len(description) > 10000:
            description = description[:10000]

        requirements: List[JobRequirement] = []
        if other_req:
            cleaned = self._clean_description(other_req)
            if cleaned:
                requirements.append(
                    JobRequirement(category="Requirements", text=cleaned[:2000])
                )

        skills = [
            Skill(name=item["skill"], is_required=bool(item.get("isKeySkill")))
            for item in (raw.get("skills") or [])
            if isinstance(item, dict) and item.get("skill")
        ][:30]

        salary_range = self._parse_salary(raw.get("salary") or {})
        job_type = self._map_employment_types(raw.get("employmentTypes") or [])
        experience_level = self._map_position_levels(raw.get("positionLevels") or [])
        years = raw.get("minimumYearsExperience")
        if experience_level is None and isinstance(years, (int, float)):
            experience_level = self._years_to_level(float(years))
        if job_type is None:
            job_type = JobType.FULL_TIME
        if experience_level is None:
            experience_level = ExperienceLevel.NOT_SPECIFIED

        posted_date = self._parse_date(
            metadata.get("newPostingDate") or metadata.get("originalPostingDate")
        )
        application_deadline = self._parse_date(metadata.get("expiryDate"))

        work_mode = WorkMode.ON_SITE
        fwa = raw.get("flexibleWorkArrangements") or []
        fwa_text = " ".join(
            str(item.get("flexibleWorkArrangement") or item) for item in fwa if item
        ).lower()
        is_remote = "remote" in fwa_text or "work from home" in fwa_text
        if is_remote:
            work_mode = WorkMode.REMOTE
        elif "hybrid" in fwa_text:
            work_mode = WorkMode.HYBRID

        job_post_id = metadata.get("jobPostId")
        return JobListing(
            title=title,
            company=company,
            job_id=f"mcf-{uuid}",
            source=self.source_name,
            source_url=source_url,
            location=location or "Singapore",
            work_mode=work_mode,
            is_remote=is_remote,
            job_type=job_type,
            experience_level=experience_level,
            salary_range=salary_range,
            description=description or None,
            requirements=requirements,
            skills=skills,
            posted_date=posted_date,
            application_deadline=application_deadline,
            scraped_at=datetime.now(),
            last_seen_at=datetime.now(),
            metadata={
                "mcf_uuid": uuid,
                "mcf_job_post_id": job_post_id,
                "mcf_status": (raw.get("status") or {}).get("jobStatus"),
                "mcf_categories": [
                    c.get("category")
                    for c in (raw.get("categories") or [])
                    if isinstance(c, dict) and c.get("category")
                ],
                "mcf_uen": company_obj.get("uen"),
                "sg_board_overseas": bool(address.get("isOverseas")),
            },
        )

    @staticmethod
    def _with_singapore(text: str) -> str:
        """
        Append Singapore for display. Geography matching uses source
        policy (Singapore-scoped boards), not this suffix.

        MCF districts are local names (``Islandwide``, ``D01 Marina...``).

        Args:
            text: District or street location.

        Returns:
            Location string that includes Singapore when missing.
        """
        cleaned = text.strip()
        if "singapore" in cleaned.lower():
            return cleaned
        return f"{cleaned}, Singapore"

    @staticmethod
    def _format_location(address: Dict[str, Any]) -> Optional[str]:
        """
        Build a short Singapore location string from MCF address.

        Args:
            address: MCF address object.

        Returns:
            Location string or None.
        """
        if address.get("isOverseas"):
            country = address.get("overseasCountry")
            return str(country) if country else "Overseas"
        districts = address.get("districts") or []
        if districts and isinstance(districts[0], dict):
            loc = districts[0].get("location")
            if loc:
                return MyCareersFutureScraper._with_singapore(str(loc))
        parts = [
            p
            for p in [
                address.get("building"),
                address.get("street"),
                address.get("postalCode"),
            ]
            if p
        ]
        if parts:
            return MyCareersFutureScraper._with_singapore(
                ", ".join(str(p) for p in parts)
            )
        return None

    @staticmethod
    def _parse_salary(salary: Dict[str, Any]) -> Optional[SalaryRange]:
        """
        Map MCF salary object to SalaryRange (SGD).

        Args:
            salary: MCF salary dict.

        Returns:
            SalaryRange or None when empty.
        """
        minimum = salary.get("minimum")
        maximum = salary.get("maximum")
        if minimum is None and maximum is None:
            return None
        salary_type = ((salary.get("type") or {}).get("salaryType") or "").lower()
        period = "monthly"
        if "annual" in salary_type or "year" in salary_type:
            period = "annual"
        elif "hour" in salary_type:
            period = "hourly"
        return SalaryRange(
            min_amount=float(minimum) if minimum is not None else None,
            max_amount=float(maximum) if maximum is not None else None,
            currency="SGD",
            period=period,
        )

    @staticmethod
    def _map_employment_types(types: List[Any]) -> Optional[JobType]:
        """
        Map MCF employment type list to JobType.

        Args:
            types: MCF employmentTypes array.

        Returns:
            Best-effort JobType or None.
        """
        labels = " ".join(
            str(item.get("employmentType") or "")
            for item in types
            if isinstance(item, dict)
        ).lower()
        if "intern" in labels:
            return JobType.INTERNSHIP
        if "part" in labels:
            return JobType.PART_TIME
        if "contract" in labels or "temporary" in labels:
            return JobType.CONTRACT
        if "full" in labels or "permanent" in labels:
            return JobType.FULL_TIME
        return None

    @staticmethod
    def _map_position_levels(levels: List[Any]) -> Optional[ExperienceLevel]:
        """
        Map MCF position levels to ExperienceLevel.

        Args:
            levels: MCF positionLevels array.

        Returns:
            ExperienceLevel or None.
        """
        labels = " ".join(
            str(item.get("position") or "") for item in levels if isinstance(item, dict)
        ).lower()
        if "intern" in labels:
            return ExperienceLevel.INTERNSHIP
        if "senior management" in labels or "director" in labels:
            return ExperienceLevel.EXECUTIVE
        if "senior manager" in labels or "manager" in labels:
            return ExperienceLevel.LEAD
        if "senior" in labels:
            return ExperienceLevel.SENIOR
        if "professional" in labels or "executive" in labels:
            return ExperienceLevel.MID
        if "non-executive" in labels or "junior" in labels:
            return ExperienceLevel.ENTRY
        return None

    @staticmethod
    def _years_to_level(years: float) -> ExperienceLevel:
        """
        Infer experience level from minimum years.

        Args:
            years: Minimum years of experience.

        Returns:
            ExperienceLevel band.
        """
        if years < 1:
            return ExperienceLevel.ENTRY
        if years < 3:
            return ExperienceLevel.MID
        if years < 7:
            return ExperienceLevel.SENIOR
        return ExperienceLevel.LEAD

    @staticmethod
    def _parse_date(value: Any) -> Optional[datetime]:
        """
        Parse MCF date strings (``YYYY-MM-DD`` or ISO datetime).

        Args:
            value: Raw date string or None.

        Returns:
            datetime or None.
        """
        if not value or not isinstance(value, str):
            return None
        text = value.strip()
        try:
            if len(text) == 10 and text[4] == "-":
                return datetime.fromisoformat(text)
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        except ValueError:
            return None
