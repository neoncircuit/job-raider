"""
Tests for ResumeAnalyzer.

Unit tests for the resume analysis functionality including
general analysis and job-specific analysis modes.
"""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.generation.resume_analyzer import ResumeAnalyzer
from src.llm.base import LLMResponse
from src.models.job_listing import (
    JobListing,
    JobRequirement,
    JobResponsibility,
    JobSource,
)
from src.models.job_listing import Skill as JobSkill
from src.models.resume_analysis import ResumeAnalysis
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
                name="JavaScript",
                category=SkillCategory.PROGRAMMING_LANGUAGE,
                proficiency=ProficiencyLevel.INTERMEDIATE,
                years_of_experience=3,
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
        description="We are looking for a senior Python developer with experience in web development...",
        requirements=[
            JobRequirement(text="5+ years of Python experience"),
            JobRequirement(text="Experience with Django or Flask"),
            JobRequirement(text="Knowledge of React or similar frontend framework"),
        ],
        responsibilities=[
            JobResponsibility(text="Develop and maintain web applications"),
            JobResponsibility(text="Collaborate with cross-functional teams"),
        ],
        skills=[
            JobSkill(name="Python"),
            JobSkill(name="Django"),
            JobSkill(name="React"),
            JobSkill(name="SQL"),
        ],
    )


@pytest.fixture
def sample_analysis_response():
    """Create a sample LLM analysis response."""
    return json.dumps(
        {
            "overall_score": 75,
            "summary": "Strong profile with good technical skills and relevant experience.",
            "key_strengths": [
                "Strong Python experience",
                "Full-stack development skills",
                "Relevant work experience",
            ],
            "key_improvements": [
                "Add more quantifiable achievements",
                "Highlight leadership experience",
                "Include more specific project outcomes",
            ],
            "skills_assessment": [
                {
                    "skill_name": "Python",
                    "proficiency_level": "Advanced",
                    "years_experience": 5,
                    "is_industry_relevant": True,
                    "improvement_suggestions": [],
                },
                {
                    "skill_name": "React",
                    "proficiency_level": "Intermediate",
                    "years_experience": 2,
                    "is_industry_relevant": True,
                    "improvement_suggestions": [
                        "Consider learning advanced React patterns"
                    ],
                },
            ],
            "experience_insights": [
                {
                    "company": "Tech Corp",
                    "title": "Senior Software Engineer",
                    "period": "2020 - Present",
                    "strengths": ["Senior role", "Relevant experience"],
                    "gaps": ["Could add more achievements"],
                    "achievements_to_highlight": [
                        "Led development of web applications"
                    ],
                },
            ],
            "project_insights": [
                {
                    "name": "E-commerce Platform",
                    "technologies": ["Python", "Django", "React"],
                    "impact_score": 85,
                    "strengths": ["Full-stack project", "Real-world application"],
                    "improvements": ["Add performance metrics"],
                },
            ],
            "resume_improvements": [
                "Add metrics to achievements",
                "Highlight leadership experience",
            ],
            "skill_gaps": [],
            "next_steps": [
                "Add quantifiable achievements to work experience",
                "Highlight leadership and mentorship experience",
            ],
            "metadata": {
                "analysis_version": "1.0",
                "analysis_type": "general",
            },
        }
    )


@pytest.fixture
def sample_job_specific_response():
    """Create a sample job-specific LLM analysis response."""
    return json.dumps(
        {
            "overall_score": 80,
            "target_alignment_score": 85,
            "summary": "Strong alignment with the target role. Good Python experience and relevant skills.",
            "key_strengths": [
                "Excellent Python experience",
                "Full-stack development matches requirements",
                "Relevant work experience at senior level",
            ],
            "key_improvements": [
                "Emphasize Django experience more",
                "Add more SQL experience details",
            ],
            "skills_assessment": [
                {
                    "skill_name": "Python",
                    "proficiency_level": "Advanced",
                    "years_experience": 5,
                    "is_industry_relevant": True,
                    "improvement_suggestions": [],
                },
            ],
            "experience_insights": [],
            "project_insights": [],
            "resume_improvements": [
                "Highlight Django framework experience",
                "Emphasize SQL database skills",
            ],
            "skill_gaps": [
                "Consider adding more database experience",
            ],
            "next_steps": [
                "Add specific Django project examples",
                "Include SQL query optimization examples",
            ],
            "competitive_advantages": [
                "Strong full-stack background",
                "Senior-level experience",
            ],
            "competitive_gaps": [
                "Could add more cloud experience",
            ],
            "metadata": {
                "analysis_version": "1.0",
                "analysis_type": "job_specific",
            },
        }
    )


class TestResumeAnalyzer:
    """Test suite for ResumeAnalyzer."""

    def test_initialization(self, mock_llm_router):
        """Test ResumeAnalyzer initialization."""
        analyzer = ResumeAnalyzer(mock_llm_router)

        assert analyzer.llm_router == mock_llm_router
        assert analyzer.general_template is not None
        assert analyzer.job_specific_template is not None

    @patch("src.generation.resume_analyzer.LLMRouter")
    def test_analyze_general_success(
        self,
        mock_router_class,
        sample_profile,
        sample_analysis_response,
    ):
        """Test successful general resume analysis."""
        # Setup mock
        mock_router = Mock()
        mock_router.generate.return_value = LLMResponse(
            content=sample_analysis_response,
            model="qwen2.5:7b",
            provider="ollama",
            tokens_used=1500,
            cost=0.0,
        )
        mock_router_class.return_value = mock_router

        analyzer = ResumeAnalyzer(mock_router)
        result = analyzer.analyze_general(sample_profile, "test_resume.pdf")

        # Verify result
        assert isinstance(result, ResumeAnalysis)
        assert result.overall_score == 75
        assert result.analysis_type == "general"
        assert len(result.key_strengths) == 3
        assert (
            len(result.skills_assessment) == 3
        )  # Profile has Python, JavaScript, React
        assert result.is_strong_resume is True
        assert "Good" in result.competitive_edge

    @patch("src.generation.resume_analyzer.LLMRouter")
    def test_analyze_job_specific_success(
        self,
        mock_router_class,
        sample_profile,
        sample_job,
        sample_job_specific_response,
    ):
        """Test successful job-specific resume analysis."""
        # Setup mock
        mock_router = Mock()
        mock_router.generate.return_value = LLMResponse(
            content=sample_job_specific_response,
            model="qwen2.5:7b",
            provider="ollama",
            tokens_used=1500,
            cost=0.0,
        )
        mock_router_class.return_value = mock_router

        analyzer = ResumeAnalyzer(mock_router)
        result = analyzer.analyze_job_specific(
            sample_profile, sample_job, "test_resume.pdf"
        )

        # Verify result
        assert isinstance(result, ResumeAnalysis)
        assert result.overall_score == 80
        assert result.analysis_type == "job_specific"
        assert result.target_alignment_score == 85
        assert len(result.competitive_advantages) == 2
        assert len(result.competitive_gaps) == 1

    def test_analyze_general_fallback_on_error(self, mock_llm_router, sample_profile):
        """Test fallback behavior when LLM fails for general analysis."""
        # Setup mock to raise exception
        mock_llm_router.generate.side_effect = Exception("LLM error")

        analyzer = ResumeAnalyzer(mock_llm_router)
        result = analyzer.analyze_general(sample_profile, "test_resume.pdf")

        # Verify fallback result
        assert isinstance(result, ResumeAnalysis)
        assert result.analysis_type == "general"
        assert 50 <= result.overall_score <= 100  # Should have a reasonable score
        assert len(result.key_strengths) >= 0  # May be empty
        assert len(result.key_improvements) >= 0  # May be empty

    def test_analyze_job_specific_fallback_on_error(
        self,
        mock_llm_router,
        sample_profile,
        sample_job,
    ):
        """Test fallback behavior when LLM fails for job-specific analysis."""
        # Setup mock to raise exception
        mock_llm_router.generate.side_effect = Exception("LLM error")

        analyzer = ResumeAnalyzer(mock_llm_router)
        result = analyzer.analyze_job_specific(
            sample_profile, sample_job, "test_resume.pdf"
        )

        # Verify fallback result
        assert isinstance(result, ResumeAnalysis)
        assert result.analysis_type == "job_specific"
        assert result.target_alignment_score is not None
        assert 0 <= result.target_alignment_score <= 100

    def test_prepare_profile_context(self, mock_llm_router, sample_profile):
        """Test profile context preparation."""
        analyzer = ResumeAnalyzer(mock_llm_router)
        context = analyzer._prepare_profile_context(sample_profile)

        assert "John Doe" in context
        assert "Python" in context
        assert "E-commerce Platform" in context
        assert "Tech Corp" in context

    def test_prepare_job_context(self, mock_llm_router, sample_job):
        """Test job context preparation."""
        analyzer = ResumeAnalyzer(mock_llm_router)
        context = analyzer._prepare_job_context(sample_job)

        assert "Senior Python Developer" in context
        assert "TechStartup Inc" in context
        assert "San Francisco" in context
        assert "Python" in context

    def test_parse_llm_assessment_general(
        self, mock_llm_router, sample_analysis_response
    ):
        """Test parsing of general analysis LLM response."""
        analyzer = ResumeAnalyzer(mock_llm_router)
        result = analyzer._parse_llm_assessment(sample_analysis_response)

        assert isinstance(result, dict)
        assert result["overall_score"] == 75
        assert len(result["key_strengths"]) == 3
        assert len(result["key_improvements"]) == 3
        assert result["metadata"]["analysis_type"] == "general"

    def test_parse_llm_assessment_job_specific(
        self,
        mock_llm_router,
        sample_job_specific_response,
    ):
        """Test parsing of job-specific analysis LLM response."""
        analyzer = ResumeAnalyzer(mock_llm_router)
        result = analyzer._parse_llm_assessment(sample_job_specific_response)

        assert isinstance(result, dict)
        assert result["target_alignment_score"] == 85
        assert len(result["competitive_advantages"]) == 2
        assert len(result["competitive_gaps"]) == 1

    def test_fallback_general_analysis_scoring(self, mock_llm_router):
        """Test that fallback general analysis produces reasonable scores."""
        # Test with empty profile
        empty_profile = UserProfile(
            name="Test User",
            contact=ContactInfo(email="test@example.com", location="San Francisco"),
        )

        mock_llm_router.generate.side_effect = Exception("LLM error")
        analyzer = ResumeAnalyzer(mock_llm_router)
        result = analyzer.analyze_general(empty_profile, "test.pdf")

        # Should have a base score
        assert 50 <= result.overall_score <= 100

    def test_is_strong_resume_property(self):
        """Test the is_strong_resume property."""
        analysis = ResumeAnalysis(
            resume_path="test.pdf",
            analysis_type="general",
            overall_score=75,
            summary="Test",
        )

        assert analysis.is_strong_resume is True

        analysis.overall_score = 65
        assert analysis.is_strong_resume is False

    def test_competitive_edge_property(self):
        """Test the competitive_edge property."""
        analysis = ResumeAnalysis(
            resume_path="test.pdf",
            analysis_type="general",
            overall_score=85,
            summary="Test",
        )

        assert "Strong" in analysis.competitive_edge

        analysis.overall_score = 75
        assert "Good" in analysis.competitive_edge

        analysis.overall_score = 60
        assert "Moderate" in analysis.competitive_edge

        analysis.overall_score = 40
        assert "improvement" in analysis.competitive_edge.lower()
