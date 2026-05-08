"""
Job Raider - Base Scraper

This module provides the abstract base class for job board scrapers.
All scrapers should inherit from this class to ensure a consistent interface.

Author: Job Raider
Date: 2026-04-20
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel
import time
import random

from ..models.job_listing import JobListing, JobListingCollection, JobSource
from ..extractors.jd_extractor import JDExtractor, ExtractionResult


class ScraperError(Exception):
    """Base exception for scraper errors."""
    pass


class RateLimitError(ScraperError):
    """Raised when rate limit is hit."""
    pass


class AuthenticationError(ScraperError):
    """Raised when authentication fails."""
    pass


class ScrapingException(ScraperError):
    """Raised when scraping fails for other reasons."""
    pass


class SearchParams(BaseModel):
    """Parameters for job search."""
    keywords: List[str]
    location: Optional[str] = None
    experience_level: Optional[str] = None
    remote: bool = False
    days_since_posted: Optional[int] = None  # e.g., 7, 30
    limit: int = 100


class BaseScraper(ABC):
    """
    Abstract base class for job board scrapers.

    All scrapers must implement these methods to ensure consistent
    behavior across different job boards.
    """

    def __init__(
        self,
        rate_limit: float = 1.0,
        max_retries: int = 3,
        timeout: int = 30,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize the base scraper.

        Args:
            rate_limit: Minimum seconds between requests
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            user_agent: Custom user agent string
        """
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.timeout = timeout
        self.user_agent = user_agent or self._default_user_agent()

        self._last_request_time = 0
        self._request_count = 0
        self._jd_extractor = JDExtractor()

    @property
    @abstractmethod
    def source_name(self) -> JobSource:
        """Return the JobSource enum value for this scraper."""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Return the base URL for the job board."""
        pass

    @abstractmethod
    def build_search_url(self, params: SearchParams) -> str:
        """
        Build the search URL for given parameters.

        Args:
            params: Search parameters

        Returns:
            Complete URL for the search
        """
        pass

    @abstractmethod
    def parse_job_listings(self, html: str) -> List[JobListing]:
        """
        Parse job listings from HTML response.

        Args:
            html: Raw HTML from search results

        Returns:
            List of JobListing objects
        """
        pass

    @abstractmethod
    def get_job_details(self, job_id: str) -> Optional[JobListing]:
        """
        Get detailed information for a specific job.

        Args:
            job_id: Job identifier

        Returns:
            Complete JobListing or None if not found
        """
        pass

    def search(self, params: SearchParams) -> JobListingCollection:
        """
        Search for jobs matching the given parameters.

        Args:
            params: Search parameters

        Returns:
            JobListingCollection with results
        """
        url = self.build_search_url(params)

        try:
            html = self._fetch_page(url)
            listings = self.parse_job_listings(html)

            # Enrich listings with details if needed
            enriched_listings = []
            for listing in listings:
                try:
                    detailed = self.get_job_details(listing.job_id)
                    enriched_listings.append(detailed or listing)
                except Exception as e:
                    # Use basic listing if detail fetch fails
                    enriched_listings.append(listing)

            return JobListingCollection(
                listings=enriched_listings,
                source=self.source_name,
                metadata={
                    "search_params": params.model_dump(),
                    "searched_at": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            raise ScrapingException(f"Search failed: {str(e)}")

    def _fetch_page(self, url: str) -> str:
        """
        Fetch a page from the given URL.

        Handles rate limiting, retries, and user agent.

        Args:
            url: URL to fetch

        Returns:
            HTML content

        Raises:
            ScrapingException: If fetch fails after retries
        """
        self._rate_limit_wait()

        for attempt in range(self.max_retries):
            try:
                import requests
                from playwright.sync_api import sync_playwright

                # Use Playwright for JavaScript-heavy sites
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()

                    # Set user agent
                    page.set_extra_http_headers({
                        "User-Agent": self.user_agent
                    })

                    # Navigate and wait for content
                    page.goto(url, timeout=self.timeout * 1000)
                    page.wait_for_timeout(2000)  # Wait for JS to render

                    html = page.content()
                    browser.close()

                    self._request_count += 1
                    self._last_request_time = time.time()

                    return html

            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 5  # Exponential backoff
                    time.sleep(wait_time)
                    continue
                else:
                    raise ScrapingException(f"Failed to fetch page after {self.max_retries} attempts: {str(e)}")

    def _rate_limit_wait(self) -> None:
        """Wait to respect rate limit between requests."""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.rate_limit:
                time.sleep(self.rate_limit - elapsed + random.uniform(0, 0.5))

    def _default_user_agent(self) -> str:
        """Return a default user agent string."""
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def _generate_job_id(self, *args: Any) -> str:
        """
        Generate a unique job ID from scraping data.

        Args:
            *args: Components to include in ID

        Returns:
            Unique job ID
        """
        import hashlib
        combined = "|".join(str(arg) for arg in args)
        return hashlib.md5(combined.encode()).hexdigest()[:12]

    def _extract_text_content(self, element) -> str:
        """
        Safely extract text from a BeautifulSoup element.

        Args:
            element: BeautifulSoup element

        Returns:
            Text content or empty string
        """
        if element is None:
            return ""
        return element.get_text(strip=True)

    @property
    def stats(self) -> Dict[str, Any]:
        """Return scraping statistics."""
        return {
            "request_count": self._request_count,
            "last_request_time": self._last_request_time,
            "rate_limit": self.rate_limit,
        }
