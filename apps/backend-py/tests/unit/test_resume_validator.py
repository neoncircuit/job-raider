"""Tests for the skill check of `ResumeValidator` (resume generation fix, MH-2)."""

from typing import Any, List

from src.generation.resume_writer import GeneratedResume
from src.generation.selector import SelectionOutput
from src.generation.validator import ResumeValidator, ValidationIssue


def _resume(skills: Any) -> GeneratedResume:
    """Build a small generated resume with the given skills value.

    Args:
        skills: The skills value, in any shape.

    Returns:
        A `GeneratedResume` with no projects or experience.
    """
    return GeneratedResume(
        summary="Python developer.",
        skills=skills,
        experience=[],
        projects=[],
        education=[],
        raw_response="{}",
        model_used="fake",
    )


def _selection(keywords: List[Any]) -> SelectionOutput:
    """Build a selection with no projects and the given keywords.

    Args:
        keywords: Keywords to emphasize.

    Returns:
        A `SelectionOutput`.
    """
    return SelectionOutput(
        selected_projects=[],
        keywords_to_emphasize=keywords,
        key_achievements=[],
        summary_suggestion="",
        raw_response="{}",
    )


def test_grouped_skills_do_not_crash_and_are_checked(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """A list of category objects is checked skill by skill."""
    resume = _resume([{"category": "Languages", "skills": ["Python", "Rust"]}])

    result = ResumeValidator().validate(
        resume=resume,
        job=sample_job_listing,
        profile=sample_user_profile,
        selection=_selection(["Python"]),
    )

    assert result.fabricated_content == ["rust"]
    assert ValidationIssue.HALLUCINATED_SKILL in result.issues


def test_category_names_are_not_reported_as_skills(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """A dict of categories is not checked by its category names."""
    resume = _resume({"Technical Skills": ["Python", "FastAPI"]})

    result = ResumeValidator().validate(
        resume=resume,
        job=sample_job_listing,
        profile=sample_user_profile,
        selection=_selection(["Python"]),
    )

    assert result.fabricated_content == []
    assert ValidationIssue.HALLUCINATED_SKILL not in result.issues


def test_a_keyword_that_is_not_a_string_does_not_crash(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """A keyword such as a number is compared as text."""
    result = ResumeValidator().validate(
        resume=_resume(["Python"]),
        job=sample_job_listing,
        profile=sample_user_profile,
        selection=_selection(["Python", 3]),
    )

    assert result.missing_keywords == [3]
