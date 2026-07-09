"""
Job Raider - Cover Letter Validator

This module provides deterministic validation for generated cover letters
to ensure structural quality, content accuracy, and professional tone.

Author: Job Raider
Date: 2026-05-13
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger
from .cover_letter_writer import GeneratedCoverLetter
from .selector import SelectionOutput


class CoverLetterIssue(str, Enum):
    """Types of cover letter validation issues."""

    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    MISSING_COMPANY = "missing_company"
    MISSING_JOB_TITLE = "missing_job_title"
    POOR_STRUCTURE = "poor_structure"
    GENERIC_OPENING = "generic_opening"
    NO_CALL_TO_ACTION = "no_call_to_action"
    FABRICATED_EXPERIENCE = "fabricated_experience"
    MISSING_SELECTED_PROJECT = "missing_selected_project"
    FEW_PARAGRAPHS = "few_paragraphs"


@dataclass
class CoverLetterValidationResult:
    """Result of validating a generated cover letter."""

    is_valid: bool
    score: int  # 0-100
    issues: List[CoverLetterIssue]
    word_count: int
    structure_score: int  # 0-100
    content_score: int  # 0-100
    tone_score: int  # 0-100
    recommendation: str  # "approve", "needs_revision", "reject"
    details: Dict[str, Any]


class CoverLetterValidator:
    """
    Validate generated cover letters for quality and correctness.

    Performs deterministic checks across three dimensions:
    - Structure: paragraphs, opening, closing, length
    - Content: company/job title mention, selected projects, accuracy
    - Tone: professional language, no generic phrases, confidence
    """

    MIN_WORDS = 150
    MAX_WORDS = 400
    IDEAL_MIN = 200
    IDEAL_MAX = 300
    MIN_PARAGRAPHS = 3

    GENERIC_OPENINGS = [
        "i am writing to apply",
        "i am writing in response to",
        "please accept this letter",
        "i would like to express my interest",
        "i am submitting my application",
    ]

    CALL_TO_ACTION_PHRASES = [
        "i would welcome",
        "i look forward to",
        "i would appreciate the opportunity",
        "i am eager to discuss",
        "thank you for considering",
        "thank you for your time",
        "i hope to hear from you",
    ]

    def __init__(
        self,
        llm_router: Optional[LLMRouter] = None,
        strict_mode: bool = True,
    ):
        """
        Initialize the cover letter validator.

        Args:
            llm_router: Optional LLM router for AI-based validation
            strict_mode: Whether to enforce strict validation rules
        """
        self.llm_router = llm_router
        self.strict_mode = strict_mode
        self.logger = get_logger(Components.GENERATION)

    def validate(
        self,
        cover_letter: GeneratedCoverLetter,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
    ) -> CoverLetterValidationResult:
        """
        Validate a generated cover letter.

        Args:
            cover_letter: Generated cover letter to validate
            job: Target job listing
            profile: Original user profile
            selection: Selection output used for generation

        Returns:
            CoverLetterValidationResult with detailed findings
        """
        issues: List[CoverLetterIssue] = []
        content = cover_letter.content
        content_lower = content.lower()

        structure_issues = self._check_structure(content)
        issues.extend(structure_issues)

        content_issues = self._check_content(content_lower, job, selection)
        issues.extend(content_issues)

        tone_issues = self._check_tone(content_lower)
        issues.extend(tone_issues)

        accuracy_issues = self._check_accuracy(content_lower, profile, selection)
        issues.extend(accuracy_issues)

        structure_score = self._calc_structure_score(content, structure_issues)
        content_score = self._calc_content_score(content_issues, accuracy_issues)
        tone_score = self._calc_tone_score(tone_issues)

        overall_score = int(
            (structure_score * 0.3) + (content_score * 0.4) + (tone_score * 0.3)
        )

        if overall_score >= 80:
            recommendation = "approve"
        elif overall_score >= 60:
            recommendation = "needs_revision"
        else:
            recommendation = "reject"

        is_valid = recommendation == "approve" or (
            not self.strict_mode and recommendation == "needs_revision"
        )

        details = {
            "word_count": cover_letter.word_count,
            "paragraph_count": self._count_paragraphs(content),
            "has_generic_opening": any(
                phrase in content_lower for phrase in self.GENERIC_OPENINGS
            ),
            "has_call_to_action": any(
                phrase in content_lower for phrase in self.CALL_TO_ACTION_PHRASES
            ),
            "company_mentioned": job.company.lower() in content_lower,
            "job_title_mentioned": job.title.lower() in content_lower,
            "referenced_projects": [
                p["name"]
                for p in selection.selected_projects
                if p["name"].lower() in content_lower
            ],
        }

        return CoverLetterValidationResult(
            is_valid=is_valid,
            score=overall_score,
            issues=issues,
            word_count=cover_letter.word_count,
            structure_score=structure_score,
            content_score=content_score,
            tone_score=tone_score,
            recommendation=recommendation,
            details=details,
        )

    def _check_structure(self, content: str) -> List[CoverLetterIssue]:
        """
        Check structural quality of the cover letter.

        Args:
            content: Cover letter text

        Returns:
            List of structural issues found
        """
        issues = []
        word_count = len(content.split())
        paragraph_count = self._count_paragraphs(content)

        if word_count < self.MIN_WORDS:
            issues.append(CoverLetterIssue.TOO_SHORT)
        elif word_count > self.MAX_WORDS:
            issues.append(CoverLetterIssue.TOO_LONG)

        if paragraph_count < self.MIN_PARAGRAPHS:
            issues.append(CoverLetterIssue.FEW_PARAGRAPHS)

        if "\n\n" not in content and "\n" not in content:
            issues.append(CoverLetterIssue.POOR_STRUCTURE)

        return issues

    def _check_content(
        self,
        content_lower: str,
        job: JobListing,
        selection: SelectionOutput,
    ) -> List[CoverLetterIssue]:
        """
        Check content completeness and relevance.

        Args:
            content_lower: Lowercase cover letter text
            job: Target job listing
            selection: Selection output

        Returns:
            List of content issues found
        """
        issues = []

        if job.company.lower() not in content_lower:
            issues.append(CoverLetterIssue.MISSING_COMPANY)

        if job.title.lower() not in content_lower:
            issues.append(CoverLetterIssue.MISSING_JOB_TITLE)

        if selection.selected_projects:
            any_project_mentioned = any(
                proj["name"].lower() in content_lower
                for proj in selection.selected_projects
            )
            if not any_project_mentioned:
                issues.append(CoverLetterIssue.MISSING_SELECTED_PROJECT)

        return issues

    def _check_tone(self, content_lower: str) -> List[CoverLetterIssue]:
        """
        Check tone and professionalism.

        Args:
            content_lower: Lowercase cover letter text

        Returns:
            List of tone issues found
        """
        issues = []

        if any(phrase in content_lower[:100] for phrase in self.GENERIC_OPENINGS):
            issues.append(CoverLetterIssue.GENERIC_OPENING)

        closing = content_lower[-200:] if len(content_lower) > 200 else content_lower
        if not any(phrase in closing for phrase in self.CALL_TO_ACTION_PHRASES):
            issues.append(CoverLetterIssue.NO_CALL_TO_ACTION)

        return issues

    def _check_accuracy(
        self,
        content_lower: str,
        profile: UserProfile,
        selection: SelectionOutput,
    ) -> List[CoverLetterIssue]:
        """
        Check factual accuracy against the user profile.

        Args:
            content_lower: Lowercase cover letter text
            profile: Original user profile
            selection: Selection output

        Returns:
            List of accuracy issues found
        """
        issues = []
        profile_project_names = {p.name.lower() for p in profile.projects}

        for proj in selection.selected_projects:
            name = proj["name"].lower()
            if name in content_lower and name not in profile_project_names:
                issues.append(CoverLetterIssue.FABRICATED_EXPERIENCE)
                self.logger.warning(
                    "Cover letter references project not in profile: %s",
                    proj["name"],
                )

        return issues

    def _count_paragraphs(self, content: str) -> int:
        """
        Count the number of paragraphs in the text.

        Args:
            content: Text to count paragraphs in

        Returns:
            Number of paragraphs
        """
        if not content.strip():
            return 0
        paragraphs = [p for p in content.split("\n\n") if p.strip()]
        return len(paragraphs)

    def _calc_structure_score(
        self, content: str, issues: List[CoverLetterIssue]
    ) -> int:
        """
        Calculate structure quality score.

        Args:
            content: Cover letter text
            issues: Structural issues found

        Returns:
            Score from 0-100
        """
        score = 100
        word_count = len(content.split())
        paragraphs = self._count_paragraphs(content)

        if CoverLetterIssue.TOO_SHORT in issues:
            score -= 20
        if CoverLetterIssue.TOO_LONG in issues:
            score -= 10
        if CoverLetterIssue.FEW_PARAGRAPHS in issues:
            score -= 15
        if CoverLetterIssue.POOR_STRUCTURE in issues:
            score -= 20

        if self.IDEAL_MIN <= word_count <= self.IDEAL_MAX:
            score = min(100, score + 5)

        if 3 <= paragraphs <= 5:
            score = min(100, score + 5)

        return max(0, score)

    def _calc_content_score(
        self,
        content_issues: List[CoverLetterIssue],
        accuracy_issues: List[CoverLetterIssue],
    ) -> int:
        """
        Calculate content quality score.

        Args:
            content_issues: Content completeness issues
            accuracy_issues: Factual accuracy issues

        Returns:
            Score from 0-100
        """
        score = 100

        if CoverLetterIssue.MISSING_COMPANY in content_issues:
            score -= 25
        if CoverLetterIssue.MISSING_JOB_TITLE in content_issues:
            score -= 20
        if CoverLetterIssue.MISSING_SELECTED_PROJECT in content_issues:
            score -= 15
        if CoverLetterIssue.FABRICATED_EXPERIENCE in accuracy_issues:
            score -= 30

        return max(0, score)

    def _calc_tone_score(self, issues: List[CoverLetterIssue]) -> int:
        """
        Calculate tone quality score.

        Args:
            issues: Tone issues found

        Returns:
            Score from 0-100
        """
        score = 100

        if CoverLetterIssue.GENERIC_OPENING in issues:
            score -= 20
        if CoverLetterIssue.NO_CALL_TO_ACTION in issues:
            score -= 15

        return max(0, score)

    def validate_with_llm(
        self,
        cover_letter: GeneratedCoverLetter,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
    ) -> CoverLetterValidationResult:
        """
        Validate using LLM for nuanced quality assessment.

        Falls back to deterministic validation when LLM is unavailable.

        Args:
            cover_letter: Generated cover letter to validate
            job: Target job listing
            profile: Original user profile
            selection: Selection output

        Returns:
            CoverLetterValidationResult with detailed findings
        """
        if not self.llm_router:
            return self.validate(cover_letter, job, profile, selection)

        messages = [
            Message(
                role=MessageType.SYSTEM,
                content=(
                    "You are a cover letter quality analyst. Evaluate the "
                    "cover letter for structure, content, tone, and accuracy."
                ),
            ),
            Message(
                role=MessageType.USER,
                content=(
                    f"Evaluate this cover letter for the {job.title} "
                    f"position at {job.company}:\n\n"
                    f"COVER LETTER:\n{cover_letter.content}\n\n"
                    f"CANDIDATE PROJECTS: "
                    f"{', '.join(p['name'] for p in selection.selected_projects)}\n"
                    f"KEYWORDS: {', '.join(selection.keywords_to_emphasize)}\n\n"
                    f"Rate each dimension 0-100 and return JSON:\n"
                    f'{{"structure_score": 0-100, "content_score": 0-100, '
                    f'"tone_score": 0-100, "overall_score": 0-100, '
                    f'"is_valid": true/false, '
                    f'"recommendation": "approve/needs_revision/reject", '
                    f'"issues": ["issue1", "issue2"]}}'
                ),
            ),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.VALIDATION,
                temperature=0.3,
                max_tokens=400,
            )

            import json

            json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
            if not json_match:
                raise ValueError("Failed to extract JSON from validation response")

            data = json.loads(json_match.group(0))
            overall = data.get("overall_score", 0)

            return CoverLetterValidationResult(
                is_valid=data.get("is_valid", False),
                score=overall,
                issues=[],
                word_count=cover_letter.word_count,
                structure_score=data.get("structure_score", 0),
                content_score=data.get("content_score", 0),
                tone_score=data.get("tone_score", 0),
                recommendation=data.get("recommendation", "needs_revision"),
                details={"llm_feedback": data.get("issues", [])},
            )

        except Exception as e:
            self.logger.error("LLM validation failed: %s", str(e))
            return self.validate(cover_letter, job, profile, selection)
