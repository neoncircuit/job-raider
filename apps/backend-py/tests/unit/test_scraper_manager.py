"""
Tests for ``ScraperManager.search_all`` and ``keyword_searches``: one search per
keyword phrase (scrape-keyword-search task). Fake scrapers, no network.
"""

from pathlib import Path
from typing import Any, List

import pytest

from src.models.job_listing import JobListingCollection, JobSource
from src.scrapers.base import SearchParams
from src.scrapers.manager import (
    MIN_RESULTS_PER_KEYWORD,
    ScraperManager,
    keyword_searches,
)


class TestKeywordSearches:
    """Tests for keyword_searches."""

    def test_one_phrase_keeps_the_limit(self) -> None:
        """A single phrase is one search with the full limit."""
        searches = keyword_searches(
            SearchParams(keywords=["python engineer"], limit=100)
        )
        assert [(s.keywords, s.limit) for s in searches] == [(["python engineer"], 100)]

    def test_each_phrase_is_its_own_search_with_a_share_of_the_limit(self) -> None:
        """Three phrases give three searches; the limit is shared (rounded up)."""
        searches = keyword_searches(
            SearchParams(
                keywords=["Computer Science", "AI Systems", "Backend Developer"],
                limit=100,
            )
        )
        assert [s.keywords for s in searches] == [
            ["Computer Science"],
            ["AI Systems"],
            ["Backend Developer"],
        ]
        assert {s.limit for s in searches} == {34}

    def test_share_has_a_minimum(self) -> None:
        """Many phrases still get the minimum each."""
        phrases = [f"skill {i}" for i in range(30)]
        searches = keyword_searches(SearchParams(keywords=phrases, limit=100))
        assert len(searches) == 30
        assert {s.limit for s in searches} == {MIN_RESULTS_PER_KEYWORD}

    def test_blank_and_repeated_phrases_are_dropped(self) -> None:
        """Blank phrases and repeats (any letter case) are searched once."""
        searches = keyword_searches(
            SearchParams(keywords=[" Python ", "", "python", "Go"], limit=40)
        )
        assert [s.keywords for s in searches] == [["Python"], ["Go"]]

    def test_no_phrase_is_one_search_without_keywords(self) -> None:
        """No keyword gives one search with no keywords (the scraper default)."""
        searches = keyword_searches(SearchParams(keywords=[], limit=50))
        assert [(s.keywords, s.limit) for s in searches] == [([], 50)]


class FakeScraper:
    """Returns two listings per keyword (one shared by all), or fails for 'Broken'."""

    def __init__(self, listing: Any) -> None:
        """
        Keep a listing to copy.

        Args:
            listing: A ``JobListing`` used as a template.
        """
        self.listing = listing
        self.calls: List[SearchParams] = []

    def search(self, params: SearchParams) -> JobListingCollection:
        """
        Record the search and return its listings.

        Args:
            params: The search.

        Returns:
            One listing for the keyword and one shared listing.

        Raises:
            RuntimeError: For the keyword "Broken".
        """
        self.calls.append(params)
        keyword = params.keywords[0]
        if keyword == "Broken":
            raise RuntimeError("board down")
        own = self.listing.model_copy(
            update={
                "job_id": f"job-{keyword}",
                "title": f"{keyword} role",
                "company": f"Co {keyword}",
            }
        )
        shared = self.listing.model_copy(
            update={
                "job_id": "job-shared",
                "title": "Shared role",
                "company": "Shared Co",
            }
        )
        return JobListingCollection(listings=[own, shared])


@pytest.fixture
def manager(tmp_path: Path, sample_job_listing: Any) -> Any:
    """
    A manager with one fake source that writes only under ``tmp_path``.

    Args:
        tmp_path: Temporary folder.
        sample_job_listing: Listing fixture.

    Returns:
        The manager, with the fake scraper as ``manager.fake``.
    """
    m = ScraperManager(output_dir=str(tmp_path / "listings"))
    m.fake = FakeScraper(sample_job_listing)
    m.scrapers = {JobSource.MYCAREERSFUTURE: m.fake}
    return m


def test_each_keyword_is_searched_and_results_are_merged(manager: Any) -> None:
    """One search per keyword; listings are merged and copies removed."""
    params = SearchParams(keywords=["Python", "Go"], location="Singapore", limit=40)
    collection = manager.search_all(params, sources=[JobSource.MYCAREERSFUTURE])

    assert sorted(c.keywords[0] for c in manager.fake.calls) == ["Go", "Python"]
    assert {c.location for c in manager.fake.calls} == {"Singapore"}
    assert {c.limit for c in manager.fake.calls} == {20}
    assert sorted(listing.job_id for listing in collection.listings) == [
        "job-Go",
        "job-Python",
        "job-shared",
    ]


def test_a_failed_search_is_reported_and_does_not_lose_the_others(manager: Any) -> None:
    """A failing keyword search is recorded; the other keywords still count."""
    params = SearchParams(keywords=["Python", "Broken"], limit=40)
    collection = manager.search_all(params, sources=[JobSource.MYCAREERSFUTURE])

    assert sorted(listing.job_id for listing in collection.listings) == [
        "job-Python",
        "job-shared",
    ]
    records = collection.metadata["searches"]
    assert records == [
        {"source": "mycareersfuture", "keyword": "Python", "count": 2, "error": None},
        {
            "source": "mycareersfuture",
            "keyword": "Broken",
            "count": 0,
            "error": "RuntimeError: board down",
        },
    ]
