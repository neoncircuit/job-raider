"""
Job Raider - LinkedIn Integration Package

Provides authenticated session management, form parsing, question answering,
and automated form filling for LinkedIn Easy Apply.
"""

from .answer_engine import AnswerBank, QuestionAnswerEngine
from .applied_scraper import LinkedInAppliedScraper
from .form_filler import EasyApplyFormFiller, FormFillResult
from .form_models import (
    AnswerConfidence,
    FormQuestion,
    FormStep,
    ParsedForm,
    QuestionAnswer,
    QuestionType,
)
from .form_parser import EasyApplyFormParser
from .safety import SafetyConfig, SafetyController
from .session import LinkedInSession, LinkedInSessionConfig

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
