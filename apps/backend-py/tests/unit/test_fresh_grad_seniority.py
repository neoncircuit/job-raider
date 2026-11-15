"""
Tests for change C of the scoring-calibration task.

- C1: in fresh graduate mode, senior, lead, principal, and executive jobs are
  capped below the matcher threshold, as internships already are when the
  profile excludes them. A senior title counts when the level is not given.
- C2: the MyCareersFuture position levels map "Fresh/entry level",
  "Junior Executive", and "Non-executive" to entry level.
- C3: the internship check matches "intern" and "internship" as whole words,
  so "internal" and "international" do not count.
- The score distribution counts the scored jobs per experience level.
"""

from types import SimpleNamespace

import pytest

from src.models.job_listing import ExperienceLevel
from src.scoring.distribution import score_distribution
from src.scoring.filter import JobFilter
from src.scoring.matcher import JobMatcher
from src.scrapers.mycareersfuture_scraper import MyCareersFutureScraper


def job_with(base, **changes):
    """
    A copy of the sample job with changed fields.

    Args:
        base: The sample job.
        **changes: Job fields to change.

    Returns:
        The job copy.
    """
    return base.model_copy(update=changes)


# --- C1: seniority cap in fresh graduate mode --------------------------------


@pytest.mark.parametrize(
    "level",
    [
        ExperienceLevel.SENIOR,
        ExperienceLevel.LEAD,
        ExperienceLevel.PRINCIPAL,
        ExperienceLevel.EXECUTIVE,
    ],
)
def test_senior_levels_are_capped_in_fresh_graduate_mode(
    sample_job_listing, sample_user_profile, level
) -> None:
    """A senior-level job cannot pass the fresh graduate threshold."""
    matcher = JobMatcher(fresh_grad_mode=True)
    job = job_with(sample_job_listing, title="Data Engineer", experience_level=level)

    score = matcher.score_job(job, sample_user_profile)

    assert score.total_score <= matcher.threshold - 15
    assert score.passed_threshold is False


def test_senior_title_is_capped_when_the_level_is_not_given(
    sample_job_listing, sample_user_profile
) -> None:
    """A 'Senior' title counts as senior when the job states no level."""
    matcher = JobMatcher(fresh_grad_mode=True)
    job = job_with(
        sample_job_listing,
        title="Senior Data Engineer",
        experience_level=ExperienceLevel.NOT_SPECIFIED,
    )

    score = matcher.score_job(job, sample_user_profile)

    assert score.total_score <= matcher.threshold - 15


def test_entry_level_job_is_not_capped(sample_job_listing, sample_user_profile) -> None:
    """An entry-level job keeps its full score in fresh graduate mode."""
    matcher = JobMatcher(fresh_grad_mode=True)
    entry = job_with(
        sample_job_listing,
        title="Junior Data Engineer",
        experience_level=ExperienceLevel.ENTRY,
    )

    score = matcher.score_job(entry, sample_user_profile)

    assert score.total_score == sum(score.breakdown.values())


def test_standard_mode_does_not_cap_senior_jobs(
    sample_job_listing, sample_user_profile
) -> None:
    """The cap is for fresh graduate mode only."""
    matcher = JobMatcher(fresh_grad_mode=False)
    job = job_with(
        sample_job_listing,
        title="Senior Data Engineer",
        experience_level=ExperienceLevel.SENIOR,
    )

    score = matcher.score_job(job, sample_user_profile)

    assert score.total_score == sum(score.breakdown.values())


# --- C2: MyCareersFuture position levels -------------------------------------


@pytest.mark.parametrize(
    ("label", "level"),
    [
        ("Fresh/entry level", ExperienceLevel.ENTRY),
        ("Junior Executive", ExperienceLevel.ENTRY),
        ("Non-executive", ExperienceLevel.ENTRY),
        ("Executive", ExperienceLevel.MID),
        ("Professional", ExperienceLevel.MID),
        ("Senior Executive", ExperienceLevel.SENIOR),
        ("Manager", ExperienceLevel.LEAD),
        ("Senior Management", ExperienceLevel.EXECUTIVE),
        ("Internship/Attachment", ExperienceLevel.INTERNSHIP),
    ],
)
def test_mycareersfuture_position_levels(label: str, level: ExperienceLevel) -> None:
    """Each MyCareersFuture position level maps to the right experience level."""
    assert MyCareersFutureScraper._map_position_levels([{"position": label}]) == level


# --- C3: internship check on whole words -------------------------------------


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [
        ("Backend Engineer", "Build internal tools for an international team.", False),
        ("Backend Engineer", "Work on internet-scale services.", False),
        ("Software Engineering Intern", "Join the team for 6 months.", True),
        ("Backend Engineer", "This is a paid internship.", True),
        ("Data Analyst", "Interns are welcome to apply.", True),
    ],
)
def test_internship_check_uses_whole_words(
    sample_job_listing, title: str, description: str, expected: bool
) -> None:
    """'intern' and 'internship' count; 'internal' and 'international' do not."""
    job = job_with(
        sample_job_listing,
        title=title,
        description=description,
        experience_level=ExperienceLevel.ENTRY,
    )

    assert JobFilter._looks_like_internship(job) is expected


# --- Measurement: jobs per experience level ----------------------------------


def test_distribution_counts_jobs_per_level() -> None:
    """The distribution counts the scored jobs per experience level."""
    pairs = [
        (
            SimpleNamespace(skills=["a"], experience_level=ExperienceLevel.ENTRY),
            SimpleNamespace(total_score=55),
        ),
        (
            SimpleNamespace(skills=["a"], experience_level=ExperienceLevel.SENIOR),
            SimpleNamespace(total_score=30),
        ),
        (
            SimpleNamespace(skills=["a"], experience_level=ExperienceLevel.SENIOR),
            SimpleNamespace(total_score=35),
        ),
    ]

    result = score_distribution(pairs)

    assert result["levels"] == {"Entry Level": 1, "Senior": 2}
