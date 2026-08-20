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
from .cover_letter_grounding import (
    calc_grounding_penalty,
    collect_resume_bullets,
    flag_analogical_claims,
    flag_claim_overclaims,
    flag_fabricated_technologies,
    flag_inconsistent_percent_claims,
    flag_inflated_duration_claims,
    flag_ungrounded_sentences,
)
from .cover_letter_instructions import (
    DetectedInstructions,
    count_length_units,
    inclusion_present_in_text,
    length_within_spec,
)
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
    LOW_JD_COVERAGE = "low_jd_coverage"
    UNGROUNDED_CLAIMS = "ungrounded_claims"
    SCOPE_INFLATION = "scope_inflation"
    TECHNIQUE_MISMATCH = "technique_mismatch"
    FABRICATED_TECHNOLOGY = "fabricated_technology"
    INFLATED_DURATION = "inflated_duration"
    INCONSISTENT_METRIC = "inconsistent_metric"
    ANALOGICAL_CLAIM = "analogical_claim"
    INSTRUCTION_LENGTH_MISMATCH = "instruction_length_mismatch"
    MISSING_REQUIRED_INCLUSION = "missing_required_inclusion"


HARD_FAIL_ISSUES: frozenset[CoverLetterIssue] = frozenset(
    {
        CoverLetterIssue.FABRICATED_TECHNOLOGY,
        CoverLetterIssue.INFLATED_DURATION,
        CoverLetterIssue.INCONSISTENT_METRIC,
        CoverLetterIssue.FABRICATED_EXPERIENCE,
        CoverLetterIssue.ANALOGICAL_CLAIM,
    }
)


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


def collect_hard_fail_issues(
    issues: List[CoverLetterIssue],
) -> List[CoverLetterIssue]:
    """
    Return grounding issues that must reject the letter.

    Soft ungrounded wording and structure/tone findings do not hard-fail.

    Args:
        issues: Validation issues from a cover-letter check.

    Returns:
        Hard-fail issues in the original order, de-duplicated.
    """
    seen: set[CoverLetterIssue] = set()
    hard: List[CoverLetterIssue] = []
    for issue in issues:
        if issue in HARD_FAIL_ISSUES and issue not in seen:
            seen.add(issue)
            hard.append(issue)
    return hard


def build_grounding_rewrite_critique(
    validation: CoverLetterValidationResult,
) -> str:
    """
    Build a writer critique from deterministic hard-fail findings.

    Names the unsupported claims so the rewrite can delete them. Do not use
    this text on the first-write prompt (that would teach the missing stack).

    Args:
        validation: Result of the first deterministic proofread.

    Returns:
        Plain-text editor critique for ``CoverLetterWriter.rewrite``.
    """
    lines = [
        "Deterministic proofread found resume-unsupported claims.",
        "Rewrite the letter. Delete the flagged claims.",
        "Do not name tools that are not on the candidate profile.",
        "Do not apologize for skill gaps. Do not invent replacement metrics.",
        "Do not analogize resume work to job duties that are not on the resume.",
    ]
    details = validation.details or {}
    fabricated = details.get("fabricated_technologies") or []
    if fabricated:
        lines.append(
            "Remove these technologies: " + ", ".join(str(item) for item in fabricated)
        )
    for item in details.get("inflated_duration_claims") or []:
        flags = item.get("flags") if isinstance(item, dict) else None
        if flags:
            lines.append("Duration: " + "; ".join(str(flag) for flag in flags))
    for item in details.get("inconsistent_percent_claims") or []:
        flags = item.get("flags") if isinstance(item, dict) else None
        if flags:
            lines.append("Metric: " + "; ".join(str(flag) for flag in flags))
    for item in details.get("claim_overclaims") or []:
        flags = item.get("flags") if isinstance(item, dict) else None
        sentence = item.get("sentence") if isinstance(item, dict) else None
        if flags:
            prefix = f"{sentence} — " if sentence else ""
            lines.append(prefix + "; ".join(str(flag) for flag in flags))
    for item in details.get("analogical_claims") or []:
        flags = item.get("flags") if isinstance(item, dict) else None
        sentence = item.get("sentence") if isinstance(item, dict) else None
        if flags:
            prefix = f"{sentence} — " if sentence else ""
            lines.append(prefix + "; ".join(str(flag) for flag in flags))
    return "\n".join(lines)


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
        style: str = "modern",
        *,
        short_answer_mode: bool = False,
        detected_instructions: Optional[DetectedInstructions] = None,
        inclusion_urls: Optional[Dict[str, Optional[str]]] = None,
    ) -> CoverLetterValidationResult:
        """
        Validate a generated cover letter.

        Args:
            cover_letter: Generated cover letter to validate
            job: Target job listing
            profile: Original user profile
            selection: Selection output used for generation
            style: ``modern`` or ``classic`` (classic softens generic-opening checks)
            short_answer_mode: When True, relax full-letter structure checks
            detected_instructions: Phase C detected JD instructions
            inclusion_urls: kind→URL map for inclusion checks

        Returns:
            CoverLetterValidationResult with detailed findings
        """
        issues: List[CoverLetterIssue] = []
        content = cover_letter.content
        content_lower = content.lower()
        letter_style = style if style in ("modern", "classic") else "modern"
        instructions = detected_instructions or DetectedInstructions()
        urls = inclusion_urls or {}

        if short_answer_mode:
            structure_issues: List[CoverLetterIssue] = []
        else:
            structure_issues = self._check_structure(content)
            issues.extend(structure_issues)

        content_issues = self._check_content(
            content_lower,
            job,
            selection,
            short_answer_mode=short_answer_mode,
        )
        issues.extend(content_issues)

        if short_answer_mode:
            tone_issues: List[CoverLetterIssue] = []
        else:
            tone_issues = self._check_tone(content_lower, style=letter_style)
            issues.extend(tone_issues)

        accuracy_issues = self._check_accuracy(content_lower, profile, selection)
        issues.extend(accuracy_issues)

        if short_answer_mode:
            jd_issues: List[CoverLetterIssue] = []
            jd_coverage: Dict[str, Any] = {
                "skipped": True,
                "reason": "short_answer_mode",
            }
        else:
            jd_issues, jd_coverage = self._check_jd_coverage(
                content_lower, job, profile
            )
            issues.extend(jd_issues)

        grounding_terms: List[str] = []
        if job.title:
            grounding_terms.append(job.title)
        if job.company:
            grounding_terms.append(job.company)

        resume_bullets = collect_resume_bullets(profile, selection)
        ungrounded_sentences = flag_ungrounded_sentences(
            content,
            resume_bullets,
            jd_terms=grounding_terms,
        )
        claim_overclaims = flag_claim_overclaims(
            content,
            profile,
            resume_bullets=resume_bullets,
        )
        analogical_claims = flag_analogical_claims(
            content,
            profile,
            job,
        )
        fabricated_technologies = flag_fabricated_technologies(content, profile)
        inflated_duration_claims = flag_inflated_duration_claims(content, profile)
        inconsistent_percent_claims = flag_inconsistent_percent_claims(content)
        grounding_issues: List[CoverLetterIssue] = []
        if ungrounded_sentences:
            grounding_issues.append(CoverLetterIssue.UNGROUNDED_CLAIMS)
        if any(
            any(flag.lower().startswith("scope inflation") for flag in item["flags"])
            for item in claim_overclaims
        ):
            grounding_issues.append(CoverLetterIssue.SCOPE_INFLATION)
        if any(
            any(flag.lower().startswith("technique mismatch") for flag in item["flags"])
            for item in claim_overclaims
        ):
            grounding_issues.append(CoverLetterIssue.TECHNIQUE_MISMATCH)
        if analogical_claims:
            grounding_issues.append(CoverLetterIssue.ANALOGICAL_CLAIM)
        if fabricated_technologies:
            grounding_issues.append(CoverLetterIssue.FABRICATED_TECHNOLOGY)
        if inflated_duration_claims:
            grounding_issues.append(CoverLetterIssue.INFLATED_DURATION)
        if inconsistent_percent_claims:
            grounding_issues.append(CoverLetterIssue.INCONSISTENT_METRIC)
        issues.extend(grounding_issues)

        instruction_issues, instructions_context = self._check_instructions(
            content,
            instructions=instructions,
            inclusion_urls=urls,
            short_answer_mode=short_answer_mode,
        )
        issues.extend(instruction_issues)

        grounding_penalty, grounding_penalty_breakdown = calc_grounding_penalty(
            ungrounded_sentences,
            claim_overclaims,
            fabricated_technologies=fabricated_technologies,
            inflated_duration_claims=inflated_duration_claims,
            inconsistent_percent_claims=inconsistent_percent_claims,
            analogical_claims=analogical_claims,
        )

        if short_answer_mode:
            structure_score = 100
            tone_score = 100
        else:
            structure_score = self._calc_structure_score(content, structure_issues)
            tone_score = self._calc_tone_score(tone_issues)

        content_score = self._calc_content_score(
            content_issues + jd_issues + instruction_issues,
            accuracy_issues,
            grounding_penalty=grounding_penalty,
        )

        overall_score = int(
            (structure_score * 0.3) + (content_score * 0.4) + (tone_score * 0.3)
        )

        if overall_score >= 80:
            recommendation = "approve"
        elif overall_score >= 60:
            recommendation = "needs_revision"
        else:
            recommendation = "reject"

        hard_fail = collect_hard_fail_issues(issues)
        if hard_fail:
            recommendation = "reject"
            is_valid = False
        else:
            is_valid = recommendation == "approve" or (
                not self.strict_mode and recommendation == "needs_revision"
            )

        details = {
            "word_count": cover_letter.word_count,
            "paragraph_count": self._count_paragraphs(content),
            "style": letter_style,
            "short_answer_mode": short_answer_mode,
            "has_generic_opening": (
                False
                if letter_style == "classic" or short_answer_mode
                else any(phrase in content_lower for phrase in self.GENERIC_OPENINGS)
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
            "jd_coverage": jd_coverage,
            "ungrounded_sentences": ungrounded_sentences,
            "claim_overclaims": claim_overclaims,
            "fabricated_technologies": fabricated_technologies,
            "inflated_duration_claims": inflated_duration_claims,
            "inconsistent_percent_claims": inconsistent_percent_claims,
            "analogical_claims": analogical_claims,
            "grounding_penalty": grounding_penalty_breakdown,
            "instructions_context": instructions_context,
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
        *,
        short_answer_mode: bool = False,
    ) -> List[CoverLetterIssue]:
        """
        Check content completeness and relevance.

        Args:
            content_lower: Lowercase cover letter text
            job: Target job listing
            selection: Selection output
            short_answer_mode: When True, skip project-mention requirements

        Returns:
            List of content issues found
        """
        issues = []

        if job.company.lower() not in content_lower:
            issues.append(CoverLetterIssue.MISSING_COMPANY)

        if not short_answer_mode and job.title.lower() not in content_lower:
            issues.append(CoverLetterIssue.MISSING_JOB_TITLE)

        if short_answer_mode:
            return issues

        if selection.selected_projects:
            any_project_mentioned = any(
                proj["name"].lower() in content_lower
                for proj in selection.selected_projects
            )
            if not any_project_mentioned:
                issues.append(CoverLetterIssue.MISSING_SELECTED_PROJECT)

        return issues

    def _check_instructions(
        self,
        content: str,
        *,
        instructions: DetectedInstructions,
        inclusion_urls: Dict[str, Optional[str]],
        short_answer_mode: bool,
    ) -> tuple[List[CoverLetterIssue], Dict[str, Any]]:
        """
        Check Phase C length and inclusion adherence.

        Soft issues only (score penalty); not hard-fail rewrite triggers.

        Args:
            content: Generated letter / short-answer text.
            instructions: Detected JD instructions.
            inclusion_urls: kind→URL map (URL may be None if missing on profile).
            short_answer_mode: Whether output is the why-interest replace path.

        Returns:
            Tuple of (issues, instructions_context dict).
        """
        issues: List[CoverLetterIssue] = []
        context: Dict[str, Any] = {
            "detected": instructions.to_dict(),
            "short_answer_mode": short_answer_mode,
            "length_ok": None,
            "length_count": None,
            "inclusion_checks": [],
        }

        if instructions.why_interest is not None and short_answer_mode:
            spec = instructions.why_interest
            count = count_length_units(content, spec.unit)
            ok = length_within_spec(content, spec)
            context["length_ok"] = ok
            context["length_count"] = count
            context["length_unit"] = spec.unit
            context["length_range"] = [spec.min_n, spec.max_n]
            if not ok:
                issues.append(CoverLetterIssue.INSTRUCTION_LENGTH_MISMATCH)

        for kind, url in inclusion_urls.items():
            entry: Dict[str, Any] = {
                "kind": kind,
                "url": url,
                "present": None,
                "available_on_profile": bool(url),
            }
            if not url:
                # JD asked but profile has no URL — do not invent; soft flag.
                issues.append(CoverLetterIssue.MISSING_REQUIRED_INCLUSION)
                entry["present"] = False
            else:
                present = inclusion_present_in_text(content, url)
                entry["present"] = present
                if not present:
                    issues.append(CoverLetterIssue.MISSING_REQUIRED_INCLUSION)
            context["inclusion_checks"].append(entry)

        return issues, context

    def _check_tone(
        self, content_lower: str, style: str = "modern"
    ) -> List[CoverLetterIssue]:
        """
        Check tone and professionalism.

        Args:
            content_lower: Lowercase cover letter text
            style: ``modern`` or ``classic``. Classic skips GENERIC_OPENING
                penalties for traditional apply openers.

        Returns:
            List of tone issues found
        """
        issues = []

        if style != "classic" and any(
            phrase in content_lower[:100] for phrase in self.GENERIC_OPENINGS
        ):
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

    def _check_jd_coverage(
        self,
        content_lower: str,
        job: JobListing,
        profile: UserProfile,
    ) -> tuple[List[CoverLetterIssue], Dict[str, Any]]:
        """
        Cross-check the letter against the job description's must-haves.

        Two sources of "terms the letter should address", in priority order:

        1. Structured: required skills parsed on the job listing
           (scraped jobs from JSearch/LinkedIn).
        2. Profile-match fallback: for manually pasted JDs with no
           structured skills, profile skills whose names appear in the
           raw JD text. This only ever suggests skills the candidate
           actually has, so acting on it can never fabricate experience.

        Args:
            content_lower: Lowercase cover letter text
            job: Target job listing
            profile: Original user profile

        Returns:
            Tuple of (issues, coverage details for the response payload)
        """
        terms: List[str] = []
        source: Optional[str] = None

        structured = [
            skill.name for skill in job.skills if skill.is_required and skill.name
        ]
        if structured:
            source = "structured"
            terms = structured[:10]
        elif job.description:
            jd_lower = job.description.lower()
            matched_profile_skills = [
                name
                for name in profile.all_skills_names
                if name and self._term_in_text(name.lower(), jd_lower)
            ]
            if matched_profile_skills:
                source = "profile_match"
                terms = matched_profile_skills[:10]

        coverage: Dict[str, Any] = {
            "source": source,
            "matched": [],
            "missing": [],
        }
        if len(terms) < 2:
            # Not enough signal to judge coverage either way.
            return [], coverage

        for term in terms:
            if self._term_in_text(term.lower(), content_lower):
                coverage["matched"].append(term)
            else:
                coverage["missing"].append(term)

        issues: List[CoverLetterIssue] = []
        if len(coverage["matched"]) * 2 < len(terms):
            issues.append(CoverLetterIssue.LOW_JD_COVERAGE)

        return issues, coverage

    @staticmethod
    def _term_in_text(term_lower: str, text_lower: str) -> bool:
        """
        Whole-token match so short skills ("R", "Go", "C#") do not
        false-positive on substrings of unrelated words.
        """
        if not term_lower:
            return False
        pattern = r"(?<!\w)" + re.escape(term_lower) + r"(?!\w)"
        return re.search(pattern, text_lower) is not None

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
        *,
        grounding_penalty: int = 0,
    ) -> int:
        """
        Calculate content quality score.

        Grounding findings are severity-weighted via ``grounding_penalty``
        (soft vague overlap vs hard overclaim / scope / technique). Flat
        per-issue grounding deductions are intentionally not used.

        Args:
            content_issues: Content completeness / JD coverage issues
            accuracy_issues: Factual accuracy issues
            grounding_penalty: Points to subtract from severity-weighted
                grounding findings (already capped by the grounding module)

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
        if CoverLetterIssue.LOW_JD_COVERAGE in content_issues:
            score -= 15
        if CoverLetterIssue.INSTRUCTION_LENGTH_MISMATCH in content_issues:
            score -= 15
        if CoverLetterIssue.MISSING_REQUIRED_INCLUSION in content_issues:
            score -= 20
        if grounding_penalty:
            score -= grounding_penalty
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
        style: str = "modern",
        *,
        short_answer_mode: bool = False,
        detected_instructions: Optional[DetectedInstructions] = None,
        inclusion_urls: Optional[Dict[str, Optional[str]]] = None,
    ) -> CoverLetterValidationResult:
        """
        Validate using LLM for nuanced quality assessment.

        Falls back to deterministic validation when LLM is unavailable.

        Args:
            cover_letter: Generated cover letter to validate
            job: Target job listing
            profile: Original user profile
            selection: Selection output
            style: ``modern`` or ``classic``
            short_answer_mode: When True, relax full-letter structure checks
            detected_instructions: Phase C detected JD instructions
            inclusion_urls: kind→URL map for inclusion checks

        Returns:
            CoverLetterValidationResult with detailed findings
        """
        if not self.llm_router:
            return self.validate(
                cover_letter,
                job,
                profile,
                selection,
                style=style,
                short_answer_mode=short_answer_mode,
                detected_instructions=detected_instructions,
                inclusion_urls=inclusion_urls,
            )

        deterministic = self.validate(
            cover_letter,
            job,
            profile,
            selection,
            style=style,
            short_answer_mode=short_answer_mode,
            detected_instructions=detected_instructions,
            inclusion_urls=inclusion_urls,
        )
        if collect_hard_fail_issues(deterministic.issues):
            return deterministic
        if short_answer_mode:
            # Keep deterministic instruction checks; skip LLM re-score of
            # full-letter dimensions on short answers.
            return deterministic

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
                # 0.0 keeps scoring deterministic: identical text must always
                # produce identical scores (greedy decoding, no sampling noise).
                temperature=0.0,
                max_tokens=400,
            )

            import json

            json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
            if not json_match:
                raise ValueError("Failed to extract JSON from validation response")

            data = json.loads(json_match.group(0))
            overall = data.get("overall_score", 0)

            # The LLM can return a non-canonical recommendation (wrong case,
            # spaces, or an unexpected word). Normalize to the three allowed
            # values so downstream consumers never receive a surprise string.
            raw_recommendation = (
                str(data.get("recommendation", "needs_revision"))
                .strip()
                .lower()
                .replace(" ", "_")
                .replace("-", "_")
            )
            recommendation = (
                raw_recommendation
                if raw_recommendation in {"approve", "needs_revision", "reject"}
                else "needs_revision"
            )

            return CoverLetterValidationResult(
                is_valid=data.get("is_valid", False),
                score=overall,
                issues=[],
                word_count=cover_letter.word_count,
                structure_score=data.get("structure_score", 0),
                content_score=data.get("content_score", 0),
                tone_score=data.get("tone_score", 0),
                recommendation=recommendation,
                details={"llm_feedback": data.get("issues", [])},
            )

        except Exception as e:
            self.logger.error("LLM validation failed: %s", str(e))
            return self.validate(cover_letter, job, profile, selection, style=style)
