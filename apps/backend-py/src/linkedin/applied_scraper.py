"""
Job Raider - LinkedIn Applied Jobs Scraper

Scrapes the LinkedIn "My Jobs > Applied" page to build a canonical
list of jobs the user has already applied to.

Author: Job Raider
Date: 2026-05-04
"""

import random
import re
import time
from typing import Any, Optional, Set

from playwright.sync_api import Page

from ..submission.applied_tracker import AppliedJobsTracker
from ..utils.logger import Components, get_logger
from .session import LinkedInSession


class LinkedInAppliedScraper:
    """
    Scrape the LinkedIn applied jobs page for canonical applied-job tracking.

    Uses an authenticated LinkedIn session to navigate to the applied jobs
    page and extract job IDs from the listing.
    """

    APPLIED_JOBS_URL = "https://www.linkedin.com/jobs/cv/application/"

    # Selectors for the applied jobs page (multiple fallbacks for resilience)
    JOB_CARD_SELECTORS = [
        "div.job-card-container",
        "div.jobs-saved-job-card",
        "li.jobs-unified-top-card",
        "div.application-entity",
    ]

    JOB_LINK_SELECTORS = [
        "a.job-card-container__link",
        "a[data-control-name*='job_card']",
        "a[href*='/jobs/view/']",
    ]

    def __init__(self, session: LinkedInSession) -> None:
        """
        Initialize the applied jobs scraper.

        Args:
            session: An authenticated LinkedIn session.
        """
        self.session = session
        self.logger = get_logger(Components.SCRAPERS)

    def get_applied_job_ids(self, max_pages: int = 10) -> Set[str]:
        """
        Scrape all applied job IDs from the Applied Jobs page.

        Args:
            max_pages: Maximum number of pages to scrape.

        Returns:
            Set of LinkedIn job IDs that have been applied to.
        """
        if not self.session.is_authenticated:
            self.logger.error(
                "Session is not authenticated. Call session.start() first."
            )
            return set()

        applied_ids: Set[str] = set()
        page = self.session.get_page()

        try:
            page.goto(self.APPLIED_JOBS_URL, timeout=30000)
            time.sleep(random.uniform(2, 4))

            for page_num in range(max_pages):
                self.logger.info(f"Scraping applied jobs page {page_num + 1}")

                new_ids = self._parse_applied_page(page)
                applied_ids.update(new_ids)

                if not self._has_next_page(page):
                    break

                self._scroll_and_load_more(page)
                time.sleep(random.uniform(2, 5))

            self.logger.info(f"Found {len(applied_ids)} applied job IDs")

        except Exception as e:
            self.logger.error(f"Failed to scrape applied jobs: {e}")

        return applied_ids

    def sync_with_tracker(self, tracker: AppliedJobsTracker) -> int:
        """
        Scrape applied jobs and sync with the local tracker.

        Args:
            tracker: The AppliedJobsTracker to sync with.

        Returns:
            Number of newly discovered applied job IDs.
        """
        job_ids = self.get_applied_job_ids()
        return tracker.sync_ids(job_ids, source="linkedin_applied_page")

    def _parse_applied_page(self, page: Page) -> Set[str]:
        """
        Parse job IDs from the currently visible applied jobs.

        Args:
            page: Playwright page with applied jobs loaded.

        Returns:
            Set of job IDs found on this page.
        """
        job_ids: Set[str] = set()

        # Try each card selector
        for card_selector in self.JOB_CARD_SELECTORS:
            cards = page.query_selector_all(card_selector)
            if cards:
                for card in cards:
                    job_id = self._extract_job_id_from_card(card, page)
                    if job_id:
                        job_ids.add(job_id)
                break

        # Fallback: scan all links for job view URLs
        if not job_ids:
            links = page.query_selector_all("a[href*='/jobs/view/']")
            for link in links:
                href = link.get_attribute("href") or ""
                job_id = self._extract_job_id_from_url(href)
                if job_id:
                    job_ids.add(job_id)

        return job_ids

    def _extract_job_id_from_card(self, card: Any, page: Page) -> Optional[str]:
        """
        Extract a job ID from a job card element.

        Args:
            card: Playwright element handle for the job card.
            page: The page for querying within the card.

        Returns:
            Job ID string, or None if not found.
        """
        for link_selector in self.JOB_LINK_SELECTORS:
            link = card.query_selector(link_selector)
            if link:
                href = link.get_attribute("href") or ""
                job_id = self._extract_job_id_from_url(href)
                if job_id:
                    return job_id

        # Fallback: search for any link with job ID in the card
        links = card.query_selector_all("a")
        for link in links:
            href = link.get_attribute("href") or ""
            job_id = self._extract_job_id_from_url(href)
            if job_id:
                return job_id

        return None

    def _extract_job_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract LinkedIn job ID from a URL.

        Args:
            url: URL containing a LinkedIn job ID.

        Returns:
            Job ID string, or None if not found.
        """
        match = re.search(r"/jobs/view/(\d+)", url)
        if match:
            return match.group(1)
        return None

    def _has_next_page(self, page: Page) -> bool:
        """
        Check if there are more applied jobs to load.

        Args:
            page: Current page.

        Returns:
            True if more pages appear to be available.
        """
        next_selectors = [
            "button[aria-label='Next']",
            "button[aria-label='Load more']",
            "button.jobs-pagination__button--next",
            "button.artdeco-pagination__button--next",
        ]
        for selector in next_selectors:
            btn = page.query_selector(selector)
            if btn and btn.is_enabled():
                return True
        return False

    def _scroll_and_load_more(self, page: Page) -> None:
        """
        Scroll down and click load more if available.

        Args:
            page: Current page.
        """
        # Scroll to bottom to trigger lazy loading
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(1, 2))

        # Try to click next/load more
        next_selectors = [
            "button[aria-label='Next']",
            "button[aria-label='Load more']",
            "button.jobs-pagination__button--next",
            "button.artdeco-pagination__button--next",
        ]
        for selector in next_selectors:
            btn = page.query_selector(selector)
            if btn and btn.is_enabled():
                btn.click()
                time.sleep(random.uniform(2, 4))
                return
