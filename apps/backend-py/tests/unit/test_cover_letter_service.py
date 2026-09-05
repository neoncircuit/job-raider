"""
Unit tests for the shared cover-letter service.

Tests cover:
- Default generation without review
- Review enabled but no rewrite needed
- Review enabled with rewrite triggered
- Review failure gracefully preserves draft
- Review and deep flags compose independently
- Review metadata appears in validation details

Author: Job Raider
Date: 2026-07-08
"""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.generation.cover_letter_reviewer import CoverLetterReviewResult
from src.generation.cover_letter_service import generate_cover_letter_for_profile
from src.generation.cover_letter_validator import (
    CoverLetterIssue,
    CoverLetterValidationResult,
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
def sample_job():
    """Create a sample job listing."""
    return JobListing(
        title="Senior Python Developer",
        company="TechStartup Inc",
        job_id="test_job_123",
        source=JobSource.MANUAL,
        location="San Francisco, CA",
        description="We are looking for a senior Python developer.",
        requirements=[
            JobRequirement(text="5+ years of Python experience"),
            JobRequirement(text="Experience with Django or Flask"),
        ],
        skills=[
            JobSkill(name="Python"),
            JobSkill(name="Django"),
        ],
    )


@pytest.fixture
def sample_profile():
    """Create a sample user profile."""
    return UserProfile(
        name="John Doe",
        contact=ContactInfo(email="john@example.com", location="San Francisco, CA"),
        summary="Software engineer with 5 years of experience",
        skills=[
            Skill(
                name="Python",
                category=SkillCategory.PROGRAMMING_LANGUAGE,
                proficiency=ProficiencyLevel.ADVANCED,
                years_of_experience=5,
            ),
        ],
        projects=[
            Project(
                name="E-commerce Platform",
                description="Built a full-stack e-commerce platform",
                technologies=["Python", "Django"],
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
            ),
        ],
        target_job=TargetJob(
            keywords=["software engineer", "python"],
            locations=["San Francisco"],
        ),
    )


@pytest.fixture
def mock_selector():
    """Mock ResumeSelector."""
    selector = MagicMock()
    selection = SelectionOutput(
        selected_projects=[{"name": "E-commerce Platform", "reason": "Uses Python"}],
        keywords_to_emphasize=["Python", "Django"],
        key_achievements=["Reduced API latency by 40%"],
        summary_suggestion="Experienced Python developer",
        raw_response="",
        prompt_tokens=80,
        completion_tokens=30,
        tokens_used=110,
    )
    selector.select.return_value = selection
    return selector, selection


@pytest.fixture
def mock_writer():
    """Mock CoverLetterWriter returning deterministic drafts."""
    writer = MagicMock()
    original_draft = GeneratedCoverLetter(
        content="Original draft content.",
        highlighted_experiences=[
            {"name": "E-commerce Platform", "reason": "Uses Python"}
        ],
        word_count=4,
        model_used="qwen2.5:7b",
        prompt_tokens=100,
        completion_tokens=40,
        tokens_used=140,
    )
    rewritten_draft = GeneratedCoverLetter(
        content="Rewritten draft content.",
        highlighted_experiences=[
            {"name": "E-commerce Platform", "reason": "Uses Python"}
        ],
        word_count=4,
        model_used="qwen2.5:7b",
        prompt_tokens=120,
        completion_tokens=50,
        tokens_used=170,
    )
    writer.write.return_value = original_draft
    writer.rewrite.return_value = rewritten_draft
    return writer, original_draft, rewritten_draft


@pytest.fixture
def mock_validator():
    """Mock CoverLetterValidator."""
    validator = MagicMock()
    validator.validate.return_value = CoverLetterValidationResult(
        is_valid=True,
        score=85,
        issues=[],
        word_count=4,
        structure_score=80,
        content_score=90,
        tone_score=85,
        recommendation="approve",
        details={},
    )
    validator.validate_with_llm.return_value = CoverLetterValidationResult(
        is_valid=True,
        score=92,
        issues=[],
        word_count=4,
        structure_score=90,
        content_score=95,
        tone_score=90,
        recommendation="approve",
        details={"llm_feedback": ["Strong personalization"]},
    )
    return validator


@pytest.fixture(autouse=True)
def patch_dependencies(mock_selector, mock_writer, mock_validator):
    """Patch service dependencies for every test."""
    selector, _ = mock_selector
    writer, _, _ = mock_writer
    with patch(
        "src.generation.cover_letter_service.create_router"
    ) as mock_create_router, patch(
        "src.generation.cover_letter_service.ResumeSelector", return_value=selector
    ), patch(
        "src.generation.cover_letter_service.CoverLetterWriter", return_value=writer
    ), patch(
        "src.generation.cover_letter_service.CoverLetterValidator",
        return_value=mock_validator,
    ), patch(
        "src.generation.cover_letter_service.CoverLetterReviewer"
    ) as mock_reviewer_cls:
        router = MagicMock()
        router.routes = {}
        mock_create_router.return_value = router
        yield {
            "create_router": mock_create_router,
            "selector": selector,
            "writer": writer,
            "validator": mock_validator,
            "reviewer_cls": mock_reviewer_cls,
        }


class TestGenerateCoverLetterService:
    """Test suite for generate_cover_letter_for_profile."""

    def test_generate_without_review_does_not_create_reviewer(
        self, sample_job, sample_profile, patch_dependencies
    ):
        """When review=False, no reviewer should be instantiated."""
        asyncio.run(
            generate_cover_letter_for_profile(
                sample_job, sample_profile, deep=False, review=False
            )
        )
        patch_dependencies["reviewer_cls"].assert_not_called()

    def test_generate_with_review_no_rewrite(
        self, sample_job, sample_profile, patch_dependencies, mock_writer
    ):
        """Review enabled with no rewrite keeps original draft and records metadata."""
        writer, original_draft, _ = mock_writer
        reviewer = MagicMock()
        reviewer.review.return_value = CoverLetterReviewResult(
            critique="Looks good.",
            rewrite_needed=False,
            model_used="qwen2.5:3b",
        )
        patch_dependencies["reviewer_cls"].return_value = reviewer

        response = asyncio.run(
            generate_cover_letter_for_profile(sample_job, sample_profile, review=True)
        )

        assert response.cover_letter["content"] == original_draft.content
        writer.rewrite.assert_not_called()
        assert response.validation.details["review"]["critique"] == "Looks good."
        assert response.validation.details["review"]["rewrite_needed"] is False
        assert response.validation.details["review"]["rewrite_count"] == 0
        assert response.validation.details["review"]["model_used"] == "qwen2.5:3b"

    def test_generate_with_review_triggers_rewrite(
        self, sample_job, sample_profile, patch_dependencies, mock_writer
    ):
        """Review enabled with rewrite_needed=True rewrites once and records metadata."""
        writer, _, rewritten_draft = mock_writer
        reviewer = MagicMock()
        reviewer.review.return_value = CoverLetterReviewResult(
            critique="Add stronger call to action.",
            rewrite_needed=True,
            model_used="qwen2.5:3b",
            prompt_tokens=60,
            completion_tokens=20,
            tokens_used=80,
        )
        patch_dependencies["reviewer_cls"].return_value = reviewer

        response = asyncio.run(
            generate_cover_letter_for_profile(sample_job, sample_profile, review=True)
        )

        assert response.cover_letter["content"] == rewritten_draft.content
        writer.rewrite.assert_called_once()
        assert response.validation.details["review"]["rewrite_needed"] is True
        assert response.validation.details["review"]["rewrite_count"] == 1
        assert (
            response.validation.details["review"]["critique"]
            == "Add stronger call to action."
        )
        timing = response.cover_letter["timing"]
        assert timing["generation_ms"] >= 0
        assert timing["rewrite_ms"] is not None and timing["rewrite_ms"] >= 0
        assert timing["review_ms"] is not None and timing["review_ms"] >= 0
        assert timing["total_ms"] >= timing["generation_ms"]
        assert (
            response.validation.details["review"]["rewrite_ms"] == timing["rewrite_ms"]
        )
        token_usage = response.cover_letter["token_usage"]
        assert token_usage["selection_tokens"] == 110
        assert token_usage["generation_tokens"] == 140
        assert token_usage["review_tokens"] == 80
        assert token_usage["rewrite_tokens"] == 170
        assert token_usage["total_tokens"] == 110 + 140 + 80 + 170
        assert token_usage["prompt_tokens"] == 80 + 100 + 60 + 120
        assert token_usage["completion_tokens"] == 30 + 40 + 20 + 50

    def test_generate_without_review_includes_timing_without_rewrite(
        self, sample_job, sample_profile, patch_dependencies
    ):
        """Timing always includes generation; rewrite_ms is null when unused."""
        response = asyncio.run(
            generate_cover_letter_for_profile(
                sample_job, sample_profile, deep=False, review=False
            )
        )
        timing = response.cover_letter["timing"]
        assert timing["generation_ms"] >= 0
        assert timing["rewrite_ms"] is None
        assert timing["review_ms"] is None
        assert timing["total_ms"] >= timing["generation_ms"]
        token_usage = response.cover_letter["token_usage"]
        assert token_usage["selection_tokens"] == 110
        assert token_usage["generation_tokens"] == 140
        assert token_usage["review_tokens"] is None
        assert token_usage["rewrite_tokens"] is None
        assert token_usage["total_tokens"] == 110 + 140

    def test_generate_with_review_failure_continues_with_draft(
        self, sample_job, sample_profile, patch_dependencies, mock_writer
    ):
        """Reviewer failure should keep the original draft and record the error."""
        _, original_draft, _ = mock_writer
        reviewer = MagicMock()
        reviewer.review.return_value = CoverLetterReviewResult(
            critique="Review unavailable.",
            rewrite_needed=False,
            model_used="error",
            error="Review unavailable",
        )
        patch_dependencies["reviewer_cls"].return_value = reviewer

        response = asyncio.run(
            generate_cover_letter_for_profile(sample_job, sample_profile, review=True)
        )

        assert response.cover_letter["content"] == original_draft.content
        assert response.validation.details["review"]["error"] == "Review unavailable"

    def test_generate_with_deep_and_review(
        self, sample_job, sample_profile, patch_dependencies, mock_validator
    ):
        """Deep validation and review flags should compose independently."""
        reviewer = MagicMock()
        reviewer.review.return_value = CoverLetterReviewResult(
            critique="Looks good.",
            rewrite_needed=False,
            model_used="qwen2.5:3b",
        )
        patch_dependencies["reviewer_cls"].return_value = reviewer

        response = asyncio.run(
            generate_cover_letter_for_profile(
                sample_job, sample_profile, deep=True, review=True
            )
        )

        mock_validator.validate_with_llm.assert_called_once()
        assert response.validation.score == 92
        assert response.validation.details["review"]["model_used"] == "qwen2.5:3b"

    def test_generate_review_metadata_only_when_review_enabled(
        self, sample_job, sample_profile, patch_dependencies
    ):
        """Review metadata should not appear when review=False."""
        response = asyncio.run(
            generate_cover_letter_for_profile(sample_job, sample_profile, review=False)
        )
        assert "review" not in response.validation.details

    def test_hard_fail_triggers_grounding_rewrite(
        self,
        sample_job,
        sample_profile,
        patch_dependencies,
        mock_writer,
        mock_validator,
    ):
        """Fabricated-tech proofread must rewrite once even when review is off."""
        writer, _, rewritten_draft = mock_writer
        failing = CoverLetterValidationResult(
            is_valid=False,
            score=40,
            issues=[CoverLetterIssue.FABRICATED_TECHNOLOGY],
            word_count=4,
            structure_score=80,
            content_score=40,
            tone_score=80,
            recommendation="reject",
            details={"fabricated_technologies": ["tensorflow"]},
        )
        passing = CoverLetterValidationResult(
            is_valid=True,
            score=85,
            issues=[],
            word_count=4,
            structure_score=80,
            content_score=90,
            tone_score=85,
            recommendation="approve",
            details={},
        )
        mock_validator.validate.side_effect = [failing, passing]

        response = asyncio.run(
            generate_cover_letter_for_profile(
                sample_job, sample_profile, deep=False, review=False
            )
        )

        writer.rewrite.assert_called_once()
        critique = writer.rewrite.call_args.args[4]
        assert "tensorflow" in critique.lower()
        assert response.cover_letter["content"] == rewritten_draft.content
        assert response.validation.details["grounding_rewrite"]["applied"] is True

    def test_analogical_hard_fail_triggers_grounding_rewrite(
        self,
        sample_job,
        sample_profile,
        patch_dependencies,
        mock_writer,
        mock_validator,
    ):
        """Analogical-claim proofread must rewrite once even when review is off."""
        writer, _, rewritten_draft = mock_writer
        failing = CoverLetterValidationResult(
            is_valid=False,
            score=40,
            issues=[CoverLetterIssue.ANALOGICAL_CLAIM],
            word_count=4,
            structure_score=80,
            content_score=40,
            tone_score=80,
            recommendation="reject",
            details={
                "analogical_claims": [
                    {
                        "sentence": "Pipelines are similar to work orders",
                        "flags": ["Analogical claim: work orders"],
                    }
                ]
            },
        )
        passing = CoverLetterValidationResult(
            is_valid=True,
            score=85,
            issues=[],
            word_count=4,
            structure_score=80,
            content_score=90,
            tone_score=85,
            recommendation="approve",
            details={},
        )
        mock_validator.validate.side_effect = [failing, passing]

        response = asyncio.run(
            generate_cover_letter_for_profile(
                sample_job, sample_profile, deep=False, review=False
            )
        )

        writer.rewrite.assert_called_once()
        critique = writer.rewrite.call_args.args[4]
        assert "analogize" in critique.lower() or "work orders" in critique.lower()
        assert response.cover_letter["content"] == rewritten_draft.content
        assert response.validation.details["grounding_rewrite"]["applied"] is True
