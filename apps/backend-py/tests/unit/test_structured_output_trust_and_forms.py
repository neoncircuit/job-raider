"""Tests for the output models of the trust analysis and the form-question fallback (Step 3.7, MH-11)."""

import json
from typing import Any, Dict

import pytest

from src.llm.structured import (
    FormQuestionAnswer,
    StructuredOutputError,
    TrustAnalysisAnswer,
    parse_structured,
)

TRUST_ANSWER: Dict[str, Any] = {
    "summary": "Looks legitimate.",
    "additional_indicators": [],
    "confidence_adjustment": 0.0,
}
FORM_ANSWER: Dict[str, Any] = {
    "answer": "Yes",
    "confidence": "high",
    "reasoning": "The profile says the candidate can relocate.",
}


def test_trust_answer_matches_its_prompt_shape() -> None:
    """A trust answer in the prompt's shape validates."""
    parsed = parse_structured(json.dumps(TRUST_ANSWER), TrustAnalysisAnswer)

    assert parsed.summary == "Looks legitimate."


def test_form_answer_matches_its_prompt_shape() -> None:
    """A form answer in the prompt's shape validates."""
    parsed = parse_structured(json.dumps(FORM_ANSWER), FormQuestionAnswer)

    assert parsed.answer == "Yes"


def test_both_schemas_require_every_field() -> None:
    """Each schema requires all of its prompt's fields."""
    trust = TrustAnalysisAnswer.model_json_schema()
    form = FormQuestionAnswer.model_json_schema()

    assert set(trust["required"]) == {
        "summary",
        "additional_indicators",
        "confidence_adjustment",
    }
    assert set(form["required"]) == {"answer", "confidence", "reasoning"}


@pytest.mark.parametrize("adjustment", [-0.1, 0.0, 0.2])
def test_trust_adjustment_inside_the_prompt_range(adjustment: float) -> None:
    """Adjustments from -0.1 to 0.2 match."""
    answer = dict(TRUST_ANSWER, confidence_adjustment=adjustment)

    parsed = parse_structured(json.dumps(answer), TrustAnalysisAnswer)

    assert parsed.confidence_adjustment == adjustment


@pytest.mark.parametrize("adjustment", [-0.11, 0.21, 0.5])
def test_trust_adjustment_outside_the_prompt_range(adjustment: float) -> None:
    """Adjustments below -0.1 or above 0.2 do not match."""
    answer = dict(TRUST_ANSWER, confidence_adjustment=adjustment)

    with pytest.raises(StructuredOutputError) as caught:
        parse_structured(json.dumps(answer), TrustAnalysisAnswer)

    assert caught.value.reason == "schema"


@pytest.mark.parametrize("confidence", ["unknown", "certain", "High"])
def test_form_confidence_has_three_values(confidence: str) -> None:
    """A confidence outside high, medium, and low does not match."""
    answer = dict(FORM_ANSWER, confidence=confidence)

    with pytest.raises(StructuredOutputError):
        parse_structured(json.dumps(answer), FormQuestionAnswer)
