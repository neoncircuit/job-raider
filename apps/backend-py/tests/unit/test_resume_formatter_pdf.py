"""
Tests for PDF resume output (resume generation fix, MH-7).

Before this fix, ``ResumeFormatter._format_pdf`` called ``Spacer`` with only
a height. The reportlab ``Spacer`` needs a width and a height, so every PDF
raised ``TypeError``. ``format_resume`` caught it, so the DOCX file was still
written and the PDF file was silently missing.
"""

from pathlib import Path

import pytest

from src.generation.formatter import REPORTLAB_AVAILABLE, ResumeFormatter
from src.generation.resume_writer import GeneratedResume

pytestmark = pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="reportlab missing")


def make_resume() -> GeneratedResume:
    """Build a resume with every section that adds a spacer to the PDF.

    Returns:
        A generated resume with a summary, experience, projects, and education.
    """
    return GeneratedResume(
        summary="Backend engineer focused on Python services.",
        skills=["Python", "FastAPI", "PostgreSQL"],
        experience=[
            {
                "title": "Software Engineer",
                "company": "Example Pte Ltd",
                "dates": "2024 - 2026",
                "highlights": ["Built a job ingestion service."],
            }
        ],
        projects=[
            {
                "name": "Job Raider",
                "description": "Local-first job search pipeline.",
                "technologies": ["Python", "Next.js"],
                "highlights": ["Deterministic cover-letter grounding."],
            }
        ],
        education=[{"degree": "BSc Computer Science", "school": "NUS", "year": "2024"}],
        raw_response="{}",
        model_used="test-model",
    )


def test_pdf_export_writes_a_pdf_file(tmp_path: Path) -> None:
    """PDF export writes a PDF file and reports no error.

    Args:
        tmp_path: Temporary output directory.
    """
    result = ResumeFormatter(output_dir=str(tmp_path)).format_resume(
        make_resume(), filename="resume_test", formats=["pdf"]
    )

    assert result.errors == []
    assert result.pdf_path is not None
    assert Path(result.pdf_path).read_bytes().startswith(b"%PDF")


def test_pdf_and_docx_are_both_written(tmp_path: Path) -> None:
    """With the default formats, the PDF and the DOCX are both written.

    Args:
        tmp_path: Temporary output directory.
    """
    result = ResumeFormatter(output_dir=str(tmp_path)).format_resume(
        make_resume(), filename="resume_test"
    )

    assert result.errors == []
    assert result.pdf_path is not None
    assert result.docx_path is not None
    assert Path(result.pdf_path).exists()
    assert Path(result.docx_path).exists()
