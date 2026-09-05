"""
Unit tests for the profile PDF formatter.

Tests cover:
- PDF export creates a non-empty file
- Empty sections are omitted from the section list
- Experience highlights are capped
- Missing optional sections do not fail export

Author: Job Raider
Date: 2026-08-25
"""

from datetime import datetime
from pathlib import Path

import pytest

from src.generation.profile_formatter import (
    MAX_EXPERIENCE_HIGHLIGHTS,
    ProfileFormatter,
    collect_included_sections,
)
from src.models.user_profile import (
    Certification,
    ContactInfo,
    Education,
    Skill,
    UserProfile,
    WorkExperience,
)


@pytest.fixture
def formatter(tmp_path):
    """Formatter writing into a temporary output directory."""
    return ProfileFormatter(output_dir=str(tmp_path / "outputs"))


@pytest.fixture
def full_profile():
    """Profile with every PDF section populated."""
    return UserProfile(
        name="Alex Chen",
        contact=ContactInfo(
            email="alex@example.com",
            phone="+1 555 0100",
            location="San Francisco, CA",
            linkedin="https://www.linkedin.com/in/alexchen",
        ),
        summary="Software engineer focused on APIs and data pipelines.",
        core_skills=["Python", "FastAPI", "PostgreSQL"],
        experience=[
            WorkExperience(
                title="Software Engineer",
                company="TechCorp",
                location="Remote",
                start_date=datetime(2022, 1, 1),
                current=True,
                description="Built internal APIs.",
                highlights=[
                    "Shipped billing API used by 12 teams",
                    "Cut p95 latency by 30%",
                    "extra-1",
                    "extra-2",
                    "extra-3",
                    "extra-4",
                ],
            )
        ],
        education=[
            Education(
                degree="B.S. Computer Science",
                school="State University",
                end_date=datetime(2021, 6, 1),
                gpa=3.7,
                honors=["Dean List"],
            )
        ],
        certifications=[
            Certification(
                name="AWS Cloud Practitioner",
                issuer="Amazon",
                issue_date=datetime(2023, 3, 1),
            )
        ],
        skills=[
            Skill(name="Python"),
            Skill(name="FastAPI"),
        ],
    )


@pytest.fixture
def minimal_profile():
    """Profile with identity only (no experience/education/skills)."""
    return UserProfile(
        name="Jordan Lee",
        contact=ContactInfo(email="jordan@example.com", location="Remote"),
    )


class TestCollectIncludedSections:
    """Tests for section selection."""

    def test_full_profile_includes_all_sections(self, full_profile):
        """Populated fields should produce every planned section."""
        sections = collect_included_sections(full_profile)
        assert sections == [
            "Identity",
            "Summary",
            "Experience",
            "Education",
            "Skills",
            "Certifications",
        ]

    def test_minimal_profile_skips_empty_sections(self, minimal_profile):
        """Empty optional sections must be omitted."""
        sections = collect_included_sections(minimal_profile)
        assert sections == ["Identity"]
        assert "Summary" not in sections
        assert "Experience" not in sections
        assert "Education" not in sections
        assert "Skills" not in sections
        assert "Certifications" not in sections


class TestProfileFormatter:
    """Tests for ProfileFormatter PDF export."""

    def test_format_pdf_creates_file(self, formatter, full_profile):
        """PDF export should produce a readable, non-empty file."""
        pytest.importorskip("reportlab")

        result = formatter.format_pdf(full_profile, filename="profile_full_test")

        assert result.success is True
        assert result.pdf_path is not None
        assert Path(result.pdf_path).exists()
        assert Path(result.pdf_path).stat().st_size > 0
        assert "Experience" in result.sections_included
        assert "Certifications" in result.sections_included

    def test_format_pdf_minimal_profile(self, formatter, minimal_profile):
        """Minimal profiles should still export successfully."""
        pytest.importorskip("reportlab")

        result = formatter.format_pdf(minimal_profile, filename="profile_min_test")

        assert result.success is True
        assert result.pdf_path is not None
        assert Path(result.pdf_path).exists()
        assert result.sections_included == ["Identity"]

    def test_experience_highlights_cap_constant(self):
        """Highlight cap used by the formatter should stay at five."""
        assert MAX_EXPERIENCE_HIGHLIGHTS == 5
