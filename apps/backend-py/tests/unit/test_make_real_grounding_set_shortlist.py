"""Tests for shortlist items in the real-letter generator (Step 3.2, MH-A2)."""

from typing import Any, Dict

from scripts import make_real_grounding_set as gen
from src.models.job_listing import JobListing

LONG_TEXT = "We build payment services in Python and run them on PostgreSQL. " * 5


def shortlist_item(job: JobListing, **changes: Any) -> Dict[str, Any]:
    """Build one shortlist item as the Jobs page stores it.

    Args:
        job: The sample job.
        **changes: Fields to change.

    Returns:
        A shortlist item with the salary as display text and score fields.
    """
    item = dict(
        job.model_dump(mode="json"),
        description=LONG_TEXT,
        salary_range="SGD 9,000 - 18,000 (monthly)",
        relevance_score=72,
        matched_keywords=["Python"],
    )
    item.update(changes)
    return item


def test_a_display_salary_is_dropped(sample_job_listing: JobListing) -> None:
    """The shortlist's salary text does not stop the job; the salary is left out."""
    job = gen.shortlist_job(shortlist_item(sample_job_listing))

    assert job is not None
    assert job.job_id == sample_job_listing.job_id
    assert job.title == sample_job_listing.title
    assert job.salary_range is None


def test_pick_jobs_takes_shortlist_items(sample_job_listing: JobListing) -> None:
    """pick_jobs keeps real shortlist items, one per company."""
    items = [
        shortlist_item(sample_job_listing, job_id="j1", company="Acme Pay"),
        shortlist_item(sample_job_listing, job_id="j2", company="Beta Labs"),
    ]

    assert [job.job_id for job in gen.pick_jobs(items, limit=5)] == ["j1", "j2"]


def test_a_bad_required_field_skips_the_job(sample_job_listing: JobListing) -> None:
    """A job whose title does not validate is skipped, not changed."""
    assert gen.shortlist_job(shortlist_item(sample_job_listing, title=None)) is None
