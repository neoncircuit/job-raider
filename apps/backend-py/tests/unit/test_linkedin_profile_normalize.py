"""
Unit tests for LinkedIn profile text normalization.
"""

from src.utils.text_normalizer import normalize_linkedin_profile_text


class TestLinkedInProfileNormalize:
    """Profile paste/fetch cleaner removes HTML and UI chrome."""

    def test_strips_html_tags(self) -> None:
        """HTML tags and entities are removed from profile text."""
        raw = "<div>Jane Doe</div><p>Senior &amp; Engineer</p>"
        result = normalize_linkedin_profile_text(raw)
        assert "<div" not in result
        assert "Jane Doe" in result
        assert "Senior & Engineer" in result

    def test_strips_profile_chrome_lines(self) -> None:
        """LinkedIn UI chrome lines are removed."""
        raw = (
            "Jane Doe\n"
            "Software Engineer\n"
            "Show more\n"
            "Message\n"
            "Connect\n"
            "1,234 followers\n"
            "500+ connections\n"
            "People you may know\n"
            "Explore Premium\n"
            "Open to work\n"
            "Activity\n"
            "Resources\n"
            "Built scalable APIs for 5 years."
        )
        result = normalize_linkedin_profile_text(raw)
        lower = result.lower()
        assert "show more" not in lower
        assert "message" not in lower.split("\n")
        assert "connect" not in lower.split("\n")
        assert "followers" not in lower
        assert "connections" not in lower
        assert "people you may know" not in lower
        assert "explore premium" not in lower
        assert "open to work" not in lower
        assert "activity" not in lower.split("\n")
        assert "resources" not in lower.split("\n")
        assert "Built scalable APIs" in result

    def test_empty_after_clean_returns_original(self) -> None:
        """When cleaning removes everything, return stripped original."""
        raw = "   Show more\nConnect\n   "
        result = normalize_linkedin_profile_text(raw)
        assert result == raw.strip()
