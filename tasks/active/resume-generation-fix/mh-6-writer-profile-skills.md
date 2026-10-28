# MH-6: The resume lists only profile skills

Read `AGENT.md` first. Do MH-5 first: this step uses `profile_skill_names` from `selector.py`.

## Why

The writer model adds skills that are not in the profile (for example "Leadership" or "Neo4j"), and the validator rejects the draft. After this change, the skills list keeps only profile skills, and it also lists the selected keywords (after MH-5, these are profile skills). A resume then never claims a skill that the candidate does not have.

## Files

- `apps/backend-py/src/generation/resume_writer.py` (change)
- `apps/backend-py/tests/unit/test_resume_writer_profile_skills.py` (new)
- `apps/backend-py/tests/unit/test_resume_writer_skills.py` (one existing test changes; see Step 3)

## Step 1: add this test file, run it, and see it fail

`apps/backend-py/tests/unit/test_resume_writer_profile_skills.py`:

```python
"""Tests for the profile-only skill list of ``ResumeWriter`` (resume generation fix, MH-6)."""

import json
from typing import Any
from unittest.mock import MagicMock

from src.generation.resume_writer import ResumeWriter, keep_profile_skills
from src.generation.selector import SelectionOutput
from src.generation.validator import ResumeValidator
from src.llm.base import LLMResponse


def test_skills_not_in_the_profile_are_dropped(sample_user_profile: Any) -> None:
    """Skills that are not profile skills are dropped; the profile spelling is used."""
    result = keep_profile_skills(
        ["python", "Kubernetes", "Leadership", "AWS"], [], sample_user_profile
    )

    assert result == ["Python", "AWS"]


def test_profile_keywords_are_added(sample_user_profile: Any) -> None:
    """Selected keywords that are profile skills are added after the model's skills."""
    result = keep_profile_skills(
        ["Python"], ["FastAPI", "Kubernetes", "python"], sample_user_profile
    )

    assert result == ["Python", "FastAPI"]


def test_no_skill_left_gives_the_profile_skills(sample_user_profile: Any) -> None:
    """When no skill is left, the result is all profile skill names."""
    result = keep_profile_skills(["Kubernetes"], [], sample_user_profile)

    assert result == [skill.name for skill in sample_user_profile.skills]


def test_a_written_resume_passes_the_skill_and_keyword_checks(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """A draft with extra skills passes once only profile skills are kept."""
    payload = {
        "summary": "Backend engineer.",
        "skills": ["Python", "Leadership", "Neo4j"],
        "experience": [],
        "projects": [],
        "education": [],
    }
    router = MagicMock()
    router.generate.return_value = LLMResponse(
        content=json.dumps(payload), model="fake"
    )
    selection = SelectionOutput(
        selected_projects=[],
        keywords_to_emphasize=["FastAPI"],
        key_achievements=[],
        summary_suggestion="",
        raw_response="{}",
    )

    resume = ResumeWriter(llm_router=router).write(
        job=sample_job_listing, profile=sample_user_profile, selection=selection
    )
    result = ResumeValidator().validate(
        resume=resume,
        job=sample_job_listing,
        profile=sample_user_profile,
        selection=selection,
    )

    assert resume.skills == ["Python", "FastAPI"]
    assert result.fabricated_content == []
    assert result.missing_keywords == []
    assert result.is_valid
    system_prompt = router.generate.call_args.kwargs["messages"][0].content
    assert "Do not add other skills" in system_prompt
```

## Step 2: change `src/generation/resume_writer.py`

1. Change the import `from .selector import SelectionOutput` to `from .selector import SelectionOutput, profile_skill_names`.

2. Add this module-level function after `match_project_names`:

```python
def keep_profile_skills(
    skills: List[str], keywords: List[str], profile: UserProfile
) -> List[str]:
    """
    Keep only profile skills, then add the selected keywords that are profile skills.

    Names are compared without letter case and without spaces at the ends,
    and the profile's spelling is used. A name is kept one time. When no
    skill is left, the result is all profile skill names.

    Args:
        skills: Flat skill names from the model.
        keywords: The selection's keywords to emphasize.
        profile: The user profile.

    Returns:
        Profile skill names: the model's skills first, then the keywords.
    """
    allowed = profile_skill_names(profile)
    result: List[str] = []
    for item in list(skills) + list(keywords):
        name = allowed.get(str(item).strip().lower())
        if name and name not in result:
            result.append(name)
    return result or [skill.name for skill in profile.skills]
```

3. In `ResumeWriter.write`, where `GeneratedResume(...)` is built from `data`, change `skills=flatten_skills(data.get("skills", [])),` to:

```text
                skills=keep_profile_skills(
                    flatten_skills(data.get("skills", [])),
                    selection.keywords_to_emphasize,
                    profile,
                ),
```

4. In the system message rules, change rule 7 from `7. "skills" is one flat list of skill names from the BASE RESUME. Do not group skills by category.` to `7. "skills" lists only skill names from the BASE RESUME, in one flat list. Do not add other skills, and do not group skills by category.`

## Step 3: change one existing test (allowed for this step only)

MH-1's writer test uses the skill "SQL", which is not in the sample profile, so this step would drop it. In `apps/backend-py/tests/unit/test_resume_writer_skills.py`, in `test_writer_returns_a_flat_skill_list` only:

- change `"skills": [{"category": "Languages", "skills": ["Python", "SQL"]}],` to `"skills": [{"category": "Languages", "skills": ["Python", "Django"]}],`
- change `assert resume.skills == ["Python", "SQL"]` to `assert resume.skills == ["Python", "Django"]`

Do not change any other test.

## Done when

Run the new tests and all resume generation tests:

```bash
.venv/bin/python -m pytest tests/unit/test_resume_writer_profile_skills.py tests/unit/test_resume_writer_skills.py tests/unit/test_resume_writer_projects.py tests/unit/test_resume_validator.py tests/unit/test_resume_selector.py tests/unit/test_resume_selector_keywords.py tests/unit/test_resume_writer_fallback.py -q
```

Format the changed files:

```bash
.venv/bin/python -m black src/generation/resume_writer.py tests/unit/test_resume_writer_profile_skills.py tests/unit/test_resume_writer_skills.py
```

Check the lint:

```bash
.venv/bin/python -m ruff check src/generation/resume_writer.py tests/unit/test_resume_writer_profile_skills.py tests/unit/test_resume_writer_skills.py
```

Commit message: `fix(generation): list only profile skills on the resume`
