"""
Tests for CoverLetterWriter.

Unit tests for the cover letter generation functionality including
LLM-based generation, fallback behavior, and content quality checks.
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.generation.cover_letter_writer import (
    _COVER_LETTER_SYSTEM,
    CoverLetterWriter,
    GeneratedCoverLetter,
)
from src.generation.selector import SelectionOutput
from src.llm.base import LLMResponse
from src.llm.router import TaskType
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
def mock_llm_router():
    """Create a mock LLM router."""
    router = Mock()
    router.routes = {
        TaskType.COVER_LETTER_WRITING: Mock(primary_model="qwen2.5:7b"),
    }
    return router


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
                highlights=[
                    "Reduced API latency by 40%",
                    "Mentored 3 junior developers",
                ],
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
            JobRequirement(text="Experience with Django or Flask"),
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
        key_achievements=[
            "Reduced API latency by 40%",
            "Mentored junior developers",
        ],
        summary_suggestion="Experienced Python developer with full-stack expertise",
        raw_response="",
    )


SAMPLE_COVER_LETTER = (
    "I am excited to apply for the Senior Python Developer position at "
    "TechStartup Inc. With five years of experience building scalable web "
    "applications, I am confident in my ability to contribute meaningfully "
    "to your engineering team.\n\n"
    "My work on the E-commerce Platform, a full-stack application built with "
    "Python, Django, and React, directly aligns with your requirements. I "
    "reduced API latency by 40% through strategic optimization, demonstrating "
    "both technical depth and a results-driven approach. Additionally, my "
    "experience on the Task Management App further solidified my full-stack "
    "capabilities.\n\n"
    "I would welcome the opportunity to discuss how my background in Python "
    "development and full-stack engineering can benefit TechStartup Inc. "
    "Thank you for considering my application."
)


class TestCoverLetterWriter:
    """Test suite for CoverLetterWriter."""

    def test_initialization(self, mock_llm_router):
        """Test CoverLetterWriter initialization."""
        writer = CoverLetterWriter(mock_llm_router)
        assert writer.llm_router == mock_llm_router

    def test_successful_generation(
        self, mock_llm_router, sample_job, sample_profile, sample_selection
    ):
        """Test successful cover letter generation via LLM."""
        mock_llm_router.generate.return_value = LLMResponse(
            content=SAMPLE_COVER_LETTER,
            model="qwen2.5:7b",
            provider="ollama",
            tokens_used=400,
            cost=0.0,
        )

        writer = CoverLetterWriter(mock_llm_router)
        result = writer.write(sample_job, sample_profile, sample_selection)

        assert isinstance(result, GeneratedCoverLetter)
        assert result.content == SAMPLE_COVER_LETTER
        assert result.word_count > 0
        assert result.model_used == "qwen2.5:7b"
        mock_llm_router.generate.assert_called_once()

    def test_fallback_on_llm_failure(
        self, mock_llm_router, sample_job, sample_profile, sample_selection
    ):
        """Test fallback cover letter when LLM fails."""
        mock_llm_router.generate.side_effect = Exception("LLM unavailable")

        writer = CoverLetterWriter(mock_llm_router)
        result = writer.write(sample_job, sample_profile, sample_selection)

        assert isinstance(result, GeneratedCoverLetter)
        assert result.model_used == "template_fallback"
        assert result.word_count > 0
        assert sample_job.company in result.content

    def test_word_count_within_bounds(
        self, mock_llm_router, sample_job, sample_profile, sample_selection
    ):
        """Test that generated cover letter has a positive word count."""
        mock_llm_router.generate.return_value = LLMResponse(
            content=SAMPLE_COVER_LETTER,
            model="qwen2.5:7b",
            provider="ollama",
            tokens_used=400,
            cost=0.0,
        )

        writer = CoverLetterWriter(mock_llm_router)
        result = writer.write(sample_job, sample_profile, sample_selection)

        assert result.word_count >= 50
        assert result.word_count <= 500

    def test_company_name_in_content(
        self, mock_llm_router, sample_job, sample_profile, sample_selection
    ):
        """Test that the company name appears in the cover letter."""
        mock_llm_router.generate.return_value = LLMResponse(
            content=SAMPLE_COVER_LETTER,
            model="qwen2.5:7b",
            provider="ollama",
            tokens_used=400,
            cost=0.0,
        )

        writer = CoverLetterWriter(mock_llm_router)
        result = writer.write(sample_job, sample_profile, sample_selection)

        assert sample_job.company in result.content

    def test_job_title_in_content(
        self, mock_llm_router, sample_job, sample_profile, sample_selection
    ):
        """Test that the job title appears in the cover letter."""
        mock_llm_router.generate.return_value = LLMResponse(
            content=SAMPLE_COVER_LETTER,
            model="qwen2.5:7b",
            provider="ollama",
            tokens_used=400,
            cost=0.0,
        )

        writer = CoverLetterWriter(mock_llm_router)
        result = writer.write(sample_job, sample_profile, sample_selection)

        assert sample_job.title in result.content

    def test_highlighted_experiences_extraction(
        self, mock_llm_router, sample_job, sample_profile, sample_selection
    ):
        """Test that highlighted experiences are extracted from content."""
        mock_llm_router.generate.return_value = LLMResponse(
            content=SAMPLE_COVER_LETTER,
            model="qwen2.5:7b",
            provider="ollama",
            tokens_used=400,
            cost=0.0,
        )

        writer = CoverLetterWriter(mock_llm_router)
        result = writer.write(sample_job, sample_profile, sample_selection)

        assert isinstance(result.highlighted_experiences, list)
        assert len(result.highlighted_experiences) >= 1
        assert any(
            "E-commerce Platform" in exp["name"]
            for exp in result.highlighted_experiences
        )

    def test_uses_cover_letter_task_type(
        self, mock_llm_router, sample_job, sample_profile, sample_selection
    ):
        """Test that the correct TaskType is used for routing."""
        mock_llm_router.generate.return_value = LLMResponse(
            content=SAMPLE_COVER_LETTER,
            model="qwen2.5:7b",
            provider="ollama",
            tokens_used=400,
            cost=0.0,
        )

        writer = CoverLetterWriter(mock_llm_router)
        writer.write(sample_job, sample_profile, sample_selection)

        call_kwargs = mock_llm_router.generate.call_args
        assert call_kwargs.kwargs.get("task_type") == TaskType.COVER_LETTER_WRITING

    def test_prepare_job_context(self, mock_llm_router, sample_job):
        """Test job context preparation."""
        writer = CoverLetterWriter(mock_llm_router)
        context = writer._prepare_job_context(sample_job)

        assert "Senior Python Developer" in context
        assert "TechStartup Inc" in context
        assert "Python" in context

    def test_prepare_profile_context(self, mock_llm_router, sample_profile):
        """Test profile context preparation."""
        writer = CoverLetterWriter(mock_llm_router)
        context = writer._prepare_profile_context(sample_profile)

        assert "John Doe" in context
        assert "Python" in context
        assert "Tech Corp" in context

    def test_prepare_selection_context(self, mock_llm_router, sample_selection):
        """Test selection context preparation."""
        writer = CoverLetterWriter(mock_llm_router)
        context = writer._prepare_selection_context(sample_selection)

        assert "E-commerce Platform" in context
        assert "Python" in context

    def test_fallback_contains_company_and_title(
        self, mock_llm_router, sample_job, sample_profile, sample_selection
    ):
        """Test that fallback letter includes company name and job title."""
        mock_llm_router.generate.side_effect = Exception("LLM error")

        writer = CoverLetterWriter(mock_llm_router)
        result = writer.write(sample_job, sample_profile, sample_selection)

        assert sample_job.company in result.content
        assert sample_job.title in result.content

    def test_write_and_rewrite_share_system_prompt(
        self, mock_llm_router, sample_job, sample_profile, sample_selection
    ):
        """Write and rewrite use the same unified system prompt."""
        mock_llm_router.generate.return_value = LLMResponse(
            content=SAMPLE_COVER_LETTER,
            model="qwen2.5:7b",
            provider="ollama",
            tokens_used=400,
            cost=0.0,
        )

        writer = CoverLetterWriter(mock_llm_router)
        writer.write(sample_job, sample_profile, sample_selection)
        write_messages = mock_llm_router.generate.call_args.kwargs["messages"]
        write_system = write_messages[0].content

        draft = GeneratedCoverLetter(
            content="Draft letter",
            highlighted_experiences=[],
            word_count=2,
            model_used="qwen2.5:7b",
        )
        writer.rewrite(sample_job, sample_profile, sample_selection, draft, "Fix tone")
        rewrite_messages = mock_llm_router.generate.call_args.kwargs["messages"]
        rewrite_system = rewrite_messages[0].content

        assert write_system == _COVER_LETTER_SYSTEM
        assert rewrite_system == _COVER_LETTER_SYSTEM
        assert write_system == rewrite_system


class TestGeneratedCoverLetter:
    """Test suite for GeneratedCoverLetter dataclass."""

    def test_dataclass_fields(self):
        """Test GeneratedCoverLetter has required fields."""
        letter = GeneratedCoverLetter(
            content="Test content",
            highlighted_experiences=[],
            word_count=2,
            model_used="test_model",
        )

        assert letter.content == "Test content"
        assert letter.highlighted_experiences == []
        assert letter.word_count == 2
        assert letter.model_used == "test_model"
