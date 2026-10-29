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
