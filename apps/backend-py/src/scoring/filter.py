"""
Job Raider - Job Filter

This module provides keyword-based filtering for job listings
to quickly identify potentially relevant opportunities.

Author: Job Raider
Date: 2026-04-20
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set

from ..models.job_listing import ExperienceLevel, JobListing, JobListingCollection
from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger
from ..utils.source_geography import listing_matches_requested_locations


class MatchReason(str, Enum):
    """Reasons for a job match."""

    KEYWORD = "keyword"
    SKILL = "skill"
    LOCATION = "location"
    EXPERIENCE = "experience"
    REMOTE = "remote"


# Substrings that indicate an internship listing (title/description).
_INTERNSHIP_TEXT_MARKERS = (
    "internship",
    "intern ",
    " intern",
    "summer intern",
    "student intern",
)


@dataclass
class FilterResult:
    """Result of filtering a job listing."""

    job: JobListing
    matched: bool
    matched_keywords: List[str]
    matched_skills: List[str]
    match_reasons: List[MatchReason]
    score: int = 0


class JobFilter:
    """
    Filter job listings based on keywords, skills, and criteria.

    Provides fast pre-filtering before more expensive scoring operations.
    """

    def __init__(
        self,
        keywords: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        remote_only: bool = False,
        require_salary: bool = False,
    ):
        """
        Initialize the job filter.

        Args:
            keywords: Required keywords (any match is sufficient)
            locations: Acceptable locations
            remote_only: Only include remote positions
            require_salary: Require salary information
        """
        self.keywords = [k.lower() for k in (keywords or [])]
        self.locations = locations or []
        self.remote_only = remote_only
        self.require_salary = require_salary

        self.logger = get_logger(Components.SCORING)

    def filter_collection(
        self,
        collection: JobListingCollection,
    ) -> JobListingCollection:
        """
        Filter a job listing collection.

        Args:
            collection: Job listing collection to filter

        Returns:
            Filtered JobListingCollection
        """
        filtered_listings = []

        for listing in collection.listings:
            result = self.filter_listing(listing)
            if result.matched:
                filtered_listings.append(listing)

        self.logger.info(
            f"Filtered {len(collection.listings)} -> {len(filtered_listings)} listings"
        )

        return JobListingCollection(
            listings=filtered_listings,
            source=collection.source,
            metadata={
                **collection.metadata,
                "filtered": True,
                "original_count": collection.total_count,
                "filter_criteria": {
                    "keywords": self.keywords,
                    "locations": self.locations,
                    "remote_only": self.remote_only,
                    "require_salary": self.require_salary,
                },
            },
        )

    def filter_listing(self, listing: JobListing) -> FilterResult:
        """
        Filter a single job listing.

        Args:
            listing: Job listing to filter

        Returns:
            FilterResult with match details
        """
        matched_keywords = []
        matched_skills = []
        match_reasons = []
        score = 0

        # Check keywords
        for keyword in self.keywords:
            if listing.matches_keyword(keyword):
                matched_keywords.append(keyword)
                match_reasons.append(MatchReason.KEYWORD)
                score += 10

        # Check skills
        if listing.skills:
            listing_skills = [s.name.lower() for s in listing.skills]
            for keyword in self.keywords:
                if keyword in listing_skills:
                    matched_skills.append(keyword)
                    if MatchReason.SKILL not in match_reasons:
                        match_reasons.append(MatchReason.SKILL)
                    score += 15

        # Check location
        if self.locations:
            if listing_matches_requested_locations(
                listing, self.locations, include_missing=False
            ):
                match_reasons.append(MatchReason.LOCATION)
                score += 10

        # Check remote
        if self.remote_only and listing.is_remote:
            match_reasons.append(MatchReason.REMOTE)
            score += 10
        elif self.remote_only and not listing.is_remote:
            # Failed remote filter
            return FilterResult(
                job=listing,
                matched=False,
                matched_keywords=[],
                matched_skills=[],
                match_reasons=[],
                score=0,
            )

        # Check salary
        if self.require_salary and not listing.salary_range:
            # Failed salary filter
            return FilterResult(
                job=listing,
                matched=False,
                matched_keywords=[],
                matched_skills=[],
                match_reasons=[],
                score=0,
            )

        # Determine if matched (at least one keyword or skill match)
        matched = bool(matched_keywords or matched_skills)

        return FilterResult(
            job=listing,
            matched=matched,
            matched_keywords=matched_keywords,
            matched_skills=matched_skills,
            match_reasons=match_reasons,
            score=score,
        )

    def filter_by_profile(
        self,
        collection: JobListingCollection,
        profile: UserProfile,
    ) -> JobListingCollection:
        """
        Filter collection based on user profile.

        Uses profile's target keywords, locations, and apprenticeship
        field constraint when in filter mode.

        Args:
            collection: Job listing collection to filter
            profile: User profile with targets

        Returns:
            Filtered JobListingCollection
        """
        # Update filter with profile targets
        self.keywords = [k.lower() for k in profile.targets.keywords]
        self.locations = profile.targets.locations
        self.remote_only = profile.targets.remote_preference

        # In filter mode, add apprenticeship field as required keyword
        if (
            profile.apprenticeship
            and profile.apprenticeship.is_active
            and profile.targets.constraint_mode == "filter"
        ):
            field_terms = [
                term.lower().strip()
                for term in profile.apprenticeship.field.replace("/", " ").split()
                if term.strip()
            ]
            for term in field_terms:
                if term not in self.keywords:
                    self.keywords.append(term)

        filtered = self.filter_collection(collection)
        return self._apply_preference_constraints(filtered, profile)

    def _apply_preference_constraints(
        self,
        collection: JobListingCollection,
        profile: UserProfile,
    ) -> JobListingCollection:
        """
        Apply experience-level and internship preference constraints.

        Exclude-internships applies whenever enabled. Experience-level hard
        filtering applies only when ``constraint_mode == "filter"`` and the
        profile lists target levels. Unspecified job levels are kept.

        Args:
            collection: Already keyword-filtered listings.
            profile: User profile with targets.

        Returns:
            Collection with preference constraints applied.
        """
        exclude_internships = bool(
            getattr(profile.targets, "exclude_internships", False)
        )
        allowed_levels = list(profile.targets.experience_levels or [])
        hard_level_filter = profile.targets.constraint_mode == "filter" and bool(
            allowed_levels
        )

        if not exclude_internships and not hard_level_filter:
            return collection

        kept: List[JobListing] = []
        for listing in collection.listings:
            if exclude_internships and self._looks_like_internship(listing):
                continue
            if hard_level_filter and not self._experience_level_allowed(
                listing, allowed_levels
            ):
                continue
            kept.append(listing)

        self.logger.info(
            "Preference constraints %s -> %s listings "
            "(exclude_internships=%s, hard_level_filter=%s)",
            len(collection.listings),
            len(kept),
            exclude_internships,
            hard_level_filter,
        )

        return JobListingCollection(
            listings=kept,
            source=collection.source,
            metadata={
                **collection.metadata,
                "preference_constraints": {
                    "exclude_internships": exclude_internships,
                    "hard_level_filter": hard_level_filter,
                    "allowed_levels": [
                        level.value if hasattr(level, "value") else str(level)
                        for level in allowed_levels
                    ],
                },
            },
        )

    @staticmethod
    def _looks_like_internship(listing: JobListing) -> bool:
        """
        Return True when a listing is internship-level or internship-worded.

        Args:
            listing: Job listing to inspect.

        Returns:
            Whether the listing should be treated as an internship.
        """
        if listing.experience_level == ExperienceLevel.INTERNSHIP:
            return True
        if getattr(listing, "job_type", None) is not None:
            job_type = listing.job_type
            job_type_value = (
                job_type.value if hasattr(job_type, "value") else str(job_type)
            )
            if "internship" in job_type_value.lower():
                return True
        searchable = f"{listing.title} {listing.description or ''}".lower()
        return any(marker in searchable for marker in _INTERNSHIP_TEXT_MARKERS)

    @staticmethod
    def _experience_level_allowed(
        listing: JobListing,
        allowed_levels: List[ExperienceLevel],
    ) -> bool:
        """
        Return True when the listing's level is allowed or unspecified.

        Args:
            listing: Job listing to inspect.
            allowed_levels: Target experience levels from the profile.

        Returns:
            Whether the listing passes a hard experience-level filter.
        """
        level = listing.experience_level
        if level is None or level == ExperienceLevel.NOT_SPECIFIED:
            return True
        return level in allowed_levels

    def get_matching_keywords(
        self,
        listing: JobListing,
        profile: UserProfile,
    ) -> Set[str]:
        """
        Get keywords from a job listing that match user's targets.

        Args:
            listing: Job listing to check
            profile: User profile with target keywords

        Returns:
            Set of matching keyword names
        """
        target_keywords = {k.lower() for k in profile.targets.keywords}
        matched = set()

        # Check title
        for keyword in target_keywords:
            if keyword in listing.title.lower():
                matched.add(keyword)

        # Check description
        if listing.description:
            for keyword in target_keywords:
                if keyword in listing.description.lower():
                    matched.add(keyword)

        # Check requirements
        for req in listing.requirements:
            for keyword in target_keywords:
                if keyword in req.text.lower():
                    matched.add(keyword)

        # Check skills
        listing_skills = {s.name.lower() for s in listing.skills}
        matched.update(target_keywords & listing_skills)

        return matched


class QuickFilter:
    """
    Quick filter for fast pre-screening.

    Uses simple rules to quickly eliminate obviously irrelevant jobs.
    """

    # Quick rejection patterns
    REJECT_PATTERNS = [
        "director",
        "vp ",
        "vice president",
        "cto",
        "chief",
        "internship",
        "unpaid",
        "volunteer",
        "contract to hire",
    ]

    @classmethod
    def should_reject(cls, listing: JobListing) -> bool:
        """
        Quick check if listing should be rejected.

        Args:
            listing: Job listing to check

        Returns:
            True if listing should be rejected
        """
        title_lower = listing.title.lower()

        for pattern in cls.REJECT_PATTERNS:
            if pattern in title_lower:
                return True

        # Reject very old postings (> 60 days)
        if listing.days_since_posted and listing.days_since_posted > 60:
            return True

        return False

    @classmethod
    def filter_collection(
        cls,
        collection: JobListingCollection,
    ) -> JobListingCollection:
        """
        Quickly filter out obviously irrelevant listings.

        Args:
            collection: Job listing collection to filter

        Returns:
            Filtered JobListingCollection
        """
        filtered = [
            listing for listing in collection.listings if not cls.should_reject(listing)
        ]

        return JobListingCollection(
            listings=filtered,
            source=collection.source,
            metadata={
                **collection.metadata,
                "quick_filtered": True,
                "rejected_count": collection.total_count - len(filtered),
            },
        )
