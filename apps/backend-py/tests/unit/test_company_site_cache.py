"""
Unit tests for the company site cache and service (company-site-apply, S1).

The finder is injected as a fake, so these tests make no network calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from src.submission.company_site_cache import CompanySiteCache, get_company_site


def _fake_finder(calls: List[str]):
    """
    Build a finder fake that records each call.

    Args:
        calls: List that receives the company name of each call.

    Returns:
        A function with the finder's signature.
    """

    def finder(company: str, job_title: str, **_: Any) -> Any:
        calls.append(company)

        class _Result:
            def to_dict(self) -> Dict[str, Any]:
                return {"level": "exact", "url": "https://boards.greenhouse.io/x/1"}

        return _Result()

    return finder


def test_cache_round_trip(tmp_path: Path) -> None:
    """A stored payload is read back unchanged; a missing job gives None.

    Args:
        tmp_path: Pytest temp directory.
    """
    cache = CompanySiteCache(tmp_path)
    assert cache.get("job-1") is None
    cache.put("job-1", {"level": "careers", "url": "https://a.example/careers"})
    assert cache.get("job-1") == {
        "level": "careers",
        "url": "https://a.example/careers",
    }


def test_cache_keeps_unsafe_job_ids_inside_directory(tmp_path: Path) -> None:
    """A job ID with path characters is stored as a file inside the cache folder.

    Args:
        tmp_path: Pytest temp directory.
    """
    cache = CompanySiteCache(tmp_path / "cache")
    path = cache.path_for("../../etc/passwd x")
    assert path.parent == tmp_path / "cache"
    cache.put("../../etc/passwd x", {"level": "none"})
    assert cache.get("../../etc/passwd x") == {"level": "none"}


def test_cache_treats_corrupt_file_as_miss(tmp_path: Path) -> None:
    """A corrupt cache file is a cache miss, not an error.

    Args:
        tmp_path: Pytest temp directory.
    """
    cache = CompanySiteCache(tmp_path)
    cache.path_for("job-2").write_text("{not json", encoding="utf-8")
    assert cache.get("job-2") is None


def test_service_runs_finder_once_then_uses_cache(tmp_path: Path) -> None:
    """The second call for the same job is served from the cache.

    Args:
        tmp_path: Pytest temp directory.
    """
    calls: List[str] = []
    cache = CompanySiteCache(tmp_path)
    fake = _fake_finder(calls)
    first = get_company_site(
        "job-3", "Lumen Analytics", "Data Engineer", cache=cache, finder=fake
    )
    second = get_company_site(
        "job-3", "Lumen Analytics", "Data Engineer", cache=cache, finder=fake
    )
    assert calls == ["Lumen Analytics"]
    assert first["cached"] is False
    assert second["cached"] is True
    assert second["url"] == first["url"]


def test_failed_search_is_not_cached(tmp_path: Path) -> None:
    """A result from a failed search is not stored, so the next call searches again.

    Args:
        tmp_path: Pytest temp directory.
    """
    calls: List[str] = []

    class _Failed:
        def to_dict(self) -> Dict[str, Any]:
            return {"level": "none", "url": None, "search_failed": True}

    def failing(company: str, job_title: str, **_: Any) -> Any:
        calls.append(company)
        return _Failed()

    cache = CompanySiteCache(tmp_path)
    get_company_site("job-5", "Tiny Startup", "Founder", cache=cache, finder=failing)
    get_company_site("job-5", "Tiny Startup", "Founder", cache=cache, finder=failing)
    assert len(calls) == 2
    assert cache.get("job-5") is None


def test_none_with_every_page_failed_is_not_cached(tmp_path: Path) -> None:
    """A "none" where every candidate page failed to load is not stored.

    Args:
        tmp_path: Pytest temp directory.
    """
    calls: List[str] = []

    class _Unloaded:
        def to_dict(self) -> Dict[str, Any]:
            return {
                "level": "none",
                "url": None,
                "search_failed": False,
                "pages_attempted": 2,
                "pages_loaded": 0,
            }

    def unloaded(company: str, job_title: str, **_: Any) -> Any:
        calls.append(company)
        return _Unloaded()

    cache = CompanySiteCache(tmp_path)
    get_company_site(
        "job-7", "Northwind Energy", "Site Engineer", cache=cache, finder=unloaded
    )
    get_company_site(
        "job-7", "Northwind Energy", "Site Engineer", cache=cache, finder=unloaded
    )
    assert len(calls) == 2
    assert cache.get("job-7") is None


def test_none_with_a_loaded_rejected_page_is_cached(tmp_path: Path) -> None:
    """A "none" where at least one page loaded and was rejected is stored.

    Args:
        tmp_path: Pytest temp directory.
    """
    calls: List[str] = []

    class _Rejected:
        def to_dict(self) -> Dict[str, Any]:
            return {
                "level": "none",
                "url": None,
                "search_failed": False,
                "pages_attempted": 2,
                "pages_loaded": 1,
            }

    def rejected(company: str, job_title: str, **_: Any) -> Any:
        calls.append(company)
        return _Rejected()

    cache = CompanySiteCache(tmp_path)
    get_company_site("job-8", "Tiny Startup", "Founder", cache=cache, finder=rejected)
    second = get_company_site(
        "job-8", "Tiny Startup", "Founder", cache=cache, finder=rejected
    )
    assert len(calls) == 1
    assert second["cached"] is True


def test_real_none_is_cached(tmp_path: Path) -> None:
    """A search that ran and found nothing is cached like any other outcome.

    Args:
        tmp_path: Pytest temp directory.
    """
    calls: List[str] = []

    class _Empty:
        def to_dict(self) -> Dict[str, Any]:
            return {"level": "none", "url": None, "search_failed": False}

    def empty(company: str, job_title: str, **_: Any) -> Any:
        calls.append(company)
        return _Empty()

    cache = CompanySiteCache(tmp_path)
    get_company_site("job-6", "Tiny Startup", "Founder", cache=cache, finder=empty)
    second = get_company_site(
        "job-6", "Tiny Startup", "Founder", cache=cache, finder=empty
    )
    assert len(calls) == 1
    assert second["cached"] is True


def test_service_refresh_runs_finder_again(tmp_path: Path) -> None:
    """With refresh on, the finder runs again even when a result is cached.

    Args:
        tmp_path: Pytest temp directory.
    """
    calls: List[str] = []
    cache = CompanySiteCache(tmp_path)
    fake = _fake_finder(calls)
    get_company_site("job-4", "Kestrel Insurance", "Analyst", cache=cache, finder=fake)
    refreshed = get_company_site(
        "job-4",
        "Kestrel Insurance",
        "Analyst",
        refresh=True,
        cache=cache,
        finder=fake,
    )
    assert len(calls) == 2
    assert refreshed["cached"] is False
