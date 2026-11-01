"""Tests for the schema and the strict parsing of the resume pipeline (Step 3.7, MH-4)."""

import json
from typing import Any, Dict
from unittest.mock import MagicMock

from src.generation.resume_writer import GeneratedResume, ResumeWriter
from src.generation.selector import ResumeSelector, SelectionOutput
from src.generation.validator import ResumeValidator, ValidationResult
from src.llm.base import LLMResponse
from src.llm.structured import (
    ResumeValidationAnswer,
    ResumeWritingAnswer,
    SelectionAnswer,
)

SELECTION_ANSWER: Dict[str, Any] = {
    "selected_projects": [{"name": "Ledger", "reason": "Payments work"}],
    "keywords_to_emphasize": ["Python"],
    "key_achievements": ["Built a ledger"],
    "summary_suggestion": "Backend engineer with payment APIs.",
}
WRITING_ANSWER: Dict[str, Any] = {
    "summary": "Backend engineer.",
    "skills": ["Python"],
    "experience": [
        {
            "title": "Engineer",
            "company": "Acme",
            "dates": "2024 - 2025",
            "highlights": ["Built an API"],
        }
    ],
    "projects": [],
    "education": [{"degree": "BSc", "school": "NUS", "year": "2025"}],
}
VALIDATION_ANSWER: Dict[str, Any] = {
    "is_valid": True,
    "missing_projects": [],
    "missing_keywords": [],
    "fabricated_content": [],
    "date_inconsistencies": [],
    "overall_score": 85,
    "recommendation": "approve",
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


def empty_selection() -> SelectionOutput:
    """
    Build a selection with no projects and no keywords.

    Returns:
        A SelectionOutput with empty lists.
    """
    return SelectionOutput(
        selected_projects=[],
        keywords_to_emphasize=[],
        key_achievements=[],
        summary_suggestion="",
        raw_response="{}",
    )


def small_resume() -> GeneratedResume:
    """
    Build a small generated resume for the validator.

    Returns:
        A GeneratedResume with one skill and no sections.
    """
    return GeneratedResume(
        summary="Backend engineer.",
        skills=["Python"],
        experience=[],
        projects=[],
        education=[],
        raw_response="",
        model_used="fake",
    )


def logged_errors(component: Any) -> str:
    """
    Join the text of all error log calls of a component.

    Args:
        component: A component whose ``logger`` is a MagicMock.

    Returns:
        The messages of all ``logger.error`` calls, as one string.
    """
    return " ".join(str(call.args[0]) for call in component.logger.error.call_args_list)


def test_selection_sends_its_schema(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """The selector sends the JSON schema of SelectionAnswer."""
    router = router_returning(json.dumps(SELECTION_ANSWER))

    ResumeSelector(router).select(sample_job_listing, sample_user_profile)

    assert (
        router.generate.call_args.kwargs["response_schema"]
        == SelectionAnswer.model_json_schema()
    )


def test_selection_parses_a_strict_answer(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """A strict selection answer is parsed into the selection."""
    content = json.dumps(SELECTION_ANSWER)
    router = router_returning(content)

    selection = ResumeSelector(router).select(sample_job_listing, sample_user_profile)

    assert selection.summary_suggestion == "Backend engineer with payment APIs."
    assert selection.raw_response == content


def test_selection_falls_back_on_text_around_the_json(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """Text around the selection JSON makes the selector fall back and log why."""
    router = router_returning("Here it is: " + json.dumps(SELECTION_ANSWER))
    selector = ResumeSelector(router)
    selector.logger = MagicMock()

    selection = selector.select(sample_job_listing, sample_user_profile)

    assert selection.raw_response == ""
    assert "not_json" in logged_errors(selector)


def test_selection_falls_back_on_a_missing_field(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """A selection answer without summary_suggestion makes the selector fall back."""
    answer = {k: v for k, v in SELECTION_ANSWER.items() if k != "summary_suggestion"}
    router = router_returning(json.dumps(answer))

    selection = ResumeSelector(router).select(sample_job_listing, sample_user_profile)

    assert selection.raw_response == ""


def test_resume_writing_sends_its_schema(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """The writer sends the JSON schema of ResumeWritingAnswer."""
    router = router_returning(json.dumps(WRITING_ANSWER))

    ResumeWriter(router).write(
        sample_job_listing, sample_user_profile, empty_selection()
    )

    assert (
        router.generate.call_args.kwargs["response_schema"]
        == ResumeWritingAnswer.model_json_schema()
    )


def test_resume_writing_parses_a_strict_answer(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """A strict writing answer is parsed into the resume."""
    router = router_returning(json.dumps(WRITING_ANSWER))

    resume = ResumeWriter(router).write(
        sample_job_listing, sample_user_profile, empty_selection()
    )

    assert resume.summary == "Backend engineer."
    assert resume.model_used != "template_fallback"
    assert resume.experience == WRITING_ANSWER["experience"]
    assert resume.education == WRITING_ANSWER["education"]


def test_resume_writing_falls_back_on_text_around_the_json(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """Text around the writing JSON makes the writer fall back and log why."""
    router = router_returning("Sure:\n" + json.dumps(WRITING_ANSWER))
    writer = ResumeWriter(router)
    writer.logger = MagicMock()

    resume = writer.write(sample_job_listing, sample_user_profile, empty_selection())

    assert resume.model_used == "template_fallback"
    assert "not_json" in logged_errors(writer)


def test_resume_writing_falls_back_on_grouped_skills(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """Grouped skills do not match the flat skill list, so the writer falls back."""
    answer = dict(WRITING_ANSWER)
    answer["skills"] = [{"category": "Languages", "skills": ["Python"]}]
    router = router_returning(json.dumps(answer))

    resume = ResumeWriter(router).write(
        sample_job_listing, sample_user_profile, empty_selection()
    )

    assert resume.model_used == "template_fallback"


def test_resume_validation_sends_its_schema(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """The validator sends the JSON schema of ResumeValidationAnswer."""
    router = router_returning(json.dumps(VALIDATION_ANSWER))

    ResumeValidator(llm_router=router).validate_with_llm(
        small_resume(), sample_job_listing, sample_user_profile, empty_selection()
    )

    assert (
        router.generate.call_args.kwargs["response_schema"]
        == ResumeValidationAnswer.model_json_schema()
    )


def test_resume_validation_parses_a_strict_answer(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """A strict validation answer is parsed into the validation result."""
    router = router_returning(json.dumps(VALIDATION_ANSWER))

    result = ResumeValidator(llm_router=router).validate_with_llm(
        small_resume(), sample_job_listing, sample_user_profile, empty_selection()
    )

    assert result.overall_score == 85
    assert result.recommendation == "approve"
    assert result.issues == []


def test_resume_validation_falls_back_on_text_around_the_json(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """Text around the validation JSON makes the validator fall back and log why."""
    router = router_returning("Result: " + json.dumps(VALIDATION_ANSWER))
    validator = ResumeValidator(llm_router=router)
    validator.logger = MagicMock()
    rule_result = MagicMock(spec=ValidationResult)
    validator.validate = MagicMock(return_value=rule_result)

    result = validator.validate_with_llm(
        small_resume(), sample_job_listing, sample_user_profile, empty_selection()
    )

    assert result is rule_result
    assert "not_json" in logged_errors(validator)


def test_resume_validation_falls_back_on_an_unknown_recommendation(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """A recommendation outside the allowed values makes the validator fall back."""
    answer = dict(VALIDATION_ANSWER, recommendation="Approve")
    router = router_returning(json.dumps(answer))
    validator = ResumeValidator(llm_router=router)
    rule_result = MagicMock(spec=ValidationResult)
    validator.validate = MagicMock(return_value=rule_result)

    result = validator.validate_with_llm(
        small_resume(), sample_job_listing, sample_user_profile, empty_selection()
    )

    assert result is rule_result


def test_no_regex_json_parsing_left() -> None:
    """The three pipeline files no longer search the answer with the regex."""
    from pathlib import Path

    base = Path(__file__).resolve().parents[2] / "src" / "generation"
    for name in ("selector.py", "resume_writer.py", "validator.py"):
        assert r're.search(r"\{.*\}"' not in (base / name).read_text(encoding="utf-8")
