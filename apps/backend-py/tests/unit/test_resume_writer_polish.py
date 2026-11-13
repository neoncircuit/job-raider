"""Tests for the stock-phrase polish step in ``ResumeWriter.write``."""

import json
from typing import Any
from unittest.mock import MagicMock

from src.generation.resume_writer import ResumeWriter
from src.generation.selector import SelectionOutput
from src.llm.base import LLMResponse
from src.llm.router import TaskType

SELECTION = SelectionOutput(
    selected_projects=[],
    keywords_to_emphasize=[],
    key_achievements=[],
    summary_suggestion="",
    raw_response="{}",
)


def _router(*answers: str) -> MagicMock:
    """
    A mock router that gives the answers in order.

    Args:
        *answers: Answer texts, one per call.

    Returns:
        The mock router.
    """
    router = MagicMock()
    router.routes = {TaskType.RESUME_WRITING: MagicMock(primary_model="qwen2.5:7b")}
    router.generate.side_effect = [
        LLMResponse(content=answer, model="qwen2.5:7b") for answer in answers
    ]
    return router


CV_JSON = json.dumps(
    {
        "summary": "A proven track record in Python services.",
        "skills": ["Python"],
        "experience": [],
        "projects": [],
        "education": [],
    }
)


def test_write_polishes_by_default(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """write() rewrites the summary sentence with the stock phrase and counts it."""
    router = _router(CV_JSON, "1. Years of work on Python services.")
    resume = ResumeWriter(router).write(
        sample_job_listing, sample_user_profile, SELECTION
    )
    assert resume.summary == "Years of work on Python services."
    assert resume.stock_phrase_edits == 1
    assert router.generate.call_count == 2
    assert (
        router.generate.call_args_list[1].kwargs["task_type"] == TaskType.RESUME_WRITING
    )


def test_write_without_polish_makes_one_call(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """write(polish=False) returns the CV as written."""
    router = _router(CV_JSON)
    resume = ResumeWriter(router).write(
        sample_job_listing, sample_user_profile, SELECTION, polish=False
    )
    assert resume.summary == "A proven track record in Python services."
    assert resume.stock_phrase_edits == 0
    assert router.generate.call_count == 1
