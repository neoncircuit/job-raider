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
