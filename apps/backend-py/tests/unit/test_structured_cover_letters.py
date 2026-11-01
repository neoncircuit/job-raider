"""Tests for the schema and the strict parsing of the cover-letter LLM calls (Step 3.7, MH-5)."""

import json
from typing import Any, Dict, Tuple
from unittest.mock import MagicMock

from src.generation.cover_letter_reviewer import CoverLetterReviewer
from src.generation.cover_letter_validator import CoverLetterValidator
from src.generation.cover_letter_writer import GeneratedCoverLetter
from src.generation.selector import SelectionOutput
from src.llm.base import LLMResponse
from src.llm.structured import CoverLetterReviewAnswer, CoverLetterValidationAnswer

REVIEW_ANSWER: Dict[str, Any] = {
    "critique": "  Name the role in the first line.  ",
    "rewrite_needed": True,
}
VALIDATION_ANSWER: Dict[str, Any] = {
    "structure_score": 80,
    "content_score": 75,
    "tone_score": 90,
    "overall_score": 82,
    "is_valid": True,
    "recommendation": "approve",
    "issues": ["Generic opening"],
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
        model="qwen2.5:3b",
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


def short_letter() -> GeneratedCoverLetter:
    """
    Build a short cover letter draft.

    Returns:
        A GeneratedCoverLetter with a small body text.
    """
    content = "Dear Hiring Team, I build Python services. Thank you."
    return GeneratedCoverLetter(
        content=content,
        highlighted_experiences=[],
        word_count=len(content.split()),
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
    return " ".join(
        str(call.args[0]) % tuple(call.args[1:])
        for call in component.logger.error.call_args_list
    )


def validator_with_rules(content: str) -> Tuple[CoverLetterValidator, MagicMock]:
    """
    Build a validator whose rule check passes and whose LLM answers ``content``.

    Args:
        content: The raw text that the fake model returns.

    Returns:
        The validator and the rule result that its ``validate`` returns.
    """
    validator = CoverLetterValidator(llm_router=router_returning(content))
    rule_result = MagicMock()
    rule_result.issues = []
    validator.validate = MagicMock(return_value=rule_result)
    return validator, rule_result


def test_review_sends_its_schema(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """The reviewer sends the JSON schema of CoverLetterReviewAnswer."""
    router = router_returning(json.dumps(REVIEW_ANSWER))

    CoverLetterReviewer(router).review(
        short_letter(), sample_job_listing, sample_user_profile, empty_selection()
    )

    assert (
        router.generate.call_args.kwargs["response_schema"]
        == CoverLetterReviewAnswer.model_json_schema()
    )


def test_review_parses_a_strict_answer(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """A strict review answer gives the stripped critique and the flag."""
    router = router_returning(json.dumps(REVIEW_ANSWER))

    result = CoverLetterReviewer(router).review(
        short_letter(), sample_job_listing, sample_user_profile, empty_selection()
    )

    assert result.critique == "Name the role in the first line."
    assert result.rewrite_needed is True
    assert result.model_used != "error"


def test_review_falls_back_on_text_around_the_json(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """Text around the review JSON makes the reviewer fall back and log why."""
    router = router_returning("Review: " + json.dumps(REVIEW_ANSWER))
    reviewer = CoverLetterReviewer(router)
    reviewer.logger = MagicMock()

    result = reviewer.review(
        short_letter(), sample_job_listing, sample_user_profile, empty_selection()
    )

    assert result.model_used == "error"
    assert result.critique == "Review unavailable."
    assert "not_json" in logged_errors(reviewer)


def test_review_falls_back_on_a_missing_field(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """A review answer without rewrite_needed makes the reviewer fall back."""
    router = router_returning(json.dumps({"critique": "Fine."}))

    result = CoverLetterReviewer(router).review(
        short_letter(), sample_job_listing, sample_user_profile, empty_selection()
    )

    assert result.model_used == "error"


def test_letter_validation_sends_its_schema(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """The validator sends the JSON schema of CoverLetterValidationAnswer."""
    validator, _ = validator_with_rules(json.dumps(VALIDATION_ANSWER))

    validator.validate_with_llm(
        short_letter(), sample_job_listing, sample_user_profile, empty_selection()
    )

    assert (
        validator.llm_router.generate.call_args.kwargs["response_schema"]
        == CoverLetterValidationAnswer.model_json_schema()
    )


def test_letter_validation_parses_a_strict_answer(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """A strict validation answer is parsed into the result."""
    validator, rule_result = validator_with_rules(json.dumps(VALIDATION_ANSWER))

    result = validator.validate_with_llm(
        short_letter(), sample_job_listing, sample_user_profile, empty_selection()
    )

    assert result is not rule_result
    assert result.score == 82
    assert result.structure_score == 80
    assert result.recommendation == "approve"
    assert result.details == {"llm_feedback": ["Generic opening"]}


def test_letter_validation_falls_back_on_text_around_the_json(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """Text around the validation JSON makes the validator fall back and log why."""
    content = "Here is the evaluation of the cover letter:\n" + json.dumps(
        VALIDATION_ANSWER
    )
    validator, rule_result = validator_with_rules(content)
    validator.logger = MagicMock()

    result = validator.validate_with_llm(
        short_letter(), sample_job_listing, sample_user_profile, empty_selection()
    )

    assert result is rule_result
    assert "not_json" in logged_errors(validator)


def test_letter_validation_falls_back_on_an_unknown_recommendation(
    sample_job_listing: Any, sample_user_profile: Any
) -> None:
    """A recommendation outside the three allowed values makes the validator fall back."""
    answer = dict(VALIDATION_ANSWER, recommendation="Needs Revision")
    validator, rule_result = validator_with_rules(json.dumps(answer))

    result = validator.validate_with_llm(
        short_letter(), sample_job_listing, sample_user_profile, empty_selection()
    )

    assert result is rule_result


def test_no_regex_json_parsing_left() -> None:
    """The two cover-letter files no longer search the answer with the regex."""
    from pathlib import Path

    base = Path(__file__).resolve().parents[2] / "src" / "generation"
    for name in ("cover_letter_reviewer.py", "cover_letter_validator.py"):
        assert r're.search(r"\{.*\}"' not in (base / name).read_text(encoding="utf-8")
