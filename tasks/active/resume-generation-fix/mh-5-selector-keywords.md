# MH-5: The selector's keywords are profile skills

Read `AGENT.md` first.

## Why

The selector picks "the 5 most important keywords" from the job, also skills that the candidate does not have. The writer must use every keyword, so it puts them in the skills list, and the validator then reports skills that are not in the profile. After this change, the keywords are only profile skills that the job asks for.

## Files

- `apps/backend-py/src/generation/selector.py` (change)
- `apps/backend-py/tests/unit/test_resume_selector_keywords.py` (new)

## Step 1: add this test file, run it, and see it fail

`apps/backend-py/tests/unit/test_resume_selector_keywords.py`:

```python
"""Tests for the keyword choice of ``ResumeSelector`` (resume generation fix, MH-5)."""

import json
from typing import Any, Dict
from unittest.mock import MagicMock

from src.generation.selector import ResumeSelector, keep_profile_keywords
from src.llm.base import LLMResponse


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


def test_keywords_are_only_profile_skills(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """Keywords that are not profile skills are dropped; the profile spelling is used."""
    router = _router_returning(
        {
            "selected_projects": [],
            "keywords_to_emphasize": ["python", "Kubernetes", "FASTAPI", "Python", 7],
        }
    )

    selection = ResumeSelector(llm_router=router).select(
        job=sample_job_listing, profile=sample_user_profile
    )

    assert selection.keywords_to_emphasize == ["Python", "FastAPI"]


def test_a_value_that_is_not_a_list_gives_no_keywords(
    sample_user_profile: Any,
) -> None:
    """A keywords value that is not a list gives an empty list."""
    assert keep_profile_keywords("Python", sample_user_profile) == []
    assert keep_profile_keywords(None, sample_user_profile) == []


def test_prompt_asks_for_profile_skills(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """The prompt asks for profile skills that the job asks for."""
    router = _router_returning({"selected_projects": [], "keywords_to_emphasize": []})

    ResumeSelector(llm_router=router).select(
        job=sample_job_listing, profile=sample_user_profile
    )

    prompt = router.generate.call_args.kwargs["messages"][1].content
    assert "skills from the candidate profile that this job asks for" in prompt.lower()
    assert "The 5 most important keywords" not in prompt
```

## Step 2: change `src/generation/selector.py`

1. Add these two module-level functions after `keep_profile_projects`:

```python
def profile_skill_names(profile: UserProfile) -> Dict[str, str]:
    """
    Map each profile skill name to its spelling.

    Args:
        profile: The user profile.

    Returns:
        A dict from the skill name in lower case, without spaces at the
        ends, to the profile's spelling.
    """
    return {skill.name.strip().lower(): skill.name for skill in profile.skills}


def keep_profile_keywords(keywords: Any, profile: UserProfile) -> List[str]:
    """
    Keep only keywords that are skills in the profile.

    Names are compared without letter case and without spaces at the ends.
    The kept keyword uses the profile's spelling. A keyword is kept one time.

    Args:
        keywords: The ``keywords_to_emphasize`` value from the model.
        profile: The user profile.

    Returns:
        Profile skill names, in the model's order.
    """
    allowed = profile_skill_names(profile)
    kept: List[str] = []
    for item in keywords if isinstance(keywords, list) else []:
        if not isinstance(item, str):
            continue
        name = allowed.get(item.strip().lower())
        if name and name not in kept:
            kept.append(name)
    return kept
```

2. In the prompt, change `2. The 5 most important keywords to emphasize in the resume` to `2. Up to 5 skills from the CANDIDATE PROFILE that this job asks for. Use the exact skill names from the profile.`

3. In the JSON example of the prompt, change `  "keywords_to_emphasize": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],` to `  "keywords_to_emphasize": ["Skill name from the profile", "..."],`

4. Where `SelectionOutput(...)` is built from `data`, change `keywords_to_emphasize=data.get("keywords_to_emphasize", []),` to:

```text
                keywords_to_emphasize=keep_profile_keywords(
                    data.get("keywords_to_emphasize", []), profile
                ),
```

## Done when

Run the new tests and the MH-3 tests:

```bash
.venv/bin/python -m pytest tests/unit/test_resume_selector_keywords.py tests/unit/test_resume_selector.py -q
```

Format the changed files:

```bash
.venv/bin/python -m black src/generation/selector.py tests/unit/test_resume_selector_keywords.py
```

Check the lint:

```bash
.venv/bin/python -m ruff check src/generation/selector.py tests/unit/test_resume_selector_keywords.py
```

Commit message: `fix(generation): choose only profile skills as resume keywords`
