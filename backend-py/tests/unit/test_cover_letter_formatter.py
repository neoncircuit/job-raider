"""
Unit tests for the cover-letter formatter.

Tests cover:
- DOCX export creates a non-empty file
- PDF export creates a non-empty file
- Formatter returns errors gracefully when libraries are unavailable
- Sender block is included when options provide sender details

Author: Job Raider
Date: 2026-06-29
"""

from pathlib import Path

import pytest

from src.generation.cover_letter_formatter import (
    CoverLetterExportOptions,
    CoverLetterFormatter,
)


@pytest.fixture
def formatter(tmp_path):
    """Formatter writing into a temporary output directory."""
    return CoverLetterFormatter(output_dir=str(tmp_path / "outputs"))


@pytest.fixture
def sample_letter():
    """Plain-text cover letter for export tests."""
    return (
        "Dear Hiring Manager,\n\n"
        "I am excited about the Senior Engineer role at TechCorp. "
        "My background in Python, FastAPI, and scalable systems makes me a strong fit. "
        "At my previous company, I led the design of microservices serving millions of requests daily.\n\n"
        "I would welcome the opportunity to discuss how my experience aligns with TechCorp's goals.\n\n"
        "Sincerely,\nAlex Chen"
    )


class TestCoverLetterFormatter:
    """Tests for CoverLetterFormatter."""

    def test_format_docx_creates_file(self, formatter, sample_letter):
        """DOCX export should produce a readable, non-empty file."""
        pytest = __import__("pytest")
        docx = pytest.importorskip("docx")

        result = formatter.format_letter(
            content=sample_letter,
            filename="cover_letter_docx_test",
            formats=["docx"],
            company="TechCorp",
            title="Senior Engineer",
        )

        assert result.success is True
        assert result.docx_path is not None
        assert Path(result.docx_path).exists()
        assert Path(result.docx_path).stat().st_size > 0

        doc = docx.Document(result.docx_path)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "TechCorp" in full_text
        assert "Senior Engineer" in full_text

    def test_format_pdf_creates_file(self, formatter, sample_letter):
        """PDF export should produce a readable, non-empty file."""
        pytest.importorskip("reportlab")

        result = formatter.format_letter(
            content=sample_letter,
            filename="cover_letter_pdf_test",
            formats=["pdf"],
            company="TechCorp",
            title="Senior Engineer",
        )

        assert result.success is True
        assert result.pdf_path is not None
        assert Path(result.pdf_path).exists()
        assert Path(result.pdf_path).stat().st_size > 0

    def test_format_with_sender_details(self, formatter, sample_letter):
        """Sender details should appear in the exported document."""
        pytest.importorskip("docx")

        options = CoverLetterExportOptions(
            sender_name="Alex Chen",
            sender_email="alex.chen@example.com",
            sender_location="San Francisco, CA",
        )

        result = formatter.format_letter(
            content=sample_letter,
            filename="cover_letter_sender_test",
            formats=["docx"],
            company="TechCorp",
            title="Senior Engineer",
            options=options,
        )

        assert result.success is True
        doc = __import__("docx").Document(result.docx_path)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Alex Chen" in full_text
        assert "alex.chen@example.com" in full_text
        assert "San Francisco, CA" in full_text

    def test_format_missing_libraries_returns_error(self, tmp_path, sample_letter):
        """If libraries are not importable, the formatter should report errors."""
        formatter = CoverLetterFormatter(output_dir=str(tmp_path / "outputs"))

        # Simulate unavailable libraries by patching module-level flags.
        import src.generation.cover_letter_formatter as formatter_module

        original_docx = formatter_module.DOCX_AVAILABLE
        original_pdf = formatter_module.REPORTLAB_AVAILABLE
        try:
            formatter_module.DOCX_AVAILABLE = False
            formatter_module.REPORTLAB_AVAILABLE = False

            result = formatter.format_letter(
                content=sample_letter,
                filename="cover_letter_no_libs",
                formats=["docx", "pdf"],
                company="TechCorp",
                title="Senior Engineer",
            )

            assert result.success is False
            assert result.docx_path is None
            assert result.pdf_path is None
            assert len(result.errors) == 2
        finally:
            formatter_module.DOCX_AVAILABLE = original_docx
            formatter_module.REPORTLAB_AVAILABLE = original_pdf
