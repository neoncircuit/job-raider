"""
Tests for the trust analysis and the form-answer calls (Step 3.7, MH-12).

Both calls send a system and a user message, the task type, a low
temperature, and the output model's JSON schema, and parse the whole
answer with ``parse_structured``. A parse failure gives ``None`` and a
warning with the reason.

Author: Job Raider
Date: 2026-11-02
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from src.linkedin.answer_engine import QuestionAnswerEngine
from src.linkedin.form_models import AnswerConfidence, FormQuestion, QuestionType
from src.llm.base import LLMResponse, Message, MessageType
from src.llm.router import TaskType
from src.llm.structured import FormQuestionAnswer, TrustAnalysisAnswer
from src.scoring.trust_analyzer import TrustAnalyzer

TRUST_ANSWER = {
    "summary": "Looks legitimate.",
    "additional_indicators": ["Asks for a fee"],
    "confidence_adjustment": 0.2,
}
FORM_ANSWER = {
    "answer": "Yes",
    "confidence": "high",
    "reasoning": "The profile says the candidate can relocate.",
}
QUESTION = FormQuestion(
    question_text="Are you willing to relocate?",
    question_type=QuestionType.RADIO,
    options=["Yes", "No"],
)


def router_returning(content: str) -> MagicMock:
    """
    Build a fake LLM router that returns one fixed answer.

    Args:
        content: The text that ``generate`` returns.

    Returns:
        A MagicMock router whose ``generate`` returns an ``LLMResponse``.
    """
    router = MagicMock()
    router.generate.return_value = LLMResponse(
        content=content, model="qwen2.5:7b", provider="ollama"
    )
    return router


def logged_warnings(component: Any) -> str:
    """
    Join the text of all warnings that a component logged.

    Args:
        component: A component whose ``logger`` is a MagicMock.

    Returns:
        All warning messages as one string.
    """
    return " ".join(str(c.args[0]) for c in component.logger.warning.call_args_list)


def test_trust_analysis_sends_messages_and_its_schema(sample_job_listing) -> None:
    """
    Check the messages, the task type, and the schema of the trust call.

    Args:
        sample_job_listing: A sample job listing fixture.
    """
    router = router_returning(json.dumps(TRUST_ANSWER))
    TrustAnalyzer(llm_router=router).analyze(sample_job_listing, deep=True)

    call = router.generate.call_args
    roles = [m.role for m in call.args[0]]
    assert roles == [MessageType.SYSTEM, MessageType.USER]
    assert call.kwargs["task_type"] == TaskType.TRUST_ANALYSIS
    assert call.kwargs["response_schema"] == TrustAnalysisAnswer.model_json_schema()


def test_trust_analysis_uses_a_strict_answer(sample_job_listing) -> None:
    """
    Check that a valid trust answer fills the result fields.

    Args:
        sample_job_listing: A sample job listing fixture.
    """
    router = router_returning(json.dumps(TRUST_ANSWER))
    result = TrustAnalyzer(llm_router=router).analyze(sample_job_listing, deep=True)

    assert result.llm_summary == "Looks legitimate."
    assert result.llm_indicators == ["Asks for a fee"]
    assert result.llm_confidence_adjustment == 0.2


def test_trust_adjustment_changes_the_confidence(sample_job_listing) -> None:
    """
    Check that the LLM adjustment moves the rule-based confidence.

    Args:
        sample_job_listing: A sample job listing fixture.
    """
    router = router_returning(json.dumps(TRUST_ANSWER))
    base = TrustAnalyzer().analyze(sample_job_listing).confidence
    result = TrustAnalyzer(llm_router=router).analyze(sample_job_listing, deep=True)

    assert result.confidence == round(min(1.0, base + 0.2), 3)


def test_trust_analysis_drops_text_around_the_json(sample_job_listing) -> None:
    """
    Check that text around the trust JSON gives no summary and a reason.

    Args:
        sample_job_listing: A sample job listing fixture.
    """
    router = router_returning("Analysis: " + json.dumps(TRUST_ANSWER))
    analyzer = TrustAnalyzer(llm_router=router)
    analyzer.logger = MagicMock()
    result = analyzer.analyze(sample_job_listing, deep=True)

    assert result.llm_summary is None
    assert "not_json" in logged_warnings(analyzer)


def test_trust_analysis_drops_an_adjustment_out_of_range(sample_job_listing) -> None:
    """
    Check that an out-of-range trust adjustment gives no summary and a reason.

    Args:
        sample_job_listing: A sample job listing fixture.
    """
    out_of_range = dict(TRUST_ANSWER, confidence_adjustment=0.5)
    router = router_returning(json.dumps(out_of_range))
    analyzer = TrustAnalyzer(llm_router=router)
    analyzer.logger = MagicMock()
    result = analyzer.analyze(sample_job_listing, deep=True)

    assert result.llm_summary is None
    assert "schema" in logged_warnings(analyzer)


def test_form_answer_sends_messages_and_its_schema(sample_user_profile) -> None:
    """
    Check the messages, the task type, and the schema of the form call.

    Args:
        sample_user_profile: A sample user profile fixture.
    """
    router = router_returning(json.dumps(FORM_ANSWER))
    QuestionAnswerEngine(user_profile=sample_user_profile, llm_router=router)._try_llm(
        QUESTION
    )

    call = router.generate.call_args
    messages: list[Message] = call.args[0]
    assert [m.role for m in messages] == [MessageType.SYSTEM, MessageType.USER]
    assert "NEEDS_MANUAL_REVIEW" in messages[0].content
    assert call.kwargs["task_type"] == TaskType.QUESTION_ANSWERING
    assert call.kwargs["response_schema"] == FormQuestionAnswer.model_json_schema()


def test_form_answer_uses_a_strict_answer(sample_user_profile) -> None:
    """
    Check that a valid form answer fills the question answer.

    Args:
        sample_user_profile: A sample user profile fixture.
    """
    router = router_returning(json.dumps(FORM_ANSWER))
    answer = QuestionAnswerEngine(
        user_profile=sample_user_profile, llm_router=router
    )._try_llm(QUESTION)

    assert answer is not None
    assert answer.answer_value == "Yes"
    assert answer.confidence == AnswerConfidence.HIGH
    assert answer.needs_review is False
    assert answer.reasoning == FORM_ANSWER["reasoning"]


def test_form_answer_marks_manual_review(sample_user_profile) -> None:
    """
    Check that a NEEDS_MANUAL_REVIEW answer asks for a manual review.

    Args:
        sample_user_profile: A sample user profile fixture.
    """
    manual = dict(FORM_ANSWER, answer="NEEDS_MANUAL_REVIEW", confidence="low")
    router = router_returning(json.dumps(manual))
    answer = QuestionAnswerEngine(
        user_profile=sample_user_profile, llm_router=router
    )._try_llm(QUESTION)

    assert answer is not None
    assert answer.needs_review is True
    assert answer.answer_value == ""


def test_form_answer_drops_text_around_the_json(sample_user_profile) -> None:
    """
    Check that text around the form JSON gives no answer and a reason.

    Args:
        sample_user_profile: A sample user profile fixture.
    """
    router = router_returning("Answer: " + json.dumps(FORM_ANSWER))
    engine = QuestionAnswerEngine(user_profile=sample_user_profile, llm_router=router)
    engine.logger = MagicMock()

    assert engine._try_llm(QUESTION) is None
    assert "not_json" in logged_warnings(engine)


def test_form_answer_drops_an_unknown_confidence(sample_user_profile) -> None:
    """
    Check that an unknown form confidence gives no answer and a reason.

    Args:
        sample_user_profile: A sample user profile fixture.
    """
    certain = dict(FORM_ANSWER, confidence="certain")
    router = router_returning(json.dumps(certain))
    engine = QuestionAnswerEngine(user_profile=sample_user_profile, llm_router=router)
    engine.logger = MagicMock()

    assert engine._try_llm(QUESTION) is None
    assert "schema" in logged_warnings(engine)


def test_no_brace_search_left() -> None:
    """Check that the two call sites no longer cut the answer by brace position."""
    root = Path(__file__).resolve().parents[2]
    sources = (root / "src/scoring/trust_analyzer.py").read_text(encoding="utf-8")
    sources += (root / "src/linkedin/answer_engine.py").read_text(encoding="utf-8")

    assert 'index("{")' not in sources
    assert 'rfind("}")' not in sources
