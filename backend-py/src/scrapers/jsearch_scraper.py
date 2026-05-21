"""
Job Raider - JSearch API Scraper

Scrapes job listings via the JSearch API (RapidAPI), which aggregates
results from Google for Jobs covering Indeed, Glassdoor, Jobstreet,
and 50+ other job boards.

Author: Job Raider
Date: 2026-04-25
"""

import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from .base import (
    BaseScraper,
    SearchParams,
    ScraperError,
    ScrapingException,
)
from ..models.job_listing import (
    ExperienceLevel,
    JobListing,
    JobListingCollection,
    JobSource,
    JobType,
    SalaryRange,
    WorkMode,
)

logger = logging.getLogger(__name__)

JSEARCH_API_BASE = "https://jsearch.p.rapidapi.com"


class JSearchScraper(BaseScraper):
    """
    Job scraper using the JSearch API via RapidAPI.

    Aggregates listings from Google for Jobs, providing results from
    Indeed, Glassdoor, Jobstreet, and many other boards without
    requiring individual Playwright scrapers.

    Requires the RAPIDAPI_KEY environment variable.
    """

    def __init__(self, **kwargs):
        """Initialize the JSearch scraper.

        Args:
            **kwargs: Arguments forwarded to BaseScraper.__init__.
        """
        super().__init__(**kwargs)
        self._api_key = os.environ.get("RAPIDAPI_KEY", "")
        self._session = requests.Session()
        self._session.headers.update({
            "X-RapidAPI-Key": self._api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        })

    @property
    def source_name(self) -> JobSource:
        """Return the JobSource enum value for this scraper."""
        return JobSource.JSEARCH

    @property
    def base_url(self) -> str:
        """Return the base URL for the JSearch API."""
        return JSEARCH_API_BASE

    def build_search_url(self, params: SearchParams) -> str:
        """Not used for API-based scrapers. Use search() instead.

        Args:
            params: Search parameters (ignored).

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("JSearchScraper uses search() directly, not build_search_url()")

    def parse_job_listings(self, html: str) -> List[JobListing]:
        """Not used for API-based scrapers. JSearch returns JSON.

        Args:
            html: Raw HTML (ignored).

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("JSearchScraper parses JSON responses, not HTML")

    def search(self, params: SearchParams) -> JobListingCollection:
        """Search for jobs via the JSearch API.

        Args:
            params: Search parameters including keywords, location, and filters.

        Returns:
            JobListingCollection with parsed results.

        Raises:
            ScrapingException: If the API call fails or returns an error.
            ScraperError: If the RAPIDAPI_KEY is not configured.
        """
        if not self._api_key:
            raise ScraperError("RAPIDAPI_KEY environment variable not set")

        query = self._build_query(params)
        request_params = self._build_request_params(params, query)

        try:
            response = self._session.get(
                f"{JSEARCH_API_BASE}/search",
                params=request_params,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise ScrapingException(f"JSearch API unreachable: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise ScrapingException(f"JSearch API request timed out: {exc}") from exc
        except requests.exceptions.HTTPError as exc:
            raise ScrapingException(
                f"JSearch API returned HTTP {response.status_code}: {response.text[:200]}"
            ) from exc

        body = response.json()
        if body.get("status") == "ERROR":
            raise ScrapingException(
                f"JSearch API error: {body.get('error', 'Unknown error')}"
            )

        raw_jobs = body.get("data", [])
        listings = [self._parse_job(job) for job in raw_jobs[:params.limit]]

        logger.info(f"JSearch returned {len(listings)} jobs for query: {query}")

        return JobListingCollection(
            listings=listings,
            source=self.source_name,
            metadata={
                "search_params": params.model_dump(),
                "jsearch_query": query,
                "searched_at": datetime.now().isoformat(),
                "total_results": len(raw_jobs),
            },
        )

    def get_job_details(self, job_id: str) -> Optional[JobListing]:
        """Fetch full details for a specific job via the JSearch /job-details endpoint.

        Args:
            job_id: The JSearch job_id string.

        Returns:
            Complete JobListing or None if not found.
        """
        if not self._api_key:
            raise ScraperError("RAPIDAPI_KEY environment variable not set")

        try:
            response = self._session.get(
                f"{JSEARCH_API_BASE}/job-details",
                params={"job_id": job_id, "country": "us"},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.warning(f"JSearch job-details failed for {job_id}: {exc}")
            return None

        body = response.json()
        if body.get("status") == "ERROR" or not body.get("data"):
            return None

        jobs = body["data"]
        if jobs and len(jobs) > 0:
            return self._parse_job(jobs[0])
        return None

    def _build_query(self, params: SearchParams) -> str:
        """Build the JSearch query string from search parameters.

        JSearch expects a single query string like "python developer in Singapore".

        Args:
            params: Search parameters.

        Returns:
            Formatted query string.
        """
        query_parts = " ".join(params.keywords)
        if params.location:
            query_parts += f" in {params.location}"
        return query_parts

    def _build_request_params(self, params: SearchParams, query: str) -> Dict[str, Any]:
        """Build the JSearch API request parameters.

        Args:
            params: Search parameters.
            query: Formatted query string.

        Returns:
            Dictionary of query parameters for the JSearch API.
        """
        request_params: Dict[str, Any] = {
            "query": query,
            "page": 1,
            "num_pages": 1,
        }

        if params.remote:
            request_params["work_from_home"] = "true"

        if params.days_since_posted:
            date_map = {
                1: "today",
                7: "week",
                30: "month",
            }
            closest = min(date_map.keys(), key=lambda d: abs(d - params.days_since_posted))
            request_params["date_posted"] = date_map[closest]

        return request_params

    def _parse_job(self, raw: Dict[str, Any]) -> JobListing:
        """Parse a single JSearch job result into a JobListing.

        Args:
            raw: Raw job data dict from JSearch API response.

        Returns:
            Populated JobListing model instance.
        """
        title = raw.get("job_title", "Unknown")
        company = raw.get("employer_name", "Unknown")
        job_id = raw.get("job_id", self._generate_job_id(title, company))

        # Location
        location_parts = [
            p for p in [
                raw.get("job_city"),
                raw.get("job_state"),
                raw.get("job_country"),
            ] if p
        ]
        location = ", ".join(location_parts) if location_parts else None

        # Source URL
        source_url = raw.get("job_apply_link") or raw.get("job_google_link") or raw.get("job_link")

        # Salary
        salary = None
        min_sal = raw.get("job_min_salary")
        max_sal = raw.get("job_max_salary")
        if min_sal or max_sal:
            salary = SalaryRange(
                min_amount=float(min_sal) if min_sal else None,
                max_amount=float(max_sal) if max_sal else None,
                currency=raw.get("job_salary_currency", "USD") or "USD",
                period=self._map_salary_period(raw.get("job_salary_period")),
            )

        # Posted date
        posted_date = None
        posted_str = raw.get("job_posted_at_datetime")
        if posted_str:
            try:
                posted_date = datetime.fromisoformat(posted_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Work mode and remote
        is_remote = raw.get("job_is_remote", False) or False
        work_mode = WorkMode.REMOTE if is_remote else WorkMode.ON_SITE

        # Job type
        job_type_str = (raw.get("job_employment_type") or "").lower()
        job_type = self._map_job_type(job_type_str)

        # Experience level
        exp_keywords = (raw.get("job_required_experience", {}) or {}).get("required_experience_in_months")
        experience_level = self._infer_experience_level(
            raw.get("job_title", ""),
            exp_keywords,
        )

        # Description
        description = raw.get("job_description", "")
        if description and len(description) > 10000:
            description = description[:10000]
        if description:
            description = self._clean_description(description)

        return JobListing(
            title=title,
            company=company,
            job_id=str(job_id),
            source=self.source_name,
            source_url=source_url,
            location=location,
            work_mode=work_mode,
            is_remote=is_remote,
            job_type=job_type,
            experience_level=experience_level,
            salary_range=salary,
            description=description,
            posted_date=posted_date,
            scraped_at=datetime.now(),
            metadata={
                "employer_logo": raw.get("employer_logo"),
                "job_publisher": raw.get("job_publisher"),
                "job_apply_quality_score": raw.get("job_apply_quality_score"),
                "job_required_skills": raw.get("job_required_skills"),
                "job_highlights": raw.get("job_highlights"),
                "job_benefits": raw.get("job_benefits"),
                "job_google_link": raw.get("job_google_link"),
                "job_onet_soc": raw.get("job_onet_soc"),
                "job_naics_code": raw.get("job_naics_code"),
            },
        )

    @staticmethod
    def _map_salary_period(period: Optional[str]) -> str:
        """Map JSearch salary period to our SalaryRange period format.

        Args:
            period: JSearch salary period string (e.g. "YEAR", "MONTH", "HOUR").

        Returns:
            Normalized period string.
        """
        if not period:
            return "annual"
        period_lower = period.lower()
        if "year" in period_lower or "annual" in period_lower:
            return "annual"
        if "month" in period_lower:
            return "monthly"
        if "hour" in period_lower:
            return "hourly"
        if "week" in period_lower:
            return "weekly"
        return period_lower

    @staticmethod
    def _map_job_type(employment_type: str) -> JobType:
        """Map JSearch employment type string to our JobType enum.

        Args:
            employment_type: Employment type string from JSearch (e.g. "FULL_TIME").

        Returns:
            Corresponding JobType enum value.
        """
        mapping = {
            "full_time": JobType.FULL_TIME,
            "fulltime": JobType.FULL_TIME,
            "full-time": JobType.FULL_TIME,
            "part_time": JobType.PART_TIME,
            "parttime": JobType.PART_TIME,
            "part-time": JobType.PART_TIME,
            "contract": JobType.CONTRACT,
            "internship": JobType.INTERNSHIP,
            "temporary": JobType.TEMPORARY,
            "freelance": JobType.FREELANCE,
        }
        return mapping.get(employment_type.lower(), JobType.FULL_TIME)

    @staticmethod
    def _infer_experience_level(title: str, required_months: Optional[Any]) -> ExperienceLevel:
        """Infer experience level from job title and required experience.

        Args:
            title: Job title string.
            required_months: Required experience in months (from JSearch), if available.

        Returns:
            Estimated ExperienceLevel enum value.
        """
        title_lower = title.lower()

        if any(kw in title_lower for kw in ("intern", "apprentice")):
            return ExperienceLevel.INTERNSHIP
        if any(kw in title_lower for kw in ("junior", "entry", "graduate", "fresh")):
            return ExperienceLevel.ENTRY
        if any(kw in title_lower for kw in ("senior", "lead", "principal", "staff")):
            return ExperienceLevel.SENIOR
        if any(kw in title_lower for kw in ("director", "vp", "head of", "chief")):
            return ExperienceLevel.EXECUTIVE

        # Fall back to required_months heuristic
        if required_months is not None:
            try:
                months = int(required_months)
                if months <= 12:
                    return ExperienceLevel.ENTRY
                if months <= 36:
                    return ExperienceLevel.MID
                if months <= 72:
                    return ExperienceLevel.SENIOR
                return ExperienceLevel.LEAD
            except (ValueError, TypeError):
                pass

        return ExperienceLevel.NOT_SPECIFIED
