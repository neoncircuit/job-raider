"""
Job Raider - Location Normalizer

Normalizes location names and country codes for consistency.
"""

import re
from typing import Optional, Set

# Common country code mappings
COUNTRY_CODE_MAP = {
    "sg": "Singapore",
    "us": "United States",
    "uk": "United Kingdom",
    "in": "India",
    "ca": "Canada",
    "au": "Australia",
    "de": "Germany",
    "fr": "France",
    "nl": "Netherlands",
    "jp": "Japan",
    "kr": "South Korea",
    "my": "Malaysia",
    "th": "Thailand",
    "vn": "Vietnam",
    "id": "Indonesia",
    "ph": "Philippines",
    "hk": "Hong Kong",
    "tw": "Taiwan",
    "cn": "China",
    "ae": "United Arab Emirates",
    "il": "Israel",
    "ie": "Ireland",
    "ch": "Switzerland",
    "se": "Sweden",
    "no": "Norway",
    "dk": "Denmark",
    "fi": "Finland",
    "it": "Italy",
    "es": "Spain",
    "pt": "Portugal",
    "gr": "Greece",
    "pl": "Poland",
    "cz": "Czech Republic",
    "ro": "Romania",
    "hu": "Hungary",
    "br": "Brazil",
    "ar": "Argentina",
    "mx": "Mexico",
    "co": "Colombia",
    "cl": "Chile",
    "pe": "Peru",
    "za": "South Africa",
    "nz": "New Zealand",
}

# City to country mapping for common tech hubs
CITY_COUNTRY_MAP = {
    "singapore": "Singapore, SG",
    "san francisco": "San Francisco, US",
    "new york": "New York, US",
    "seattle": "Seattle, US",
    "austin": "Austin, US",
    "boston": "Boston, US",
    "london": "London, UK",
    "paris": "Paris, FR",
    "berlin": "Berlin, DE",
    "amsterdam": "Amsterdam, NL",
    "dublin": "Dublin, IE",
    "tel aviv": "Tel Aviv, IL",
    "tokyo": "Tokyo, JP",
    "seoul": "Seoul, KR",
    "shanghai": "Shanghai, CN",
    "beijing": "Beijing, CN",
    "bangalore": "Bangalore, IN",
    "mumbai": "Mumbai, IN",
    "sydney": "Sydney, AU",
    "melbourne": "Melbourne, AU",
    "toronto": "Toronto, CA",
    "vancouver": "Vancouver, CA",
}

# Bidirectional alias map for common location short forms.
# Each key maps to the set of synonymous strings used for matching.
LOCATION_ALIASES = {
    "us": {"usa", "united states"},
    "usa": {"us", "united states"},
    "united states": {"us", "usa"},
    "uk": {"gb", "united kingdom"},
    "gb": {"uk", "united kingdom"},
    "united kingdom": {"uk", "gb"},
    "nyc": {"new york"},
    "new york": {"nyc"},
    "sf": {"san francisco"},
    "san francisco": {"sf"},
    "la": {"los angeles"},
    "los angeles": {"la"},
    "sg": {"singapore"},
    "singapore": {"sg"},
}


def expand_location_aliases(location: Optional[str]) -> Set[str]:
    """
    Expand a location string into a set of normalized matching candidates.

    The returned set always contains the lower-cased input (with and without
    spaces) plus any known synonyms, country-code expansions, and recognized
    city names. This lets callers match "US" to "United States", "NYC" to
    "New York", etc.

    Args:
        location: Raw location string (may be None).

    Returns:
        Set of lower-cased candidate strings. Empty when input is empty.
    """
    if not location:
        return set()

    raw = location.strip().lower()
    if not raw:
        return set()

    variants = {raw, raw.replace(" ", "")}

    # Country-code expansion (e.g. "us" -> "united states")
    if raw in COUNTRY_CODE_MAP:
        variants.add(COUNTRY_CODE_MAP[raw].lower())

    # Recognized city names (e.g. "san francisco" -> "san francisco")
    for city in CITY_COUNTRY_MAP:
        if city in raw or raw == city:
            variants.add(city)

    # Static bidirectional aliases (e.g. "sf" <-> "san francisco")
    for token in list(variants) + raw.split():
        if token in LOCATION_ALIASES:
            variants.update(LOCATION_ALIASES[token])

    return {v for v in variants if v}


def location_matches(target: str, listing_location: Optional[str]) -> bool:
    """
    Check whether a target location matches a job listing location.

    Matching is case-insensitive and supports alias expansion (see
    :func:`expand_location_aliases`). Very short candidates (two characters
    or fewer) are matched with word boundaries to avoid false positives such
    as "la" matching "California".

    Args:
        target: Desired location (e.g. "US", "San Francisco", "Remote").
        listing_location: Location text from a job listing.

    Returns:
        True when any expanded alias of ``target`` is found in the listing
        location.
    """
    if not target or not listing_location:
        return False

    candidates = expand_location_aliases(target)
    if not candidates:
        return False

    haystack = listing_location.lower()

    for candidate in candidates:
        if len(candidate) <= 2:
            pattern = r"\b" + re.escape(candidate) + r"\b"
            if re.search(pattern, haystack):
                return True
        elif candidate in haystack:
            return True

    return False


def normalize_location(location: Optional[str]) -> str:
    """
    Normalize a location string to a consistent format.

    Args:
        location: Raw location string

    Returns:
        Normalized location string
    """
    if not location:
        return "Not Specified"

    loc_lower = location.strip().lower()

    # Check for standalone country codes
    if len(loc_lower) == 2 and loc_lower in COUNTRY_CODE_MAP:
        country = COUNTRY_CODE_MAP[loc_lower]
        return f"{country}, {loc_lower.upper()}"

    # Check for common city names
    for city, normalized in CITY_COUNTRY_MAP.items():
        if city in loc_lower or loc_lower == city:
            return normalized

    # Already looks formatted (has comma and country code)
    if ", " in location and len(location.split(", ")[-1]) == 2:
        return location

    # Has comma but no country code - try to add one
    if ", " in location:
        parts = location.split(", ")
        # Check if the last part might be a country name
        last_part = parts[-1].lower()
        for code, country in COUNTRY_CODE_MAP.items():
            if country.lower() in last_part or last_part == country.lower():
                return f"{', '.join(parts[:-1])}, {code.upper()}"

    # Just return the original if we can't normalize
    return location


def normalize_all_locations(location: Optional[str]) -> str:
    """
    Normalize location for display in job listings.

    This is a simpler version that handles common cases like "Sg" -> "Singapore, SG".

    Args:
        location: Raw location string

    Returns:
        Normalized location string
    """
    return normalize_location(location)
