"""
Job Raider - LinkedIn Scraper

This module implements the LinkedIn job board scraper.

Scrapes job listings from LinkedIn's public job search and individual
job detail pages to collect titles, companies, locations, descriptions,
and posting dates.

Author: Job Raider
Date: 2026-04-20
"""

from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlencode, urljoin, urlparse

from bs4 import BeautifulSoup

from ..models.job_listing import JobListing, JobListingCollection, JobSource
from .base import BaseScraper, SearchParams


class LinkedInScraper(BaseScraper):
    """
    LinkedIn job board scraper.

    Scrapes job listings from LinkedIn Jobs with rate limiting
    and anti-scraping measures. Enriches search results with
    full descriptions by fetching individual job detail pages.
    """

    # LinkedIn-specific constants
    BASE_URL = "https://www.linkedin.com"
    JOBS_SEARCH_URL = f"{BASE_URL}/jobs/search"

    # Cap on how many listings get enriched with descriptions per search.
    _MAX_ENRICH = 25

    @property
    def source_name(self) -> JobSource:
        """Return the source name."""
        return JobSource.LINKEDIN

    @property
    def base_url(self) -> str:
        """Return the base URL."""
        return self.BASE_URL

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def build_search_url(self, params: SearchParams) -> str:
        """
        Build LinkedIn search URL from parameters.

        Args:
            params: Search parameters

        Returns:
            Complete search URL
        """
        query_params = {}

        # Keywords
        if params.keywords:
            query_params["keywords"] = " ".join(params.keywords)

        # Location
        if params.location:
            query_params["location"] = params.location

        # Remote filter
        if params.remote:
            query_params["f_WT"] = "2"  # Remote

        # Experience level
        if params.experience_level:
            level_map = {
                "entry": "1",  # Entry level
                "associate": "2",  # Associate
                "mid": "3",  # Mid-Senior
                "senior": "4",  # Senior
                "director": "5",  # Director
                "executive": "6",  # Executive
            }
            if params.experience_level.lower() in level_map:
                query_params["f_E"] = level_map[params.experience_level.lower()]

        # Time posted
        if params.days_since_posted:
            time_map = {
                24: "r86400",  # Past 24 hours
                168: "r604800",  # Past week
                720: "r2592000",  # Past month
            }
            if params.days_since_posted in time_map:
                query_params["f_TPR"] = time_map[params.days_since_posted]

        # Limit results
        if params.limit:
            # LinkedIn shows 25 per page, calculate pages needed
            # Start at page 0
            query_params["start"] = 0

        # Build URL
        url = f"{self.JOBS_SEARCH_URL}?{urlencode(query_params)}"
        return url

    def search(self, params: SearchParams) -> JobListingCollection:
        """
        Search LinkedIn jobs and enrich listings with descriptions.

        Overrides the base search to merge descriptions fetched from
        individual job detail pages into the basic search results.
        Enrichment is capped at ``_MAX_ENRICH`` listings to keep
        response times reasonable.

        Args:
            params: Search parameters.

        Returns:
            JobListingCollection with enriched listings.
        """
        url = self.build_search_url(params)
        html = self._fetch_page(url)
        listings = self.parse_job_listings(html)

        enrich_count = min(len(listings), self._MAX_ENRICH)
        for i in range(enrich_count):
            listing = listings[i]
            if listing.description:
                continue
            try:
                detailed = self.get_job_details(listing.job_id)
                if detailed and detailed.description:
                    listing.description = detailed.description
            except Exception:
                pass

        return JobListingCollection(
            listings=listings,
            source=self.source_name,
            metadata={
                "search_params": params.model_dump(),
                "searched_at": datetime.now().isoformat(),
            },
        )

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse_job_listings(self, html: str) -> List[JobListing]:
        """
        Parse job listings from LinkedIn search results HTML.

        Args:
            html: Raw HTML from search results

        Returns:
            List of JobListing objects
        """
        soup = BeautifulSoup(html, "html.parser")
        listings = []

        # LinkedIn job cards
        job_cards = soup.find_all("div", class_="job-search-card")

        for card in job_cards:
            try:
                listing = self._parse_job_card(card)
                if listing:
                    listings.append(listing)
            except Exception:
                continue

        return listings

    def _parse_job_card(self, card) -> Optional[JobListing]:
        """
        Parse a single job card.

        Args:
            card: BeautifulSoup element for a job card

        Returns:
            JobListing or None if parsing fails
        """
        # Extract job title
        title_elem = card.find("h3", class_="base-search-card__title")
        title = self._extract_text_content(title_elem) or "Unknown"

        # Extract company
        company_elem = card.find("h4", class_="base-search-card__subtitle")
        company = self._extract_text_content(company_elem) or "Unknown"

        # Extract location
        location_elem = card.find("span", class_="job-search-card__location")
        location = self._extract_text_content(location_elem)

        # Extract job link
        link_elem = card.find("a", class_="base-card__full-link")
        job_url = None
        if link_elem and link_elem.get("href"):
            job_url = urljoin(self.BASE_URL, link_elem["href"])

        # Extract job ID from URL
        job_id = (
            self._extract_job_id_from_url(job_url)
            if job_url
            else self._generate_job_id(title, company)
        )

        # Extract posted date (LinkedIn uses <time> element, not <span>)
        posted_elem = card.find(
            "time", class_="job-search-card__listdate"
        ) or card.find("span", class_="job-search-card__listdate")
        if posted_elem and posted_elem.get("datetime"):
            # Prefer the machine-readable datetime attribute
            from datetime import datetime as dt

            try:
                posted_date = dt.strptime(posted_elem["datetime"], "%Y-%m-%d")
            except ValueError:
                posted_date = None
        else:
            posted_str = self._extract_text_content(posted_elem) or ""
            posted_date = self._parse_posted_date(posted_str)

        # Check if user already applied (LinkedIn shows "Applied" badge on job cards)
        card_text = card.get_text(separator=" ").lower()
        applied_badge = card.find("span", class_="job-alert-status")
        applied_state = card.find("div", class_="applied-state")
        already_applied = (
            applied_badge is not None
            or applied_state is not None
            or "applied" in card_text
        )

        return JobListing(
            title=title,
            company=company,
            job_id=job_id,
            source=self.source_name,
            source_url=job_url,
            location=location,
            posted_date=posted_date,
            already_applied=already_applied,
        )

    # ------------------------------------------------------------------
    # Job details
    # ------------------------------------------------------------------

    def get_job_details(self, job_id: str) -> Optional[JobListing]:
        """
        Fetch full job details from a LinkedIn public job view page.

        Uses lightweight ``requests`` (not Playwright) for faster
        individual page fetching.  Falls back to ``None`` on any
        failure so the caller can keep the basic listing.

        Args:
            job_id: LinkedIn job identifier.

        Returns:
            JobListing with description and metadata, or None.
        """
        import requests as req

        url = f"{self.BASE_URL}/jobs/view/{job_id}"
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            self._rate_limit_wait()
            response = req.get(url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Bail out if LinkedIn served a login / auth wall
            if soup.select_one("form.login-form, div.authwall"):
                return None

            description = self._extract_description(soup)
            if not description:
                return None

            title = self._extract_detail_title(soup)
            company = self._extract_detail_company(soup)
            location = self._extract_detail_location(soup)

            return JobListing(
                job_id=job_id,
                title=title,
                company=company,
                source=self.source_name,
                source_url=url,
                location=location,
                description=description,
            )

        except Exception:
            return None

    # ------------------------------------------------------------------
    # Detail-page extraction helpers
    # ------------------------------------------------------------------

    _DESC_SELECTORS = [
        "div.show-more-less-html__markup",
        "div.jobs-description__content",
        "div.jobs-description-content__text",
        "div.description__text",
        "section.description div",
    ]

    _TITLE_SELECTORS = [
        "h1.top-card-layout__title",
        "h1.topcard__title",
        "h1",
    ]

    _COMPANY_SELECTORS = [
        "a.topcard__org-name-link",
        "span.topcard__flavor:nth-child(1)",
        "h4.top-card-layout__second-subline a",
        "a.top-card-layout__click-target",
    ]

    _LOCATION_SELECTORS = [
        "span.topcard__flavor--bullet",
        "span.top-card-layout__second-subline span:nth-child(1)",
    ]

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract job description from a LinkedIn detail page.

        Tries multiple CSS selectors used across LinkedIn page
        versions.

        Args:
            soup: Parsed HTML of the job detail page.

        Returns:
            Description text, or None if not found.
        """
        for selector in self._DESC_SELECTORS:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(separator="\n", strip=True)
                if len(text) > 50:
                    return self._clean_description(text)
        return None

    def _extract_detail_title(self, soup: BeautifulSoup) -> str:
        """
        Extract job title from a LinkedIn detail page.

        Args:
            soup: Parsed HTML of the job detail page.

        Returns:
            Title string, or "Unknown" if not found.
        """
        for selector in self._TITLE_SELECTORS:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return "Unknown"

    def _extract_detail_company(self, soup: BeautifulSoup) -> str:
        """
        Extract company name from a LinkedIn detail page.

        Args:
            soup: Parsed HTML of the job detail page.

        Returns:
            Company name string, or "Unknown" if not found.
        """
        for selector in self._COMPANY_SELECTORS:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return "Unknown"

    def _extract_detail_location(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract location from a LinkedIn detail page.

        Args:
            soup: Parsed HTML of the job detail page.

        Returns:
            Location string, or None if not found.
        """
        for selector in self._LOCATION_SELECTORS:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return None

    # ------------------------------------------------------------------
    # URL and date helpers
    # ------------------------------------------------------------------

    def _extract_job_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract job ID from LinkedIn job URL.

        Args:
            url: Job URL

        Returns:
            Job ID or None
        """
        import re

        try:
            parsed = urlparse(url)
            path_parts = parsed.path.split("/")

            for part in path_parts:
                if "-view-" in part:
                    return part.split("-view-")[0]
                elif part.isdigit():
                    return part
                # New format: job ID at end of slug (e.g., "software-engineer-at-company-1234567890")
                elif any(c.isdigit() for c in part):
                    numbers = re.findall(r"\d+", part)
                    if numbers:
                        return numbers[-1]

        except Exception:
            pass

        return None

    def _parse_posted_date(self, posted_str: str) -> Optional[datetime]:
        """
        Parse a LinkedIn posted-date string into a datetime.

        Handles relative formats ("2 days ago", "Just posted"),
        and absolute date formats ("April 20, 2026").

        Args:
            posted_str: Raw posted date text from the card.

        Returns:
            Approximate datetime, or None if unparseable.
        """
        if not posted_str:
            return None

        posted_str = posted_str.strip()
        lower = posted_str.lower()

        # "Just posted", "Just now", "Recently" -> today
        if lower in ("just posted", "just now", "recently"):
            return datetime.now()

        # Relative "X unit(s) ago"
        if "ago" in lower:
            try:
                if "minute" in lower:
                    mins = int(lower.split()[0])
                    return datetime.now() - timedelta(minutes=mins)
                elif "hour" in lower:
                    hours = int(lower.split()[0])
                    return datetime.now() - timedelta(hours=hours)
                elif "day" in lower:
                    days = int(lower.split()[0])
                    return datetime.now() - timedelta(days=days)
                elif "week" in lower:
                    weeks = int(lower.split()[0])
                    return datetime.now() - timedelta(weeks=weeks)
                elif "month" in lower:
                    months = int(lower.split()[0])
                    return datetime.now() - timedelta(days=months * 30)
            except (ValueError, IndexError):
                pass

        # Absolute date formats
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(posted_str, fmt)
            except ValueError:
                continue

        return None
