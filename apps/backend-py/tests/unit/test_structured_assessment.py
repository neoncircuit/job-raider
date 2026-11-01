"""Tests for the schema and the strict parsing of the assessment engine (Step 3.7, MH-10)."""

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import yaml

from src.assessment.engine import AssessmentEngine
from src.llm.structured import AssessmentQuestionsAnswer, AssessmentScoreAnswer
from src.models.assessment import (
    Answer,
    AnswerFormat,
    AssessmentMode,
    AssessmentSession,
    DifficultyLevel,
    MultipleChoiceOption,
    Question,
    QuestionType,
)

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


def make_engine(content: str) -> AssessmentEngine:
    """
    Build an engine whose router answers ``content`` and whose templates are small.

    Args:
        content: The raw text that the fake model returns.

    Returns:
        An AssessmentEngine without the real prompt files loaded.
    """
    engine = AssessmentEngine.__new__(AssessmentEngine)
    engine.llm_router = MagicMock()
    engine.llm_router.generate.return_value = MagicMock(content=content)
    engine.logger = MagicMock()
    engine._gen_template = {
        "system": "You are a technical interviewer.",
        "user": "Generate {{count}} questions on {{topic_seed}}.",
    }
    engine._eval_freeform_template = {
        "system": "Evaluate the answer.",
        "user": "Question: {{question_text}}\nAnswer: {{candidate_answer}}",
    }
    engine._eval_mc_template = {
        "system": "Explain MC answer.",
        "user": "Question: {{question_text}}\nSelected: {{selected_option}}",
    }
    return engine


def free_form_question() -> Question:
    """
    Build a free-form question for the scoring tests.

    Returns:
        A conceptual Python question with a short hint.
    """
    return Question(
        question_id="q-ff",
        question_type=QuestionType.CONCEPTUAL,
        answer_format=AnswerFormat.FREEFORM,
        difficulty=DifficultyLevel.INTERMEDIATE,
        topic="Python",
        question_text="Explain a tuple.",
        correct_answer_hint="Immutable sequence.",
    )


def choice_question() -> Question:
    """
    Build a multiple-choice question whose correct option is A.

    Returns:
        A question with options A (correct) and B.
    """
    return Question(
        question_id="q-mc",
        question_type=QuestionType.CONCEPTUAL,
        answer_format=AnswerFormat.MULTIPLE_CHOICE,
        difficulty=DifficultyLevel.INTERMEDIATE,
        topic="Python",
        question_text="Which is a tuple?",
        options=[
            MultipleChoiceOption(label="A", text="(1, 2)", is_correct=True),
            MultipleChoiceOption(label="B", text="[1, 2]", is_correct=False),
        ],
        correct_answer_hint="Parentheses.",
    )


def logged_errors(engine: AssessmentEngine) -> str:
    """
    Join the text of all error log calls of an engine.

    Args:
        engine: An engine whose ``logger`` is a MagicMock.

    Returns:
        The messages of all ``logger.error`` calls, as one string.
    """
    return " ".join(
        str(call.args[0]) % tuple(call.args[1:])
        for call in engine.logger.error.call_args_list
    )


def test_question_generation_sends_its_schema() -> None:
    """The question generation sends the questions schema."""
    engine = make_engine(json.dumps({"questions": [QUESTION]}))
    session = AssessmentSession(
        mode=AssessmentMode.SKILL_BASED, target_skills=["Python"], question_count=1
    )

    engine.generate_questions(session, count=1)

    assert (
        engine.llm_router.generate.call_args.kwargs["response_schema"]
        == AssessmentQuestionsAnswer.model_json_schema()
    )


def test_questions_parse_a_strict_answer() -> None:
    """A strict questions object gives the question fields."""
    engine = make_engine("")

    questions = engine._parse_questions(json.dumps({"questions": [QUESTION]}), 1)

    assert questions[0].question_type == QuestionType.CODING
    assert questions[0].topic == "algorithms"
    assert questions[0].options[0].is_correct is True
    assert questions[0].time_limit_seconds == 120


def test_questions_fall_back_on_a_bare_list() -> None:
    """A bare list of questions falls back, with the reason logged."""
    engine = make_engine("")

    questions = engine._parse_questions(json.dumps([QUESTION]), 1)

    assert questions[0].topic != "algorithms"
    assert "not_object" in logged_errors(engine)


def test_questions_fall_back_on_text_around_the_json() -> None:
    """Text around the questions JSON falls back, with the reason logged."""
    engine = make_engine("")

    questions = engine._parse_questions(
        "Here are the questions: " + json.dumps({"questions": [QUESTION]}), 1
    )

    assert questions[0].topic != "algorithms"
    assert "not_json" in logged_errors(engine)


def test_free_form_scoring_sends_its_schema() -> None:
    """The free-form scoring sends the score schema."""
    engine = make_engine(json.dumps(SCORE_ANSWER))

    engine._evaluate_freeform(
        free_form_question(), Answer(question_id="q-ff", freeform_text="A tuple.")
    )

    assert (
        engine.llm_router.generate.call_args.kwargs["response_schema"]
        == AssessmentScoreAnswer.model_json_schema()
    )


def test_choice_scoring_sends_its_schema() -> None:
    """The multiple-choice scoring sends the same score schema."""
    engine = make_engine(json.dumps(dict(SCORE_ANSWER, is_correct=True)))

    engine._evaluate_mc(
        choice_question(), Answer(question_id="q-mc", selected_option="A")
    )

    assert (
        engine.llm_router.generate.call_args.kwargs["response_schema"]
        == AssessmentScoreAnswer.model_json_schema()
    )


def test_score_parses_a_strict_answer() -> None:
    """A strict score answer gives the score and the feedback."""
    engine = make_engine("")

    score = engine._parse_score(json.dumps(SCORE_ANSWER), "q-ff")

    assert score.score == 80.0
    assert score.feedback == "Good answer."
    assert score.is_correct is None


def test_score_falls_back_on_a_missing_field() -> None:
    """A score answer without model_answer falls back to the score of 50."""
    engine = make_engine("")
    answer = {k: v for k, v in SCORE_ANSWER.items() if k != "model_answer"}

    score = engine._parse_score(json.dumps(answer), "q-ff")

    assert score.score == 50.0
    assert score.feedback == "Could not parse evaluation response."


def test_score_falls_back_on_text_around_the_json() -> None:
    """Text around the score JSON falls back to the score of 50, with the reason logged."""
    engine = make_engine("")

    score = engine._parse_score("Score: " + json.dumps(SCORE_ANSWER), "q-ff")

    assert score.score == 50.0
    assert "not_json" in logged_errors(engine)


def test_prompt_asks_for_a_questions_object() -> None:
    """The generation prompt asks for an object with one key, questions."""
    path = Path(__file__).resolve().parents[2] / "config" / "prompt_templates.yaml"
    prompts = yaml.safe_load(path.read_text(encoding="utf-8"))["prompts"]
    user = prompts["assessment_generation"]["user"]

    assert 'Return a JSON object with one key, "questions"' in user
    assert "Return a JSON array" not in user


def test_no_json_loads_left() -> None:
    """The engine no longer calls json.loads."""
    text = (
        Path(__file__).resolve().parents[2] / "src" / "assessment" / "engine.py"
    ).read_text(encoding="utf-8")
    assert "json.loads" not in text
