"""
Tests for the per-rule removal counts of the profile filter (scoring-calibration task).

The profile filter removed half of the scraped jobs before scoring, and the
run recorded only the totals. The filter now records how many jobs each rule
removed (``no_keyword_match``, ``remote``, ``salary``, ``internship``,
``experience_level``), and the filter stage copies the counts into its
metadata. A job counts under the first rule that removes it, in the order the
filter checks the rules. The kept jobs do not change.
"""

from pathlib import Path

import pytest

from src.models.job_listing import ExperienceLevel, JobListingCollection
from src.pipeline.stages import PipelineContext, PipelineStages
from src.scoring.filter import JobFilter
from src.scrapers.storage import JobListingStorage


def targets(profile, **changes):
    """
    A copy of the profile with changed targets.

    Args:
        profile: The sample profile.
        **changes: Target fields to change.

    Returns:
        The profile copy.
    """
    return profile.model_copy(
        update={"targets": profile.targets.model_copy(update=changes)}
    )


def listing(base, job_id: str, **changes):
    """
    A copy of the sample job with a new ID and changed fields.

    Args:
        base: The sample job.
        job_id: The new job ID.
        **changes: Job fields to change.

    Returns:
        The job copy.
    """
    return base.model_copy(update={"job_id": job_id, **changes})


def run_filter(jobs, profile):
    """
    Run the profile filter on the jobs.

    Args:
        jobs: The job listings.
        profile: The profile.

    Returns:
        The filtered collection.
    """
    return JobFilter().filter_by_profile(JobListingCollection(listings=jobs), profile)


def test_no_keyword_match_is_counted(sample_job_listing, sample_user_profile) -> None:
    """A job with none of the target keywords counts as no_keyword_match."""
    profile = targets(sample_user_profile, keywords=["rust"], exclude_internships=False)
    jobs = [
        listing(sample_job_listing, "a"),
        listing(sample_job_listing, "b", title="Rust Engineer"),
    ]

    result = run_filter(jobs, profile)

    assert [j.job_id for j in result.listings] == ["b"]
    assert result.metadata["removed_by"]["no_keyword_match"] == 1


def test_remote_rule_is_counted(sample_job_listing, sample_user_profile) -> None:
    """With remote only, a job that is not remote counts as remote."""
    profile = targets(
        sample_user_profile,
        keywords=["python"],
        remote_preference=True,
        exclude_internships=False,
    )
    jobs = [
        listing(sample_job_listing, "a", is_remote=False),
        listing(sample_job_listing, "b", is_remote=True),
    ]

    result = run_filter(jobs, profile)

    assert [j.job_id for j in result.listings] == ["b"]
    assert result.metadata["removed_by"]["remote"] == 1


def test_internship_rule_is_counted(sample_job_listing, sample_user_profile) -> None:
    """With internships excluded, an internship job counts as internship."""
    profile = targets(
        sample_user_profile, keywords=["python"], exclude_internships=True
    )
    jobs = [
        listing(sample_job_listing, "a", title="Python Internship"),
        listing(sample_job_listing, "b"),
    ]

    result = run_filter(jobs, profile)

    assert [j.job_id for j in result.listings] == ["b"]
    assert result.metadata["removed_by"]["internship"] == 1


def test_experience_level_rule_is_counted(
    sample_job_listing, sample_user_profile
) -> None:
    """In filter mode with target levels, another stated level counts as experience_level."""
    profile = targets(
        sample_user_profile,
        keywords=["python"],
        constraint_mode="filter",
        experience_levels=[ExperienceLevel.ENTRY],
        exclude_internships=False,
    )
    jobs = [
        listing(sample_job_listing, "a", experience_level=ExperienceLevel.SENIOR),
        listing(sample_job_listing, "b", experience_level=ExperienceLevel.ENTRY),
    ]

    result = run_filter(jobs, profile)

    assert [j.job_id for j in result.listings] == ["b"]
    assert result.metadata["removed_by"]["experience_level"] == 1


def test_counts_add_up_to_the_removed_jobs(
    sample_job_listing, sample_user_profile
) -> None:
    """Every removed job counts once; all rules appear, also with zero."""
    profile = targets(sample_user_profile, keywords=["rust"], exclude_internships=True)
    jobs = [
        listing(sample_job_listing, "a"),
        listing(sample_job_listing, "b", title="Rust Internship"),
        listing(sample_job_listing, "c", title="Rust Engineer"),
    ]

    result = run_filter(jobs, profile)
    removed_by = result.metadata["removed_by"]

    assert set(removed_by) == {
        "no_keyword_match",
        "remote",
        "salary",
        "internship",
        "experience_level",
    }
    assert sum(removed_by.values()) == len(jobs) - len(result.listings) == 2


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
        user_profile=targets(
            sample_user_profile, keywords=["rust"], exclude_internships=False
        ),
        storage=JobListingStorage(storage_dir=str(temp_data_dir / "listings")),
        results_dir=temp_data_dir / "results",
        config={"dry_run": True},
    )
    return PipelineStages(context)


def test_filter_stage_metadata_has_the_counts(stages, sample_job_listing) -> None:
    """The filter stage copies the per-rule counts into its metadata."""
    jobs = [
        listing(sample_job_listing, "a"),
        listing(sample_job_listing, "b", title="Rust Engineer"),
    ]

    result = stages.stage_filter_by_profile(jobs)

    assert result.success
    assert result.metadata["removed_count"] == 1
    assert result.metadata["removed_by"]["no_keyword_match"] == 1
