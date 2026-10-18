"""
Tests for the template fallback in ``ResumeWriter``.

Before 2026-10-18, the fallback summary called ``.name`` on a list slice
(``profile.skills[:5].name``). The fallback runs when the LLM call fails, so
the path meant to recover from an LLM failure raised ``AttributeError``.
"""

from typing import Any
from unittest.mock import MagicMock

from src.generation.resume_writer import GeneratedResume, ResumeWriter
from src.generation.selector import SelectionOutput


def test_fallback_summary_lists_the_first_five_skills(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """With no suggested summary, the fallback names the first five skills.

    Args:
        sample_user_profile: Profile fixture.
        sample_job_listing: Job listing fixture.
    """
    selection = SelectionOutput(
        selected_projects=[],
        keywords_to_emphasize=[],
        key_achievements=[],
        summary_suggestion="",
        raw_response="{}",
    )
    writer = ResumeWriter(llm_router=MagicMock())

    resume = writer._fallback_resume(sample_job_listing, sample_user_profile, selection)

    assert isinstance(resume, GeneratedResume)
    expected = ", ".join(skill.name for skill in sample_user_profile.skills[:5])
    assert resume.summary.endswith(f"with expertise in {expected}")
