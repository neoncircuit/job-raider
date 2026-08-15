"""
Job Raider - Scraper Manager

This module provides a manager for orchestrating multiple scrapers
with parallel execution and rate limiting.

Author: Job Raider
Date: 2026-04-20
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models.job_listing import JobListing, JobListingCollection, JobSource
from ..utils.logger import Components, get_logger
from .base import BaseScraper, SearchParams
from .careersatgov_scraper import CareersAtGovScraper, careersatgov_enabled
from .jobstreet_scraper import JobStreetScraper, jobstreet_enabled
from .jsearch_scraper import JSearchScraper
from .linkedin_scraper import LinkedInScraper
from .mycareersfuture_scraper import MyCareersFutureScraper, mcf_enabled


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
        self.scrapers: Dict[JobSource, BaseScraper] = {
            JobSource.LINKEDIN: LinkedInScraper(),
            JobSource.JSEARCH: JSearchScraper(),
        }
        if mcf_enabled():
            self.scrapers[JobSource.MYCAREERSFUTURE] = MyCareersFutureScraper()
        if jobstreet_enabled():
            self.scrapers[JobSource.JOBSTREET] = JobStreetScraper()
        if careersatgov_enabled():
            self.scrapers[JobSource.CAREERSATGOV] = CareersAtGovScraper()

        self.logger = get_logger(Components.SCRAPERS)

    def search_all(
        self,
        params: SearchParams,
        sources: Optional[List[JobSource]] = None,
    ) -> JobListingCollection:
        """
        Search across multiple job boards in parallel.

        Args:
            params: Search parameters
            sources: List of sources to search (all if None)

        Returns:
            Combined JobListingCollection with results from all sources
        """
        if sources is None:
            sources = list(self.scrapers.keys())

        self.logger.info(f"Searching {len(sources)} sources with params: {params}")

        all_listings = []

        # Run scrapers in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            for source in sources:
                if source in self.scrapers:
                    future = executor.submit(self._search_source, source, params)
                    futures[future] = source

            for future in as_completed(futures):
                source = futures[future]
                try:
                    collection = future.result(timeout=120)
                    all_listings.extend(collection.listings)
                    self.logger.info(
                        f"{source.value}: found {len(collection.listings)} listings"
                    )
                except Exception as e:
                    self.logger.error(f"{source.value}: scraping failed - {str(e)}")

        # Create combined collection
        combined = JobListingCollection(
            listings=all_listings,
            metadata={
                "sources_searched": [s.value for s in sources],
                "search_params": params.model_dump(),
                "scraped_at": datetime.now().isoformat(),
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
