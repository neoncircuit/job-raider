"""
Unit tests for Singapore-scoped board geography.

Author: Job Raider
Date: 2026-08-15
"""

from types import SimpleNamespace

from src.models.job_listing import JobSource, WorkMode
from src.utils.source_geography import (
    listing_matches_requested_locations,
    singapore_board_applies,
)


def _listing(**kwargs: object) -> SimpleNamespace:
    """Build a listing-like object for geography tests."""
    defaults: dict = {
        "source": JobSource.MYCAREERSFUTURE,
        "location": "Islandwide",
        "is_remote": False,
        "work_mode": WorkMode.ON_SITE,
        "metadata": {},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestSingaporeBoardApplies:
    """When MCF / Careers@Gov should run."""

    def test_singapore_and_empty_and_remote(self) -> None:
        """Singapore, SG, Remote, and empty location are allowed."""
        assert singapore_board_applies("Singapore") is True
        assert singapore_board_applies("SG") is True
        assert singapore_board_applies("Remote") is True
        assert singapore_board_applies(None) is True
        assert singapore_board_applies("") is True
        assert singapore_board_applies("London", remote=True) is True

    def test_other_countries_skipped(self) -> None:
        """Other countries do not query Singapore boards."""
        assert singapore_board_applies("New York") is False
        assert singapore_board_applies("United States") is False
        assert singapore_board_applies("London") is False


class TestListingMatchesRequestedLocations:
    """Source override, not district-name matching."""

    def test_mcf_district_matches_singapore(self) -> None:
        """District text without Singapore still matches a Singapore search."""
        job = _listing(location="D07 Middle Road, Golden Mile")
        assert listing_matches_requested_locations(job, ["Singapore"]) is True
        assert listing_matches_requested_locations(job, ["SG"]) is True

    def test_mcf_does_not_match_other_countries(self) -> None:
        """Singapore boards do not appear in US/UK searches."""
        job = _listing(location="Islandwide, Singapore")
        assert listing_matches_requested_locations(job, ["New York"]) is False
        assert listing_matches_requested_locations(job, ["United States"]) is False

    def test_mcf_remote_matches_remote_query(self) -> None:
        """Remote search keeps remote or hybrid MCF jobs."""
        remote = _listing(
            location="Islandwide", is_remote=True, work_mode=WorkMode.REMOTE
        )
        hybrid = _listing(location="Central", work_mode=WorkMode.HYBRID)
        onsite = _listing(location="Central", work_mode=WorkMode.ON_SITE)
        assert listing_matches_requested_locations(remote, ["Remote"]) is True
        assert listing_matches_requested_locations(hybrid, ["Remote"]) is True
        assert listing_matches_requested_locations(onsite, ["Remote"]) is False

    def test_overseas_mcf_excluded_from_singapore(self) -> None:
        """Overseas MCF postings are not treated as Singapore."""
        job = _listing(
            location="Malaysia",
            metadata={"sg_board_overseas": True},
        )
        assert listing_matches_requested_locations(job, ["Singapore"]) is False
        assert listing_matches_requested_locations(job, ["Malaysia"]) is True

    def test_careersatgov_uses_same_rule(self) -> None:
        """Careers@Gov is reserved as Singapore-scoped."""
        job = _listing(source="careersatgov", location="Somewhere")
        assert listing_matches_requested_locations(job, ["Singapore"]) is True
        assert listing_matches_requested_locations(job, ["London"]) is False

    def test_jobstreet_uses_same_rule(self) -> None:
        """Dedicated JobStreet stays Singapore-scoped until SG is solid."""
        job = _listing(source="jobstreet", location="Somewhere")
        assert listing_matches_requested_locations(job, ["Singapore"]) is True
        assert listing_matches_requested_locations(job, ["Kuala Lumpur"]) is False

    def test_linkedin_still_uses_text_match(self) -> None:
        """Non-scoped sources keep alias-aware location text matching."""
        job = _listing(
            source=JobSource.LINKEDIN,
            location="San Francisco, US",
        )
        assert listing_matches_requested_locations(job, ["SF"]) is True
        assert listing_matches_requested_locations(job, ["Singapore"]) is False
