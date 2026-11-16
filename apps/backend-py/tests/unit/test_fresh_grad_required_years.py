"""
Tests for change D of the project-scoring task: required years.

- D1: the MyCareersFuture scraper keeps ``minimumYearsExperience`` as an
  experience requirement, also when the listing gives a position level.
- D2: in fresh graduate mode, a job that asks for 5 or more years is capped
  below the threshold, whatever its stated level. Fewer years (3 or 4 included), or no stated
  years, do not change the score. Standard mode does not change.
- D3: the score distribution counts the scored jobs that ask for 5 or more
  years.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest

from src.evaluation.suites.ranking import load_ranking_set
from src.models.job_listing import ExperienceLevel, JobListing, JobRequirement
from src.models.user_profile import UserProfile
from src.scoring.distribution import score_distribution
from src.scoring.matcher import JobMatcher
from src.scrapers.mycareersfuture_scraper import MyCareersFutureScraper

MCF_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "mycareersfuture"
    / "search_page.json"
)


def mcf_row(**changes: Any) -> Dict[str, Any]:
    """
    The first MCF fixture row (position level "Professional", 3 minimum years).

    Args:
        **changes: Raw fields to change.

    Returns:
        The raw MCF job dict.
    """
    row = json.loads(MCF_FIXTURE.read_text(encoding="utf-8"))["results"][0]
    row.update(changes)
    return row


@pytest.fixture(scope="module")
def fresh_ml() -> SimpleNamespace:
    """The `fresh_ml` profile and the ranking job rk-001 (a graduate ML job)."""
    data = load_ranking_set()
    job = next(job for job in data.jobs if job.job_id == "rk-001")
    return SimpleNamespace(profile=data.profiles["fresh_ml"], job=job)


def with_years(
    job: JobListing, years: Optional[float], level: ExperienceLevel
) -> JobListing:
    """
    A copy of a job with a stated level and, optionally, required years.

    Args:
        job: The base job.
        years: Required years, or None for no experience requirement.
        level: The stated experience level.

    Returns:
        The job copy.
    """
    requirements = list(job.requirements)
    if years is not None:
        requirements.append(
            JobRequirement(
                category="Experience",
                text=f"At least {years:g} years of experience",
                years_of_experience=years,
            )
        )
    return job.model_copy(
        update={"requirements": requirements, "experience_level": level}
    )


# --- D1: the MCF scraper keeps the minimum years -----------------------------


def test_mcf_keeps_minimum_years_when_a_level_is_given() -> None:
    """A Professional (Mid Level) listing with 3 minimum years keeps the 3 years."""
    job = MyCareersFutureScraper(rate_limit=0)._parse_job(mcf_row())

    years = [r.years_of_experience for r in job.requirements if r.years_of_experience]
    assert job.experience_level == ExperienceLevel.MID.value
    assert years == [3]


@pytest.mark.parametrize("value", [0, None])
def test_mcf_adds_no_experience_requirement_without_years(value: Any) -> None:
    """Zero or missing minimum years add no experience requirement."""
    job = MyCareersFutureScraper(rate_limit=0)._parse_job(
        mcf_row(minimumYearsExperience=value)
    )

    assert all(r.years_of_experience is None for r in job.requirements)


# --- D2: required years in fresh graduate mode -------------------------------


def test_required_years_is_the_largest_stated_value(fresh_ml: SimpleNamespace) -> None:
    """``required_years`` gives the largest stated years, or None."""
    from src.scoring.matcher import required_years

    two = with_years(fresh_ml.job, 2, ExperienceLevel.MID)
    two_and_four = with_years(two, 4, ExperienceLevel.MID)

    assert required_years(fresh_ml.job) is None
    assert required_years(two) == 2
    assert required_years(two_and_four) == 4


@pytest.mark.parametrize("years", [5, 6])
def test_three_or_more_years_are_capped(fresh_ml: SimpleNamespace, years: int) -> None:
    """A Mid Level job that asks for 5 or more years cannot pass in fresh graduate mode."""
    matcher = JobMatcher(fresh_grad_mode=True)
    plain = with_years(fresh_ml.job, None, ExperienceLevel.MID)
    asks = with_years(fresh_ml.job, years, ExperienceLevel.MID)

    assert matcher.score_job(plain, fresh_ml.profile).passed_threshold
    score = matcher.score_job(asks, fresh_ml.profile)
    assert not score.passed_threshold
    assert score.total_score <= matcher.threshold - 15


@pytest.mark.parametrize("years", [None, 2, 3, 4])
def test_mid_level_with_fewer_years_still_passes(
    fresh_ml: SimpleNamespace, years: Optional[int]
) -> None:
    """Mid Level jobs that ask for fewer than 5 years, or state none, keep their score."""
    matcher = JobMatcher(fresh_grad_mode=True)
    plain = with_years(fresh_ml.job, None, ExperienceLevel.MID)
    asks = with_years(fresh_ml.job, years, ExperienceLevel.MID)

    plain_score = matcher.score_job(plain, fresh_ml.profile)
    asks_score = matcher.score_job(asks, fresh_ml.profile)
    assert asks_score.passed_threshold
    assert asks_score.total_score == plain_score.total_score


def test_years_override_a_stated_entry_level(fresh_ml: SimpleNamespace) -> None:
    """An Entry Level job that asks for 5 years is capped: the years decide."""
    matcher = JobMatcher(fresh_grad_mode=True)
    job = with_years(fresh_ml.job, 5, ExperienceLevel.ENTRY)

    assert not matcher.score_job(job, fresh_ml.profile).passed_threshold


def test_standard_mode_ignores_required_years(fresh_ml: SimpleNamespace) -> None:
    """Standard mode scores a job with 5 required years as before."""
    matcher = JobMatcher()
    plain = with_years(fresh_ml.job, None, ExperienceLevel.MID)
    asks = with_years(fresh_ml.job, 5, ExperienceLevel.MID)

    assert (
        matcher.score_job(asks, fresh_ml.profile).total_score
        == matcher.score_job(plain, fresh_ml.profile).total_score
    )


# --- D3: the distribution counts jobs that ask for 5 or more years -----------


def test_distribution_counts_jobs_with_five_or_more_years(
    fresh_ml: SimpleNamespace,
) -> None:
    """``required_years_at_or_above_5`` counts scored jobs, numbers only."""
    profile: UserProfile = fresh_ml.profile
    matcher = JobMatcher(fresh_grad_mode=True)
    jobs = [
        with_years(fresh_ml.job, years, ExperienceLevel.MID)
        for years in (None, 2, 4, 5, 7)
    ]
    pairs = [(job, matcher.score_job(job, profile)) for job in jobs]

    assert score_distribution(pairs)["required_years_at_or_above_5"] == 2
