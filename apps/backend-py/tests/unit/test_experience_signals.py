"""
Tests for the job-card-labels task: required years and fresh-grad-friendly postings.

- The detector meets the decision rule on the labelled set
  (``tests/fixtures/eval/experience_signals/cases.jsonl``): exact years on at
  least 90 % of the cases that state years, no invented years, fresh-grad
  precision 1.0 and recall at least 0.85.
- ``job_required_years`` prefers the structured years (change D) and falls
  back to the text, including text after the 5000-character cut of the API.
- The job API sends ``required_years`` and ``fresh_grad_friendly``.
- In fresh graduate mode a fresh-grad-friendly posting is not capped for its
  years; a senior role stays capped.
- The score distribution counts fresh-grad-friendly jobs.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from src.evaluation.suites.ranking import load_ranking_set
from src.models.job_listing import ExperienceLevel, JobListing, JobRequirement
from src.pipeline.shortlist import serialize_listing
from src.scoring.distribution import score_distribution
from src.scoring.matcher import JobMatcher

CASES_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "eval"
    / "experience_signals"
    / "cases.jsonl"
)


def load_cases() -> List[Dict[str, Any]]:
    """
    Load the labelled postings.

    Returns:
        The cases: ``case_id``, ``text``, ``years`` (number or None),
        ``fresh_grad`` (bool), ``note``.
    """
    lines = CASES_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@pytest.fixture(scope="module")
def fresh_ml() -> SimpleNamespace:
    """The `fresh_ml` profile and the ranking job rk-001 (a graduate ML job)."""
    data = load_ranking_set()
    job = next(job for job in data.jobs if job.job_id == "rk-001")
    return SimpleNamespace(profile=data.profiles["fresh_ml"], job=job)


def variant(
    job: JobListing,
    years: Optional[float] = None,
    extra_text: str = "",
    title: Optional[str] = None,
) -> JobListing:
    """
    A copy of a job at Mid Level with structured years and extra description text.

    Args:
        job: The base job.
        years: Structured required years, or None.
        extra_text: Text added to the end of the description.
        title: A new title, or None to keep it.

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
        update={
            "requirements": requirements,
            "experience_level": ExperienceLevel.MID,
            "description": f"{job.description or ''} {extra_text}".strip(),
            "title": title or job.title,
        }
    )


# --- Labelled set (decision rule E2 and E3) ----------------------------------


def test_labelled_set_is_complete() -> None:
    """The set has 40 cases with unique IDs, years and fresh-grad cases, and traps."""
    cases = load_cases()

    assert len(cases) == 40
    assert len({c["case_id"] for c in cases}) == 40
    assert sum(c["years"] is not None for c in cases) >= 20
    assert sum(c["fresh_grad"] for c in cases) >= 10


def test_years_meet_the_decision_rule() -> None:
    """Exact years on at least 90 % of the cases that state years; none invented."""
    from src.scoring.experience_signals import years_from_text

    cases = load_cases()
    stated = [c for c in cases if c["years"] is not None]
    none = [c for c in cases if c["years"] is None]

    exact = [c["case_id"] for c in stated if years_from_text(c["text"]) == c["years"]]
    invented = [c["case_id"] for c in none if years_from_text(c["text"]) is not None]

    assert len(exact) / len(stated) >= 0.9, sorted(
        {c["case_id"] for c in stated} - set(exact)
    )
    assert invented == []


def test_fresh_grad_meets_the_decision_rule() -> None:
    """Fresh-grad precision 1.0 and recall at least 0.85."""
    from src.scoring.experience_signals import is_fresh_grad_friendly

    cases = load_cases()
    found = {c["case_id"] for c in cases if is_fresh_grad_friendly(c["text"])}
    truth = {c["case_id"] for c in cases if c["fresh_grad"]}

    assert found - truth == set(), "false fresh-grad labels"
    assert len(found & truth) / len(truth) >= 0.85, sorted(truth - found)


# --- Required years of a job --------------------------------------------------


def test_structured_years_win_over_text(fresh_ml: SimpleNamespace) -> None:
    """The structured value decides when there is one; the text otherwise."""
    from src.scoring.experience_signals import job_required_years

    text_only = variant(fresh_ml.job, extra_text="At least 6 years of experience.")
    both = variant(fresh_ml.job, years=2, extra_text="At least 6 years of experience.")

    assert job_required_years(fresh_ml.job) is None
    assert job_required_years(text_only) == 6
    assert job_required_years(both) == 2


# --- The job API sends both values -------------------------------------------


def test_serializer_sends_required_years_and_fresh_grad(
    fresh_ml: SimpleNamespace,
) -> None:
    """``serialize_listing`` sends ``required_years`` and ``fresh_grad_friendly``."""
    friendly = variant(
        fresh_ml.job, years=4, extra_text="Fresh graduates are welcome to apply."
    )

    plain_data = serialize_listing(fresh_ml.job)
    friendly_data = serialize_listing(friendly)

    assert plain_data["required_years"] is None
    assert plain_data["fresh_grad_friendly"] is False
    assert friendly_data["required_years"] == 4
    assert friendly_data["fresh_grad_friendly"] is True


def test_serializer_reads_text_after_the_description_cut(
    fresh_ml: SimpleNamespace,
) -> None:
    """Signals after the 5000-character cut of the description still count."""
    filler = "We build things. " * 400  # about 6800 characters
    late = variant(
        fresh_ml.job,
        extra_text=filler + "At least 4 years of experience. Fresh grads may apply.",
    )

    data = serialize_listing(late)

    assert len(data["description"]) <= 5000
    assert data["required_years"] == 4
    assert data["fresh_grad_friendly"] is True


# --- The change D cap in fresh graduate mode ---------------------------------


def test_fresh_grad_friendly_lifts_the_years_cap(fresh_ml: SimpleNamespace) -> None:
    """A 6-year job that welcomes fresh graduates is not capped for its years."""
    matcher = JobMatcher(fresh_grad_mode=True)
    capped = variant(fresh_ml.job, years=6)
    friendly = variant(
        fresh_ml.job, years=6, extra_text="Fresh graduates are welcome to apply."
    )

    assert not matcher.score_job(capped, fresh_ml.profile).passed_threshold
    assert matcher.score_job(friendly, fresh_ml.profile).passed_threshold


def test_fresh_grad_friendly_keeps_the_senior_cap(fresh_ml: SimpleNamespace) -> None:
    """A senior title stays capped, even when the text welcomes fresh graduates."""
    matcher = JobMatcher(fresh_grad_mode=True)
    senior = variant(
        fresh_ml.job,
        extra_text="Fresh graduates are welcome to apply.",
        title="Senior Machine Learning Engineer",
    )

    assert not matcher.score_job(senior, fresh_ml.profile).passed_threshold


def test_text_years_do_not_cap(fresh_ml: SimpleNamespace) -> None:
    """Years found only in the text label the job but do not cap it (choice C1a)."""
    matcher = JobMatcher(fresh_grad_mode=True)
    text_years = variant(fresh_ml.job, extra_text="At least 6 years of experience.")

    assert matcher.score_job(text_years, fresh_ml.profile).passed_threshold


# --- Distribution ---------------------------------------------------------------


def test_distribution_counts_fresh_grad_friendly_jobs(
    fresh_ml: SimpleNamespace,
) -> None:
    """``fresh_grad_friendly`` counts scored jobs, numbers only."""
    matcher = JobMatcher(fresh_grad_mode=True)
    jobs = [
        fresh_ml.job,
        variant(fresh_ml.job, extra_text="Fresh graduates are welcome to apply."),
        variant(fresh_ml.job, extra_text="Fresh grads may apply."),
    ]
    pairs = [(job, matcher.score_job(job, fresh_ml.profile)) for job in jobs]

    assert score_distribution(pairs)["fresh_grad_friendly"] == 2
