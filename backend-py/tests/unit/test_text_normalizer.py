"""
Unit tests for text_normalizer.normalize_job_description.
"""

import pytest

from src.utils.text_normalizer import normalize_job_description


class TestHTMLEntityDecoding:
    """Tests for HTML entity decoding."""

    def test_decodes_common_entities(self):
        """Common HTML entities are decoded to plain text."""
        assert normalize_job_description("Ben &amp; Jerry&#39;s") == "Ben & Jerry's"

    def test_decodes_nbsp(self):
        """Non-breaking spaces are decoded to regular spaces."""
        result = normalize_job_description("Hello&nbsp;&nbsp;World")
        assert "Hello" in result
        assert "World" in result
        assert "\xa0" not in result

    def test_decodes_lt_gt(self):
        """Less-than/greater-than entities are decoded, then stripped as HTML tags."""
        result = normalize_job_description("5+ years &lt;required&gt;")
        # <required> looks like an HTML tag after entity decoding, so it gets stripped
        assert "5+ years" in result
        assert "<required>" not in result


class TestHTMLTagStripping:
    """Tests for residual HTML tag removal."""

    def test_strips_simple_tags(self):
        """Simple HTML tags are removed from text."""
        result = normalize_job_description(
            "We need a <strong>Python</strong> developer"
        )
        assert "<strong>" not in result
        assert "Python developer" in result

    def test_strips_div_span(self):
        """div and span tags are removed."""
        result = normalize_job_description('<div class="desc">Content here</div>')
        assert "<div" not in result
        assert "Content here" in result


class TestBulletNormalization:
    """Tests for bullet character normalization."""

    def test_normalizes_bullet_dots(self):
        """Unicode bullet dots are normalized to dashes."""
        result = normalize_job_description("Skills:\n• Python\n• Java\n• SQL")
        assert "- Python" in result
        assert "- Java" in result
        assert "- SQL" in result

    def test_normalizes_various_bullets(self):
        """Multiple bullet character types are normalized."""
        result = normalize_job_description("◦ Item 1\n▪ Item 2\n▸ Item 3\n► Item 4")
        assert "- Item 1" in result
        assert "- Item 2" in result
        assert "- Item 3" in result
        assert "- Item 4" in result

    def test_preserves_existing_dashes(self):
        """Existing dash bullets are preserved."""
        result = normalize_job_description("- Already a dash bullet")
        assert "- Already a dash bullet" in result


class TestWhitespaceCollapse:
    """Tests for whitespace normalization."""

    def test_collapses_excessive_newlines(self):
        """Three or more consecutive newlines become two."""
        result = normalize_job_description("Paragraph 1\n\n\n\n\nParagraph 2")
        assert "\n\n\n" not in result
        assert "Paragraph 1\n\nParagraph 2" in result

    def test_collapses_multiple_spaces(self):
        """Multiple consecutive spaces become one."""
        result = normalize_job_description("Python     developer     wanted")
        assert "Python developer wanted" in result

    def test_preserves_single_newlines(self):
        """Single newlines between lines are preserved."""
        result = normalize_job_description("Line 1\nLine 2")
        assert "Line 1\nLine 2" in result


class TestSectionHeaderSeparation:
    """Tests for section header formatting."""

    def test_colon_ending_line_becomes_header(self):
        """Lines ending with colon get blank line separation."""
        result = normalize_job_description("Some intro\nRequirements:\n- Python\n- SQL")
        assert "Requirements:\n\n- Python" in result

    def test_all_caps_line_becomes_header(self):
        """ALL CAPS lines get blank line separation."""
        result = normalize_job_description("Intro text\nREQUIREMENTS\n- Python")
        assert "REQUIREMENTS\n\n- Python" in result

    def test_known_keyword_becomes_header(self):
        """Known section keywords get blank line separation."""
        result = normalize_job_description("Intro\nresponsibilities\n- Build things")
        assert "responsibilities\n\n- Build things" in result


class TestBoilerplateRemoval:
    """Tests for boilerplate text removal."""

    def test_removes_eeo_statement(self):
        """Equal Opportunity Employer statements are removed."""
        text = "We need a Python developer.\n\nWe are an equal opportunity employer and value diversity."
        result = normalize_job_description(text)
        assert "equal opportunity" not in result.lower()
        assert "Python developer" in result


class TestEmptyInputHandling:
    """Tests for edge case inputs."""

    def test_empty_string_returns_empty(self):
        """Empty string input returns empty string."""
        assert normalize_job_description("") == ""

    def test_whitespace_only_returns_empty(self):
        """Whitespace-only input returns empty string."""
        assert normalize_job_description("   \n\n   ") == ""

    def test_clean_text_passes_through(self):
        """Already clean text passes through without damage."""
        clean = "We are hiring a Python developer.\n\nRequirements:\n\n- 3+ years experience\n- Django knowledge"
        result = normalize_job_description(clean)
        assert "Python developer" in result
        assert "- 3+ years experience" in result


class TestFullPipeline:
    """Integration test with realistic LinkedIn description."""

    def test_normalizes_realistic_linkedin_description(self):
        """A realistic messy LinkedIn description is fully normalized."""
        raw = (
            "<div>We are looking for a <strong>Senior Python Developer</strong> "
            "to join our team&nbsp;&nbsp;in San Francisco.</div>\n\n"
            "Requirements:\n"
            "• 5+ years of Python experience\n"
            "◦ Django or FastAPI\n"
            "▪ Cloud experience (AWS/GCP)\n"
            "\n\n\n\n"
            "RESPONSIBILITIES\n"
            "▸ Build scalable APIs\n"
            "► Mentor junior developers\n"
            "\n\n"
            "We are an equal opportunity employer and celebrate diversity. "
            "All qualified applicants will receive consideration."
        )

        result = normalize_job_description(raw)

        # HTML cleaned
        assert "<div>" not in result
        assert "<strong>" not in result

        # Entities decoded
        assert "\xa0" not in result

        # Bullets normalized
        assert "- 5+ years" in result
        assert "- Django or FastAPI" in result
        assert "- Build scalable APIs" in result

        # Whitespace collapsed
        assert "\n\n\n" not in result

        # Section headers separated
        assert "Requirements:\n\n-" in result
        assert "RESPONSIBILITIES\n\n-" in result

        # Boilerplate removed
        assert "equal opportunity" not in result.lower()

        # Core content preserved
        assert "Senior Python Developer" in result
        assert "San Francisco" in result
