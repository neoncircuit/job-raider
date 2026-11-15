"""
Tests for the project-scoring task: project points in fresh graduate mode.

Project points come from how many of a project's terms (its technologies, and
the profile skills that its text names) occur in the job text (title,
description, requirements, responsibilities, and skill names). The project
count alone does not add points, and one strong project counts more than one
weak hit in each project.
"""

from typing import Any, Dict, List, Optional

import pytest

from src.models.job_listing import JobListing
from src.models.user_profile import UserProfile
from src.scoring.matcher import JobMatcher, ScoreCategory


def make_profile(
    projects: List[Dict[str, Any]], skills: Optional[List[str]] = None
) -> UserProfile:
    """
    A profile with the given projects and skills.

    Args:
        projects: Project dicts (name, description, technologies).
        skills: Profile skill names.

    Returns:
        The profile.
    """
    return UserProfile.model_validate(
        {
            "name": "Test Person",
            "contact": {"email": "test@example.com", "location": "Singapore"},
            "skills": [{"name": name} for name in (skills or [])],
            "projects": projects,
        }
    )


def project(
    name: str, technologies: List[str], description: str = "A project."
) -> Dict[str, Any]:
    """
    A project dict.

    Args:
        name: The project name.
        technologies: The project's technologies.
        description: The project description.

    Returns:
        The project dict.
    """
    return {"name": name, "description": description, "technologies": technologies}


def make_job(
    description: str,
    title: str = "Engineer",
    skills: Optional[List[str]] = None,
    requirements: Optional[List[str]] = None,
    responsibilities: Optional[List[str]] = None,
) -> JobListing:
    """
    A job with the given text parts.

    Args:
        description: The job description.
        title: The job title.
        skills: Skill names of the structured skill list.
        requirements: Requirement texts.
        responsibilities: Responsibility texts.

    Returns:
        The job.
    """
    return JobListing.model_validate(
        {
            "job_id": "j1",
            "title": title,
            "company": "Test Co",
            "source": "other",
            "description": description,
            "skills": [{"name": name} for name in (skills or [])],
            "requirements": [{"text": text} for text in (requirements or [])],
            "responsibilities": [{"text": text} for text in (responsibilities or [])],
        }
    )


@pytest.fixture
def matcher() -> JobMatcher:
    """A matcher in fresh graduate mode."""
    return JobMatcher(fresh_grad_mode=True)


ML_PROFILE = make_profile(
    [project("Leaf Classifier", ["PyTorch", "Docker", "FastAPI"])]
)


def test_job_text_without_a_skill_list_counts(matcher: JobMatcher) -> None:
    """A job that names the project's tools in its text gets more points than one that names none."""
    relevant = make_job("You will train models in PyTorch and serve them with FastAPI.")
    unrelated = make_job("You will plan store layouts and manage suppliers.")

    assert matcher._score_projects(relevant, ML_PROFILE) > matcher._score_projects(
        unrelated, ML_PROFILE
    )


@pytest.mark.parametrize("part", ["requirements", "responsibilities", "title"])
def test_requirements_responsibilities_and_title_count(
    matcher: JobMatcher, part: str
) -> None:
    """A project term in the requirements, the responsibilities, or the title counts."""
    named: Dict[str, Any] = {"description": "Join our team."}
    other: Dict[str, Any] = {"description": "Join our team."}
    if part == "title":
        named["title"], other["title"] = "PyTorch Engineer", "Excel Engineer"
    else:
        named[part], other[part] = ["Experience with PyTorch"], [
            "Experience with Excel"
        ]

    assert matcher._score_projects(
        make_job(**named), ML_PROFILE
    ) > matcher._score_projects(make_job(**other), ML_PROFILE)


def test_profile_skill_named_in_project_text_counts(matcher: JobMatcher) -> None:
    """A profile skill that the project description names counts as a project term."""
    proj = [project("Leaf Classifier", [], "An image classifier trained in PyTorch.")]
    with_skill = make_profile(proj, skills=["PyTorch"])
    without_skill = make_profile(proj, skills=["Excel"])
    job = make_job("You will train models in PyTorch.")

    assert matcher._score_projects(job, with_skill) > matcher._score_projects(
        job, without_skill
    )


def test_job_text_matches_whole_terms(matcher: JobMatcher) -> None:
    """A JavaScript project gets a hit from a JavaScript job text, not from a Java job text."""
    profile = make_profile([project("Shop Front", ["JavaScript"])])
    java = make_job("You will build services in Java.")
    javascript = make_job("You will build pages in JavaScript.")

    assert matcher._score_projects(javascript, profile) > matcher._score_projects(
        java, profile
    )


def test_project_count_alone_adds_no_points(matcher: JobMatcher) -> None:
    """Three unrelated projects get no more points than one unrelated project."""
    one = make_profile([project("Leaf Classifier", ["PyTorch"])])
    three = make_profile(
        [
            project("Leaf Classifier", ["PyTorch"]),
            project("Chat Bot", ["LangChain"]),
            project("Game", ["Unity"]),
        ]
    )
    job = make_job("You will plan store layouts.", skills=["Excel"])

    assert matcher._score_projects(job, three) <= matcher._score_projects(job, one)


def test_one_strong_project_beats_one_weak_hit_in_each(matcher: JobMatcher) -> None:
    """A job that fits one project well gets more points than one weak hit per project."""
    profile = make_profile(
        [
            project("Leaf Classifier", ["PyTorch", "Docker", "FastAPI"]),
            project("Shop Front", ["React"]),
            project("Budget Sheet", ["Excel"]),
        ]
    )
    strong = make_job("Build models.", skills=["PyTorch", "Docker", "FastAPI"])
    spread = make_job("Build things.", skills=["PyTorch", "React", "Excel"])

    assert matcher._score_projects(strong, profile) > matcher._score_projects(
        spread, profile
    )


def test_points_stay_within_the_weight(matcher: JobMatcher) -> None:
    """Points stay within 0 and 35; a profile with no projects gets a quarter."""
    weight = matcher.weights[ScoreCategory.PROJECTS]
    job = make_job(
        "PyTorch Docker FastAPI LangChain React",
        skills=["PyTorch", "Docker", "FastAPI", "LangChain", "React"],
    )
    full = make_profile(
        [
            project("A", ["PyTorch", "Docker", "FastAPI"]),
            project("B", ["LangChain", "Docker", "PyTorch"]),
            project("C", ["React", "FastAPI", "Docker"]),
        ]
    )

    assert 0 <= matcher._score_projects(job, full) <= weight
    assert matcher._score_projects(job, make_profile([])) == weight // 4


def test_standard_mode_has_no_project_part() -> None:
    """Standard mode does not score projects."""
    score = JobMatcher().score_job(make_job("PyTorch"), ML_PROFILE)

    assert ScoreCategory.PROJECTS.value not in score.breakdown
