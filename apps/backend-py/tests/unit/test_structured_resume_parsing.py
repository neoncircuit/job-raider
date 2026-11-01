"""Tests for the schema and the strict parsing of resume parsing and analysis (Step 3.7, MH-7)."""

import json
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from src.extractors.resume_parser import ResumeParser
from src.generation.resume_analyzer import ResumeAnalyzer
from src.llm.base import LLMResponse
from src.llm.structured import ResumeAnalysisAnswer, ResumeParsingAnswer

RESUME_TEXT = (
    "Mara Chen\nSingapore, Singapore\nmara@example.com\n\n"
    "TECHNICAL SKILLS\nPython, FastAPI, PostgreSQL\n\n"
    "EXPERIENCE\nEngineer - Acme\nJan 2024 - Present\n- Built an API\n"
)
PARSING_ANSWER: Dict[str, Any] = {
    "basics": {
        "name": "Mara Chen",
        "email": "mara@example.com",
        "phone": None,
        "location": "Singapore, Singapore",
        "linkedin": None,
        "github": None,
    },
    "summary": None,
    "skills": {
        "programming_languages": ["Python"],
        "frameworks": ["FastAPI"],
        "tools": [],
        "databases": ["PostgreSQL"],
        "cloud": [],
        "domains": [],
    },
    "experience": [
        {
            "title": "Engineer",
            "company": "Acme",
            "location": None,
            "start_date": "2024-01",
            "end_date": "present",
            "highlights": ["Built an API"],
        }
    ],
    "projects": [],
    "education": [],
    "certifications": [],
    "target_job": {
        "keywords": ["Software Engineer"],
        "locations": ["Singapore"],
        "experience_levels": ["Entry Level"],
        "remote_preference": None,
        "industries": ["Technology"],
    },
    "apprenticeship": None,
}
ANALYSIS_ANSWER: Dict[str, Any] = {
    "overall_score": 73,
    "summary": "Strong backend profile.",
    "key_strengths": ["Python"],
    "key_improvements": ["Add metrics"],
    "resume_improvements": ["Quantify results"],
    "skill_gaps": ["Kubernetes"],
    "next_steps": ["Build a cloud project"],
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


def parse_method(profile: Any) -> str:
    """
    Read how the resume was parsed from the profile metadata.

    Args:
        profile: The parsed UserProfile.

    Returns:
        The method name, ``llm`` or ``rule_based``.
    """
    return str(profile.metadata["resume_parse"]["method"])


def test_resume_parsing_sends_its_schema_and_answer_limit() -> None:
    """The parser sends the parsing schema and a 3,000-token answer limit."""
    router = router_returning(json.dumps(PARSING_ANSWER))

    ResumeParser(llm_router=router).parse_text(RESUME_TEXT)

    kwargs = router.generate.call_args.kwargs
    assert kwargs["response_schema"] == ResumeParsingAnswer.model_json_schema()
    assert kwargs["max_tokens"] == 3000


def test_resume_parsing_parses_a_strict_answer() -> None:
    """A strict parsing answer gives an LLM-parsed profile."""
    router = router_returning(json.dumps(PARSING_ANSWER))

    profile = ResumeParser(llm_router=router).parse_text(RESUME_TEXT)

    assert profile.name == "Mara Chen"
    assert parse_method(profile) == "llm"


def test_resume_parsing_falls_back_on_text_after_the_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prose after the fenced JSON makes the parser fall back, with the reason logged."""
    log = MagicMock()
    monkeypatch.setattr("src.extractors.resume_parser.logger", log)
    content = (
        "```json\n" + json.dumps(PARSING_ANSWER) + "\n```\nI extracted the fields."
    )
    router = router_returning(content)

    profile = ResumeParser(llm_router=router).parse_text(RESUME_TEXT)

    assert parse_method(profile) == "rule_based"
    assert "not_json" in str(log.error.call_args)


def test_resume_parsing_falls_back_on_flat_skills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A flat skills list does not match the grouped skills object, so the parser falls back."""
    monkeypatch.setattr("src.extractors.resume_parser.logger", MagicMock())
    answer = dict(PARSING_ANSWER, skills=["Python", "FastAPI"])
    router = router_returning(json.dumps(answer))

    profile = ResumeParser(llm_router=router).parse_text(RESUME_TEXT)

    assert parse_method(profile) == "rule_based"


def test_resume_parsing_cuts_a_long_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    """A resume longer than 8,000 characters is cut for the LLM, with a warning."""
    log = MagicMock()
    monkeypatch.setattr("src.extractors.resume_parser.logger", log)
    router = router_returning(json.dumps(PARSING_ANSWER))

    ResumeParser(llm_router=router).parse_text("y" * 20000)

    content = router.generate.call_args.kwargs["messages"][1].content
    assert "y" * 8000 in content
    assert "y" * 8001 not in content
    warning = str(log.warning.call_args)
    assert "20000" in warning
    assert "8000" in warning


def test_resume_parsing_prompt_asks_for_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """The prompt asks for null for missing URLs and for grouped skills only."""
    monkeypatch.setattr("src.extractors.resume_parser.logger", MagicMock())
    router = router_returning(json.dumps(PARSING_ANSWER))

    ResumeParser(llm_router=router).parse_text(RESUME_TEXT)

    content = router.generate.call_args.kwargs["messages"][1].content
    assert '"linkedin": "LinkedIn URL, or null"' in content
    assert '"github": "GitHub URL, or null"' in content
    assert "A flat skills array is also acceptable" not in content


def test_general_analysis_sends_its_schema(sample_user_profile: Any) -> None:
    """The general analysis sends the analysis schema."""
    router = router_returning(json.dumps(ANALYSIS_ANSWER))

    ResumeAnalyzer(router).analyze_general(sample_user_profile)

    assert (
        router.generate.call_args.kwargs["response_schema"]
        == ResumeAnalysisAnswer.model_json_schema()
    )


def test_job_analysis_sends_its_schema(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """The job-specific analysis sends the analysis schema."""
    router = router_returning(json.dumps(ANALYSIS_ANSWER))

    ResumeAnalyzer(router).analyze_job_specific(sample_user_profile, sample_job_listing)

    assert (
        router.generate.call_args.kwargs["response_schema"]
        == ResumeAnalysisAnswer.model_json_schema()
    )


def test_analysis_parses_a_strict_answer(sample_user_profile: Any) -> None:
    """A strict analysis answer gives its score and summary."""
    router = router_returning(json.dumps(ANALYSIS_ANSWER))

    analysis = ResumeAnalyzer(router).analyze_general(sample_user_profile)

    assert analysis.overall_score == 73
    assert analysis.summary == "Strong backend profile."


def test_analysis_falls_back_on_text_around_the_json(sample_user_profile: Any) -> None:
    """Text around the analysis JSON makes the analyzer fall back and log why."""
    router = router_returning("Analysis:\n" + json.dumps(ANALYSIS_ANSWER))
    analyzer = ResumeAnalyzer(router)
    analyzer.logger = MagicMock()

    analysis = analyzer.analyze_general(sample_user_profile)

    assert analysis.summary != "Strong backend profile."
    errors = " ".join(str(c.args[0]) for c in analyzer.logger.error.call_args_list)
    assert "not_json" in errors


def test_analysis_falls_back_on_a_score_above_100(sample_user_profile: Any) -> None:
    """A score above 100 makes the analyzer fall back to the rule-based summary."""
    answer = dict(ANALYSIS_ANSWER, overall_score=150)
    router = router_returning(json.dumps(answer))
    analyzer = ResumeAnalyzer(router)
    analyzer.logger = MagicMock()

    analysis = analyzer.analyze_general(sample_user_profile)

    assert analysis.summary != "Strong backend profile."


def test_no_regex_json_parsing_left() -> None:
    """The two files no longer search the answer with the regex."""
    from pathlib import Path

    base = Path(__file__).resolve().parents[2] / "src"
    for path in ("extractors/resume_parser.py", "generation/resume_analyzer.py"):
        assert r're.search(r"\{.*\}"' not in (base / path).read_text(encoding="utf-8")
