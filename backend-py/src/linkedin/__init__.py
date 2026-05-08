"""
Job Raider - LinkedIn Integration Package

Provides authenticated session management, form parsing, question answering,
and automated form filling for LinkedIn Easy Apply.
"""

from .session import LinkedInSession, LinkedInSessionConfig
from .applied_scraper import LinkedInAppliedScraper
from .form_models import (
    QuestionType,
    FormQuestion,
    FormStep,
    ParsedForm,
    AnswerConfidence,
    QuestionAnswer,
)
from .form_parser import EasyApplyFormParser
from .answer_engine import QuestionAnswerEngine, AnswerBank
from .form_filler import EasyApplyFormFiller, FormFillResult
from .safety import SafetyController, SafetyConfig

__all__ = [
    "LinkedInSession",
    "LinkedInSessionConfig",
    "LinkedInAppliedScraper",
    "QuestionType",
    "FormQuestion",
    "FormStep",
    "ParsedForm",
    "AnswerConfidence",
    "QuestionAnswer",
    "EasyApplyFormParser",
    "QuestionAnswerEngine",
    "AnswerBank",
    "EasyApplyFormFiller",
    "FormFillResult",
    "SafetyController",
    "SafetyConfig",
]
