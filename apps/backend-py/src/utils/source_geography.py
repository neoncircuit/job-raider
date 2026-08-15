"""
Source geography policy for job boards.

Singapore-scoped sources (MyCareersFuture, Careers@Gov, JobStreet SG)
are Singapore and remote only. District names must not be required to
contain "Singapore". Other countries skip these boards. Do not add
JobStreet country sites until Singapore is fully working.

Author: Job Raider
Date: 2026-08-15
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from .location_normalizer import expand_location_aliases, location_matches

# Careers@Gov uses a delayed public dump, not live search. JobStreet is
# SG-only; do not add MY/PH/ID JobStreet sites.
SINGAPORE_SCOPED_SOURCES = frozenset({"mycareersfuture", "careersatgov", "jobstreet"})

_SINGAPORE_ALIASES = frozenset({"singapore", "sg"})
_REMOTE_TOKENS = frozenset({"remote", "wfh", "work from home"})


def source_value(source: Any) -> str:
    """
    Normalize a JobSource enum or string to a lower-case source id.

    Args:
        source: JobSource enum, string, or None.

    Returns:
        Lower-case source id, or empty string.
    """
    if source is None:
        return ""
    return str(getattr(source, "value", source)).strip().lower()


def is_singapore_scoped_source(source: Any) -> bool:
    """
    Return whether a source is Singapore-only (plus remote).

    Args:
        source: JobSource enum or string.

    Returns:
        True for MyCareersFuture, Careers@Gov, and JobStreet SG.
    """
    return source_value(source) in SINGAPORE_SCOPED_SOURCES


def is_singapore_query(location: Optional[str]) -> bool:
    """
    Return whether a search location means Singapore.

    Args:
        location: Requested location text.

    Returns:
        True for Singapore / SG aliases.
    """
    if not location or not str(location).strip():
        return False
    aliases = expand_location_aliases(location)
    return bool(aliases & _SINGAPORE_ALIASES)


def is_remote_query(location: Optional[str]) -> bool:
    """
    Return whether a search location means remote work.

    Args:
        location: Requested location text.

    Returns:
        True when the text refers to remote work.
    """
    if not location:
        return False
    raw = location.strip().lower()
    if not raw:
        return False
    return any(token in raw for token in _REMOTE_TOKENS)


def singapore_board_applies(
    location: Optional[str],
    *,
    remote: bool = False,
) -> bool:
    """
    Return whether a Singapore-scoped board should run for this search.

    Empty location is allowed (caller did not constrain geography).
    Singapore and remote are allowed. Other countries are not.

    Args:
        location: Search location, if any.
        remote: True when the search is remote-only.

    Returns:
        True when the board should be queried.
    """
    if remote:
        return True
    if not location or not str(location).strip():
        return True
    return is_singapore_query(location) or is_remote_query(location)


def listing_allows_remote(listing: Any) -> bool:
    """
    Return whether a listing is remote or hybrid.

    Args:
        listing: JobListing or similar object.

    Returns:
        True for remote or hybrid work modes.
    """
    if getattr(listing, "is_remote", False):
        return True
    mode = getattr(listing, "work_mode", None)
    text = str(getattr(mode, "value", mode) or "").lower()
    return text in {"remote", "hybrid"}


def listing_is_sg_board_overseas(listing: Any) -> bool:
    """
    Return whether a Singapore-board listing is posted overseas.

    Args:
        listing: JobListing or similar object.

    Returns:
        True when metadata marks the row as overseas.
    """
    metadata = getattr(listing, "metadata", None) or {}
    if isinstance(metadata, dict) and metadata.get("sg_board_overseas"):
        return True
    location = (getattr(listing, "location", None) or "").lower()
    return location.startswith("overseas") or location == "overseas"


def listing_matches_requested_locations(
    listing: Any,
    locations: Iterable[str],
    *,
    include_missing: bool = True,
) -> bool:
    """
    Return whether a listing matches any requested search location.

    Singapore-scoped sources match Singapore / SG without requiring the
    word Singapore in the district string. They also match Remote when
    the listing is remote or hybrid. Other countries do not match unless
    the listing is an overseas posting whose location text matches.

    Args:
        listing: JobListing or similar object.
        locations: Requested location strings.
        include_missing: When True, non-scoped listings with no location
            are kept (Jobs search behaviour).

    Returns:
        True when the listing should be kept.
    """
    requested = [loc for loc in locations if loc and str(loc).strip()]
    if not requested:
        return True

    listing_location = getattr(listing, "location", None)
    scoped = is_singapore_scoped_source(getattr(listing, "source", None))

    if scoped:
        overseas = listing_is_sg_board_overseas(listing)
        for loc in requested:
            if is_remote_query(loc) and listing_allows_remote(listing):
                return True
            if is_singapore_query(loc) and not overseas:
                return True
            if overseas and location_matches(loc, listing_location):
                return True
        return False

    if not listing_location:
        return include_missing
    return any(location_matches(loc, listing_location) for loc in requested)
