"""
Job Raider - LinkedIn Form Models

Pydantic models for representing LinkedIn Easy Apply form questions,
parsed forms, and generated answers.

Author: Job Raider
Date: 2026-05-04
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """Types of form question inputs found in LinkedIn Easy Apply."""

    TEXT = "text"
    DROPDOWN = "dropdown"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    DATE = "date"
    FILE_UPLOAD = "file_upload"
    MULTI_SELECT = "multi_select"
    NUMERIC = "numeric"


class FormQuestion(BaseModel):
    """A single question from a LinkedIn Easy Apply form."""

    question_text: str = Field(description="The label or text of the question")
    question_type: QuestionType = Field(description="Type of form input")
    is_required: bool = Field(default=True, description="Whether the field is required")
    options: List[str] = Field(
        default_factory=list,
        description="Available options for dropdown/radio/checkbox questions",
    )
    current_value: Optional[str] = Field(
        default=None,
        description="Pre-filled value if any",
    )
    field_selector: Optional[str] = Field(
        default=None,
        description="CSS selector for Playwright interaction",
    )
    placeholder: Optional[str] = Field(
        default=None,
        description="Placeholder text for the input field",
    )


class FormStep(BaseModel):
    """A single step/page within a multi-step Easy Apply form."""

    step_number: int = Field(description="Step index (1-based)")
    questions: List[FormQuestion] = Field(
        default_factory=list,
        description="Questions on this step",
    )
    has_next: bool = Field(default=True, description="Whether a Next button exists")
    has_review: bool = Field(
        default=False,
        description="Whether this is the review step",
    )


class ParsedForm(BaseModel):
    """Complete parsed LinkedIn Easy Apply form."""

    job_id: str = Field(description="LinkedIn job ID")
    job_title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    steps: List[FormStep] = Field(
        default_factory=list,
        description="All form steps",
    )
    total_steps: int = Field(default=0, description="Total number of steps")
    requires_resume: bool = Field(
        default=False,
        description="Whether resume upload is required",
    )
    requires_cover_letter: bool = Field(
        default=False,
        description="Whether cover letter is required",
    )


class AnswerConfidence(str, Enum):
    """Confidence level for a generated answer."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class QuestionAnswer(BaseModel):
    """An answer generated for a form question."""

    question: FormQuestion = Field(description="The question being answered")
    answer_value: str = Field(description="The generated answer string")
    confidence: AnswerConfidence = Field(
        default=AnswerConfidence.UNKNOWN,
        description="Confidence in the answer",
    )
    source: str = Field(
        description="Where the answer came from (rule_*, llm, profile, cached)",
    )
    needs_review: bool = Field(
        default=False,
        description="Whether this answer needs manual review",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Why this answer was chosen",
    )


class FormFillResult(BaseModel):
    """Result of a form fill and submission attempt."""

    job_id: str = Field(description="LinkedIn job ID")
    job_title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    success: bool = Field(description="Whether the application was submitted")
    steps_completed: int = Field(default=0, description="Number of steps completed")
    questions_answered: int = Field(
        default=0,
        description="Number of questions answered",
    )
    questions_skipped: int = Field(
        default=0,
        description="Number of questions skipped (optional/unknown)",
    )
    low_confidence_answers: List[QuestionAnswer] = Field(
        default_factory=list,
        description="Answers with low confidence that may need review",
    )
    screenshot_paths: List[str] = Field(
        default_factory=list,
        description="Paths to screenshots taken",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if submission failed",
    )
    submission_timestamp: Optional[datetime] = Field(
        default=None,
        description="When the application was submitted",
    )
