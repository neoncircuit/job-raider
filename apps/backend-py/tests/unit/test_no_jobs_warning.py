"""
Tests for the no-jobs notice of a run (no-jobs-notice task).

When Scrape returns no listings, the notice must say why: a job source that
did not answer (for example MyCareersFuture HTTP 504) is not the same as a
search that found nothing, and other keywords do not help with a source that
timed out.
"""

from typing import Any, Dict, List

from src.pipeline.orchestrator import NO_JOBS_WARNING

TIMEOUT = (
    "ScrapingException: MyCareersFuture API returned HTTP 504: "
    '{"message": "Endpoint request timed out"}'
)
UNAVAILABLE = "ScrapingException: MyCareersFuture API returned HTTP 503: down"


def searches(*rows: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrape metadata with the given search rows.

    Args:
        *rows: Search rows (``source``, ``count``, ``error``).

    Returns:
        The metadata dict.
    """
    return {"searches": list(rows), "listings_count": 0}


def failed(error: str = TIMEOUT) -> Dict[str, Any]:
    """
    A MyCareersFuture search row that failed.

    Args:
        error: The error text.

    Returns:
        The search row.
    """
    return {"source": "mycareersfuture", "count": 0, "error": error}


EMPTY: Dict[str, Any] = {"source": "mycareersfuture", "count": 0, "error": None}


def test_every_search_failed_says_the_source_did_not_answer() -> None:
    """All searches timed out: the notice names the source and the reason, not keywords."""
    from src.pipeline.orchestrator import no_jobs_warning

    notice = no_jobs_warning(searches(failed(), failed(), failed()))

    assert "MyCareersFuture" in notice
    assert "timed out (HTTP 504)" in notice
    assert "try again later" in notice.lower()
    assert "keywords" not in notice.lower()
    assert "{" not in notice  # no raw response text


def test_some_searches_failed_says_both() -> None:
    """Some searches failed and others found nothing: the notice says both."""
    from src.pipeline.orchestrator import no_jobs_warning

    notice = no_jobs_warning(searches(failed(UNAVAILABLE), EMPTY))

    assert "HTTP 503" in notice
    assert "MyCareersFuture" in notice
    assert "try again later" in notice.lower()
    assert "keywords" in notice.lower()


def test_no_failed_search_keeps_the_notice() -> None:
    """Searches that ran and found nothing keep today's notice."""
    from src.pipeline.orchestrator import no_jobs_warning

    assert no_jobs_warning(searches(EMPTY, EMPTY)) == NO_JOBS_WARNING


def test_no_search_rows_keep_the_notice() -> None:
    """Missing or empty search rows keep today's notice."""
    from src.pipeline.orchestrator import no_jobs_warning

    assert no_jobs_warning({}) == NO_JOBS_WARNING
    assert no_jobs_warning(searches()) == NO_JOBS_WARNING


def test_unknown_error_reads_as_an_error() -> None:
    """An error without an HTTP status reads as "an error", with the source name."""
    from src.pipeline.orchestrator import no_jobs_warning

    rows: List[Dict[str, Any]] = [failed("ConnectionError: reset by peer")]
    notice = no_jobs_warning(searches(*rows))

    assert "MyCareersFuture" in notice
    assert "an error" in notice
    assert "reset by peer" not in notice
