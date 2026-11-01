"""Tests for the schema and the strict parsing of JD extraction and classification (Step 3.7, MH-6)."""

import json
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from src.classifiers.job_classifier import JobClassifier
from src.extractors.jd_extractor import JDExtractor
from src.llm.base import LLMResponse
from src.llm.structured import JDExtractionAnswer, JobClassificationAnswer

JD_TEXT = (
    "Backend Engineer\nAcme - Singapore\n\nWe build payment APIs in Python.\n"
    "Requirements: 3 years of Python.\n"
)
JD_ANSWER: Dict[str, Any] = {
    "title": "Backend Engineer",
    "company": "Acme",
    "location": "Singapore",
    "requirements": ["3 years of Python"],
    "responsibilities": ["Build APIs"],
    "skills": ["Python"],
    "experience_level": "Mid",
    "salary_range": None,
}
CLASSIFICATION_ANSWER: Dict[str, Any] = {
    "industry": "Technology",
    "role_category": "Engineering",
    "company_size": "Unknown",
    "company_stage": None,
    "work_pace": "Unknown",
    "team_structure": "Unknown",
    "technical_skills": [
        {
            "name": "Python",
            "proficiency": "Advanced",
            "is_required": True,
            "category": "programming_language",
        }
    ],
    "soft_skills": [],
    "domain_skills": [],
    "experience_level_confidence": 0.8,
    "actual_experience_years": [3.0, 5.0],
    "management_level": None,
    "impact_scope": None,
    "classification_confidence": 0.7,
    "tags": ["backend"],
    "red_flags": [],
}


def router_returning(content: str) -> MagicMock:
    """
    Build a fake router whose ``generate`` returns ``content``.

    Args:
        content: The raw text that the fake model returns.

    Returns:
        A MagicMock that acts as an ``LLMRouter``.
    """
    router = MagicMock()
    router.generate.return_value = LLMResponse(
        content=content,
        model="qwen2.5:7b",
        provider="ollama",
        prompt_tokens=10,
        completion_tokens=5,
    )
    return router


def test_jd_extraction_sends_its_schema_and_answer_limit() -> None:
    """The extractor sends the JD schema and a 1,500-token answer limit."""
    router = router_returning(json.dumps(JD_ANSWER))

    JDExtractor(llm_router=router).extract_from_text(JD_TEXT)

    kwargs = router.generate.call_args.kwargs
    assert kwargs["response_schema"] == JDExtractionAnswer.model_json_schema()
    assert kwargs["max_tokens"] == 1500


def test_jd_extraction_parses_a_strict_answer() -> None:
    """A strict JD answer gives the job listing."""
    router = router_returning(json.dumps(JD_ANSWER))

    result = JDExtractor(llm_router=router).extract_from_text(JD_TEXT)

    assert result.success is True
    assert result.job_listing.title == "Backend Engineer"
    assert result.errors == []


def test_jd_extraction_accepts_a_null_level() -> None:
    """A null experience level does not end in the rule-based parser."""
    answer = dict(JD_ANSWER, experience_level=None)
    router = router_returning(json.dumps(answer))

    result = JDExtractor(llm_router=router).extract_from_text(JD_TEXT)

    assert result.errors == []
    assert result.job_listing.title == "Backend Engineer"


def test_jd_extraction_falls_back_on_text_around_the_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Text around the JD JSON makes the extractor fall back, with the reason."""
    log = MagicMock()
    monkeypatch.setattr("src.extractors.jd_extractor.logger", log)
    router = router_returning("Here is the JSON:\n" + json.dumps(JD_ANSWER))

    result = JDExtractor(llm_router=router).extract_from_text(JD_TEXT)

    assert any("not_json" in error for error in result.errors)
    assert "not_json" in str(log.warning.call_args)


def test_jd_extraction_falls_back_on_a_missing_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A JD answer without skills falls back, with the schema reason."""
    monkeypatch.setattr("src.extractors.jd_extractor.logger", MagicMock())
    answer = {k: v for k, v in JD_ANSWER.items() if k != "skills"}
    router = router_returning(json.dumps(answer))

    result = JDExtractor(llm_router=router).extract_from_text(JD_TEXT)

    assert any("schema" in error for error in result.errors)


def test_jd_extraction_cuts_a_long_posting() -> None:
    """A posting longer than 18,000 characters is cut, with a warning."""
    router = router_returning(json.dumps(JD_ANSWER))

    result = JDExtractor(llm_router=router).extract_from_text("A" * 30000)

    content = router.generate.call_args.kwargs["messages"][1].content
    assert "A" * 18000 in content
    assert "A" * 18001 not in content
    assert "Text truncated from 30000 to 18000 characters" in result.warnings


def test_classification_sends_its_schema(sample_job_listing: Any) -> None:
    """The classifier sends the classification schema."""
    router = router_returning(json.dumps(CLASSIFICATION_ANSWER))

    JobClassifier(llm_router=router).classify(sample_job_listing, use_llm=True)

    assert (
        router.generate.call_args.kwargs["response_schema"]
        == JobClassificationAnswer.model_json_schema()
    )


def test_classification_parses_a_strict_answer(sample_job_listing: Any) -> None:
    """A strict classification answer gives the classification."""
    router = router_returning(json.dumps(CLASSIFICATION_ANSWER))

    result = JobClassifier(llm_router=router).classify(sample_job_listing, use_llm=True)

    assert result.success is True
    assert result.errors == []
    assert result.classification.tags == ["backend"]


def test_classification_falls_back_on_text_after_the_fence(
    sample_job_listing: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prose after the fenced JSON makes the classifier fall back, with the reason."""
    log = MagicMock()
    monkeypatch.setattr("src.classifiers.job_classifier.logger", log)
    content = (
        "```json\n"
        + json.dumps(CLASSIFICATION_ANSWER)
        + "\n```\n- **Industry**: the posting names payments."
    )
    router = router_returning(content)

    result = JobClassifier(llm_router=router).classify(sample_job_listing, use_llm=True)

    assert any("not_json" in error for error in result.errors)
    assert "not_json" in str(log.warning.call_args)


def test_classification_falls_back_on_a_confidence_above_1(
    sample_job_listing: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A confidence above 1 makes the classifier fall back, with the schema reason."""
    monkeypatch.setattr("src.classifiers.job_classifier.logger", MagicMock())
    answer = dict(CLASSIFICATION_ANSWER, classification_confidence=1.5)
    router = router_returning(json.dumps(answer))

    result = JobClassifier(llm_router=router).classify(sample_job_listing, use_llm=True)

    assert any("schema" in error for error in result.errors)


def test_no_regex_json_parsing_left() -> None:
    """The two files no longer search the answer with the regex."""
    from pathlib import Path

    base = Path(__file__).resolve().parents[2] / "src"
    for path in ("extractors/jd_extractor.py", "classifiers/job_classifier.py"):
        assert r're.search(r"\{.*\}"' not in (base / path).read_text(encoding="utf-8")
