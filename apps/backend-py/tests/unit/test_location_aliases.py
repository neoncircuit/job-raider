"""
Unit tests for location alias expansion and matching.

These tests verify that location-based filtering supports common short forms
and country/city aliases without matching false positives on very short
substrings.
"""

from src.utils.location_normalizer import (
    expand_location_aliases,
    location_matches,
)


class TestExpandLocationAliases:
    """Tests for the :func:`expand_location_aliases` helper."""

    def test_empty_and_none_input(self):
        """Empty or None inputs should return an empty set."""
        assert expand_location_aliases(None) == set()
        assert expand_location_aliases("") == set()
        assert expand_location_aliases("   ") == set()

    def test_base_variant_without_spaces(self):
        """The base variant should include the raw text without spaces."""
        aliases = expand_location_aliases("United States")
        assert "unitedstates" in aliases
        assert "united states" in aliases

    def test_country_code_expansion(self):
        """Two-letter country codes expand to the full country name."""
        aliases = expand_location_aliases("us")
        assert "united states" in aliases

    def test_city_aliases(self):
        """Recognized city names are included in the alias set."""
        aliases = expand_location_aliases("San Francisco")
        assert "san francisco" in aliases

    def test_static_aliases(self):
        """Static bidirectional aliases are added from the input tokens."""
        aliases = expand_location_aliases("SG")
        assert "singapore" in aliases


class TestLocationMatches:
    """Tests for the :func:`location_matches` helper."""

    def test_us_matches_united_states(self):
        """Searching for 'US' should match listings with 'United States'."""
        assert location_matches("US", "United States")

    def test_usa_matches_united_states(self):
        """Searching for 'USA' should match listings with 'United States'."""
        assert location_matches("USA", "United States")

    def test_singapore_matches_sg(self):
        """Searching for 'Singapore' should match listings with 'SG'."""
        assert location_matches("Singapore", "Singapore, SG")

    def test_sg_matches_singapore(self):
        """Searching for 'SG' should match listings with 'Singapore'."""
        assert location_matches("SG", "Singapore")

    def test_nyc_matches_new_york(self):
        """Searching for 'NYC' should match listings with 'New York'."""
        assert location_matches("NYC", "New York, US")

    def test_new_york_matches_nyc(self):
        """Searching for 'New York' should match listings with 'NYC'."""
        assert location_matches("New York", "NYC")

    def test_sf_matches_san_francisco(self):
        """Searching for 'SF' should match listings with 'San Francisco'."""
        assert location_matches("SF", "San Francisco, US")

    def test_san_francisco_matches_sf(self):
        """Searching for 'San Francisco' should match listings with 'SF'."""
        assert location_matches("San Francisco", "SF")

    def test_uk_matches_united_kingdom(self):
        """Searching for 'UK' should match listings with 'United Kingdom'."""
        assert location_matches("UK", "United Kingdom")

    def test_gb_matches_united_kingdom(self):
        """Searching for 'GB' should match listings with 'United Kingdom'."""
        assert location_matches("GB", "United Kingdom")

    def test_remote_passthrough(self):
        """'Remote' should continue to match remote listings."""
        assert location_matches("Remote", "Remote")
        assert location_matches("Remote", "Remote, US")

    def test_case_insensitive(self):
        """Matching should be case-insensitive."""
        assert location_matches("us", "UNITED STATES")
        assert location_matches("US", "united states")

    def test_la_does_not_match_california(self):
        """Short aliases must not match unrelated substrings."""
        assert not location_matches("LA", "California, US")

    def test_us_does_not_match_non_us(self):
        """'US' should not match words that simply contain the letters."""
        assert not location_matches("US", "Uzbekistan")

    def test_empty_target_or_location(self):
        """Empty targets or locations should never match."""
        assert not location_matches("", "United States")
        assert not location_matches("US", "")
        assert not location_matches(None, "United States")
        assert not location_matches("US", None)
