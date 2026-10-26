"""
Rule tests for flag-and-keep duplicate detection (Step 3.5 Stage B).

These tests follow decision 6. They do not read the committed dedupe set.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.models.job_listing import JobListing, JobListingCollection


def _listing(
    job_id: str,
    *,
    title: str = "Site Planner",
    company: str = "Oakmere Works",
    location: str = "Punggol, Singapore",
    url: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> JobListing:
    """
    Build one listing for a flag-and-keep rule test.

    Args:
        job_id: Listing identifier.
        title: Job title.
        company: Company name.
        location: Job location.
        url: Source URL. Defaults to a unique path per ``job_id``.
        extra_metadata: Extra metadata keys that must survive the call.

    Returns:
        A validated listing.
    """
    metadata = dict(extra_metadata or {})
    return JobListing(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        source="jobstreet",
        source_url=url or f"https://jobs.example.com/{job_id}",
        description="Walk the site on Monday. File the sheet before noon.",
        metadata=metadata,
    )


def _dedupe(listings: List[JobListing]) -> List[JobListing]:
    """
    Run ``deduplicate`` and return the kept listings.

    Args:
        listings: Input listings.

    Returns:
        Listings after ``deduplicate``.
    """
    return JobListingCollection(listings=listings).deduplicate().listings


def _flags(listing: JobListing) -> List[Dict[str, str]]:
    """
    Return the possible-duplicate flags on one listing.

    Args:
        listing: A listing from the result.

    Returns:
        The ``possible_duplicates`` list, or an empty list.
    """
    raw = listing.metadata.get("possible_duplicates") or []
    return list(raw)


def _flag_map(listings: List[JobListing]) -> Dict[str, List[Dict[str, str]]]:
    """
    Map each kept ``job_id`` to its flags.

    Args:
        listings: Result listings.

    Returns:
        ``job_id`` to flag list.
    """
    return {item.job_id: _flags(item) for item in listings}


def test_same_job_id_keeps_one_listing() -> None:
    """
    Two listings with one ``job_id`` give one listing.

    Returns:
        None.
    """
    first = _listing("js-100", title="Clerk")
    second = _listing("js-100", title="Other Title", company="Other Co")
    result = _dedupe([first, second])
    assert [item.job_id for item in result] == ["js-100"]
    assert result[0].title == "Clerk"


def test_different_job_ids_all_stay_when_fields_match() -> None:
    """
    Listings with different ``job_id`` values all stay.

    Returns:
        None.
    """
    left = _listing(
        "js-201",
        title="Yard Driver",
        company="Fenwick Rails",
        location="Woodlands, Singapore",
        url="https://careers.fenwick.example/yard-driver",
    )
    right = _listing(
        "js-202",
        title="Yard Driver",
        company="Fenwick Rails",
        location="Woodlands, Singapore",
        url="https://careers.fenwick.example/yard-driver",
    )
    result = _dedupe([left, right])
    assert sorted(item.job_id for item in result) == ["js-201", "js-202"]


def test_same_url_flags_fragment_slash_case_and_tracking() -> None:
    """
    Flag pairs whose cleaned URL, title, and location match.

    Returns:
        None.
    """
    cases = [
        (
            "https://jobs.example.com/posting/br-18",
            "https://jobs.example.com/posting/br-18#apply",
        ),
        (
            "https://careers.example.com/jobs/site-planner",
            "https://careers.example.com/jobs/site-planner/",
        ),
        (
            "https://jobs.example.com/Posting/BR-18",
            "https://jobs.example.com/posting/br-18",
        ),
        (
            "https://www.jobstreet.com.sg/job/22007788",
            "https://www.jobstreet.com.sg/job/22007788?utm_source=board&utm_medium=email",
        ),
        (
            "https://www.linkedin.com/jobs/view/389330044",
            "https://www.linkedin.com/jobs/view/389330044?trk=flagship&trkInfo=x&refId=1&ref=share",
        ),
    ]
    for index, (left_url, right_url) in enumerate(cases):
        left = _listing(f"url-a-{index}", url=left_url)
        right = _listing(f"url-b-{index}", url=right_url)
        flags = _flag_map(_dedupe([left, right]))
        assert {row["job_id"] for row in flags[f"url-a-{index}"]} == {f"url-b-{index}"}
        assert {row["reason"] for row in flags[f"url-a-{index}"]} == {"same_url"}
        assert {row["job_id"] for row in flags[f"url-b-{index}"]} == {f"url-a-{index}"}
        assert {row["reason"] for row in flags[f"url-b-{index}"]} == {"same_url"}


def test_same_url_does_not_flag_other_title_or_location() -> None:
    """
    A shared careers URL with another title or location is not flagged.

    Returns:
        None.
    """
    home = "https://careers.fenwickrails.example/"
    title_left = _listing("h3-a", title="Payroll Clerk", url=home)
    title_right = _listing("h3-b", title="Welder", url=home)
    title_flags = _flag_map(_dedupe([title_left, title_right]))
    assert title_flags["h3-a"] == []
    assert title_flags["h3-b"] == []

    loc_left = _listing("loc-a", location="Tuas, Singapore", url=home)
    loc_right = _listing("loc-b", location="Woodlands, Singapore", url=home)
    loc_flags = _flag_map(_dedupe([loc_left, loc_right]))
    assert loc_flags["loc-a"] == []
    assert loc_flags["loc-b"] == []


def test_same_url_keeps_non_tracking_query_parameters() -> None:
    """
    URLs that differ in a non-tracking query parameter are not flagged.

    Returns:
        None.
    """
    left = _listing("req-a", url="https://jobs.example.com/role?req=4410")
    right = _listing("req-b", url="https://jobs.example.com/role?req=4417")
    flags = _flag_map(_dedupe([left, right]))
    assert flags["req-a"] == []
    assert flags["req-b"] == []


def test_company_title_location_flags_suffix_and_punctuation() -> None:
    """
    Flag company suffix and title punctuation differences.

    Returns:
        None.
    """
    left = _listing(
        "co-a",
        title="Production Planner",
        company="Pine Kiln Pte. Ltd.",
        location="Singapore",
        url="https://www.mycareersfuture.gov.sg/job/co-a",
    )
    right = _listing(
        "co-b",
        title="production planner",
        company="Pine Kiln Pte Ltd",
        location="Singapore",
        url="https://www.jobstreet.com.sg/job/co-b",
    )
    flags = _flag_map(_dedupe([left, right]))
    assert {row["job_id"] for row in flags["co-a"]} == {"co-b"}
    assert {row["reason"] for row in flags["co-a"]} == {"same_company_title_location"}
    assert {row["job_id"] for row in flags["co-b"]} == {"co-a"}

    punct_left = _listing(
        "ti-a",
        title="Matching-Engine Engineer",
        url="https://jobs.example.com/ti-a",
    )
    punct_right = _listing(
        "ti-b",
        title="matching engine engineer",
        url="https://jobs.example.com/ti-b",
    )
    punct_flags = _flag_map(_dedupe([punct_left, punct_right]))
    assert {row["reason"] for row in punct_flags["ti-a"]} == {
        "same_company_title_location"
    }


def test_company_title_location_skips_other_place_and_placeholders() -> None:
    """
    Do not flag another location, another company, or a placeholder.

    Returns:
        None.
    """
    loc_left = _listing("h1-a", location="Tuas, Singapore")
    loc_right = _listing("h1-b", location="Woodlands, Singapore")
    loc_flags = _flag_map(_dedupe([loc_left, loc_right]))
    assert loc_flags["h1-a"] == []
    assert loc_flags["h1-b"] == []

    co_left = _listing("h4-a", company="Nerida Agency")
    co_right = _listing("h4-b", company="Amberline Press")
    co_flags = _flag_map(_dedupe([co_left, co_right]))
    assert co_flags["h4-a"] == []
    assert co_flags["h4-b"] == []

    for index, company in enumerate(("Confidential", "Unknown", "N/A", "")):
        left = _listing(
            f"ph-a-{index}",
            company=company,
            url=f"https://jobs.example.com/ph-a-{index}",
        )
        right = _listing(
            f"ph-b-{index}",
            company=company,
            url=f"https://jobs.example.com/ph-b-{index}",
        )
        flags = _flag_map(_dedupe([left, right]))
        assert flags[f"ph-a-{index}"] == []
        assert flags[f"ph-b-{index}"] == []

    title_left = _listing(
        "ph-t-a",
        title="Unknown",
        url="https://jobs.example.com/ph-t-a",
    )
    title_right = _listing(
        "ph-t-b",
        title="Unknown",
        url="https://jobs.example.com/ph-t-b",
    )
    title_flags = _flag_map(_dedupe([title_left, title_right]))
    assert title_flags["ph-t-a"] == []
    assert title_flags["ph-t-b"] == []


def test_flag_payload_is_sorted_and_does_not_name_self() -> None:
    """
    Each listing names the others, sorted by ``job_id``, and never itself.

    Returns:
        None.
    """
    listings = [
        _listing("js-30", extra_metadata={"kept": "yes"}),
        _listing("js-10"),
        _listing("js-20"),
    ]
    result = _dedupe(listings)
    flags = _flag_map(result)
    assert [row["job_id"] for row in flags["js-10"]] == ["js-20", "js-30"]
    assert [row["job_id"] for row in flags["js-20"]] == ["js-10", "js-30"]
    assert [row["job_id"] for row in flags["js-30"]] == ["js-10", "js-20"]
    for job_id, rows in flags.items():
        assert all(row["job_id"] != job_id for row in rows)
        assert all(
            row["reason"] in {"same_url", "same_company_title_location"} for row in rows
        )
    kept = next(item for item in result if item.job_id == "js-30")
    assert kept.metadata["kept"] == "yes"


def test_same_url_reason_wins_when_both_rules_match() -> None:
    """
    When both rules match, the reason is ``same_url``.

    Returns:
        None.
    """
    left = _listing(
        "both-a",
        url="https://jobs.example.com/role?utm_source=mail",
    )
    right = _listing(
        "both-b",
        url="https://jobs.example.com/role/",
    )
    flags = _flag_map(_dedupe([left, right]))
    assert flags["both-a"] == [{"job_id": "both-b", "reason": "same_url"}]
    assert flags["both-b"] == [{"job_id": "both-a", "reason": "same_url"}]


def test_deduplicate_does_not_mutate_input_listings() -> None:
    """
    The listings that the caller passed in do not gain flags.

    Returns:
        None.
    """
    left = _listing("in-a")
    right = _listing("in-b")
    _dedupe([left, right])
    assert "possible_duplicates" not in left.metadata
    assert "possible_duplicates" not in right.metadata
