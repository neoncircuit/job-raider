"""
Flag possible duplicate listings without removing them.

``deduplicate`` still removes only a repeated ``job_id``. This module
groups the remaining listings by two keys and writes
``metadata["possible_duplicates"]`` on copies of the flagged listings.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import DefaultDict, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from ..metrics.outcome_tracker import (
    _usable_match_label,
    normalize_match_label,
    normalize_match_url,
)
from .job_listing import JobListing

REASON_SAME_URL = "same_url"
REASON_SAME_COMPANY_TITLE_LOCATION = "same_company_title_location"

TRACKING_PARAM_NAMES: frozenset[str] = frozenset({"trk", "trkinfo", "refid", "ref"})
LEGAL_SUFFIXES: Tuple[str, ...] = (
    "private limited",
    "sdn bhd",
    "pte ltd",
    "limited",
    "pte",
    "ltd",
    "inc",
    "llc",
    "llp",
    "corp",
    "co",
    "bhd",
)
_PUNCT = re.compile(r"[^\w\s+#]+", flags=re.UNICODE)

FlagRow = Dict[str, str]
FlagMap = Dict[str, List[FlagRow]]
GroupKey = Tuple[str, ...]


def strip_punctuation(value: str) -> str:
    """
    Replace punctuation with spaces and collapse whitespace.

    ``+`` and ``#`` stay, so titles such as C++ and C# stay distinct.

    Args:
        value: Already-lowercased text.

    Returns:
        Tokens joined by one space.
    """
    return " ".join(_PUNCT.sub(" ", value).split())


def normalize_title_or_location(value: Optional[str]) -> str:
    """
    Normalize a title or location for a flag key.

    Args:
        value: Title or location.

    Returns:
        Lowercased text without punctuation. Abbreviations are not expanded.
    """
    return strip_punctuation(normalize_match_label(value or ""))


def normalize_company_name(value: Optional[str]) -> str:
    """
    Normalize a company name and drop a trailing legal suffix.

    Suffixes are whole words at the end of the name, so ``Disco`` keeps
    its last syllable.

    Args:
        value: Company name.

    Returns:
        Normalized company name, or an empty string.
    """
    text = strip_punctuation(normalize_match_label(value or ""))
    changed = True
    while text and changed:
        changed = False
        for suffix in LEGAL_SUFFIXES:
            if text == suffix:
                return ""
            ending = f" {suffix}"
            if text.endswith(ending):
                text = text[: -len(ending)].rstrip()
                changed = True
                break
    return text


def clean_match_url(raw: Optional[str]) -> Optional[str]:
    """
    Normalize a listing URL and drop the fragment and tracking parameters.

    Tracking names are ``utm_*``, ``trk``, ``trkInfo``, ``refId``, and
    ``ref``. Other query parameters stay.

    Args:
        raw: Stored listing URL.

    Returns:
        The cleaned URL, or None when the URL is not usable.
    """
    if raw is None:
        return None
    base = normalize_match_url(str(raw))
    if not base:
        return None
    parsed = urlparse(base)
    kept = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in TRACKING_PARAM_NAMES
    ]
    cleaned = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(kept), "")
    )
    return cleaned.rstrip("/") or None


def _listing_url(listing: JobListing) -> Optional[str]:
    """
    Read a listing URL as a string.

    Args:
        listing: One listing.

    Returns:
        The URL string, or None.
    """
    if listing.source_url is None:
        return None
    return str(listing.source_url)


def find_possible_duplicates(listings: Sequence[JobListing]) -> FlagMap:
    """
    Group listings by the two flag rules and return per-id flag rows.

    Args:
        listings: Listings that already have unique ``job_id`` values.

    Returns:
        ``job_id`` to a list of ``{"job_id", "reason"}`` rows, sorted by
        the other ``job_id``. When both rules match, the reason is
        ``same_url``.
    """
    url_groups: DefaultDict[GroupKey, List[JobListing]] = defaultdict(list)
    company_groups: DefaultDict[GroupKey, List[JobListing]] = defaultdict(list)

    for listing in listings:
        title = normalize_title_or_location(listing.title)
        location = normalize_title_or_location(listing.location)
        url = clean_match_url(_listing_url(listing))
        if url and title and location:
            url_groups[(url, title, location)].append(listing)
        if (
            _usable_match_label(listing.company or "")
            and _usable_match_label(listing.title or "")
            and _usable_match_label(listing.location or "")
        ):
            company = normalize_company_name(listing.company)
            if company and title and location and _usable_match_label(company):
                company_groups[(company, title, location)].append(listing)

    reasons: Dict[str, Dict[str, str]] = defaultdict(dict)

    def _add_group(members: Sequence[JobListing], reason: str) -> None:
        """
        Record flags for every pair in one group.

        Args:
            members: Listings that share a key.
            reason: Flag reason.

        Returns:
            None.
        """
        if len(members) < 2:
            return
        ids = [item.job_id for item in members]
        for left in ids:
            for right in ids:
                if left == right:
                    continue
                current = reasons[left].get(right)
                if current == REASON_SAME_URL:
                    continue
                if reason == REASON_SAME_URL or current is None:
                    reasons[left][right] = reason

    for members in url_groups.values():
        _add_group(members, REASON_SAME_URL)
    for members in company_groups.values():
        _add_group(members, REASON_SAME_COMPANY_TITLE_LOCATION)

    return {
        job_id: [
            {"job_id": other, "reason": reasons[job_id][other]}
            for other in sorted(reasons[job_id])
        ]
        for job_id in reasons
    }


def flag_possible_duplicates(listings: Sequence[JobListing]) -> List[JobListing]:
    """
    Return listings with flag metadata on copies of the flagged rows.

    Args:
        listings: Unique-``job_id`` listings.

    Returns:
        The same listings, in order. Flagged rows are ``model_copy``
        results. Input objects are not changed.
    """
    flags = find_possible_duplicates(listings)
    result: List[JobListing] = []
    for listing in listings:
        rows = flags.get(listing.job_id)
        if not rows:
            if "possible_duplicates" in listing.metadata:
                metadata = dict(listing.metadata)
                metadata.pop("possible_duplicates")
                result.append(listing.model_copy(update={"metadata": metadata}))
            else:
                result.append(listing)
            continue
        metadata = dict(listing.metadata)
        metadata["possible_duplicates"] = rows
        result.append(listing.model_copy(update={"metadata": metadata}))
    return result


def summarize_duplicate_flags(listings: Iterable[JobListing]) -> Dict[str, int]:
    """
    Count flagged listings and undirected flagged pairs by reason.

    Args:
        listings: Listings after ``deduplicate``.

    Returns:
        ``flagged_listings`` and a pair count per reason.
    """
    flagged_listings = 0
    pair_counts = {
        REASON_SAME_URL: 0,
        REASON_SAME_COMPANY_TITLE_LOCATION: 0,
    }
    seen_pairs: set[Tuple[str, str]] = set()
    for listing in listings:
        rows = listing.metadata.get("possible_duplicates") or []
        if rows:
            flagged_listings += 1
        for row in rows:
            other = str(row.get("job_id") or "")
            first_id, second_id = sorted((listing.job_id, other))
            pair = (first_id, second_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            reason = str(row.get("reason") or "")
            if reason in pair_counts:
                pair_counts[reason] += 1
    return {
        "flagged_listings": flagged_listings,
        "flagged_pairs_same_url": pair_counts[REASON_SAME_URL],
        "flagged_pairs_same_company_title_location": pair_counts[
            REASON_SAME_COMPANY_TITLE_LOCATION
        ],
    }
