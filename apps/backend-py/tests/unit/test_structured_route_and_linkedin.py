"""Tests for the schema and the strict parsing of the route helpers and LinkedIn analysis (Step 3.7, MH-9)."""

import asyncio
import copy
import json
from typing import Any, Dict, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest

import src.api.routes.cover_letter as route
from src.generation.linkedin_analyzer import LinkedInAnalyzer
from src.llm.base import LLMResponse
from src.llm.router import LLMRouter
from src.llm.structured import LinkedInAnalysisAnswer, ScoreExplanationAnswer
from src.models.linkedin_analysis import LinkedInProfileInput

EXPLANATION_ANSWER: Dict[str, Any] = {
    "strengths": ["Names the role"],
    "concerns": ["Generic close"],
    "improvements": ["Add a metric"],
}
LINKEDIN_ANSWER: Dict[str, Any] = {
    "overall_score": 82,
    "summary": "Clear backend profile.",
    "section_scores": [
        {"section_name": "Headline", "score": 90, "weight": 0.25, "feedback": "Clear."}
    ],
    "insights": [
        {
            "category": "headline",
            "observation": "Headline names the stack.",
            "recommendation": "Add the domain.",
            "priority": "medium",
        }
    ],
    "keyword_recommendations": ["Python"],
    "action_plan": ["Step 1"],
    "generated_headline_options": ["Backend engineer"],
    "summary_rewrite_suggestions": ["Name the domain."],
    "competitive_edge": "Strong",
}


def async_router_returning(content: str) -> MagicMock:
    """
    Build a fake router whose ``generate_async`` returns ``content``.

    Args:
        content: The raw text that the fake model returns.

    Returns:
        A MagicMock whose ``generate_async`` is an AsyncMock.
    """
    router = MagicMock()
    router.generate_async = AsyncMock(
        return_value=LLMResponse(content=content, model="qwen2.5:7b", provider="ollama")
    )
    return router


def explain(monkeypatch: pytest.MonkeyPatch, content: str) -> Tuple[Any, MagicMock]:
    """
    Run the score explanation with a fake router that answers ``content``.

    Args:
        monkeypatch: Pytest fixture used to replace ``create_router``.
        content: The raw text that the fake model returns.

    Returns:
        The explanation result and the fake router.
    """
    router = async_router_returning(content)
    monkeypatch.setattr(route, "create_router", lambda prefer_local: router)
    result = asyncio.run(route._generate_explanation("system", "user"))
    return result, router


def test_explanation_sends_its_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """The explanation sends the score explanation schema."""
    _, router = explain(monkeypatch, json.dumps(EXPLANATION_ANSWER))

    assert (
        router.generate_async.call_args.kwargs["response_schema"]
        == ScoreExplanationAnswer.model_json_schema()
    )


def test_explanation_parses_a_strict_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """A strict explanation answer gives its strengths and improvements."""
    result, _ = explain(monkeypatch, json.dumps(EXPLANATION_ANSWER))

    assert result.strengths == ["Names the role"]
    assert result.improvements == ["Add a metric"]


def test_explanation_refuses_text_around_the_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Text around the explanation JSON raises a ValueError with the reason."""
    with pytest.raises(ValueError, match="not_json"):
        explain(monkeypatch, "Sure: " + json.dumps(EXPLANATION_ANSWER))


def test_explanation_refuses_a_missing_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explanation without concerns raises a ValueError with the schema reason."""
    answer = {k: v for k, v in EXPLANATION_ANSWER.items() if k != "concerns"}

    with pytest.raises(ValueError, match="schema"):
        explain(monkeypatch, json.dumps(answer))


def test_route_has_no_lenient_json_helper() -> None:
    """The route file has no lenient JSON helper and sends the prep sheet schema."""
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "api"
        / "routes"
        / "cover_letter.py"
    ).read_text(encoding="utf-8")
    assert "_parse_json_object" not in text
    assert "response_schema=PrepSheetAnswer.model_json_schema()" in text


def test_linkedin_analysis_sends_its_schema(sample_user_profile: Any) -> None:
    """The LinkedIn analysis sends the LinkedIn analysis schema."""
    router = MagicMock(spec=LLMRouter)
    router.generate.return_value = LLMResponse(
        content=json.dumps(LINKEDIN_ANSWER), model="qwen2.5:7b", provider="ollama"
    )

    LinkedInAnalyzer(router).analyze(
        LinkedInProfileInput(raw_text="Backend engineer, Python."), sample_user_profile
    )

    assert (
        router.generate.call_args.kwargs["response_schema"]
        == LinkedInAnalysisAnswer.model_json_schema()
    )


def test_linkedin_async_analysis_sends_its_schema(sample_user_profile: Any) -> None:
    """The async LinkedIn analysis sends the same schema."""
    router = MagicMock(spec=LLMRouter)
    router.generate_async = AsyncMock(
        return_value=LLMResponse(
            content=json.dumps(LINKEDIN_ANSWER), model="qwen2.5:7b", provider="ollama"
        )
    )

    asyncio.run(
        LinkedInAnalyzer(router).analyze_async(
            LinkedInProfileInput(raw_text="Backend engineer, Python."),
            sample_user_profile,
        )
    )

    assert (
        router.generate_async.call_args.kwargs["response_schema"]
        == LinkedInAnalysisAnswer.model_json_schema()
    )


def test_linkedin_parses_a_strict_answer() -> None:
    """A strict LinkedIn answer gives the scores, insights, and empty metadata."""
    analyzer = LinkedInAnalyzer(MagicMock(spec=LLMRouter))

    result = analyzer._parse_llm_analysis(json.dumps(LINKEDIN_ANSWER))

    assert result["overall_score"] == 82
    assert result["section_scores"][0]["section_name"] == "Headline"
    assert result["insights"][0]["priority"] == "medium"
    assert result["metadata"] == {}


def test_linkedin_refuses_text_around_the_json() -> None:
    """Text around the LinkedIn JSON raises a ValueError with the reason."""
    analyzer = LinkedInAnalyzer(MagicMock(spec=LLMRouter))

    with pytest.raises(ValueError, match="Failed to extract JSON.*not_json"):
        analyzer._parse_llm_analysis(
            "Here is the analysis: " + json.dumps(LINKEDIN_ANSWER)
        )


def test_linkedin_refuses_an_unknown_priority() -> None:
    """A priority outside high, medium, and low raises a ValueError with the schema reason."""
    analyzer = LinkedInAnalyzer(MagicMock(spec=LLMRouter))
    answer = copy.deepcopy(LINKEDIN_ANSWER)
    answer["insights"][0]["priority"] = "urgent"

    with pytest.raises(ValueError, match="schema"):
        analyzer._parse_llm_analysis(json.dumps(answer))


def test_no_regex_or_brace_search_left() -> None:
    """The LinkedIn analyzer has no fence regex and no brace search."""
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "generation"
        / "linkedin_analyzer.py"
    ).read_text(encoding="utf-8")
    assert "_extract_json" not in text
    assert "re.search" not in text
