"""
Tests that wipe-prone LLM JSON still maps Experience/Projects.
"""

from src.extractors.resume_parser import ResumeParser


def _minimal_basics() -> dict:
    """Return a minimal valid basics block for mapping tests."""
    return {
        "name": "James",
        "email": "j@example.com",
        "location": "Singapore",
    }


def test_create_profile_skips_null_experience_and_keeps_valid():
    """Null experience entries must not wipe the rest of the list."""
    parser = ResumeParser()
    profile = parser._create_profile_from_dict(
        {
            "basics": _minimal_basics(),
            "experience": [
                None,
                {
                    "title": "Analyst Programmer",
                    "company": "Phillip Securities",
                    "start_date": "2025-06",
                    "end_date": "2025-09",
                    "highlights": ["Built KYC screening"],
                },
            ],
            "target_job": None,
            "apprenticeship": None,
        }
    )
    assert len(profile.experience) == 1
    assert profile.experience[0].company == "Phillip Securities"
    assert profile.apprenticeship is None


def test_create_profile_keeps_project_with_scheme_less_url_and_null_sibling():
    """Scheme-less project URLs normalize; null siblings are skipped."""
    parser = ResumeParser()
    profile = parser._create_profile_from_dict(
        {
            "basics": _minimal_basics(),
            "projects": [
                {
                    "name": "Job Raider",
                    "description": "Job search assistant",
                    "technologies": ["Python", "FastAPI"],
                    "url": "github.com/example/job-raider",
                    "highlights": ["Built scam detection"],
                },
                None,
            ],
        }
    )
    assert len(profile.projects) == 1
    assert profile.projects[0].name == "Job Raider"
    assert str(profile.projects[0].url).startswith("https://github.com/")


def test_create_profile_drops_invalid_gpa_without_losing_education():
    """Non-numeric GPA is dropped; education entry is still kept."""
    parser = ResumeParser()
    profile = parser._create_profile_from_dict(
        {
            "basics": _minimal_basics(),
            "education": [
                {
                    "degree": "BSc Computer Science",
                    "school": "SIM / UoL",
                    "graduation_year": "2025",
                    "gpa": "N/A",
                }
            ],
        }
    )
    assert len(profile.education) == 1
    assert profile.education[0].school == "SIM / UoL"
    assert profile.education[0].gpa is None


def test_create_profile_uses_work_experience_alias():
    """Alternate work_experience key still populates experience."""
    parser = ResumeParser()
    profile = parser._create_profile_from_dict(
        {
            "basics": _minimal_basics(),
            "work_experience": [
                {
                    "title": "AI Associate Engineer",
                    "company": "AI Singapore",
                    "start_date": "2025-10",
                    "end_date": "present",
                    "highlights": ["Built memory pipeline"],
                }
            ],
        }
    )
    assert len(profile.experience) == 1
    assert profile.experience[0].title == "AI Associate Engineer"


def test_create_profile_null_nested_objects_do_not_raise():
    """Explicit null basics-adjacent objects still build a profile."""
    parser = ResumeParser()
    profile = parser._create_profile_from_dict(
        {
            "basics": _minimal_basics(),
            "skills": None,
            "experience": [
                {
                    "title": "Intern",
                    "company": "Acme",
                    "start_date": "2025-01",
                    "end_date": "2025-06",
                    "highlights": ["Did things"],
                }
            ],
            "projects": [
                {
                    "name": "Agent-C",
                    "description": "Memory agents",
                    "technologies": ["Python", "Letta"],
                    "highlights": ["Built graders"],
                }
            ],
            "target_job": None,
            "apprenticeship": None,
        }
    )
    assert len(profile.experience) == 1
    assert len(profile.projects) == 1
    assert profile.targets is not None
