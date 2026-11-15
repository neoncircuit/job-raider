"""
Tests for the score distribution of the score-and-rank stage (scoring-calibration task).

The stage keeps only jobs at or above ``min_score``. To calibrate the scoring,
its metadata must also describe all scored jobs: counts per 10-point band,
the counts at 50 and at 60 or more, the mean of each component, and the same
counts for jobs without a skill list. The metadata holds numbers only (no job
text, no profile data), and the stage result does not change.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.pipeline.stages import PipelineContext, PipelineStages
from src.scoring.distribution import score_distribution
from src.scrapers.storage import JobListingStorage


@pytest.fixture
def stages(sample_user_profile, temp_data_dir: Path) -> PipelineStages:
    """
    A PipelineStages instance backed by a temporary storage and results folder.

    Args:
        sample_user_profile: The shared sample profile fixture.
        temp_data_dir: The shared temporary folder fixture.

    Returns:
        The stages object.
    """
    context = PipelineContext(
        user_profile=sample_user_profile,
        storage=JobListingStorage(storage_dir=str(temp_data_dir / "listings")),
        results_dir=temp_data_dir / "results",
        config={"dry_run": True},
    )
    return PipelineStages(context)


def job(skills: list) -> SimpleNamespace:
    """
    A job with the given skill list.

    Args:
        skills: The job's structured skills.

    Returns:
        The fake job.
    """
    return SimpleNamespace(skills=skills)


def score(total: int, **breakdown: int) -> SimpleNamespace:
    """
    A match score with a total and a breakdown.

    Args:
        total: The total score.
        **breakdown: Points per component.

    Returns:
        The fake score.
    """
    return SimpleNamespace(total_score=total, breakdown=dict(breakdown))


def test_bands_and_cut_counts() -> None:
    """Each job lands in one 10-point band; 100 goes in the top band."""
    pairs = [
        (job(["python"]), score(5)),
        (job(["python"]), score(49)),
        (job(["python"]), score(50)),
        (job(["python"]), score(59)),
        (job(["python"]), score(60)),
        (job(["python"]), score(100)),
    ]

    result = score_distribution(pairs)

    assert result["count"] == 6
    assert result["bands"]["0-9"] == 1
    assert result["bands"]["40-49"] == 1
    assert result["bands"]["50-59"] == 2
    assert result["bands"]["60-69"] == 1
    assert result["bands"]["90-100"] == 1
    assert sum(result["bands"].values()) == 6
    assert result["at_or_above_50"] == 4
    assert result["at_or_above_60"] == 2


def test_component_means_over_all_jobs() -> None:
    """The mean of each component covers every scored job, below the cut-off too."""
    pairs = [
        (job(["a"]), score(40, projects=8, skills=12)),
        (job(["a"]), score(70, projects=20, skills=30)),
    ]

    result = score_distribution(pairs)

    assert result["component_means"] == {"projects": 14.0, "skills": 21.0}


def test_jobs_without_a_skill_list_are_counted_apart() -> None:
    """Jobs with no skill list get their own count, median, and cut counts."""
    pairs = [
        (job([]), score(53)),
        (job([]), score(61)),
        (job(["a"]), score(30)),
    ]

    result = score_distribution(pairs)

    no_skills = result["without_skill_list"]
    assert no_skills["count"] == 2
    assert no_skills["median"] == 57.0
    assert no_skills["at_or_above_50"] == 2
    assert no_skills["at_or_above_60"] == 1


def test_no_jobs_gives_zero_counts() -> None:
    """An empty run gives zero counts and no means."""
    result = score_distribution([])

    assert result["count"] == 0
    assert sum(result["bands"].values()) == 0
    assert result["component_means"] == {}
    assert result["without_skill_list"]["median"] is None


def test_a_score_without_a_breakdown_is_counted() -> None:
    """A score object with no breakdown dict still counts in the bands."""
    result = score_distribution([(job(["a"]), MagicMock(total_score=75))])

    assert result["bands"]["70-79"] == 1
    assert result["component_means"] == {}


def test_stage_metadata_describes_jobs_below_the_cut_off(
    stages, sample_job_listing
) -> None:
    """The stage keeps only jobs at the cut-off, but its metadata covers all jobs."""
    low = score(45, projects=10)
    high = score(70, projects=20)
    stages.job_matcher.score_job = MagicMock(side_effect=[low, high])

    result = stages.stage_score_and_rank(
        [sample_job_listing, sample_job_listing], min_score=60
    )

    assert result.success
    assert result.data == [(sample_job_listing, high)]
    distribution = result.metadata["distribution"]
    assert distribution["count"] == 2
    assert distribution["bands"]["40-49"] == 1
    assert distribution["bands"]["70-79"] == 1
    assert distribution["component_means"] == {"projects": 15.0}
    assert result.metadata["below_threshold"] == 1
