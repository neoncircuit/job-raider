"""
Job Raider - Generation Module

This module provides resume generation functionality using a two-model approach:
- Small model (qwen2.5:3b) for selection
- Large model (qwen2.5:7b) for resume writing

Author: Job Raider
Date: 2026-04-20
"""

from .cover_letter_validator import (
    CoverLetterIssue,
    CoverLetterValidationResult,
    CoverLetterValidator,
)
from .cover_letter_writer import CoverLetterWriter, GeneratedCoverLetter
from .formatter import FormattedResume, ResumeFormatter, TemplateManager
from .resume_analyzer import ResumeAnalyzer
from .resume_writer import GeneratedResume, ResumeSection, ResumeWriter
from .selector import ProjectSelector, ResumeSelector, SelectionOutput
from .validator import ResumeValidator, ValidationIssue, ValidationResult

__all__ = [
    # Selector
    "ResumeSelector",
    "ProjectSelector",
    "SelectionOutput",
    # Writer
    "ResumeWriter",
    "GeneratedResume",
    "ResumeSection",
    # Formatter
    "ResumeFormatter",
    "FormattedResume",
    "TemplateManager",
    # Validator
    "ResumeValidator",
    "ValidationResult",
    "ValidationIssue",
    # Analyzer
    "ResumeAnalyzer",
    # Cover Letter
    "CoverLetterWriter",
    "GeneratedCoverLetter",
    # Cover Letter Validation
    "CoverLetterValidator",
    "CoverLetterValidationResult",
    "CoverLetterIssue",
]
