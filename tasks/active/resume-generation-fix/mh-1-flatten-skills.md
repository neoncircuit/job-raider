# MH-1: Flatten the writer's skills

Read `AGENT.md` first.

## Why

The writer prompt says "Group by category" for skills, so the model returns grouped skills (a dict, or a list of objects). The rest of the code needs one flat list of skill names.

## Files

- `apps/backend-py/src/generation/resume_writer.py` (change)
- `apps/backend-py/tests/unit/test_resume_writer_skills.py` (new)

## Step 1: add this test file, run it, and see it fail

`apps/backend-py/tests/unit/test_resume_writer_skills.py`:

```python
"""Tests for the flat skill list of ``ResumeWriter`` (resume generation fix, MH-1)."""

import json
from typing import Any
from unittest.mock import MagicMock

from src.generation.resume_writer import ResumeWriter, flatten_skills
from src.generation.selector import SelectionOutput
from src.llm.base import LLMResponse


def test_flat_list_stays_the_same() -> None:
    """A flat list of names is returned as it is."""
    assert flatten_skills(["Python", "FastAPI"]) == ["Python", "FastAPI"]


def test_dict_of_categories_gives_the_skills() -> None:
    """A dict of category lists gives the skills, not the category names."""
    value = {"Technical Skills": ["Python", "FastAPI"], "Soft Skills": ["Mentoring"]}
    assert flatten_skills(value) == ["Python", "FastAPI", "Mentoring"]


def test_list_of_category_objects_gives_the_skills() -> None:
    """A list of category objects gives the skills in order."""
    value = [
        {"category": "Languages", "skills": ["Python", "SQL"]},
        {"category": "Cloud", "skills": ["AWS"]},
    ]
    assert flatten_skills(value) == ["Python", "SQL", "AWS"]


def test_duplicates_blanks_and_other_types_are_dropped() -> None:
    """Duplicates (any case), blanks, and numbers are dropped; a named object gives its name."""
    value = ["Python", " python ", "", None, 3, {"name": "Go"}]
    assert flatten_skills(value) == ["Python", "Go"]


def test_writer_returns_a_flat_skill_list(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """The writer flattens grouped skills, and the prompt asks for a flat list."""
    payload = {
        "summary": "Backend engineer.",
        "skills": [{"category": "Languages", "skills": ["Python", "SQL"]}],
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
        keywords_to_emphasize=[],
        key_achievements=[],
        summary_suggestion="",
        raw_response="{}",
    )

    resume = ResumeWriter(llm_router=router).write(
        job=sample_job_listing, profile=sample_user_profile, selection=selection
    )

    assert resume.skills == ["Python", "SQL"]
    prompt = router.generate.call_args.kwargs["messages"][1].content
    assert "Group by category" not in prompt
```

## Step 2: change `src/generation/resume_writer.py`

1. Add a module-level function `flatten_skills(value: Any) -> List[str]` after the `GeneratedResume` class. Rules:
    - a string gives itself, with spaces stripped from both ends;
    - a list gives the flattened result of each item, in order;
    - a dict with a `"skills"` key gives the flattened `"skills"` value;
    - a dict with a `"name"` key (and no `"skills"` key) gives the `"name"` value;
    - any other dict gives the flattened values of all its keys, in order (the keys are category names and are not returned);
    - anything else (`None`, numbers) gives nothing;
    - empty strings are dropped;
    - a name that comes again in any letter case is dropped (keep the first spelling).
2. In `ResumeWriter.write`, where `GeneratedResume(...)` is built from `data`, change `skills=data.get("skills", [])` to `skills=flatten_skills(data.get("skills", []))`.
3. In the writer prompt, change the line `  "skills": ["Skill 1", "Skill 2", ...],  // Group by category` to `  "skills": ["Skill 1", "Skill 2", ...],`.
4. In the system message rules, add a rule after rule 6: `7. "skills" is one flat list of skill names from the BASE RESUME. Do not group skills by category.`

## Done when

Run the new tests:

```bash
.venv/bin/python -m pytest tests/unit/test_resume_writer_skills.py tests/unit/test_resume_writer_fallback.py -q
```

Check the format:

```bash
.venv/bin/python -m black --check src/generation/resume_writer.py tests/unit/test_resume_writer_skills.py
```

Check the lint:

```bash
.venv/bin/python -m ruff check src/generation/resume_writer.py tests/unit/test_resume_writer_skills.py
```

Commit message: `fix(generation): flatten the writer's skills into one list of names`
