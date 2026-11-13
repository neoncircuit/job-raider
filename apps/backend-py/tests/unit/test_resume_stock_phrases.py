"""
Tests for the stock phrases that `ResumeValidator` reports for a CV
(generic-phrasing task, step 7).
"""

import json
from types import SimpleNamespace
from typing import Any, Dict, List

from src.generation.resume_writer import GeneratedResume
from src.generation.selector import SelectionOutput
from src.generation.validator import ResumeValidator


def _resume(
    summary: str, highlights: List[str], description: str, skills: List[str]
) -> GeneratedResume:
    """
    Build a generated CV with one job and one project.

    Args:
        summary: The summary text.
        highlights: The job's highlights.
        description: The project's description.
        skills: The skill names.

    Returns:
        A `GeneratedResume`. The job title, company, and project name hold
        stock phrases on purpose: they are not prose and must not count.
    """
    return GeneratedResume(
        summary=summary,
        skills=skills,
        experience=[
            {
                "title": "Team Player Lead",
                "company": "Synergy Corp",
                "dates": "Jan 2020 - Present",
                "highlights": highlights,
            }
        ],
        projects=[
            {
                "name": "Cutting-Edge App",
                "description": description,
                "technologies": ["Python"],
                "highlights": ["Invaluable to the support team."],
            }
        ],
        education=[],
        raw_response="{}",
        model_used="fake",
    )


SELECTION = SelectionOutput(
    selected_projects=[],
    keywords_to_emphasize=["Python"],
    key_achievements=[],
    summary_suggestion="",
    raw_response="{}",
)

GENERIC = _resume(
    "A results-driven engineer.",
    ["Responsible for the billing API.", "Cut latency by 40%."],
    "Moreover, a dashboard for support.",
    ["Python"],
)

PLAIN = _resume(
    "An engineer who builds billing systems.",
    ["Built the billing API.", "Cut latency by 40%."],
    "A dashboard for support.",
    ["Python"],
)


def test_stock_phrases_come_from_the_prose(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """Summary, highlights, and project text count; titles and names do not."""
    result = ResumeValidator().validate(
        resume=GENERIC,
        job=sample_job_listing,
        profile=sample_user_profile,
        selection=SELECTION,
    )
    assert result.generic_phrases == [
        "invaluable",
        "moreover",
        "responsible for",
        "results-driven",
    ]


def test_skill_names_do_not_count(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """A skill named like a stock phrase is not prose."""
    resume = _resume(
        "An engineer.", ["Built the API."], "A dashboard.", ["Team player"]
    )
    result = ResumeValidator().validate(
        resume=resume,
        job=sample_job_listing,
        profile=sample_user_profile,
        selection=SELECTION,
    )
    assert "team player" not in result.generic_phrases


def test_stock_phrases_do_not_change_the_score(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """The same CV with and without stock phrases gets the same score."""
    validator = ResumeValidator()
    generic = validator.validate(
        resume=GENERIC,
        job=sample_job_listing,
        profile=sample_user_profile,
        selection=SELECTION,
    )
    plain = validator.validate(
        resume=PLAIN,
        job=sample_job_listing,
        profile=sample_user_profile,
        selection=SELECTION,
    )
    assert plain.generic_phrases == ["invaluable"]
    assert (generic.overall_score, generic.recommendation, generic.issues) == (
        plain.overall_score,
        plain.recommendation,
        plain.issues,
    )


def test_llm_validation_also_reports_stock_phrases(
    sample_user_profile: Any, sample_job_listing: Any
) -> None:
    """The LLM validation path fills the list too."""
    answer: Dict[str, Any] = {
        "is_valid": True,
        "missing_projects": [],
        "missing_keywords": [],
        "fabricated_content": [],
        "date_inconsistencies": [],
        "overall_score": 95,
        "recommendation": "approve",
    }
    router = SimpleNamespace(
        generate=lambda **_: SimpleNamespace(content=json.dumps(answer))
    )
    result = ResumeValidator(llm_router=router).validate_with_llm(
        GENERIC, sample_job_listing, sample_user_profile, SELECTION
    )
    assert result.overall_score == 95
    assert "results-driven" in result.generic_phrases
