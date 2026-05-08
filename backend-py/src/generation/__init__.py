"""
Job Raider - Generation Module

This module provides resume generation functionality using a two-model approach:
- Small model (qwen2.5:3b) for selection
- Large model (qwen2.5:7b) for resume writing

Author: Job Raider
Date: 2026-04-20
"""

from .selector import (
    ResumeSelector,
    ProjectSelector,
    SelectionOutput,
)

from .resume_writer import (
    ResumeWriter,
    GeneratedResume,
    ResumeSection,
)

from .formatter import (
    ResumeFormatter,
    FormattedResume,
    TemplateManager,
)

from .validator import (
    ResumeValidator,
    ValidationResult,
    ValidationIssue,
)

from .resume_analyzer import (
    ResumeAnalyzer,
)

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
]
