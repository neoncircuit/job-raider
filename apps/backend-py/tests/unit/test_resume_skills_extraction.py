"""
Tests for verbatim Technical Skills section extraction in ResumeParser.
"""

from pathlib import Path

from src.extractors.resume_parser import ResumeParser
from src.generation.cover_letter_grounding import (
    collect_profile_technical_skills,
    flag_fabricated_technologies,
)
from src.models.user_profile import (
    ContactInfo,
    Skill,
    SkillCategory,
    UserProfile,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "resume"
    / "technical_skills_block.txt"
)

EXPECTED_TECHNICAL_SKILLS = [
    "Python",
    "TypeScript",
    "JavaScript",
    "SQL",
    "React",
    "Next.js",
    "FastAPI",
    "Convex",
    "Git",
    "Docker",
    "Inngest",
    "Letta",
    "PostgreSQL",
    "Model Evaluation",
    "Prompt Engineering",
    "RAG",
    "Vector Databases",
    "Agent Memory Systems",
    "REST APIs",
    "CI/CD",
    "Agile",
]


def _load_fixture() -> str:
    """Load the Technical Skills resume fixture text."""
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_technical_skills_section_returns_all_verbatim_tokens():
    """Deterministic section parse keeps every Technical Skills entry."""
    parser = ResumeParser()
    text = _load_fixture()
    section = parser._extract_technical_skills_section(text)
    assert section is not None
    tokens = parser._split_skill_tokens(section)
    assert tokens == EXPECTED_TECHNICAL_SKILLS


def test_skills_from_technical_section_count_matches_fixture():
    """Section-derived Skill list matches the fixture token count."""
    parser = ResumeParser()
    skills = parser._skills_from_technical_section(_load_fixture())
    names = [skill.name for skill in skills]
    assert names == EXPECTED_TECHNICAL_SKILLS
    assert len(skills) == len(EXPECTED_TECHNICAL_SKILLS)


def test_merge_skills_section_only_ignores_project_stack_extras():
    """When a Technical Skills section exists, project-only techs are excluded."""
    parser = ResumeParser()
    text = _load_fixture()
    section_skills = parser._skills_from_technical_section(text)
    llm_skills = [
        Skill(name="Machine Learning", category=SkillCategory.DOMAIN),
        Skill(name="Web Development", category=SkillCategory.DOMAIN),
        Skill(name="Google Gen AI", category=SkillCategory.TOOL),
        Skill(name="Azure OpenAI", category=SkillCategory.CLOUD),
        Skill(name="Qwen2.5 (Ollama)", category=SkillCategory.TOOL),
        Skill(name="Docker", category=SkillCategory.TOOL),  # also in section
        Skill(name="ExtraFromProjects", category=SkillCategory.TOOL),
    ]
    merged = parser._merge_skills(section_skills, llm_skills, text)
    names = [skill.name for skill in merged]
    assert names == EXPECTED_TECHNICAL_SKILLS
    assert len(merged) == len(EXPECTED_TECHNICAL_SKILLS)
    assert len({parser._normalize_skill_key(n) for n in names}) == len(names)
    assert "Google Gen AI" not in names
    assert "Azure OpenAI" not in names
    assert "Qwen2.5 (Ollama)" not in names
    assert "ExtraFromProjects" not in names
    assert "Machine Learning" not in names
    assert names.count("Docker") == 1


def test_merge_skills_fallback_when_no_section():
    """Without a Skills section, LLM/lexicon skills are used (filtered)."""
    parser = ResumeParser()
    text = "James Tan\nBuilt apps with Python and FastAPI.\n"
    llm_skills = [
        Skill(name="Python", category=SkillCategory.PROGRAMMING_LANGUAGE),
        Skill(name="FastAPI", category=SkillCategory.FRAMEWORK),
        Skill(name="Machine Learning", category=SkillCategory.DOMAIN),
        Skill(name="Python", category=SkillCategory.PROGRAMMING_LANGUAGE),
    ]
    merged = parser._merge_skills([], llm_skills, text)
    names = [skill.name for skill in merged]
    assert names == ["Python", "FastAPI"]
    assert "Machine Learning" not in names


def test_merge_skills_keeps_umbrella_from_section_when_present():
    """Umbrella labels listed in the Technical Skills section are kept."""
    parser = ResumeParser()
    text = "Technical Skills\nPython, Machine Learning\n\nExperience\nEngineer"
    section_skills = parser._skills_from_technical_section(text)
    llm_skills = [
        Skill(name="Web Development", category=SkillCategory.DOMAIN),
    ]
    merged = parser._merge_skills(section_skills, llm_skills, text)
    names = {skill.name for skill in merged}
    assert "Python" in names
    assert "Machine Learning" in names
    assert "Web Development" not in names


def test_create_profile_from_dict_maps_domains_and_databases():
    """Category keys domains/databases map onto SkillCategory enums."""
    parser = ResumeParser()
    profile = parser._create_profile_from_dict(
        {
            "basics": {
                "name": "Alex",
                "email": "a@example.com",
                "location": "Remote",
            },
            "skills": {
                "programming_languages": ["Python"],
                "databases": ["PostgreSQL"],
                "domains": ["Prompt Engineering"],
                "cloud": ["Azure"],
            },
        }
    )
    by_name = {skill.name: skill.category for skill in profile.skills}
    assert by_name["Python"] == SkillCategory.PROGRAMMING_LANGUAGE
    assert by_name["PostgreSQL"] == SkillCategory.DATABASE
    assert by_name["Prompt Engineering"] == SkillCategory.DOMAIN
    assert by_name["Azure"] == SkillCategory.CLOUD


def test_rule_based_parse_uses_section_only_when_present():
    """Rule-based parse keeps only Technical Skills section tokens."""
    parser = ResumeParser(llm_router=None)
    profile = parser.parse_text(_load_fixture())
    names = [skill.name for skill in profile.skills]
    assert names == EXPECTED_TECHNICAL_SKILLS
    assert "Machine Learning" not in names
    assert "Web Development" not in names
    assert "Google Gen AI" not in names
    assert "Azure OpenAI" not in names
    assert "Qwen2.5 (Ollama)" not in names


def test_cover_letter_grounding_allowlist_includes_section_skills():
    """Full profile.skills feed the cover-letter fabricated-tech allowlist."""
    skills = [
        Skill(name=name, category=SkillCategory.OTHER)
        for name in EXPECTED_TECHNICAL_SKILLS
    ]
    profile = UserProfile(
        name="James",
        contact=ContactInfo(email="j@example.com", location="Singapore"),
        skills=skills,
    )
    allowed = collect_profile_technical_skills(profile)
    assert "fastapi" in allowed
    assert "convex" in allowed
    assert "typescript" in allowed
    letter = (
        "I built services with FastAPI and Convex, and used TypeScript "
        "on the frontend with Docker."
    )
    fabricated = flag_fabricated_technologies(letter, profile)
    assert "fastapi" not in fabricated
    assert "typescript" not in fabricated
    # Convex may be absent from the curated detection lexicon; when present
    # in the letter lexicon match it must still be allowed via the profile.
    assert "convex" not in fabricated


AGENT_C_TECHS = [
    "Python",
    "Docker",
    "Convex",
    "Inngest",
    "Letta",
    "Google Gen AI",
    "Azure OpenAI",
]

JOB_RAIDER_TECHS = [
    "Python",
    "FastAPI",
    "Qwen2.5 (Ollama)",
    "Next.js",
]


def test_parse_project_tech_blocks_respects_project_boundaries():
    """Each project's tech line is parsed only from its own Projects block."""
    parser = ResumeParser()
    blocks = parser._parse_project_tech_blocks(_load_fixture())
    assert blocks["Agent-C (AI Singapore)"] == AGENT_C_TECHS
    assert blocks["Job Raider (Personal Project)"] == JOB_RAIDER_TECHS
    assert "PostgreSQL" not in blocks["Agent-C (AI Singapore)"]


def test_parse_project_tech_blocks_allows_blank_line_after_name():
    """PDF-style blank line between project name and tech stack still binds."""
    parser = ResumeParser()
    text = """
PROJECTS
Agent-C (AI Singapore)

Python, Docker, Convex, Inngest, Letta, Google Gen AI, Azure OpenAI

Job Raider (Personal Project)
Python, FastAPI, Qwen2.5 (Ollama), Next.js
"""
    blocks = parser._parse_project_tech_blocks(text)
    assert blocks["Agent-C (AI Singapore)"] == AGENT_C_TECHS
    assert "Docker" in blocks["Agent-C (AI Singapore)"]
    assert "Convex" in blocks["Agent-C (AI Singapore)"]
    assert blocks["Job Raider (Personal Project)"] == JOB_RAIDER_TECHS


def test_parse_project_tech_blocks_merges_wrapped_tech_lines():
    """Wrapped tech lines under one project are merged, not overwritten."""
    parser = ResumeParser()
    text = """
PROJECTS
Agent-C (AI Singapore)
Python, Docker, Convex, Inngest, Letta,
Google Gen AI, Azure OpenAI
"""
    blocks = parser._parse_project_tech_blocks(text)
    assert blocks["Agent-C (AI Singapore)"] == AGENT_C_TECHS


def test_parse_project_tech_blocks_ignores_prose_bullets_with_commas():
    """Comma-rich description bullets must not become technology pills."""
    parser = ResumeParser()
    blocks = parser._parse_project_tech_blocks(_load_fixture())
    assert blocks["Agent-C (AI Singapore)"] == AGENT_C_TECHS
    assert blocks["Job Raider (Personal Project)"] == JOB_RAIDER_TECHS
    joined = " ".join(token for techs in blocks.values() for token in techs).lower()
    assert "scam detection" not in joined
    assert "combining a rule-based" not in joined
    assert "evaluation graders" not in joined


def test_parse_project_tech_blocks_format_variants():
    """Pipe, blank-line, and wrap formats keep techs without ingesting prose."""
    parser = ResumeParser()
    variants = [
        """
PROJECTS
Agent-C (AI Singapore) | Python, Docker, Convex, Inngest, Letta, Google Gen AI, Azure OpenAI
- Built evaluation graders for memory agents, combining retrieval checks.
Job Raider (Personal Project): Python, FastAPI, Qwen2.5 (Ollama), Next.js
- Built a two-layer job scam detection system, combining a rule-based scoring engine.
""",
        """
PROJECTS
Agent-C (AI Singapore)

Python, Docker, Convex, Inngest, Letta,
Google Gen AI, Azure OpenAI

- Built evaluation graders for memory agents, combining retrieval checks.
Job Raider (Personal Project)

Python, FastAPI, Qwen2.5 (Ollama), Next.js
Built a two-layer job scam detection system, combining a rule-based scoring engine across five risk categories, keeping the system explainable.
""",
    ]
    for text in variants:
        blocks = parser._parse_project_tech_blocks(text)
        agent_key = next(key for key in blocks if "agent-c" in key.lower())
        raider_key = next(key for key in blocks if "job raider" in key.lower())
        assert blocks[agent_key] == AGENT_C_TECHS
        assert blocks[raider_key] == JOB_RAIDER_TECHS
        assert not any(
            "scam detection" in token.lower() for token in blocks[raider_key]
        )
        assert not any("combining" in token.lower() for token in blocks[agent_key])


def test_apply_section_project_technologies_fixes_misattribution():
    """Section overwrite removes Experience bleed and restores full Agent-C stack."""
    from src.models.user_profile import Project

    parser = ResumeParser()
    profile = UserProfile(
        name="James",
        contact=ContactInfo(email="j@example.com", location="Singapore"),
        projects=[
            Project(
                name="Agent-C",
                description="Memory agents",
                technologies=["Python", "Letta", "PostgreSQL"],
            ),
            Project(
                name="Job Raider",
                description="Job search",
                technologies=["Python", "FastAPI", "Qwen2.5 (Ollama)", "Next.js"],
            ),
        ],
    )
    parser._apply_section_project_technologies(profile, _load_fixture())
    by_name = {project.name: project.technologies for project in profile.projects}
    assert by_name["Agent-C"] == AGENT_C_TECHS
    assert "PostgreSQL" not in by_name["Agent-C"]
    assert by_name["Job Raider"] == JOB_RAIDER_TECHS


def test_dedupe_description_fills_from_first_highlight():
    """Empty description takes highlight[0] and drops it from the bullet list."""
    parser = ResumeParser()
    description, highlights = parser._dedupe_description_and_highlights(
        "",
        [
            "Built a pipeline in Python",
            "Improved accuracy from 52% to 78%",
        ],
    )
    assert description == "Built a pipeline in Python"
    assert highlights == ["Improved accuracy from 52% to 78%"]


def test_dedupe_description_drops_matching_first_highlight():
    """When description equals bullet 1, the bullet list starts at bullet 2."""
    parser = ResumeParser()
    summary = (
        "Built a two-layer job scam detection system, combining a "
        "rule-based scoring engine across five risk categories"
    )
    description, highlights = parser._dedupe_description_and_highlights(
        summary,
        [
            summary,
            "Designed a resume analysis module",
        ],
    )
    assert description == summary
    assert highlights == ["Designed a resume analysis module"]


def test_description_duplicates_technologies_detects_stack_line():
    """Tech-stack descriptions that match tag lists are flagged as duplicates."""
    parser = ResumeParser()
    techs = ["Python", "Docker", "Convex", "Inngest", "Letta"]
    assert parser._description_duplicates_technologies(
        "Python, Docker, Convex, Inngest, Letta",
        techs,
    )
    assert not parser._description_duplicates_technologies(
        "Built custom evaluation graders in Python",
        techs,
    )


def test_create_profile_dedupes_experience_and_project_descriptions():
    """Mapped experience/projects do not repeat description as highlight[0]."""
    parser = ResumeParser()
    summary = "Designed a two-stage KYC watchlist screening approach in PostgreSQL"
    profile = parser._create_profile_from_dict(
        {
            "basics": {
                "name": "James",
                "email": "j@example.com",
                "location": "Singapore",
            },
            "experience": [
                {
                    "title": "Analyst Programmer",
                    "company": "Phillip Securities",
                    "start_date": "2025-06",
                    "end_date": "2025-09",
                    "description": summary,
                    "highlights": [summary, "Performed real-time root cause analysis"],
                }
            ],
            "projects": [
                {
                    "name": "Agent-C",
                    "description": (
                        "Python, Docker, Convex, Inngest, Letta, "
                        "Google Gen AI, Azure OpenAI"
                    ),
                    "highlights": ["Built custom evaluation graders"],
                    "technologies": [
                        "Python",
                        "Docker",
                        "Convex",
                        "Inngest",
                        "Letta",
                        "Google Gen AI",
                        "Azure OpenAI",
                    ],
                },
                {
                    "name": "Job Raider",
                    "description": "",
                    "highlights": [
                        "Built a two-layer scam detector",
                        "Designed resume analysis grounding",
                    ],
                    "technologies": ["Python", "FastAPI"],
                },
            ],
        }
    )
    exp = profile.experience[0]
    assert exp.description == summary
    assert exp.highlights == ["Performed real-time root cause analysis"]
    agent_c = profile.projects[0]
    assert agent_c.description == ""
    assert agent_c.highlights == ["Built custom evaluation graders"]
    assert agent_c.technologies == [
        "Python",
        "Docker",
        "Convex",
        "Inngest",
        "Letta",
        "Google Gen AI",
        "Azure OpenAI",
    ]
    raider = profile.projects[1]
    assert raider.description == "Built a two-layer scam detector"
    assert raider.highlights == ["Designed resume analysis grounding"]


def test_apply_section_clears_tech_stack_description():
    """Section apply clears description when it only repeats technologies."""
    from src.models.user_profile import Project

    parser = ResumeParser()
    profile = UserProfile(
        name="James",
        contact=ContactInfo(email="j@example.com", location="Singapore"),
        projects=[
            Project(
                name="Agent-C",
                description=(
                    "Python, Docker, Convex, Inngest, Letta, "
                    "Google Gen AI, Azure OpenAI"
                ),
                technologies=["Python", "Letta"],
                highlights=["Built custom evaluation graders"],
            ),
        ],
    )
    parser._apply_section_project_technologies(profile, _load_fixture())
    project = profile.projects[0]
    assert project.technologies == AGENT_C_TECHS
    assert project.description == ""
    assert project.highlights == ["Built custom evaluation graders"]
