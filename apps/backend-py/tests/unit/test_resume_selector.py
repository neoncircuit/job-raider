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
