"""
Job Raider - Resume Validator

This module provides deterministic validation for generated resumes
to ensure all requirements are met.

Author: Job Raider
Date: 2026-04-20
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger
from .resume_writer import GeneratedResume
from .selector import SelectionOutput


class ValidationIssue(str, Enum):
    """Types of validation issues."""

    MISSING_PROJECT = "missing_project"
    MISSING_KEYWORD = "missing_keyword"
    FABRICATED_CONTENT = "fabricated_content"
    DATE_INCONSISTENCY = "date_inconsistency"
    HALLUCINATED_SKILL = "hallucinated_skill"


@dataclass
class ValidationResult:
    """Result of validating a generated resume."""

    is_valid: bool
    missing_projects: List[str]
    missing_keywords: List[str]
    fabricated_content: List[str]
    date_inconsistencies: List[str]
    overall_score: int  # 0-100
    recommendation: str  # "approve", "needs_revision", "reject"
    issues: List[ValidationIssue]


class ResumeValidator:
    """
    Validate generated resumes against requirements.

    Performs deterministic checks to ensure:
    - All selected projects appear in output
    - All keywords are mentioned
    - No skills were fabricated
    - Dates match the original profile
    """

    def __init__(
        self,
        llm_router: Optional[LLMRouter] = None,
        strict_mode: bool = True,
    ):
        """
        Initialize the resume validator.

        Args:
            llm_router: Optional LLM router for AI-based validation
            strict_mode: Whether to be strict about validation
        """
        self.llm_router = llm_router
        self.strict_mode = strict_mode
        self.logger = get_logger(Components.GENERATION)

    def validate(
        self,
        resume: GeneratedResume,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
    ) -> ValidationResult:
        """
        Validate a generated resume.

        Args:
            resume: Generated resume to validate
            job: Target job listing
            profile: Original user profile
            selection: Selection output

        Returns:
            ValidationResult with detailed findings
        """
        issues = []
        missing_projects = []
        missing_keywords = []
        fabricated_content = []
        date_inconsistencies = []

        # 1. Check that all selected projects are present
        for project_spec in selection.selected_projects:
            project_name = project_spec["name"]
            found = any(p["name"] == project_name for p in resume.projects)
            if not found:
                missing_projects.append(project_name)
                issues.append(ValidationIssue.MISSING_PROJECT)

        # 2. Check that all keywords are mentioned
        resume_text = self._get_resume_text(resume)
        for keyword in selection.keywords_to_emphasize:
            if keyword.lower() not in resume_text.lower():
                missing_keywords.append(keyword)
                issues.append(ValidationIssue.MISSING_KEYWORD)

        # 3. Check for fabricated skills
        resume_skills = {s.lower() for s in resume.skills}
        profile_skills = {s.name.lower() for s in profile.skills}

        fabricated = resume_skills - profile_skills
        if fabricated:
            fabricated_content.extend(list(fabricated))
            issues.append(ValidationIssue.HALLUCINATED_SKILL)

        # 4. Check date consistency
        for exp in resume.experience:
            # Find corresponding profile experience
            profile_exp = next(
                (
                    e
                    for e in profile.experience
                    if e.title == exp["title"] and e.company == exp["company"]
                ),
                None,
            )

            if profile_exp:
                # Check date format consistency
                exp_dates = exp["dates"]
                profile_dates = (
                    f"{profile_exp.start_date.strftime('%b %Y')} - {profile_exp.end_date.strftime('%b %Y')}"
                    if profile_exp.end_date
                    else f"{profile_exp.start_date.strftime('%b %Y')} - Present"
                )

                if exp_dates != profile_dates:
                    date_inconsistencies.append(
                        f"{exp['title']} at {exp['company']}: {exp_dates} != {profile_dates}"
                    )
                    issues.append(ValidationIssue.DATE_INCONSISTENCY)

        # Calculate score
        total_items = len(selection.selected_projects) + len(
            selection.keywords_to_emphasize
        )
        failed_items = (
            len(missing_projects) + len(missing_keywords) + len(fabricated_content)
        )

        overall_score = max(0, 100 - int((failed_items / max(total_items, 1)) * 100))

        # Determine recommendation
        if overall_score >= 90:
            recommendation = "approve"
        elif overall_score >= 70:
            recommendation = "needs_revision"
        else:
            recommendation = "reject"

        is_valid = recommendation == "approve" or (
            not self.strict_mode and recommendation == "needs_revision"
        )

        return ValidationResult(
            is_valid=is_valid,
            missing_projects=missing_projects,
            missing_keywords=missing_keywords,
            fabricated_content=fabricated_content,
            date_inconsistencies=date_inconsistencies,
            overall_score=overall_score,
            recommendation=recommendation,
            issues=issues,
        )

    def validate_with_llm(
        self,
        resume: GeneratedResume,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
    ) -> ValidationResult:
        """
        Validate using LLM for more thorough checking.

        Args:
            resume: Generated resume to validate
            job: Target job listing
            profile: Original user profile
            selection: Selection output

        Returns:
            ValidationResult with detailed findings
        """
        if not self.llm_router:
            # Fall back to deterministic validation
            return self.validate(resume, job, profile, selection)

        # Prepare validation prompt
        messages = [
            Message(
                role=MessageType.SYSTEM,
                content="You are a resume validator. Ensure all required elements are present and accurate.",
            ),
            Message(
                role=MessageType.USER,
                content=f"""Validate this generated resume against the requirements:

REQUIREMENTS:
{selection}

GENERATED RESUME:
{self._get_resume_text(resume)}

Check:
1. All selected projects are present
2. All keywords are mentioned
3. No skills were fabricated
4. Dates match the original profile
5. No factual inconsistencies

Return a JSON object:
{{
  "is_valid": true/false,
  "missing_projects": ["project1", "project2"],
  "missing_keywords": ["keyword1", "keyword2"],
  "fabricated_content": ["item1", "item2"],
  "date_inconsistencies": ["inconsistency1"],
  "overall_score": 0-100,
  "recommendation": "approve/needs_revision/reject"
}}""",
            ),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.VALIDATION,
                temperature=0.3,
                max_tokens=500,
            )

            # Parse JSON response
            import json
            import re

            json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
            if not json_match:
                raise ValueError("Failed to extract JSON from validation response")

            data = json.loads(json_match.group(0))

            return ValidationResult(
                is_valid=data.get("is_valid", False),
                missing_projects=data.get("missing_projects", []),
                missing_keywords=data.get("missing_keywords", []),
                fabricated_content=data.get("fabricated_content", []),
                date_inconsistencies=data.get("date_inconsistencies", []),
                overall_score=data.get("overall_score", 0),
                recommendation=data.get("recommendation", "needs_revision"),
                issues=[],
            )

        except Exception as e:
            self.logger.error(f"LLM validation failed: {str(e)}")
            # Fall back to deterministic validation
            return self.validate(resume, job, profile, selection)

    def _get_resume_text(self, resume: GeneratedResume) -> str:
        """
        Get full text content of resume for checking.

        Args:
            resume: Generated resume

        Returns:
            Combined text content
        """
        parts = []

        parts.append(resume.summary)

        parts.extend(resume.skills)

        for exp in resume.experience:
            parts.append(exp["title"])
            parts.append(exp["company"])
            parts.extend(exp.get("highlights", []))

        for project in resume.projects:
            parts.append(project["name"])
            parts.append(project.get("description", ""))
            parts.extend(project.get("technologies", []))
            parts.extend(project.get("highlights", []))

        return "\n".join(str(p) for p in parts)

    def batch_validate(
        self,
        resumes: List[GeneratedResume],
        jobs: List[JobListing],
        profile: UserProfile,
        selections: List[SelectionOutput],
    ) -> List[ValidationResult]:
        """
        Validate multiple resumes in batch.

        Args:
            resumes: List of generated resumes
            jobs: Corresponding job listings
            profile: User profile
            selections: Corresponding selection outputs

        Returns:
            List of ValidationResults
        """
        results = []

        for i, resume in enumerate(resumes):
            if i < len(jobs) and i < len(selections):
                result = self.validate(
                    resume,
                    jobs[i],
                    profile,
                    selections[i],
                )
                results.append(result)

        return results

    def get_validation_summary(
        self,
        results: List[ValidationResult],
    ) -> Dict[str, Any]:
        """
        Get summary statistics for validation results.

        Args:
            results: List of validation results

        Returns:
            Summary statistics
        """
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        approved = sum(1 for r in results if r.recommendation == "approve")
        needs_revision = sum(1 for r in results if r.recommendation == "needs_revision")
        rejected = sum(1 for r in results if r.recommendation == "reject")

        avg_score = sum(r.overall_score for r in results) / total if total > 0 else 0

        common_issues = {}
        for result in results:
            for issue in result.issues:
                common_issues[issue.value] = common_issues.get(issue.value, 0) + 1

        return {
            "total_resumes": total,
            "valid_resumes": valid,
            "approved": approved,
            "needs_revision": needs_revision,
            "rejected": rejected,
            "approval_rate": approved / total if total > 0 else 0,
            "average_score": avg_score,
            "common_issues": common_issues,
        }
