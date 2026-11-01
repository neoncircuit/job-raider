"""Tests for the output models of the prep sheet, score explanation, LinkedIn analysis, and assessments (Step 3.7, MH-8)."""

import json
from typing import Any, Dict, Set, Type

import pytest
from pydantic import BaseModel

from src.llm.structured import (
    AssessmentQuestionsAnswer,
    AssessmentScoreAnswer,
    LinkedInAnalysisAnswer,
    PrepSheetAnswer,
    ScoreExplanationAnswer,
    StructuredOutputError,
    parse_structured,
)

LINKEDIN_ANSWER: Dict[str, Any] = {
    "overall_score": 85,
    "summary": "Strong profile.",
    "section_scores": [
        {"section_name": "Headline", "score": 90, "weight": 0.25, "feedback": "Clear."}
    ],
    "insights": [
        {
            "category": "headline",
            "observation": "Headline is strong.",
            "recommendation": "Keep it.",
            "priority": "low",
        }
    ],
    "keyword_recommendations": ["Python"],
    "action_plan": ["Step 1"],
    "generated_headline_options": ["Backend engineer"],
    "summary_rewrite_suggestions": ["Name the domain."],
    "competitive_edge": "Strong",
}
QUESTION: Dict[str, Any] = {
    "question_type": "coding",
    "answer_format": "multiple_choice",
    "difficulty": "advanced",
    "topic": "algorithms",
    "question_text": "Which search is O(log n)?",
    "options": [
        {"label": "A", "text": "Binary search", "is_correct": True},
        {"label": "B", "text": "Linear search", "is_correct": False},
    ],
    "correct_answer_hint": "Binary search halves the range.",
    "time_limit_seconds": 120,
}
SCORE_ANSWER: Dict[str, Any] = {
    "score": 80,
    "feedback": "Good answer.",
    "strengths": ["Clear"],
    "improvements": ["Add an example"],
    "model_answer": "Binary search.",
}

SAMPLES = [
    (
        PrepSheetAnswer,
        {"likely_questions": ["Why us?"], "gaps_to_address": [], "talking_points": []},
    ),
    (
        ScoreExplanationAnswer,
        {"strengths": ["Python"], "concerns": [], "improvements": ["Add Go"]},
    ),
    (LinkedInAnalysisAnswer, LINKEDIN_ANSWER),
    (AssessmentQuestionsAnswer, {"questions": [QUESTION]}),
    (AssessmentScoreAnswer, SCORE_ANSWER),
]

REQUIRED: Dict[Type[BaseModel], Set[str]] = {
    PrepSheetAnswer: {"likely_questions", "gaps_to_address", "talking_points"},
    ScoreExplanationAnswer: {"strengths", "concerns", "improvements"},
    LinkedInAnalysisAnswer: {
        "overall_score",
        "summary",
        "section_scores",
        "insights",
        "keyword_recommendations",
        "action_plan",
        "generated_headline_options",
        "summary_rewrite_suggestions",
        "competitive_edge",
    },
    AssessmentQuestionsAnswer: {"questions"},
    AssessmentScoreAnswer: {
        "score",
        "feedback",
        "strengths",
        "improvements",
        "model_answer",
    },
}


@pytest.mark.parametrize("model, sample", SAMPLES)
def test_each_model_accepts_the_shape_of_its_prompt(
    model: Type[BaseModel], sample: Dict[str, Any]
) -> None:
    """A sample answer in the shape that each prompt asks for validates."""
    assert isinstance(parse_structured(json.dumps(sample), model), model)


@pytest.mark.parametrize("model", list(REQUIRED))
def test_each_schema_requires_the_prompt_fields(model: Type[BaseModel]) -> None:
    """Each schema is an object schema that requires exactly the prompt's fields."""
    schema = model.model_json_schema()

    assert schema["type"] == "object"
    assert set(schema["required"]) == REQUIRED[model]


def test_linkedin_priority_has_three_values() -> None:
    """An insight priority outside high, medium, and low does not match."""
    answer = json.loads(json.dumps(LINKEDIN_ANSWER))
    answer["insights"][0]["priority"] = "urgent"

    with pytest.raises(StructuredOutputError) as caught:
        parse_structured(json.dumps(answer), LinkedInAnalysisAnswer)

    assert caught.value.reason == "schema"


def test_linkedin_section_score_is_at_most_100() -> None:
    """A section score above 100 does not match."""
    answer = json.loads(json.dumps(LINKEDIN_ANSWER))
    answer["section_scores"][0]["score"] = 120

    with pytest.raises(StructuredOutputError):
        parse_structured(json.dumps(answer), LinkedInAnalysisAnswer)


def test_linkedin_metadata_is_optional() -> None:
    """The analysis needs no metadata."""
    parsed = parse_structured(json.dumps(LINKEDIN_ANSWER), LinkedInAnalysisAnswer)

    assert parsed.metadata == {}


def test_a_question_needs_no_hint_options_or_time_limit() -> None:
    """A free-form question without a hint, options, or a time limit matches."""
    question = {
        k: v
        for k, v in QUESTION.items()
        if k not in ("options", "correct_answer_hint", "time_limit_seconds")
    }

    parsed = parse_structured(
        json.dumps({"questions": [question]}), AssessmentQuestionsAnswer
    )

    item = parsed.questions[0]
    assert item.options == []
    assert item.correct_answer_hint == ""
    assert item.time_limit_seconds is None


def test_a_disc_question_type_does_not_match() -> None:
    """Generated questions are technical; ``disc`` is not one of their types."""
    question = dict(QUESTION, question_type="disc")

    with pytest.raises(StructuredOutputError):
        parse_structured(
            json.dumps({"questions": [question]}), AssessmentQuestionsAnswer
        )


def test_a_bare_question_list_is_not_an_object() -> None:
    """A JSON array of questions is a ``not_object`` failure."""
    with pytest.raises(StructuredOutputError) as caught:
        parse_structured(json.dumps([QUESTION]), AssessmentQuestionsAnswer)

    assert caught.value.reason == "not_object"


def test_a_free_form_score_needs_no_correct_flag() -> None:
    """A free-form score has no ``is_correct``; a multiple-choice score has one."""
    free_form = parse_structured(json.dumps(SCORE_ANSWER), AssessmentScoreAnswer)
    choice = parse_structured(
        json.dumps(dict(SCORE_ANSWER, is_correct=True)), AssessmentScoreAnswer
    )

    assert free_form.is_correct is None
    assert choice.is_correct is True


def test_a_score_above_100_does_not_match() -> None:
    """A score above 100 does not match."""
    with pytest.raises(StructuredOutputError):
        parse_structured(
            json.dumps(dict(SCORE_ANSWER, score=150)), AssessmentScoreAnswer
        )
