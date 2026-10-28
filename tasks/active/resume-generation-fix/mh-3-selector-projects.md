# MH-3: The selector keeps only profile projects

Read `AGENT.md` first.

## Why

The selector prompt asks for exactly 3 projects. A profile with 2 projects gets a third name such as `"None"` or an invented project. The writer leaves it out, and the validator then reports a missing project. Nothing checks the names against the profile.

## Files

- `apps/backend-py/src/generation/selector.py` (change)
- `apps/backend-py/tests/unit/test_resume_selector.py` (new)

## Step 1: add this test file, run it, and see it fail

`apps/backend-py/tests/unit/test_resume_selector.py`:

```python
"""Tests for the project choice of ``ResumeSelector`` (resume generation fix, MH-3)."""

import json
from typing import Any, Dict
from unittest.mock import MagicMock

from src.generation.selector import ResumeSelector
from src.llm.base import LLMResponse
from src.models.user_profile import Project


def _router_returning(payload: Dict[str, Any]) -> MagicMock:
    """Build a fake router whose ``generate`` returns ``payload`` as JSON.

    Args:
        payload: The JSON object that the fake model returns.

    Returns:
        A MagicMock that acts as an ``LLMRouter``.
    """
    router = MagicMock()
    router.generate.return_value = LLMResponse(
        content=json.dumps(payload), model="fake"
    )
    return router


def _two_project_profile(sample_user_profile: Any) -> Any:
    """Return the sample profile with two projects.

    Args:
        sample_user_profile: Profile fixture.

    Returns:
        A copy of the profile with two projects.
    """
    return sample_user_profile.model_copy(
        update={
            "projects": [
                Project(name="Agent-C (AI Singapore)", description="Agent platform."),
                Project(
                    name="Job Raider (Personal Project)", description="Job pipeline."
                ),
            ]
        }
    )


def test_selection_keeps_only_profile_projects(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """Names that are not profile projects are dropped; the profile spelling is used."""
    router = _router_returning(
        {
            "selected_projects": [
                {"name": "agent-c (ai singapore)", "reason": "agents"},
                {"name": "Job Raider (Personal Project)", "reason": "pipelines"},
                {"name": "None", "reason": "padding"},
            ],
            "keywords_to_emphasize": ["Python"],
            "key_achievements": [],
            "summary_suggestion": "",
        }
    )

    selection = ResumeSelector(llm_router=router).select(
        job=sample_job_listing, profile=_two_project_profile(sample_user_profile)
    )

    assert selection.selected_projects == [
        {"name": "Agent-C (AI Singapore)", "reason": "agents"},
        {"name": "Job Raider (Personal Project)", "reason": "pipelines"},
    ]


def test_prompt_asks_for_no_more_projects_than_the_profile_has(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """With two profile projects, the prompt asks for up to 2 projects."""
    router = _router_returning({"selected_projects": [], "keywords_to_emphasize": []})

    ResumeSelector(llm_router=router).select(
        job=sample_job_listing, profile=_two_project_profile(sample_user_profile)
    )

    prompt = router.generate.call_args.kwargs["messages"][1].content
    assert "up to 2 most relevant projects" in prompt.lower()
    assert "The 3 most relevant projects" not in prompt
```

## Step 2: change `src/generation/selector.py`

1. Add this module-level function after the `SelectionOutput` class:

```python
def keep_profile_projects(selected: Any, profile: UserProfile) -> List[Dict[str, str]]:
    """
    Keep only selected projects that name a project in the profile.

    Names are compared without letter case and without spaces at the ends.
    The kept item uses the profile's spelling. A name is kept one time.

    Args:
        selected: The ``selected_projects`` value from the model.
        profile: The user profile.

    Returns:
        Items with ``name`` (the profile's spelling) and ``reason``.
    """
    by_key = {
        project.name.strip().lower(): project.name for project in profile.projects
    }
    kept: List[Dict[str, str]] = []
    seen = set()
    for item in selected if isinstance(selected, list) else []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("name", "")).strip().lower()
        if key in by_key and key not in seen:
            seen.add(key)
            kept.append({"name": by_key[key], "reason": str(item.get("reason", ""))})
    return kept
```

   Add `Any` to the `typing` import (`from typing import Any, Dict, List, Optional`).

2. In `select`, before `messages = [`, add:

```python
        project_count = min(3, len(profile.projects))
```

3. In the prompt, change `1. The 3 most relevant projects to highlight` to `1. Up to {project_count} most relevant projects to highlight. Use the exact project names from the CANDIDATE PROFILE.`

4. In the JSON example of the prompt, change the three lines `{{"name": "Project 1", ...}}`, `{{"name": "Project 2", ...}}`, and `{{"name": "Project 3", ...}}` to this one line:

```text
    {{"name": "Exact project name from the profile", "reason": "Why this project is relevant"}}
```

5. Where `SelectionOutput(...)` is built from `data`, change `selected_projects=data.get("selected_projects", []),` to:

```text
                selected_projects=keep_profile_projects(
                    data.get("selected_projects", []), profile
                ),
```

## Done when

Run the new tests:

```bash
.venv/bin/python -m pytest tests/unit/test_resume_selector.py -q
```

Check the format:

```bash
.venv/bin/python -m black --check src/generation/selector.py tests/unit/test_resume_selector.py
```

Check the lint:

```bash
.venv/bin/python -m ruff check src/generation/selector.py tests/unit/test_resume_selector.py
```

Commit message: `fix(generation): keep only profile projects in the selection`
