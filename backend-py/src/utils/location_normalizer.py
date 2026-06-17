"""
Job Raider - Location Normalizer

Normalizes location names and country codes for consistency.
"""

from typing import Optional

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
    "sg": "Singapore",
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
        city_part = parts[0]
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
