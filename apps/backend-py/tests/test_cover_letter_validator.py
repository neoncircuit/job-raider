"""
Tests for CoverLetterValidator.

Unit tests for cover letter quality validation covering structure,
content, tone, accuracy, and scoring.
"""

from datetime import datetime

import pytest

from src.generation.cover_letter_validator import (
    CoverLetterIssue,
    CoverLetterValidationResult,
    CoverLetterValidator,
)
from src.generation.cover_letter_writer import GeneratedCoverLetter
from src.generation.selector import SelectionOutput
from src.models.job_listing import JobListing, JobRequirement, JobSource
from src.models.job_listing import Skill as JobSkill
from src.models.user_profile import (
    ContactInfo,
    Education,
    ProficiencyLevel,
    Project,
    Skill,
    SkillCategory,
    TargetJob,
    UserProfile,
    WorkExperience,
)


@pytest.fixture
def sample_profile():
    """Create a sample user profile for testing."""
    return UserProfile(
        name="John Doe",
        contact=ContactInfo(
            email="john@example.com",
            location="San Francisco, CA",
        ),
        summary="Software engineer with 5 years of experience",
        skills=[
            Skill(
                name="Python",
                category=SkillCategory.PROGRAMMING_LANGUAGE,
                proficiency=ProficiencyLevel.ADVANCED,
                years_of_experience=5,
            ),
            Skill(
                name="React",
                category=SkillCategory.FRAMEWORK,
                proficiency=ProficiencyLevel.INTERMEDIATE,
                years_of_experience=2,
            ),
        ],
        projects=[
            Project(
                name="E-commerce Platform",
                description="Built a full-stack e-commerce platform",
                technologies=["Python", "Django", "React", "PostgreSQL"],
            ),
            Project(
                name="Task Management App",
                description="A task management application",
                technologies=["JavaScript", "React", "Node.js"],
            ),
        ],
        experience=[
            WorkExperience(
                company="Tech Corp",
                title="Senior Software Engineer",
                location="San Francisco, CA",
                start_date=datetime(2020, 1, 1),
                description="Led development of web applications",
                highlights=["Reduced API latency by 40%"],
            ),
        ],
        education=[
            Education(
                school="University of California",
                degree="Bachelor of Science",
                field_of_study="Computer Science",
                end_date=datetime(2018, 5, 1),
            ),
        ],
        target_job=TargetJob(
            keywords=["software engineer", "python", "react"],
            locations=["San Francisco", "Remote"],
        ),
    )


@pytest.fixture
def sample_job():
    """Create a sample job listing for testing."""
    return JobListing(
        title="Senior Python Developer",
        company="TechStartup Inc",
        job_id="test_job_123",
        source=JobSource.MANUAL,
        location="San Francisco, CA",
        description="We are looking for a senior Python developer.",
        requirements=[
            JobRequirement(text="5+ years of Python experience"),
        ],
        skills=[
            JobSkill(name="Python"),
            JobSkill(name="Django"),
            JobSkill(name="React"),
        ],
    )


@pytest.fixture
def sample_selection():
    """Create a sample selection output for testing."""
    return SelectionOutput(
        selected_projects=[
            {"name": "E-commerce Platform", "reason": "Uses Python and React"},
            {"name": "Task Management App", "reason": "Demonstrates full-stack skills"},
        ],
        keywords_to_emphasize=["Python", "Django", "React", "API", "full-stack"],
        key_achievements=["Reduced API latency by 40%"],
        summary_suggestion="Experienced Python developer with full-stack expertise",
        raw_response="",
    )


GOOD_COVER_LETTER = GeneratedCoverLetter(
    content=(
        "I am excited to apply for the Senior Python Developer position at "
        "TechStartup Inc. With five years of experience building scalable web "
        "applications, I am confident in my ability to contribute meaningfully "
        "to your engineering team.\n\n"
        "My work on the E-commerce Platform, a full-stack application built with "
        "Python, Django, and React, directly aligns with your requirements. I "
        "reduced API latency by 40% through strategic optimization, demonstrating "
        "both technical depth and a results-driven approach. Additionally, my "
        "experience on the Task Management App further solidified my full-stack "
        "capabilities and deepened my understanding of collaborative software "
        "development practices.\n\n"
        "I would welcome the opportunity to discuss how my background in Python "
        "development and full-stack engineering can benefit TechStartup Inc. "
        "Thank you for considering my application."
    ),
    highlighted_experiences=[],
    word_count=128,
    model_used="qwen2.5:7b",
)


SHORT_COVER_LETTER = GeneratedCoverLetter(
    content="I want this job.",
    highlighted_experiences=[],
    word_count=4,
    model_used="test",
)


GENERIC_COVER_LETTER = GeneratedCoverLetter(
    content=(
        "I am writing to apply for the position at your company. "
        "I have experience in software development and believe I would be "
        "a good fit for the team. I have worked on various projects and "
        "have strong skills in multiple technologies.\n\n"
        "I am a hard worker and learn quickly. My previous experience "
        "has prepared me well for this opportunity.\n\n"
        "I hope to hear from you soon."
    ),
    highlighted_experiences=[],
    word_count=65,
    model_used="test",
)


class TestCoverLetterValidator:
    """Test suite for CoverLetterValidator."""

    def test_validates_good_letter(self, sample_job, sample_profile, sample_selection):
        """Test that a well-structured cover letter passes validation."""
        validator = CoverLetterValidator()
        result = validator.validate(
            GOOD_COVER_LETTER, sample_job, sample_profile, sample_selection
        )

        assert isinstance(result, CoverLetterValidationResult)
        assert result.score > 70
        assert result.content_score > 70
        assert CoverLetterIssue.MISSING_COMPANY not in result.issues
        assert CoverLetterIssue.MISSING_JOB_TITLE not in result.issues

    def test_detects_too_short(self, sample_job, sample_profile, sample_selection):
        """Test that a very short cover letter is flagged."""
        validator = CoverLetterValidator()
        result = validator.validate(
            SHORT_COVER_LETTER, sample_job, sample_profile, sample_selection
        )

        assert CoverLetterIssue.TOO_SHORT in result.issues
        assert result.structure_score < 80

    def test_detects_missing_company(
        self, sample_job, sample_profile, sample_selection
    ):
        """Test that missing company name is flagged."""
        letter = GeneratedCoverLetter(
            content=(
                "Some content without the company name mentioned.\n\n"
                "More content here about the Senior Python Developer role.\n\n"
                "Thank you for considering me."
            ),
            highlighted_experiences=[],
            word_count=20,
            model_used="test",
        )
        validator = CoverLetterValidator()
        result = validator.validate(
            letter, sample_job, sample_profile, sample_selection
        )

        assert CoverLetterIssue.MISSING_COMPANY in result.issues
        assert result.content_score < 100

    def test_detects_missing_job_title(
        self, sample_job, sample_profile, sample_selection
    ):
        """Test that missing job title is flagged."""
        letter = GeneratedCoverLetter(
            content=(
                "I am excited to join TechStartup Inc in a new capacity.\n\n"
                "My E-commerce Platform experience is relevant.\n\n"
                "I look forward to discussing this with you."
            ),
            highlighted_experiences=[],
            word_count=25,
            model_used="test",
        )
        validator = CoverLetterValidator()
        result = validator.validate(
            letter, sample_job, sample_profile, sample_selection
        )

        assert CoverLetterIssue.MISSING_JOB_TITLE in result.issues

    def test_detects_generic_opening(
        self, sample_job, sample_profile, sample_selection
    ):
        """Test that generic opening phrases are flagged."""
        validator = CoverLetterValidator()
        result = validator.validate(
            GENERIC_COVER_LETTER, sample_job, sample_profile, sample_selection
        )

        assert CoverLetterIssue.GENERIC_OPENING in result.issues
        assert result.tone_score < 100

    def test_classic_style_allows_traditional_opening(
        self, sample_job, sample_profile, sample_selection
    ):
        """Classic style does not flag traditional apply openers."""
        validator = CoverLetterValidator(strict_mode=False)
        result = validator.validate(
            GENERIC_COVER_LETTER,
            sample_job,
            sample_profile,
            sample_selection,
            style="classic",
        )

        assert CoverLetterIssue.GENERIC_OPENING not in result.issues
        assert result.details.get("has_generic_opening") is False

    def test_detects_missing_selected_project(
        self, sample_job, sample_profile, sample_selection
    ):
        """Test that missing project references are flagged."""
        letter = GeneratedCoverLetter(
            content=(
                "I am excited to apply for the Senior Python Developer role at "
                "TechStartup Inc.\n\n"
                "I have strong Python skills and years of relevant experience.\n\n"
                "Thank you for considering my application."
            ),
            highlighted_experiences=[],
            word_count=30,
            model_used="test",
        )
        validator = CoverLetterValidator()
        result = validator.validate(
            letter, sample_job, sample_profile, sample_selection
        )

        assert CoverLetterIssue.MISSING_SELECTED_PROJECT in result.issues

    def test_scoring_dimensions(self, sample_job, sample_profile, sample_selection):
        """Test that all three scoring dimensions are populated."""
        validator = CoverLetterValidator()
        result = validator.validate(
            GOOD_COVER_LETTER, sample_job, sample_profile, sample_selection
        )

        assert 0 <= result.structure_score <= 100
        assert 0 <= result.content_score <= 100
        assert 0 <= result.tone_score <= 100
        assert 0 <= result.score <= 100

    def test_recommendation_levels(self, sample_job, sample_profile, sample_selection):
        """Test that recommendation is set correctly based on score."""
        validator = CoverLetterValidator()

        good_result = validator.validate(
            GOOD_COVER_LETTER, sample_job, sample_profile, sample_selection
        )
        assert good_result.recommendation in ("approve", "needs_revision")

        bad_result = validator.validate(
            SHORT_COVER_LETTER, sample_job, sample_profile, sample_selection
        )
        assert bad_result.recommendation in ("needs_revision", "reject")

    def test_details_populated(self, sample_job, sample_profile, sample_selection):
        """Test that validation details are populated."""
        validator = CoverLetterValidator()
        result = validator.validate(
            GOOD_COVER_LETTER, sample_job, sample_profile, sample_selection
        )

        assert "word_count" in result.details
        assert "paragraph_count" in result.details
        assert "company_mentioned" in result.details
        assert "job_title_mentioned" in result.details
        assert "referenced_projects" in result.details
        assert "ungrounded_sentences" in result.details
        assert isinstance(result.details["ungrounded_sentences"], list)
        assert "claim_overclaims" in result.details
        assert isinstance(result.details["claim_overclaims"], list)

    def test_strict_mode_blocks_needs_revision(
        self, sample_job, sample_profile, sample_selection
    ):
        """Test that strict mode blocks 'needs_revision' results."""
        validator = CoverLetterValidator(strict_mode=True)

        letter = GeneratedCoverLetter(
            content=(
                "Some decent content for TechStartup Inc about the "
                "Senior Python Developer role.\n\n"
                "I worked on the E-commerce Platform with Python.\n\n"
                "Thank you for considering."
            ),
            highlighted_experiences=[],
            word_count=30,
            model_used="test",
        )

        result = validator.validate(
            letter, sample_job, sample_profile, sample_selection
        )

        if result.recommendation == "needs_revision":
            assert not result.is_valid

    def test_lenient_mode_allows_needs_revision(
        self, sample_job, sample_profile, sample_selection
    ):
        """Test that lenient mode allows 'needs_revision' results."""
        validator = CoverLetterValidator(strict_mode=False)

        letter = GeneratedCoverLetter(
            content=(
                "Some decent content for TechStartup Inc about the "
                "Senior Python Developer role.\n\n"
                "I worked on the E-commerce Platform with Python.\n\n"
                "Thank you for considering."
            ),
            highlighted_experiences=[],
            word_count=30,
            model_used="test",
        )

        result = validator.validate(
            letter, sample_job, sample_profile, sample_selection
        )

        if result.recommendation == "needs_revision":
            assert result.is_valid

    def test_fallback_to_deterministic_when_no_llm(
        self, sample_job, sample_profile, sample_selection
    ):
        """Test validate_with_llm falls back to deterministic without router."""
        validator = CoverLetterValidator(llm_router=None)
        result = validator.validate_with_llm(
            GOOD_COVER_LETTER, sample_job, sample_profile, sample_selection
        )

        assert isinstance(result, CoverLetterValidationResult)
        assert result.score > 0


class TestCoverLetterValidationResult:
    """Test suite for CoverLetterValidationResult dataclass."""

    def test_dataclass_fields(self):
        """Test CoverLetterValidationResult has all required fields."""
        result = CoverLetterValidationResult(
            is_valid=True,
            score=85,
            issues=[],
            word_count=250,
            structure_score=90,
            content_score=80,
            tone_score=85,
            recommendation="approve",
            details={},
        )

        assert result.is_valid is True
        assert result.score == 85
        assert result.word_count == 250
        assert result.recommendation == "approve"


class TestJdCoverage:
    """Test suite for the JD coverage cross-check."""

    def test_structured_skills_all_matched(
        self, sample_job, sample_profile, sample_selection
    ):
        """Letter mentioning every required skill passes the cross-check."""
        validator = CoverLetterValidator()
        result = validator.validate(
            GOOD_COVER_LETTER, sample_job, sample_profile, sample_selection
        )

        coverage = result.details["jd_coverage"]
        assert coverage["source"] == "structured"
        assert set(coverage["matched"]) == {"Python", "Django", "React"}
        assert coverage["missing"] == []
        assert CoverLetterIssue.LOW_JD_COVERAGE not in result.issues

    def test_detects_low_coverage(self, sample_job, sample_profile, sample_selection):
        """Letter addressing under half the required skills is flagged."""
        validator = CoverLetterValidator()
        result = validator.validate(
            GENERIC_COVER_LETTER, sample_job, sample_profile, sample_selection
        )

        coverage = result.details["jd_coverage"]
        assert set(coverage["missing"]) == {"Python", "Django", "React"}
        assert CoverLetterIssue.LOW_JD_COVERAGE in result.issues

    def test_profile_match_fallback_for_pasted_jd(
        self, sample_profile, sample_selection
    ):
        """Manual jobs with no parsed skills fall back to profile matching."""
        job = JobListing(
            title="Senior Python Developer",
            company="TechStartup Inc",
            job_id="manual-abc123",
            source=JobSource.MANUAL,
            description=(
                "We need someone strong in Python and React to build our "
                "customer-facing dashboard."
            ),
        )
        validator = CoverLetterValidator()
        result = validator.validate(
            GOOD_COVER_LETTER, job, sample_profile, sample_selection
        )

        coverage = result.details["jd_coverage"]
        assert coverage["source"] == "profile_match"
        assert set(coverage["matched"]) == {"Python", "React"}
        assert CoverLetterIssue.LOW_JD_COVERAGE not in result.issues

    def test_insufficient_signal_skips_judgement(
        self, sample_profile, sample_selection
    ):
        """Fewer than two matchable terms produces no coverage verdict."""
        job = JobListing(
            title="Senior Rust Developer",
            company="TechStartup Inc",
            job_id="manual-def456",
            source=JobSource.MANUAL,
            description="We need a Rust expert with embedded experience.",
        )
        validator = CoverLetterValidator()
        result = validator.validate(
            GENERIC_COVER_LETTER, job, sample_profile, sample_selection
        )

        coverage = result.details["jd_coverage"]
        assert coverage["source"] is None
        assert CoverLetterIssue.LOW_JD_COVERAGE not in result.issues

    def test_term_matching_uses_word_boundaries(self):
        """Short skill names must not match substrings of other words."""
        match = CoverLetterValidator._term_in_text
        assert match("go", "we use go daily") is True
        assert match("go", "we use golang and mongodb") is False
        assert match("c++", "experience with c++ and java") is True
        assert match("r", "premier league") is False
