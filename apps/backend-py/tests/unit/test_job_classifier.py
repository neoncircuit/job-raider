"""
Tests for rule-based job classification.

Before 2026-10-18, ``_infer_work_pace`` returned ``WorkPace.FAST``, a member
that does not exist. Rule-based classification of any description with
"fast-paced", "rapidly", or "startup environment" raised ``AttributeError``,
and ``classify()`` reported a failure. mypy found it; no test covered it.
"""

import pytest

from src.classifiers.job_classifier import JobClassifier, WorkPace
from src.models.job_listing import JobListing, JobSource


def make_job(description: str) -> JobListing:
    """Build a minimal job listing with the given description.

    Args:
        description: Job description text.

    Returns:
        A job listing.
    """
    return JobListing(
        title="Software Engineer",
        company="Example Pte Ltd",
        location="Singapore",
        description=description,
        source=JobSource.MANUAL,
        job_id="classifier-test",
    )


@pytest.mark.parametrize(
    "description, expected",
    [
        ("Join our fast-paced team shipping weekly.", WorkPace.FAST_PACED),
        ("We are a startup environment that moves rapidly.", WorkPace.FAST_PACED),
        ("This role is demanding and deadline-driven.", WorkPace.HIGH_PRESSURE),
        ("We offer flexible hours and good balance.", WorkPace.RELAXED),
        ("Maintain internal reporting tools.", WorkPace.STEADY),
    ],
)
def test_infer_work_pace(description: str, expected: WorkPace) -> None:
    """Each pace keyword maps to an existing WorkPace member.

    Args:
        description: Job description text.
        expected: Expected work pace.
    """
    assert JobClassifier()._infer_work_pace(description.lower()) == expected


def test_rule_based_classification_succeeds_for_fast_paced_roles() -> None:
    """classify() without an LLM succeeds for a "fast-paced" description."""
    result = JobClassifier().classify(
        make_job("Fast-paced fintech team building payment APIs in Python."),
        use_llm=False,
    )

    assert result.success, result.errors
    assert result.classification is not None
    assert result.classification.work_pace == WorkPace.FAST_PACED
