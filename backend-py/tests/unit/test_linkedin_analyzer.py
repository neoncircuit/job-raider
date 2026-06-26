"""
Unit tests for the LinkedIn profile analyzer.

Tests cover:
- Rule-based fallback scoring
- JSON parsing from LLM responses
- Invalid LLM output handling
- Model validation (input must have at least one field)
- Full analysis flow with mocked LLM router

Author: Job Raider
Date: 2026-06-25
"""

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.generation.linkedin_analyzer import LinkedInAnalyzer
from src.llm.base import LLMResponse, MessageType
from src.llm.router import LLMRouter, TaskType
from src.models.linkedin_analysis import (
    InboundAttractionInsight,
    LinkedInProfileAnalysis,
    LinkedInProfileInput,
    ProfileSectionScore,
)


class TestLinkedInProfileInput:
    """Tests for LinkedInProfileInput model validation."""

    def test_valid_with_raw_text(self) -> None:
        """Should accept input with only raw_text."""
        input_data = LinkedInProfileInput(raw_text="Some profile text")
        assert input_data.raw_text == "Some profile text"

    def test_valid_with_structured_fields(self) -> None:
        """Should accept input with structured fields."""
        input_data = LinkedInProfileInput(
            headline="Software Engineer",
            summary="Experienced developer",
            skills=["Python", "JavaScript"],
        )
        assert input_data.headline == "Software Engineer"

    def test_valid_with_both(self) -> None:
        """Should accept input with both raw_text and structured fields."""
        input_data = LinkedInProfileInput(
            raw_text="Full profile text",
            headline="Software Engineer",
        )
        assert input_data.raw_text == "Full profile text"
        assert input_data.headline == "Software Engineer"

    def test_invalid_empty_input(self) -> None:
        """Should reject empty input with no fields."""
        with pytest.raises(ValueError, match="At least one of raw_text"):
            LinkedInProfileInput()

    def test_invalid_whitespace_only_raw_text(self) -> None:
        """Should reject whitespace-only raw_text."""
        with pytest.raises(ValueError, match="At least one of raw_text"):
            LinkedInProfileInput(raw_text="   ")


class TestLinkedInAnalyzerRuleBased:
    """Tests for the rule-based fallback analysis."""

    def test_rule_based_with_complete_profile(self) -> None:
        """Should return high scores for a complete profile."""
        llm_router = MagicMock(spec=LLMRouter)
        analyzer = LinkedInAnalyzer(llm_router)

        input_data = LinkedInProfileInput(
            headline="Senior Software Engineer | Python | Cloud",
            summary="Experienced software engineer with 10 years of experience...",
            experience_entries=[
                {
                    "title": "Senior Engineer",
                    "company": "Tech Corp",
                    "dates": "2020-present",
                    "description": "Led team of 5 engineers",
                },
                {
                    "title": "Engineer",
                    "company": "Startup Inc",
                    "dates": "2018-2020",
                    "description": "Built core platform",
                },
            ],
            education_entries=[
                {"school": "MIT", "degree": "BS Computer Science"}
            ],
            skills=["Python", "JavaScript", "AWS", "Docker", "Kubernetes"],
            industry="Technology",
            target_roles=["Staff Engineer", "Principal Engineer"],
        )

        result = analyzer._rule_based_analysis(input_data)

        assert result["overall_score"] >= 50
        assert len(result["section_scores"]) == 5
        assert result["section_scores"][0]["section_name"] == "Headline"
        assert result["competitive_edge"] != ""

    def test_rule_based_with_minimal_profile(self) -> None:
        """Should return lower scores and actionable insights for minimal profile."""
        llm_router = MagicMock(spec=LLMRouter)
        analyzer = LinkedInAnalyzer(llm_router)

        input_data = LinkedInProfileInput(raw_text="Minimal profile")

        result = analyzer._rule_based_analysis(input_data)

        assert result["overall_score"] < 60
        assert len(result["insights"]) > 0
        assert any(i["priority"] == "high" for i in result["insights"])

    def test_rule_based_generates_headline_options(self) -> None:
        """Should generate headline options when headline is missing and target_roles exist."""
        llm_router = MagicMock(spec=LLMRouter)
        analyzer = LinkedInAnalyzer(llm_router)

        input_data = LinkedInProfileInput(
            raw_text="Some text",
            target_roles=["Data Scientist"],
            industry="AI",
        )

        result = analyzer._rule_based_analysis(input_data)

        assert len(result["generated_headline_options"]) > 0
        assert any("Data Scientist" in h for h in result["generated_headline_options"])

    def test_rule_based_generates_summary_suggestions(self) -> None:
        """Should generate summary rewrite suggestions when summary is short."""
        llm_router = MagicMock(spec=LLMRouter)
        analyzer = LinkedInAnalyzer(llm_router)

        input_data = LinkedInProfileInput(
            raw_text="Some text",
            summary="Short summary.",
        )

        result = analyzer._rule_based_analysis(input_data)

        assert len(result["summary_rewrite_suggestions"]) > 0


class TestLinkedInAnalyzerParseLLM:
    """Tests for parsing LLM responses."""

    def test_parse_valid_json(self) -> None:
        """Should extract and parse valid JSON from LLM response."""
        llm_router = MagicMock(spec=LLMRouter)
        analyzer = LinkedInAnalyzer(llm_router)

        response_data = {
            "overall_score": 85,
            "summary": "Strong profile with good keywords.",
            "section_scores": [
                {
                    "section_name": "Headline",
                    "score": 90,
                    "weight": 0.25,
                    "feedback": "Great headline with keywords.",
                }
            ],
            "insights": [
                {
                    "category": "headline",
                    "observation": "Headline is strong.",
                    "recommendation": "Keep it up.",
                    "priority": "low",
                }
            ],
            "keyword_recommendations": ["Python", "AWS"],
            "action_plan": ["Step 1"],
            "generated_headline_options": ["Option 1"],
            "summary_rewrite_suggestions": ["Suggestion 1"],
            "competitive_edge": "Strong",
            "metadata": {"version": "1.0"},
        }

        response_text = json.dumps(response_data)
        result = analyzer._parse_llm_analysis(response_text)

        assert result["overall_score"] == 85
        assert result["summary"] == "Strong profile with good keywords."
        assert len(result["section_scores"]) == 1
        assert result["section_scores"][0]["section_name"] == "Headline"

    def test_parse_json_with_markdown(self) -> None:
        """Should extract JSON from markdown code blocks."""
        llm_router = MagicMock(spec=LLMRouter)
        analyzer = LinkedInAnalyzer(llm_router)

        response_data = {"overall_score": 75, "summary": "Good profile."}
        markdown_text = f"```json\n{json.dumps(response_data)}\n```"

        result = analyzer._parse_llm_analysis(markdown_text)

        assert result["overall_score"] == 75

    def test_parse_invalid_json_raises(self) -> None:
        """Should raise ValueError when JSON cannot be extracted."""
        llm_router = MagicMock(spec=LLMRouter)
        analyzer = LinkedInAnalyzer(llm_router)

        with pytest.raises(ValueError, match="Failed to extract JSON"):
            analyzer._parse_llm_analysis("This is not JSON at all")

    def test_parse_malformed_json_raises(self) -> None:
        """Should raise ValueError when JSON is malformed."""
        llm_router = MagicMock(spec=LLMRouter)
        analyzer = LinkedInAnalyzer(llm_router)

        with pytest.raises(ValueError, match="Failed to extract JSON"):
            analyzer._parse_llm_analysis("{invalid json")


class TestLinkedInAnalyzerBuildAnalysis:
    """Tests for building analysis from dictionary."""

    def test_build_analysis_complete(self) -> None:
        """Should build complete LinkedInProfileAnalysis from dict."""
        llm_router = MagicMock(spec=LLMRouter)
        analyzer = LinkedInAnalyzer(llm_router)

        llm_result = {
            "overall_score": 80,
            "summary": "Good profile",
            "section_scores": [
                {
                    "section_name": "Headline",
                    "score": 85,
                    "weight": 0.25,
                    "feedback": "Good",
                }
            ],
            "insights": [
                {
                    "category": "headline",
                    "observation": "Observed",
                    "recommendation": "Recommend",
                    "priority": "medium",
                }
            ],
            "keyword_recommendations": ["Python"],
            "action_plan": ["Step 1"],
            "generated_headline_options": ["Option 1"],
            "summary_rewrite_suggestions": ["Suggestion 1"],
            "competitive_edge": "Strong",
            "metadata": {"version": "1.0"},
        }

        analysis = analyzer._build_analysis(llm_result)

        assert isinstance(analysis, LinkedInProfileAnalysis)
        assert analysis.overall_score == 80
        assert len(analysis.section_scores) == 1
        assert isinstance(analysis.section_scores[0], ProfileSectionScore)
        assert len(analysis.insights) == 1
        assert isinstance(analysis.insights[0], InboundAttractionInsight)
        assert analysis.is_strong_profile is True
        assert len(analysis.high_priority_insights) == 0
        assert analysis.weighted_overall_score == 85.0

    def test_build_analysis_empty(self) -> None:
        """Should build analysis with defaults from empty dict."""
        llm_router = MagicMock(spec=LLMRouter)
        analyzer = LinkedInAnalyzer(llm_router)

        analysis = analyzer._build_analysis({})

        assert isinstance(analysis, LinkedInProfileAnalysis)
        assert analysis.overall_score == 50
        assert analysis.section_scores == []
        assert analysis.insights == []


class TestLinkedInAnalyzerFullFlow:
    """Tests for the full analysis flow with mocked LLM."""

    def test_analyze_with_llm_success(self) -> None:
        """Should return analysis when LLM succeeds."""
        llm_router = MagicMock(spec=LLMRouter)
        response_data = {
            "overall_score": 88,
            "summary": "Excellent profile",
            "section_scores": [
                {
                    "section_name": "Headline",
                    "score": 90,
                    "weight": 0.25,
                    "feedback": "Great",
                }
            ],
            "insights": [],
            "keyword_recommendations": [],
            "action_plan": [],
            "generated_headline_options": [],
            "summary_rewrite_suggestions": [],
            "competitive_edge": "Strong",
            "metadata": {},
        }
        llm_response = LLMResponse(
            content=json.dumps(response_data),
            model="test-model",
            provider="test",
        )
        llm_router.generate.return_value = llm_response

        analyzer = LinkedInAnalyzer(llm_router)
        input_data = LinkedInProfileInput(raw_text="Test profile")

        result = analyzer.analyze(input_data)

        assert isinstance(result, LinkedInProfileAnalysis)
        assert result.overall_score == 88
        llm_router.generate.assert_called_once()
        call_args = llm_router.generate.call_args
        assert call_args.kwargs["task_type"] == TaskType.LINKEDIN_ANALYSIS
        assert call_args.kwargs["temperature"] == 0.3

    def test_analyze_with_llm_failure_fallback(self) -> None:
        """Should fall back to rule-based analysis when LLM fails."""
        llm_router = MagicMock(spec=LLMRouter)
        llm_router.generate.side_effect = Exception("LLM unavailable")

        analyzer = LinkedInAnalyzer(llm_router)
        input_data = LinkedInProfileInput(
            raw_text="Test profile",
            headline="Engineer",
        )

        result = analyzer.analyze(input_data)

        assert isinstance(result, LinkedInProfileAnalysis)
        assert result.overall_score > 0
        llm_router.generate.assert_called_once()

    def test_analyze_with_llm_invalid_json_fallback(self) -> None:
        """Should fall back to rule-based when LLM returns invalid JSON."""
        llm_router = MagicMock(spec=LLMRouter)
        llm_response = LLMResponse(
            content="Not valid JSON",
            model="test-model",
            provider="test",
        )
        llm_router.generate.return_value = llm_response

        analyzer = LinkedInAnalyzer(llm_router)
        input_data = LinkedInProfileInput(
            raw_text="Test profile",
            headline="Software Engineer",
        )

        result = analyzer.analyze(input_data)

        assert isinstance(result, LinkedInProfileAnalysis)
        assert result.overall_score >= 0


class TestLinkedInAnalyzerAsync:
    """Tests for the async analysis flow with mocked LLM."""

    @pytest.mark.asyncio
    async def test_analyze_async_with_llm_success(self) -> None:
        """Should return analysis when async LLM succeeds."""
        llm_router = MagicMock(spec=LLMRouter)
        response_data = {
            "overall_score": 88,
            "summary": "Excellent profile",
            "section_scores": [
                {
                    "section_name": "Headline",
                    "score": 90,
                    "weight": 0.25,
                    "feedback": "Great",
                }
            ],
            "insights": [],
            "keyword_recommendations": [],
            "action_plan": [],
            "generated_headline_options": [],
            "summary_rewrite_suggestions": [],
            "competitive_edge": "Strong",
            "metadata": {},
        }
        llm_response = LLMResponse(
            content=json.dumps(response_data),
            model="test-model",
            provider="test",
        )
        llm_router.generate_async = AsyncMock(return_value=llm_response)

        analyzer = LinkedInAnalyzer(llm_router)
        input_data = LinkedInProfileInput(raw_text="Test profile")

        result = await analyzer.analyze_async(input_data)

        assert isinstance(result, LinkedInProfileAnalysis)
        assert result.overall_score == 88
        llm_router.generate_async.assert_called_once()
        call_args = llm_router.generate_async.call_args
        assert call_args.kwargs["task_type"] == TaskType.LINKEDIN_ANALYSIS
        assert call_args.kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_analyze_async_fallback_on_failure(self) -> None:
        """Should fall back to rule-based analysis when async LLM fails."""
        llm_router = MagicMock(spec=LLMRouter)
        llm_router.generate_async = AsyncMock(side_effect=Exception("LLM unavailable"))

        analyzer = LinkedInAnalyzer(llm_router)
        input_data = LinkedInProfileInput(
            raw_text="Test profile",
            headline="Engineer",
        )

        result = await analyzer.analyze_async(input_data)

        assert isinstance(result, LinkedInProfileAnalysis)
        assert result.overall_score > 0
        llm_router.generate_async.assert_called_once()


class TestLinkedInProfileAnalysisProperties:
    """Tests for LinkedInProfileAnalysis computed properties."""

    def test_is_strong_profile(self) -> None:
        """Should identify strong profiles correctly."""
        strong = LinkedInProfileAnalysis(overall_score=75, summary="Good")
        weak = LinkedInProfileAnalysis(overall_score=65, summary="Okay")

        assert strong.is_strong_profile is True
        assert weak.is_strong_profile is False

    def test_high_priority_insights(self) -> None:
        """Should filter high priority insights."""
        analysis = LinkedInProfileAnalysis(
            overall_score=70,
            summary="Test",
            insights=[
                InboundAttractionInsight(
                    category="headline",
                    observation="Short",
                    recommendation="Expand",
                    priority="high",
                ),
                InboundAttractionInsight(
                    category="summary",
                    observation="Good",
                    recommendation="Keep",
                    priority="low",
                ),
            ],
        )

        high_priority = analysis.high_priority_insights
        assert len(high_priority) == 1
        assert high_priority[0].category == "headline"

    def test_weighted_overall_score(self) -> None:
        """Should compute weighted score from section scores."""
        analysis = LinkedInProfileAnalysis(
            overall_score=50,
            summary="Test",
            section_scores=[
                ProfileSectionScore(
                    section_name="A", score=80, weight=0.5, feedback="Good"
                ),
                ProfileSectionScore(
                    section_name="B", score=60, weight=0.5, feedback="Okay"
                ),
            ],
        )

        assert analysis.weighted_overall_score == 70.0

    def test_weighted_overall_score_empty(self) -> None:
        """Should return overall_score when no section scores."""
        analysis = LinkedInProfileAnalysis(overall_score=65, summary="Test")

        assert analysis.weighted_overall_score == 65
