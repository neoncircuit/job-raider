"""
Tests for cover-letter grounding overlap checks.
"""

from datetime import datetime

from src.generation.cover_letter_grounding import (
    calc_grounding_penalty,
    collect_resume_bullets,
    flag_ungrounded_sentences,
    significant_words,
)
from src.models.user_profile import (
    ContactInfo,
    Project,
    Skill,
    SkillCategory,
    UserProfile,
    WorkExperience,
)


def test_significant_words_filters_stopwords_and_short_tokens():
    """Short tokens and stopwords are dropped from overlap vocabulary."""
    words = significant_words("I will deploy the API with Python and FastAPI")
    assert "will" not in words
    assert "with" not in words
    assert "the" not in words
    assert "python" in words
    assert "fastapi" in words
    assert "deploy" in words


def test_calc_grounding_penalty_weights_severity():
    """Soft vague overlap costs less than fabricated scope or hard overclaims."""
    soft_only, soft_breakdown = calc_grounding_penalty(
        ["I am excited about this opportunity to contribute meaningfully"],
        [],
    )
    hard_only, hard_breakdown = calc_grounding_penalty(
        ["I have deployed production systems at scale"],
        [],
    )
    scope_only, scope_breakdown = calc_grounding_penalty(
        [],
        [
            {
                "sentence": "Leading the development of Job Raider improved throughput",
                "flags": ["Scope inflation: 'leading the'"],
            }
        ],
    )
    mixed, mixed_breakdown = calc_grounding_penalty(
        [
            "I am excited about this opportunity to contribute meaningfully",
            "I have deployed production systems at scale",
        ],
        [
            {
                "sentence": "Leading the development of Job Raider improved throughput",
                "flags": ["Scope inflation: 'leading the'"],
            },
            {
                "sentence": "On Job Raider I used retrieval methods",
                "flags": ["Technique mismatch: 'retrieval'"],
            },
        ],
    )

    assert soft_breakdown["soft_ungrounded"] == 1
    assert soft_breakdown["hard_ungrounded"] == 0
    assert soft_only == 3

    assert hard_breakdown["hard_ungrounded"] == 1
    assert hard_only == 10
    assert hard_only > soft_only

    assert scope_breakdown["scope_inflation"] == 1
    assert scope_only == 12
    assert scope_only > soft_only

    assert mixed_breakdown["soft_ungrounded"] == 1
    assert mixed_breakdown["hard_ungrounded"] == 1
    assert mixed_breakdown["scope_inflation"] == 1
    assert mixed_breakdown["technique_mismatch"] == 1
    assert mixed == 3 + 10 + 12 + 10
    assert mixed > soft_only
    assert mixed > hard_only


def test_calc_grounding_penalty_avoids_double_count():
    """Sentences already in claim_overclaims are not also soft/hard-penalized."""
    sentence = "Leading the development of Job Raider improved throughput"
    penalty, breakdown = calc_grounding_penalty(
        [sentence],
        [{"sentence": sentence, "flags": ["Scope inflation: 'leading the'"]}],
    )
    assert breakdown["soft_ungrounded"] == 0
    assert breakdown["hard_ungrounded"] == 0
    assert breakdown["scope_inflation"] == 1
    assert penalty == 12


def test_calc_grounding_penalty_is_capped():
    """Many findings do not exceed the max grounding penalty."""
    many_scope = [
        {
            "sentence": f"Leading the development of project {i}",
            "flags": ["Scope inflation: 'leading the'"],
        }
        for i in range(10)
    ]
    penalty, breakdown = calc_grounding_penalty([], many_scope)
    assert breakdown["raw_penalty"] == 120
    assert penalty == 50
    assert breakdown["capped_penalty"] == 50


def test_flag_ungrounded_closing_flourish():
    """Closing pitch with ungrounded overclaim verbs is flagged."""
    resume = [
        "Built Job Raider with FastAPI and PostgreSQL",
        "Designed schema for multi-tenant listings",
        "Trained 6+ model variants for ranking",
    ]
    letter = (
        "At Acme I would apply my FastAPI and PostgreSQL experience from Job Raider. "
        "I designed a schema for multi-tenant listings and trained 6+ model variants. "
        "I look forward to helping Acme transition complex ML proofs into "
        "dependable, deployed solutions."
    )
    flagged = flag_ungrounded_sentences(letter, resume)
    assert flagged
    assert any("deployed" in sentence.lower() for sentence in flagged)


def test_flag_keeps_grounded_sentences():
    """Sentences restating resume facts are not flagged."""
    resume = [
        "Built Job Raider with FastAPI and PostgreSQL",
        "Reduced API latency by 40 percent",
    ]
    letter = (
        "My work on Job Raider with FastAPI and PostgreSQL maps directly to this role. "
        "I reduced API latency by 40 percent on that stack. "
        "Thank you for considering my application."
    )
    flagged = flag_ungrounded_sentences(letter, resume, min_overlap_ratio=0.25)
    # CTA may be weakly grounded; body claims should not be flagged.
    assert not any("Job Raider" in sentence for sentence in flagged)
    assert not any("40 percent" in sentence for sentence in flagged)


def test_collect_resume_bullets_includes_highlights():
    """Profile highlights and project tech enter the grounding corpus."""
    profile = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        skills=[Skill(name="Python", category=SkillCategory.PROGRAMMING_LANGUAGE)],
        projects=[
            Project(
                name="Job Raider",
                description="Automated applications",
                technologies=["FastAPI", "PostgreSQL"],
                highlights=["6+ model variants"],
            )
        ],
        experience=[
            WorkExperience(
                title="Engineer",
                company="Corp",
                start_date=datetime(2020, 1, 1),
                highlights=["Designed PostgreSQL schemas"],
            )
        ],
    )
    bullets = collect_resume_bullets(profile)
    joined = " ".join(bullets).lower()
    assert "job raider" in joined
    assert "fastapi" in joined
    assert "postgresql" in joined
    assert "6+" in joined or "model" in joined


def test_flag_scope_inflation_even_when_overlap_is_high():
    """Leadership phrasing is flagged even inside an otherwise grounded sentence."""
    from src.generation.cover_letter_grounding import (
        flag_scope_and_technique_overclaims,
    )

    flags = flag_scope_and_technique_overclaims(
        "Leading the development of Job Raider with FastAPI and PostgreSQL.",
        "Job Raider",
        {"Job Raider": ["FastAPI", "PostgreSQL", "Built", "Designed"]},
        resume_bullets=["Built Job Raider with FastAPI", "Designed PostgreSQL schemas"],
    )
    assert flags
    assert any("Scope inflation" in flag for flag in flags)


def test_flag_technique_mismatch_for_wrong_project():
    """Technique terms must belong to the referenced project, not another one."""
    from src.generation.cover_letter_grounding import (
        flag_scope_and_technique_overclaims,
    )

    techniques = {
        "Job Raider": ["rule-based scoring", "local LLM classification", "FastAPI"],
        "Mandai chatbot": ["RAG", "retrieval", "vector search"],
    }
    flags = flag_scope_and_technique_overclaims(
        "On Job Raider I improved scam detection using retrieval methods.",
        "Job Raider",
        techniques,
        resume_bullets=["Job Raider uses rule-based scoring and a local LLM"],
    )
    assert flags
    assert any("Technique mismatch" in flag and "retrieval" in flag for flag in flags)


def test_flag_claim_overclaims_scans_full_letter():
    """Letter-level scan returns sentence + flag pairs for both failure modes."""
    from src.generation.cover_letter_grounding import flag_claim_overclaims

    profile = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        projects=[
            Project(
                name="Job Raider",
                description="Rule-based scoring and local LLM classification",
                technologies=["FastAPI"],
                highlights=["Built", "Designed", "Improved"],
            ),
            Project(
                name="Mandai chatbot",
                description="RAG retrieval over park documents",
                technologies=["vector search"],
                highlights=["retrieval"],
            ),
        ],
    )
    letter = (
        "Leading the development of Job Raider improved FastAPI throughput. "
        "On Job Raider I improved scam detection using retrieval methods. "
        "Thank you for considering my application."
    )
    findings = flag_claim_overclaims(letter, profile)
    assert len(findings) >= 2
    joined_flags = " ".join(flag for item in findings for flag in item["flags"]).lower()
    assert "scope inflation" in joined_flags
    assert "technique mismatch" in joined_flags


def _docker_only_profile() -> UserProfile:
    """Profile whose Technical Skills list contains Docker only."""
    return UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        skills=[
            Skill(name="Docker", category=SkillCategory.TOOL),
            Skill(name="Communication", category=SkillCategory.SOFT_SKILL),
            Skill(name="English", category=SkillCategory.LANGUAGE),
        ],
    )


def test_flag_fabricated_technologies_jd_only_stack():
    """JD-only AWS/K8s/Mongo/Redis claims are hard-flagged; Docker is allowed."""
    from src.generation.cover_letter_grounding import flag_fabricated_technologies

    profile = _docker_only_profile()
    letter = (
        "I containerized services with Docker and also operated AWS, "
        "Kubernetes, MongoDB, and Redis in production."
    )
    fabricated = flag_fabricated_technologies(letter, profile)
    assert fabricated == ["aws", "kubernetes", "mongodb", "redis"]
    assert "docker" not in fabricated


def test_flag_fabricated_technologies_empty_when_resume_skills_only():
    """Letter that only names resume Technical Skills yields no fabrications."""
    from src.generation.cover_letter_grounding import flag_fabricated_technologies

    profile = _docker_only_profile()
    letter = "I package services with Docker for reliable local delivery."
    assert flag_fabricated_technologies(letter, profile) == []


def test_flag_fabricated_technologies_alias_k8s_allowed():
    """Letter K8s is allowed when resume lists Kubernetes."""
    from src.generation.cover_letter_grounding import flag_fabricated_technologies

    profile = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        skills=[Skill(name="Kubernetes", category=SkillCategory.TOOL)],
    )
    letter = "I operate K8s clusters for batch workloads."
    assert flag_fabricated_technologies(letter, profile) == []


def test_calc_grounding_penalty_includes_fabricated_tech():
    """Each fabricated technology adds a hard-band penalty."""
    baseline, _ = calc_grounding_penalty([], [])
    with_tech, breakdown = calc_grounding_penalty(
        [],
        [],
        fabricated_technologies=["aws", "kubernetes", "mongodb", "redis"],
    )
    assert baseline == 0
    assert breakdown["fabricated_tech"] == 4
    assert with_tech == 40
    assert breakdown["weights"]["fabricated_tech"] == 10
