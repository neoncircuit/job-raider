"""Tests for the project names of ``ResumeWriter`` (resume generation fix, MH-4)."""

import json
from typing import Any
from unittest.mock import MagicMock

from src.generation.resume_writer import ResumeWriter, match_project_names
from src.generation.selector import SelectionOutput
from src.generation.validator import ResumeValidator
from src.llm.base import LLMResponse
from src.models.user_profile import Project


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


def test_shortened_names_get_the_profile_name(sample_user_profile: Any) -> None:
    """A name without the "(...)" part, in any case, gets the profile name."""
    projects = [
        {"name": "Agent-C", "description": "d"},
        {"name": "job raider", "description": "e"},
    ]

    result = match_project_names(projects, _two_project_profile(sample_user_profile))

    assert [p["name"] for p in result] == [
        "Agent-C (AI Singapore)",
        "Job Raider (Personal Project)",
    ]
    assert result[0]["description"] == "d"


def test_unknown_names_stay_and_other_items_are_dropped(
    sample_user_profile: Any,
) -> None:
    """A name that matches no profile project stays; an item that is not a dict is dropped."""
    result = match_project_names(
        [{"name": "Weather App"}, "text"], _two_project_profile(sample_user_profile)
    )

    assert result == [{"name": "Weather App"}]


def test_the_input_list_is_not_changed(sample_user_profile: Any) -> None:
    """The function returns new items and does not change its input."""
    projects = [{"name": "Agent-C"}]

    match_project_names(projects, _two_project_profile(sample_user_profile))

    assert projects == [{"name": "Agent-C"}]


def test_a_shortened_name_passes_validation(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """A draft with "Agent-C" passes the project check for "Agent-C (AI Singapore)"."""
    profile = _two_project_profile(sample_user_profile)
    payload = {
        "summary": "Backend engineer.",
        "skills": ["Python"],
        "experience": [],
        "projects": [{"name": "Agent-C", "description": "d"}],
        "education": [],
    }
    router = MagicMock()
    router.generate.return_value = LLMResponse(
        content=json.dumps(payload), model="fake"
    )
    selection = SelectionOutput(
        selected_projects=[{"name": "Agent-C (AI Singapore)", "reason": "agents"}],
        keywords_to_emphasize=[],
        key_achievements=[],
        summary_suggestion="",
        raw_response="{}",
    )

    resume = ResumeWriter(llm_router=router).write(
        job=sample_job_listing, profile=profile, selection=selection
    )
    result = ResumeValidator().validate(
        resume=resume, job=sample_job_listing, profile=profile, selection=selection
    )

    assert result.missing_projects == []
