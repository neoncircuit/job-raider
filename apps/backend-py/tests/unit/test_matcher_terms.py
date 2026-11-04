"""Tests for whole-term matching and the description skill score (Step 3.4, R4)."""

import json
from pathlib import Path
from typing import List

import pytest

from src.models.job_listing import JobListing
from src.models.user_profile import UserProfile
from src.scoring.matcher import JobMatcher, ScoreCategory, term_in_text
from tests.unit.test_ranking_suite import job_with, profile_with

RANKING_SET = Path(__file__).resolve().parents[1] / "fixtures" / "eval" / "ranking"


@pytest.mark.parametrize(
    ("term", "text", "expected"),
    [
        ("ai", "Plan email campaigns and maintain retail training", False),
        ("ai", "Cook Thai food", False),
        ("ai", "Build AI features", True),
        ("ai", "Build AI-driven tools", True),
        ("java", "JavaScript and TypeScript with React", False),
        ("java", "Java, Kotlin, and Spring Boot", True),
        ("go", "good service, going further, Google, Django, MongoDB", False),
        ("go", "Write Go services", True),
        ("git", "Run digital campaigns", False),
        ("c++", "We use C++ and CUDA", True),
        ("c#", "Services in C# and .NET", True),
        (".net", "Services in C# and .NET", True),
        ("node.js", "Node.js with Express", True),
        ("machine learning", "Machine\n learning models", True),
        ("sql", "PostgreSQL databases", False),
        ("", "anything", False),
        ("", "", False),
        ("   ", "a  -  b", False),
    ],
)
def test_term_in_text_matches_whole_terms(term: str, text: str, expected: bool) -> None:
    """A term matches only as a whole term, in any case."""
    assert term_in_text(term, text) is expected


def keyword_profile(keywords: List[str]) -> UserProfile:
    """
    A profile with target keywords.

    Args:
        keywords: The target keywords.

    Returns:
        The profile.
    """
    profile = profile_with(["Python"])
    profile.targets.keywords = keywords
    return profile


def test_keywords_do_not_match_inside_words() -> None:
    """The keyword "AI" does not match email, maintain, retail, or training."""
    matcher = JobMatcher()
    trap = job_with(
        "j1", "Email Executive", "Maintain retail email lists and training."
    )
    real = job_with("j2", "AI Engineer", "Build AI features.")

    trap_score, trap_matched = matcher._score_keywords(trap, keyword_profile(["AI"]))
    real_score, real_matched = matcher._score_keywords(real, keyword_profile(["AI"]))

    assert trap_matched == [] and trap_score == 0
    assert real_matched == ["ai"] and real_score > 0


def test_keywords_in_requirements_match_whole_terms() -> None:
    """A requirement line counts only when the keyword is a whole term in it."""
    matcher = JobMatcher()
    job = JobListing.model_validate(
        {
            "job_id": "j1",
            "title": "Coordinator",
            "company": "Test Co",
            "source": "other",
            "requirements": [
                {"text": "Maintain the email lists"},
                {"text": "Some AI work"},
            ],
        }
    )

    _score, matched = matcher._score_keywords(job, keyword_profile(["AI", "Java"]))

    assert matched == ["ai"]
    job.requirements = job.requirements[:1]
    _score, matched = matcher._score_keywords(job, keyword_profile(["AI", "Java"]))
    assert matched == []


def test_description_skills_do_not_match_inside_words() -> None:
    """The skills "Go" and "Git" do not match good, going, Django, or digital."""
    matcher = JobMatcher()
    weight = matcher.weights[ScoreCategory.SKILLS]
    job = job_with(
        "j1", "Clerk", "Good service, going further, Django and digital work."
    )

    score, _missing = matcher._score_skills(job, profile_with(["Go", "Git", "Rust"]))

    assert score == weight // 2


@pytest.mark.parametrize(
    ("mentions", "expected"),
    [(0, 20), (1, 23), (2, 27), (3, 30), (4, 34), (5, 34)],
)
def test_description_skill_score_rises_with_each_match(
    mentions: int, expected: int
) -> None:
    """With the weight 40: half for no match, then higher for each match, up to 34."""
    skills = ["Python", "Docker", "Kafka", "Redis", "Terraform", "Rust"]
    text = " ".join(skills[:mentions]) or "No tools are named."
    matcher = JobMatcher()

    score, missing = matcher._score_skills(
        job_with("j1", "Engineer", text), profile_with(skills)
    )

    assert matcher.weights[ScoreCategory.SKILLS] == 40
    assert score == expected
    assert missing == []


def project_profile(technologies: List[str]) -> UserProfile:
    """
    A profile with one project.

    Args:
        technologies: The project's technologies.

    Returns:
        The profile.
    """
    return UserProfile.model_validate(
        {
            "name": "Test Person",
            "contact": {"email": "test@example.com", "location": "Singapore"},
            "projects": [
                {
                    "name": "Shop Front",
                    "description": "An online shop.",
                    "technologies": technologies,
                }
            ],
        }
    )


def skilled_job(skills: List[str]) -> JobListing:
    """
    A job with a required skill list.

    Args:
        skills: The required skills.

    Returns:
        The job.
    """
    return JobListing.model_validate(
        {
            "job_id": "j1",
            "title": "Engineer",
            "company": "Test Co",
            "source": "other",
            "description": "Build things.",
            "skills": [{"name": name} for name in skills],
        }
    )


def test_project_skills_match_whole_terms() -> None:
    """A JavaScript project earns no bonus for a Java job, but does for a JavaScript job."""
    matcher = JobMatcher(fresh_grad_mode=True)
    profile = project_profile(["JavaScript", "React"])

    java = matcher._score_projects(skilled_job(["Java"]), profile)
    javascript = matcher._score_projects(skilled_job(["JavaScript"]), profile)

    assert javascript > java


def test_field_match_uses_whole_terms() -> None:
    """The field "AI/ML" does not match a maintenance job, but matches an ML job."""
    maintenance = job_with("j1", "Maintenance Technician", "Maintain the machines.")
    ml_job = job_with("j2", "ML Engineer", "Train models.")

    assert JobMatcher._job_matches_field(maintenance, "AI/ML") is False
    assert JobMatcher._job_matches_field(ml_job, "AI/ML") is True


def test_ranking_set_traps_no_longer_match() -> None:
    """In the ranking set, the Java profile keyword does not match the JavaScript job."""
    profiles = json.loads((RANKING_SET / "profiles.json").read_text(encoding="utf-8"))
    lines = (RANKING_SET / "jobs.jsonl").read_text(encoding="utf-8").splitlines()
    jobs = {
        row["job_id"]: JobListing.model_validate(row)
        for row in (json.loads(line) for line in lines if line.strip())
    }
    backend = UserProfile.model_validate(profiles["mid_backend"])

    frontend = JobMatcher().score_job(jobs["rk-044"], backend)
    backend_job = JobMatcher().score_job(jobs["rk-036"], backend)

    assert "java" not in frontend.matched_keywords
    assert "java" in backend_job.matched_keywords
