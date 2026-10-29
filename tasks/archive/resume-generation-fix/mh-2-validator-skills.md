# MH-2: The validator checks flat skills and does not crash

Read `AGENT.md` first. Do MH-1 first: this step uses `flatten_skills`.

## Why

`ResumeValidator.validate` calls `s.lower()` on each skill. A grouped skill (a dict) makes it raise `'dict' object has no attribute 'lower'`, and a dict of groups makes it check the category names instead of the skills.

## Files

- `apps/backend-py/src/generation/validator.py` (change)
- `apps/backend-py/tests/unit/test_resume_validator.py` (new)

## Step 1: add this test file, run it, and see it fail

`apps/backend-py/tests/unit/test_resume_validator.py`:

```python
"""Tests for the skill check of ``ResumeValidator`` (resume generation fix, MH-2)."""

from typing import Any, List

from src.generation.resume_writer import GeneratedResume
from src.generation.selector import SelectionOutput
from src.generation.validator import ResumeValidator, ValidationIssue


def _resume(skills: Any) -> GeneratedResume:
    """Build a small generated resume with the given skills value.

    Args:
        skills: The skills value, in any shape.

    Returns:
        A ``GeneratedResume`` with no projects or experience.
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
        A ``SelectionOutput``.
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
```

## Step 2: change `src/generation/validator.py`

1. Change the import `from .resume_writer import GeneratedResume` to `from .resume_writer import GeneratedResume, flatten_skills`.
2. In `validate`, change `resume_skills = {s.lower() for s in resume.skills}` to `resume_skills = {s.lower() for s in flatten_skills(resume.skills)}`.
3. In `validate`, change `if keyword.lower() not in resume_text.lower():` to `if str(keyword).lower() not in resume_text.lower():`.
4. In `_get_resume_text`, change `parts.extend(resume.skills)` to `parts.extend(flatten_skills(resume.skills))`.

## Done when

Run the new tests:

```bash
.venv/bin/python -m pytest tests/unit/test_resume_validator.py tests/unit/test_resume_writer_skills.py -q
```

Check the format:

```bash
.venv/bin/python -m black --check src/generation/validator.py tests/unit/test_resume_validator.py
```

Check the lint:

```bash
.venv/bin/python -m ruff check src/generation/validator.py tests/unit/test_resume_validator.py
```

Commit message: `fix(generation): validate flat skills and never crash on grouped skills`
