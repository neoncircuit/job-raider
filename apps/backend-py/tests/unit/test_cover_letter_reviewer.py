"""
Unit tests for the cover-letter reviewer.

Tests cover:
- Successful review requesting a rewrite
- Successful review that needs no rewrite
- Missing JSON fallback
- LLM failure graceful fallback
- Correct TaskType and generation parameters

Author: Job Raider
Date: 2026-07-08
"""

from unittest.mock import Mock

import pytest

from src.generation.cover_letter_reviewer import CoverLetterReviewer
from src.generation.cover_letter_writer import GeneratedCoverLetter
from src.generation.selector import SelectionOutput
from src.llm.base import LLMResponse
from src.llm.router import LLMRouter, RouteConfig, TaskType
from src.models.job_listing import JobListing, JobSource
from src.models.user_profile import ContactInfo, UserProfile


@pytest.fixture
def mock_llm_router():
    """Create a mock LLM router with a COVER_LETTER_REVIEW route."""
    router = Mock(spec=LLMRouter)
    router.routes = {
        TaskType.COVER_LETTER_REVIEW: RouteConfig(
            task_type=TaskType.COVER_LETTER_REVIEW,
            primary_provider="ollama",
            primary_model="qwen2.5:3b",
            fallback_provider="ollama",
            fallback_model="gemma3:4b",
        ),
    }
    return router


@pytest.fixture
def sample_draft():
    """Create a sample generated cover letter."""
    return GeneratedCoverLetter(
        content="Dear Hiring Manager, I am excited about this role.",
        highlighted_experiences=[],
        word_count=10,
        model_used="qwen2.5:7b",
    )


@pytest.fixture
def sample_job():
    """Create a minimal job listing."""
    return JobListing(
        title="Senior Engineer",
        company="TechCorp",
        job_id="job-123",
        source=JobSource.MANUAL,
        location="Remote",
        description="Build scalable systems.",
    )


@pytest.fixture
def sample_profile():
    """Create a minimal user profile."""
    return UserProfile(
        name="Alex Chen",
        contact=ContactInfo(email="alex@example.com", location="Remote"),
    )


@pytest.fixture
def sample_selection():
    """Create a minimal selection output."""
    return SelectionOutput(
        selected_projects=[{"name": "Job Raider", "reason": "Relevant project"}],
        keywords_to_emphasize=["Python", "FastAPI"],
        key_achievements=["Built scalable system"],
        summary_suggestion="",
        raw_response="",
    )


class TestCoverLetterReviewer:
    """Test suite for CoverLetterReviewer."""

    def test_review_requests_rewrite(
        self,
        mock_llm_router,
        sample_draft,
        sample_job,
        sample_profile,
        sample_selection,
    ):
        """Should parse critique and set rewrite_needed=True."""
        mock_llm_router.generate.return_value = LLMResponse(
            content='{"critique": "Add a stronger call to action.", "rewrite_needed": true}',
            model="qwen2.5:3b",
            provider="ollama",
            tokens_used=120,
            cost=0.0,
        )

        reviewer = CoverLetterReviewer(mock_llm_router)
        result = reviewer.review(
            sample_draft, sample_job, sample_profile, sample_selection
        )

        assert result.critique == "Add a stronger call to action."
        assert result.rewrite_needed is True
        assert result.model_used == "qwen2.5:3b"
        assert result.error is None

    def test_review_no_rewrite_needed(
        self,
        mock_llm_router,
        sample_draft,
        sample_job,
        sample_profile,
        sample_selection,
    ):
        """Should parse critique and set rewrite_needed=False."""
        mock_llm_router.generate.return_value = LLMResponse(
            content='{"critique": "Well tailored and concise.", "rewrite_needed": false}',
            model="qwen2.5:3b",
            provider="ollama",
            tokens_used=120,
            cost=0.0,
        )

        reviewer = CoverLetterReviewer(mock_llm_router)
        result = reviewer.review(
            sample_draft, sample_job, sample_profile, sample_selection
        )

        assert result.critique == "Well tailored and concise."
        assert result.rewrite_needed is False
        assert result.model_used == "qwen2.5:3b"
        assert result.error is None

    def test_review_uses_correct_task_type_and_params(
        self,
        mock_llm_router,
        sample_draft,
        sample_job,
        sample_profile,
        sample_selection,
    ):
        """Should call the review route with low temperature and short max_tokens."""
        mock_llm_router.generate.return_value = LLMResponse(
            content='{"critique": "OK.", "rewrite_needed": false}',
            model="qwen2.5:3b",
            provider="ollama",
            tokens_used=80,
            cost=0.0,
        )

        reviewer = CoverLetterReviewer(mock_llm_router)
        reviewer.review(sample_draft, sample_job, sample_profile, sample_selection)

        mock_llm_router.generate.assert_called_once()
        call_kwargs = mock_llm_router.generate.call_args.kwargs
        assert call_kwargs.get("task_type") == TaskType.COVER_LETTER_REVIEW
        assert call_kwargs.get("temperature") == 0.3
        assert call_kwargs.get("max_tokens") == 400

    def test_review_extracts_json_from_extra_text(
        self,
        mock_llm_router,
        sample_draft,
        sample_job,
        sample_profile,
        sample_selection,
    ):
        """Should find and parse JSON even when wrapped in explanatory text."""
        mock_llm_router.generate.return_value = LLMResponse(
            content='Here is my review:\n{"critique": "Too generic.", "rewrite_needed": true}\nHope this helps.',
            model="qwen2.5:3b",
            provider="ollama",
            tokens_used=150,
            cost=0.0,
        )

        reviewer = CoverLetterReviewer(mock_llm_router)
        result = reviewer.review(
            sample_draft, sample_job, sample_profile, sample_selection
        )

        assert result.critique == "Too generic."
        assert result.rewrite_needed is True

    def test_review_graceful_on_missing_json(
        self,
        mock_llm_router,
        sample_draft,
        sample_job,
        sample_profile,
        sample_selection,
    ):
        """Should return a graceful fallback when no JSON is found."""
        mock_llm_router.generate.return_value = LLMResponse(
            content="This cover letter looks fine.",
            model="qwen2.5:3b",
            provider="ollama",
            tokens_used=50,
            cost=0.0,
        )

        reviewer = CoverLetterReviewer(mock_llm_router)
        result = reviewer.review(
            sample_draft, sample_job, sample_profile, sample_selection
        )

        assert result.critique == "Review unavailable."
        assert result.rewrite_needed is False
        assert result.model_used == "error"
        assert result.error == "Review unavailable"

    def test_review_graceful_on_llm_error(
        self,
        mock_llm_router,
        sample_draft,
        sample_job,
        sample_profile,
        sample_selection,
    ):
        """Should return a graceful fallback when the LLM raises an exception."""
        mock_llm_router.generate.side_effect = RuntimeError("ollama unreachable")

        reviewer = CoverLetterReviewer(mock_llm_router)
        result = reviewer.review(
            sample_draft, sample_job, sample_profile, sample_selection
        )

        assert result.critique == "Review unavailable."
        assert result.rewrite_needed is False
        assert result.model_used == "error"
        assert result.error == "Review unavailable"

    def test_review_includes_job_and_draft_in_prompt(
        self,
        mock_llm_router,
        sample_draft,
        sample_job,
        sample_profile,
        sample_selection,
    ):
        """Should pass job title, company, selection, and draft content to the LLM."""
        mock_llm_router.generate.return_value = LLMResponse(
            content='{"critique": "OK.", "rewrite_needed": false}',
            model="qwen2.5:3b",
            provider="ollama",
            tokens_used=80,
            cost=0.0,
        )

        reviewer = CoverLetterReviewer(mock_llm_router)
        reviewer.review(sample_draft, sample_job, sample_profile, sample_selection)

        messages = mock_llm_router.generate.call_args.kwargs.get("messages", [])
        assert len(messages) == 2
        user_content = messages[1].content
        assert sample_job.title in user_content
        assert sample_job.company in user_content
        assert "Python" in user_content
        assert "Job Raider" in user_content
        assert sample_draft.content in user_content
