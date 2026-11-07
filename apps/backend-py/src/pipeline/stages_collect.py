"""
Job Raider - Collect Stages

This module defines the stages that collect jobs and remove unwanted ones:
scrape, deduplicate, scam filter, and profile filter.
"""

from datetime import datetime
from typing import Any, List, Optional, Tuple

from ..models.duplicates import summarize_duplicate_flags
from ..models.job_listing import JobListing, JobListingCollection, JobSource
from ..scoring.scam_detector import (
    DEFAULT_SCAM_ACTION,
    ScamFilter,
)
from ..scrapers.base import SearchParams
from ..submission.applied_guard import AppliedGuard
from ..submission.applied_tracker import AppliedJobsTracker
from .stage_base import StageBase, StageResult


class CollectStages(StageBase):
    """Stages that scrape jobs and filter them."""

    def stage_scrape(
        self,
        keywords: List[str],
        locations: List[str],
        sources: Optional[List[str]] = None,
    ) -> StageResult:
        """
        Stage 1: Scrape job listings from platforms.

        Args:
            keywords: Job keywords to search
            locations: Job locations
            sources: Optional list of sources (default: all)

        Returns:
            StageResult with scraped listings
        """
        stage_name = "scrape"
        start_time = datetime.now()

        try:
            self.logger.info(
                f"Starting scraping stage: keywords={keywords}, locations={locations}"
            )

            # Perform scraping. SearchParams takes a single optional location
            # (matches the convention in api/routes/jobs.py); multi-location
            # search is not currently supported, so only the first is used.
            source_map = {
                "linkedin": JobSource.LINKEDIN,
                "jsearch": JobSource.JSEARCH,
                "mycareersfuture": JobSource.MYCAREERSFUTURE,
                "jobstreet": JobSource.JOBSTREET,
                "careersatgov": JobSource.CAREERSATGOV,
            }
            source_enums = (
                [source_map[s] for s in sources if s in source_map] if sources else None
            )
            params = SearchParams(
                keywords=keywords,
                location=locations[0] if locations else None,
            )
            collection = self.scraper_manager.search_all(params, sources=source_enums)
            listings = collection.listings

            # Store raw results
            self.context.raw_listings = listings

            metadata = {
                "listings_count": len(listings),
                "keywords": keywords,
                "locations": locations,
                "sources": sources,
            }

            self.logger.info(f"Scraping complete: {len(listings)} listings found")

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=listings,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Scraping stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=[],
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )

    def stage_deduplicate(
        self,
        listings: List[JobListing],
    ) -> StageResult:
        """
        Stage 2: Remove exact job-id copies and flag possible duplicates.

        Args:
            listings: Raw job listings

        Returns:
            StageResult with unique job-id listings. Possible duplicates
            stay and carry flag metadata.
        """
        stage_name = "deduplicate"
        start_time = datetime.now()

        try:
            self.logger.info(f"Deduplicating {len(listings)} listings")

            # Use collection's deduplicate method
            collection = JobListingCollection(listings=listings)
            deduplicated_collection = collection.deduplicate()
            deduplicated = deduplicated_collection.listings
            flag_stats = summarize_duplicate_flags(deduplicated)

            # Store in context and persistent storage
            self.context.deduplicated_listings = deduplicated
            self.context.storage.save_collection(
                JobListingCollection(listings=deduplicated)
            )
            try:
                self.context.storage.upsert_listings(deduplicated)
            except Exception as catalog_err:
                self.logger.warning("Failed to upsert listing catalog: %s", catalog_err)

            # Persist scraper-detected applied status to tracker
            applied_tracker = AppliedJobsTracker()
            for job in deduplicated:
                if job.already_applied and not applied_tracker.is_applied(job.job_id):
                    applied_tracker.mark_applied(
                        job_id=job.job_id,
                        job_title=job.title,
                        company=job.company,
                        source=(
                            str(job.source.value)
                            if hasattr(job.source, "value")
                            else str(job.source)
                        ),
                    )

            # Cross-source applied guard (outcomes + AppliedJobsTracker)
            guard = AppliedGuard(applied_tracker=applied_tracker)
            annotated = guard.annotate_listings(deduplicated)
            deduplicated, applied_removed = guard.filter_unapplied(annotated)

            metadata = {
                "original_count": len(listings),
                "deduplicated_count": len(deduplicated),
                "removed_count": len(listings) - len(deduplicated),
                "already_applied_removed": applied_removed,
                "flagged_listings": flag_stats["flagged_listings"],
                "flagged_pairs_same_url": flag_stats["flagged_pairs_same_url"],
                "flagged_pairs_same_company_title_location": flag_stats[
                    "flagged_pairs_same_company_title_location"
                ],
            }

            self.logger.info(
                f"Deduplication complete: {metadata['removed_count']} duplicates removed"
            )

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=deduplicated,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Deduplication stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=listings,
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )

    def stage_filter_scams(
        self,
        listings: List[JobListing],
        use_quick_filter: bool = True,
    ) -> StageResult:
        """
        Stage 3: Filter out scam listings.

        Args:
            listings: Job listings to filter
            use_quick_filter: Use quick pre-filter first

        Returns:
            StageResult with legitimate listings
        """
        stage_name = "filter_scams"
        start_time = datetime.now()
        original_count = len(listings)
        action = self.context.config.get("scam_action", DEFAULT_SCAM_ACTION)

        try:
            self.logger.info(
                f"Filtering scams from {original_count} listings (action={action})"
            )

            kept: List[JobListing] = []
            scam_reports: List[Tuple[JobListing, Any, bool]] = []

            for job in listings:
                quick_hit = bool(use_quick_filter and ScamFilter.is_potential_scam(job))
                report = self.scam_detector.detect(job)
                flagged = quick_hit or report.is_scam
                if flagged:
                    scam_reports.append((job, report, quick_hit))
                    if action == "flag":
                        job.metadata["scam_flag"] = {
                            "quick_filter": quick_hit,
                            "confidence": report.confidence,
                            "reasons": list(report.reasons),
                        }
                        kept.append(job)
                    else:
                        self.logger.warning(
                            f"Filtered scam: {job.title} at {job.company} "
                            f"(confidence: {report.confidence:.2f})"
                        )
                else:
                    kept.append(job)

            metadata = {
                "original_count": original_count,
                "filtered_count": len(kept),
                "scam_count": len(scam_reports),
                "scam_action": action,
                "scam_reports": [
                    {
                        "title": job.title,
                        "company": job.company,
                        "confidence": report.confidence,
                        "quick_filter": quick_hit,
                        "indicators": [i.value for i in report.indicators],
                    }
                    for job, report, quick_hit in scam_reports[:10]
                ],
            }

            self.logger.info(
                f"Scam filtering complete: {metadata['scam_count']} flagged, "
                f"action={action}"
            )

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=kept,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Scam filtering stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=listings,
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )

    def stage_filter_by_profile(
        self,
        listings: List[JobListing],
    ) -> StageResult:
        """
        Stage 4: Filter listings by user profile preferences.

        Args:
            listings: Job listings to filter

        Returns:
            StageResult with filtered listings
        """
        stage_name = "filter_by_profile"
        start_time = datetime.now()

        try:
            self.logger.info(f"Filtering {len(listings)} listings by user profile")

            # Filter by user profile
            collection = JobListingCollection(listings=listings)
            filtered_collection = self.job_filter.filter_by_profile(
                collection=collection,
                profile=self.context.user_profile,
            )
            filtered = filtered_collection.listings

            self.context.filtered_listings = filtered

            metadata = {
                "original_count": len(listings),
                "filtered_count": len(filtered),
                "removed_count": len(listings) - len(filtered),
                "target_keywords": self.context.user_profile.targets.keywords,
                "target_locations": self.context.user_profile.targets.locations,
            }

            self.logger.info(
                f"Profile filtering complete: {len(filtered)} listings match profile"
            )

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=filtered,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Profile filtering stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=listings,
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )
