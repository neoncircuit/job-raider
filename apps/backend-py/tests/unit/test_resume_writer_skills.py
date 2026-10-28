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
