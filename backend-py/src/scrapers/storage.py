"""
Job Raider - Job Listing Storage

This module provides storage functionality for scraped job listings
with deduplication and timestamp management.

Author: Job Raider
Date: 2026-04-20
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..models.job_listing import JobListing, JobListingCollection, JobSource
from ..utils.logger import Components, get_logger


class JobListingStorage:
    """
    Storage manager for job listings.

    Handles saving, loading, deduplicating, and querying
    scraped job listings.
    """

    def __init__(
        self,
        storage_dir: str = "data/listings",
        max_age_days: int = 30,
    ):
        """
        Initialize the storage manager.

        Args:
            storage_dir: Directory to store listings
            max_age_days: Maximum age of listings to keep
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.max_age_days = max_age_days
        self.logger = get_logger(Components.SCRAPERS)

        # Track seen job IDs for deduplication
        self._seen_ids: Set[str] = set()

    def save_collection(self, collection: JobListingCollection) -> str:
        """
        Save a job listing collection to file.

        Args:
            collection: Collection to save

        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"{collection.source.value}_{timestamp}.json"
            if collection.source
            else f"all_{timestamp}.json"
        )
        filepath = self.storage_dir / filename

        try:
            data = {
                "total_count": collection.total_count,
                "source": collection.source.value if collection.source else None,
                "scraped_at": collection.scraped_at.isoformat(),
                "metadata": collection.metadata,
                "listings": [listing.model_dump() for listing in collection.listings],
            }

            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)

            self.logger.info(f"Saved {collection.total_count} listings to {filepath}")

            # Track IDs for deduplication
            for listing in collection.listings:
                self._seen_ids.add(listing.job_id)

            return str(filepath)

        except Exception as e:
            self.logger.error(f"Failed to save collection: {str(e)}")
            raise

    def load_collection(self, filepath: str) -> Optional[JobListingCollection]:
        """
        Load a job listing collection from file.

        Args:
            filepath: Path to collection file

        Returns:
            JobListingCollection or None if loading fails
        """
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            listings = [JobListing(**listing) for listing in data.get("listings", [])]

            source = None
            if data.get("source"):
                source = JobSource(data["source"])

            collection = JobListingCollection(
                listings=listings,
                total_count=data.get("total_count", len(listings)),
                source=source,
                metadata=data.get("metadata", {}),
            )

            # Parse scraped_at
            if data.get("scraped_at"):
                try:
                    collection.scraped_at = datetime.fromisoformat(data["scraped_at"])
                except ValueError:
                    pass

            return collection

        except Exception as e:
            self.logger.error(f"Failed to load collection from {filepath}: {str(e)}")
            return None

    def load_recent(
        self,
        hours: int = 24,
        sources: Optional[List[JobSource]] = None,
    ) -> JobListingCollection:
        """
        Load recent job listings from storage.

        Args:
            hours: Only load listings from last N hours
            sources: Filter by sources (all if None)

        Returns:
            Combined JobListingCollection with recent listings
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        all_listings = []

        for filepath in self.storage_dir.glob("*.json"):
            try:
                # Check file modification time
                if datetime.fromtimestamp(filepath.stat().st_mtime) < cutoff_time:
                    continue

                collection = self.load_collection(str(filepath))
                if collection:
                    # Filter by source if specified
                    if sources is None or collection.source in sources:
                        all_listings.extend(collection.listings)

            except Exception as e:
                self.logger.error(f"Failed to load {filepath}: {str(e)}")
                continue

        return JobListingCollection(
            listings=all_listings,
            metadata={
                "loaded_from": "recent",
                "hours": hours,
                "loaded_at": datetime.now().isoformat(),
            },
        )

    def deduplicate_across_sources(
        self,
        collections: List[JobListingCollection],
    ) -> JobListingCollection:
        """
        Deduplicate job listings across multiple collections.

        Uses job_id to identify duplicates, keeping the most recent one.

        Args:
            collections: List of collections to deduplicate

        Returns:
            Deduplicated JobListingCollection
        """
        seen_ids = {}
        unique_listings = []

        for collection in collections:
            for listing in collection.listings:
                if listing.job_id not in seen_ids:
                    seen_ids[listing.job_id] = listing
                    unique_listings.append(listing)
                else:
                    # Keep the more recent listing
                    existing = seen_ids[listing.job_id]
                    if (
                        listing.posted_date
                        and existing.posted_date
                        and listing.posted_date > existing.posted_date
                    ):
                        seen_ids[listing.job_id] = listing
                        # Replace in list
                        for i, l in enumerate(unique_listings):
                            if l.job_id == listing.job_id:
                                unique_listings[i] = listing
                                break

        self.logger.info(
            f"Deduplicated: {len(unique_listings)} unique from {sum(len(c.listings) for c in collections)} total"
        )

        return JobListingCollection(
            listings=unique_listings,
            metadata={
                "deduplicated": True,
                "original_count": sum(len(c.listings) for c in collections),
                "unique_count": len(unique_listings),
            },
        )

    def cleanup_old_listings(self) -> int:
        """
        Remove old listing files from storage.

        Returns:
            Number of files removed
        """
        removed = 0
        cutoff_time = datetime.now() - timedelta(days=self.max_age_days)

        for filepath in self.storage_dir.glob("*.json"):
            try:
                # Check file modification time
                if datetime.fromtimestamp(filepath.stat().st_mtime) < cutoff_time:
                    filepath.unlink()
                    removed += 1
                    self.logger.info(f"Removed old listing file: {filepath}")

            except Exception as e:
                self.logger.error(f"Failed to remove {filepath}: {str(e)}")
                continue

        if removed > 0:
            self.logger.info(f"Cleaned up {removed} old listing files")

        return removed

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored listings.

        Returns:
            Dictionary with storage statistics
        """
        stats = {
            "storage_dir": str(self.storage_dir),
            "total_files": 0,
            "total_listings": 0,
            "by_source": defaultdict(int),
            "listings_by_source": defaultdict(int),
        }

        for filepath in self.storage_dir.glob("*.json"):
            stats["total_files"] += 1

            try:
                collection = self.load_collection(str(filepath))
                if collection:
                    stats["total_listings"] += collection.total_count
                    if collection.source:
                        stats["by_source"][collection.source.value] += 1
                        stats["listings_by_source"][
                            collection.source.value
                        ] += collection.total_count

            except Exception:
                continue

        # Convert defaultdict to dict for JSON serialization
        stats["by_source"] = dict(stats["by_source"])
        stats["listings_by_source"] = dict(stats["listings_by_source"])

        return stats

    @property
    def seen_ids(self) -> Set[str]:
        """Return set of all seen job IDs."""
        return self._seen_ids.copy()

    def is_new_listing(self, job_id: str) -> bool:
        """
        Check if a job ID is new (not seen before).

        Args:
            job_id: Job ID to check

        Returns:
            True if job ID hasn't been seen before
        """
        return job_id not in self._seen_ids
