"""
Unit tests for the company site finder (company-site-apply, step S1).

Network-free: search and fetch are injected. The 20 labelled cases in
``tests/fixtures/company_site/cases.json`` are the rule R1 measure. Labels were
written before the finder code and must not be changed to fit the code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
import requests

from src.submission.company_site import (
    CompanySiteResult,
    clean_company_name,
    find_company_site,
    is_portal_url,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "company_site" / "cases.json"
)
MIN_EXACT_RECALL = 0.8


def _load_cases() -> List[Dict[str, Any]]:
    """
    Load the labelled fixture cases.

    Returns:
        The list of case dicts from ``cases.json``.
    """
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return list(data["cases"])


CASES = _load_cases()


def _run_case(
    case: Dict[str, Any],
    fetched: Optional[List[str]] = None,
) -> CompanySiteResult:
    """
    Run the finder on one fixture case with fake search and fetch.

    Args:
        case: A labelled case from the fixture file.
        fetched: Optional list that receives every URL the finder fetches.

    Returns:
        The finder result.
    """
    pages: Dict[str, Tuple[str, str]] = {
        url: (entry[0], entry[1]) for url, entry in case["pages"].items()
    }

    def fake_search(query: str) -> List[Dict[str, str]]:
        return [
            {"url": hit["url"], "title": hit["title"], "snippet": ""}
            for hit in case["results"]
        ]

    def fake_fetch(url: str) -> Tuple[str, str]:
        if fetched is not None:
            fetched.append(url)
        return pages.get(url, ("", ""))

    return find_company_site(
        case["company"],
        case["title"],
        search=fake_search,
        fetch=fake_fetch,
    )


def _is_wrong(case: Dict[str, Any], result: CompanySiteResult) -> bool:
    """
    Return True when the finder gives a link that the label does not allow.

    Args:
        case: The labelled case.
        result: The finder result for that case.

    Returns:
        True for a wrong link (any link other than the labelled one).
    """
    expected_url = case["expected"]["url"]
    return result.url is not None and result.url != expected_url


def test_fixture_has_twenty_three_unique_cases() -> None:
    """The fixture file holds the 23 labelled cases, with unique IDs."""
    ids = [case["case_id"] for case in CASES]
    assert len(CASES) == 23
    assert len(set(ids)) == 23


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_case_matches_label(case: Dict[str, Any]) -> None:
    """
    Each labelled case gives the labelled level and URL.

    Args:
        case: The labelled case.
    """
    result = _run_case(case)
    assert result.level == case["expected"]["level"]
    assert result.url == case["expected"]["url"]


def test_no_wrong_links_on_fixtures() -> None:
    """Rule R1: no case gives a link that its label does not allow."""
    wrong = [c["case_id"] for c in CASES if _is_wrong(c, _run_case(c))]
    assert wrong == []


def test_exact_posting_recall_on_fixtures() -> None:
    """Rule R1: the exact posting is found in at least 80 % of the cases that have one."""
    exact_cases = [c for c in CASES if c["expected"]["level"] == "exact"]
    hits = [
        c["case_id"]
        for c in exact_cases
        if _run_case(c).level == "exact" and _run_case(c).url == c["expected"]["url"]
    ]
    assert len(exact_cases) > 0
    assert len(hits) / len(exact_cases) >= MIN_EXACT_RECALL


def test_portal_urls_are_never_fetched() -> None:
    """Job portals are skipped before any page is fetched."""
    case = next(c for c in CASES if c["case_id"] == "cs-06")
    fetched: List[str] = []
    _run_case(case, fetched=fetched)
    assert fetched == []


def test_search_error_gives_no_link() -> None:
    """A failed search gives level none, with the reason in the evidence."""

    def failing_search(query: str) -> List[Dict[str, str]]:
        raise requests.RequestException("network down")

    result = find_company_site(
        "Lumen Analytics Pte. Ltd.",
        "Graduate Machine Learning Engineer",
        search=failing_search,
        fetch=lambda url: ("", ""),
    )
    assert result.level == "none"
    assert result.url is None
    assert any("search failed" in line for line in result.evidence)


def test_search_error_is_flagged_for_the_cache() -> None:
    """A failed search sets ``search_failed`` so the result is not cached."""

    def failing_search(query: str) -> List[Dict[str, str]]:
        raise requests.RequestException("network down")

    result = find_company_site(
        "Lumen Analytics Pte. Ltd.",
        "Graduate Machine Learning Engineer",
        search=failing_search,
        fetch=lambda url: ("", ""),
    )
    assert result.search_failed is True


def test_real_none_is_not_flagged_as_search_failure() -> None:
    """A search that works but finds nothing is a real outcome, not a failure."""
    case = next(c for c in CASES if c["case_id"] == "cs-17")
    result = _run_case(case)
    assert result.level == "none"
    assert result.search_failed is False


def test_all_pages_failed_is_counted_as_not_loaded() -> None:
    """When the only candidate page fails to load, no page is counted as loaded."""
    result = find_company_site(
        "Quillon Software Pte Ltd",
        "Software Engineer",
        search=lambda query: [
            {
                "url": "https://apply.workable.com/quillon-software/j/F41L0001",
                "title": "Software Engineer - Quillon Software",
            }
        ],
        fetch=lambda url: ("", ""),
    )
    assert result.level == "none"
    assert result.pages_attempted == 1
    assert result.pages_loaded == 0


def test_rejected_loaded_page_is_counted_as_loaded() -> None:
    """A page that loads but is rejected still counts as loaded."""
    result = find_company_site(
        "Quillon Software Pte Ltd",
        "Software Engineer",
        search=lambda query: [
            {
                "url": "https://apply.workable.com/quillon-software/j/RJ0001",
                "title": "Payments Operations Analyst - Quillon Software",
            }
        ],
        fetch=lambda url: (
            "Payments Operations Analyst - Quillon Software",
            "Quillon Software needs a Payments Operations Analyst.",
        ),
    )
    assert result.level == "none"
    assert result.pages_attempted == 1
    assert result.pages_loaded == 1


def test_portal_only_results_attempt_no_pages() -> None:
    """Portal results are never fetched, so no page is attempted."""
    case = next(c for c in CASES if c["case_id"] == "cs-06")
    result = _run_case(case)
    assert result.pages_attempted == 0
    assert result.pages_loaded == 0


def test_senior_job_matches_senior_posting() -> None:
    """The seniority rule does not block a posting whose job title has the same word."""
    result = find_company_site(
        "Quillon Software Pte Ltd",
        "Senior Software Engineer",
        search=lambda query: [
            {
                "url": "https://apply.workable.com/quillon-software/j/S3N10R02",
                "title": "Senior Software Engineer - Quillon Software",
            }
        ],
        fetch=lambda url: (
            "Senior Software Engineer - Quillon Software",
            "Quillon Software is hiring a Senior Software Engineer.",
        ),
    )
    assert result.level == "exact"


def test_result_records_time_checked_and_evidence() -> None:
    """A found link comes with evidence and a time checked."""
    case = next(c for c in CASES if c["case_id"] == "cs-01")
    result = _run_case(case)
    assert result.checked_at
    assert result.evidence
    assert result.page_title == case["pages"][case["expected"]["url"]][0]


def test_result_to_dict_is_json_ready() -> None:
    """The result serializes to plain JSON types."""
    case = next(c for c in CASES if c["case_id"] == "cs-02")
    payload = _run_case(case).to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert payload["level"] == "exact"
    assert payload["url"] == case["expected"]["url"]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Harbourline Logistics Pte Ltd", "harbourline logistics"),
        ("Corvid Robotics Pte. Ltd.", "corvid robotics"),
        ("Kestrel Insurance", "kestrel insurance"),
        ("MSI Global Pte Ltd", "msi global"),
    ],
)
def test_clean_company_name_drops_legal_suffix(name: str, expected: str) -> None:
    """Legal suffixes such as Pte Ltd are removed from the company name.

    Args:
        name: Company name as listed on the job.
        expected: Cleaned name used for matching.
    """
    assert clean_company_name(name) == expected


@pytest.mark.parametrize(
    ("url", "portal"),
    [
        ("https://www.mycareersfuture.gov.sg/job/it/x", True),
        ("https://www.linkedin.com/jobs/view/1", True),
        ("https://sg.indeed.com/viewjob?jk=abc", True),
        ("https://www.jobstreet.com.sg/job/987", True),
        ("https://www.corvidrobotics.com/careers", False),
        ("https://boards.greenhouse.io/lumenanalytics/jobs/1", False),
    ],
)
def test_is_portal_url(url: str, portal: bool) -> None:
    """Portal hosts are recognized; company and ATS hosts are not.

    Args:
        url: URL to check.
        portal: Expected answer.
    """
    assert is_portal_url(url) is portal
