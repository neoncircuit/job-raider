"""
Job Raider - Scraper Manager

This module provides a manager for orchestrating multiple scrapers
with parallel execution and rate limiting.

Author: Job Raider
Date: 2026-04-20
"""

import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ..models.job_listing import JobListing, JobListingCollection, JobSource
from ..utils.logger import Components, get_logger
from .base import BaseScraper, SearchParams
from .careersatgov_scraper import CareersAtGovScraper, careersatgov_enabled
from .jobstreet_scraper import JobStreetScraper, jobstreet_enabled
from .jsearch_scraper import JSearchScraper
from .linkedin_scraper import LinkedInScraper
from .mycareersfuture_scraper import MyCareersFutureScraper, mcf_enabled


def available_sources() -> List[JobSource]:
    """List the job sources that the scraper manager registers.

    LinkedIn and JSearch are always available. MyCareersFuture, JobStreet,
    and Careers@Gov are available only when their environment kill switch
    allows them. The CLI and ``ScraperManager`` both use this list, so the
    sources a user can pick match the scrapers that exist.

    Returns:
        Available sources in registration order.
    """
    sources = [JobSource.LINKEDIN, JobSource.JSEARCH]
    if mcf_enabled():
        sources.append(JobSource.MYCAREERSFUTURE)
    if jobstreet_enabled():
        sources.append(JobSource.JOBSTREET)
    if careersatgov_enabled():
        sources.append(JobSource.CAREERSATGOV)
    return sources


# Each keyword search gets at least this many results, so a long keyword
# list does not shrink every search to almost nothing.
MIN_RESULTS_PER_KEYWORD = 10


def keyword_searches(params: SearchParams) -> List[SearchParams]:
    """
    Split a search into one search per keyword phrase.

    The total ``limit`` is shared between the keywords (at least
    ``MIN_RESULTS_PER_KEYWORD`` each), so more keywords do not multiply the
    number of listings that the later stages must score.

    Args:
        params: The search, with one or more keyword phrases.

    Returns:
        One search per non-empty keyword phrase, in order. With no keyword,
        the search as given (the scrapers use their own default).
    """
    phrases: List[str] = []
    for keyword in params.keywords:
        phrase = (keyword or "").strip()
        if phrase and phrase.lower() not in {p.lower() for p in phrases}:
            phrases.append(phrase)
    if len(phrases) <= 1:
        return [params.model_copy(update={"keywords": phrases})]
    per_search = max(MIN_RESULTS_PER_KEYWORD, math.ceil(params.limit / len(phrases)))
    return [
        params.model_copy(update={"keywords": [phrase], "limit": per_search})
        for phrase in phrases
    ]


class ScraperManager:
    """
    Manager for running multiple scrapers in parallel.

    Handles rate limiting, deduplication, and storage of results.
    """

    def __init__(
        self,
        output_dir: str = "data/listings",
        max_workers: int = 3,
        deduplicate: bool = True,
    ):
        """
        Initialize the scraper manager.

        Args:
            output_dir: Directory to store scraped listings
            max_workers: Maximum number of concurrent scrapers
            deduplicate: Whether to deduplicate results across sources
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.max_workers = max_workers
        self.deduplicate = deduplicate

        # Initialize scrapers (MCF / JobStreet / CAG are kill-switched via env)
        scraper_classes: Dict[JobSource, Type[BaseScraper]] = {
            JobSource.LINKEDIN: LinkedInScraper,
            JobSource.JSEARCH: JSearchScraper,
            JobSource.MYCAREERSFUTURE: MyCareersFutureScraper,
            JobSource.JOBSTREET: JobStreetScraper,
            JobSource.CAREERSATGOV: CareersAtGovScraper,
        }
        self.scrapers: Dict[JobSource, BaseScraper] = {
            source: scraper_classes[source]() for source in available_sources()
        }

        self.logger = get_logger(Components.SCRAPERS)

    def search_all(
        self,
        params: SearchParams,
        sources: Optional[List[JobSource]] = None,
    ) -> JobListingCollection:
        """
        Search across multiple job boards in parallel, one search per keyword.

        Each keyword is its own search phrase ("python engineer" is one
        phrase), so each source is searched once for each keyword and the
        results are merged. A single search with all keywords would match
        only postings that contain every keyword (often none).

        Args:
            params: Search parameters
            sources: List of sources to search (all if None)

        Returns:
            Combined JobListingCollection with results from all sources. Its
            metadata ``searches`` lists each source and keyword with the
            count found, or the error of a failed search.
        """
        if sources is None:
            sources = list(self.scrapers.keys())

        searches = keyword_searches(params)
        self.logger.info(
            f"Searching {len(sources)} sources x {len(searches)} keyword searches "
            f"with params: {params}"
        )

        all_listings: List[JobListing] = []
        records: List[Dict[str, Any]] = []

        # Run the searches in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            for source in sources:
                if source not in self.scrapers:
                    continue
                for search in searches:
                    future = executor.submit(self._search_source, source, search)
                    futures[future] = (source, search)

            for future in as_completed(futures):
                source, search = futures[future]
                keyword = " ".join(search.keywords)
                record: Dict[str, Any] = {
                    "source": source.value,
                    "keyword": keyword,
                    "count": 0,
                    "error": None,
                }
                try:
                    collection = future.result(timeout=120)
                    all_listings.extend(collection.listings)
                    record["count"] = len(collection.listings)
                    self.logger.info(
                        f"{source.value} [{keyword}]: found "
                        f"{len(collection.listings)} listings"
                    )
                except Exception as e:
                    record["error"] = f"{type(e).__name__}: {e}"[:300]
                    self.logger.error(
                        f"{source.value} [{keyword}]: scraping failed - {str(e)}"
                    )
                records.append(record)

        order = {" ".join(s.keywords): i for i, s in enumerate(searches)}
        records.sort(key=lambda r: (r["source"], order.get(r["keyword"], 0)))

        # Create combined collection
        combined = JobListingCollection(
            listings=all_listings,
            metadata={
                "sources_searched": [s.value for s in sources],
                "search_params": params.model_dump(),
                "scraped_at": datetime.now().isoformat(),
                "searches": records,
            },
        )

        # Deduplicate if enabled
        if self.deduplicate:
            combined = combined.deduplicate()
            self.logger.info(
                f"After deduplication: {combined.total_count} unique listings"
            )

        # Save results
        self._save_results(combined)

        return combined

    def _search_source(
        self,
        source: JobSource,
        params: SearchParams,
    ) -> JobListingCollection:
        """
        Search a single job source.

        Args:
            source: Job board to search
            params: Search parameters

        Returns:
            JobListingCollection with results
        """
        scraper = self.scrapers[source]
        return scraper.search(params)

    def _save_results(self, collection: JobListingCollection) -> None:
        """
        Save scraping results to file.

        Args:
            collection: Job listing collection to save
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"listings_{timestamp}.json"
        filepath = self.output_dir / filename

        try:
            # Convert to dict for JSON serialization
            data = {
                "total_count": collection.total_count,
                "scraped_at": collection.scraped_at.isoformat(),
                "metadata": collection.metadata,
                "listings": [listing.model_dump() for listing in collection.listings],
            }

            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)

            self.logger.info(f"Saved results to {filepath}")

        except Exception as e:
            self.logger.error(f"Failed to save results: {str(e)}")

    def load_recent_results(
        self,
        hours: int = 24,
    ) -> List[JobListingCollection]:
        """
        Load recent scraping results from files.

        Args:
            hours: Only load results from last N hours

        Returns:
            List of JobListingCollections
        """
        collections = []
        cutoff_time = datetime.now().timestamp() - (hours * 3600)

        for filepath in self.output_dir.glob("listings_*.json"):
            try:
                # Check file modification time
                if filepath.stat().st_mtime < cutoff_time:
                    continue

                with open(filepath, "r") as f:
                    data = json.load(f)

                # Convert back to JobListing objects
                listings = [JobListing(**listing) for listing in data["listings"]]

                collection = JobListingCollection(
                    listings=listings,
                    total_count=data["total_count"],
                    metadata=data.get("metadata", {}),
                )

                collections.append(collection)

            except Exception as e:
                self.logger.error(f"Failed to load {filepath}: {str(e)}")
                continue

        return collections

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about scraper performance.

        Returns:
            Dictionary with scraper stats
        """
        stats = {
            "available_scrapers": list(self.scrapers.keys()),
            "scraper_stats": {},
        }

        for source, scraper in self.scrapers.items():
            stats["scraper_stats"][source.value] = scraper.stats

        return stats
