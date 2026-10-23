"""
Tests for cover-letter grounding overlap checks.
"""

from datetime import datetime

from src.generation.cover_letter_grounding import (
    calc_grounding_penalty,
    collect_resume_bullets,
    flag_analogical_claims,
    flag_ungrounded_sentences,
    is_domain_mismatch,
    jd_resume_overlap_ratio,
    redact_unsupported_technologies,
    significant_words,
)
from src.models.job_listing import JobListing, JobRequirement, JobSource
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


def test_flag_fabricated_technologies_ignores_disclaimer_and_learn_intent():
    """Honest 'rather than Java' / 'pick up Java' is not a fabricated claim."""
    from src.generation.cover_letter_grounding import (
        extract_claimed_technologies,
        extract_technologies,
        flag_fabricated_technologies,
    )

    profile = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Singapore"),
        skills=[Skill(name="Python", category=SkillCategory.LANGUAGE)],
    )
    letter = (
        "While my hands-on experience has centered on Python rather than Java, "
        "I am eager to pick up Java quickly on the job."
    )
    assert "java" in extract_technologies(letter)
    assert "java" not in extract_claimed_technologies(letter)
    assert "python" in extract_claimed_technologies(letter)
    assert flag_fabricated_technologies(letter, profile) == []


def test_flag_fabricated_technologies_still_flags_false_claim():
    """A direct proficiency claim for a resume-absent tech is still flagged."""
    from src.generation.cover_letter_grounding import flag_fabricated_technologies

    profile = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Singapore"),
        skills=[Skill(name="Python", category=SkillCategory.LANGUAGE)],
    )
    letter = "I have strong Java experience and shipped Spring services in production."
    fabricated = flag_fabricated_technologies(letter, profile)
    assert "java" in fabricated


def test_flag_fabricated_technologies_claim_wins_over_disclaimer():
    """If the letter both disclaims and later claims a tech, flag the claim."""
    from src.generation.cover_letter_grounding import flag_fabricated_technologies

    profile = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        skills=[Skill(name="Python", category=SkillCategory.LANGUAGE)],
    )
    letter = (
        "I have used Python rather than Java in past roles. "
        "I also have strong Java experience from side projects."
    )
    assert "java" in flag_fabricated_technologies(letter, profile)


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


def test_merged_experience_years_sums_non_overlapping_roles():
    """Non-overlapping roles add; overlapping roles do not double-count."""
    from src.generation.cover_letter_grounding import merged_experience_years

    non_overlap = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        experience=[
            WorkExperience(
                title="Intern",
                company="Phillip",
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 7, 1),
            ),
            WorkExperience(
                title="Associate",
                company="AIAP",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2025, 1, 1),
            ),
        ],
    )
    years = merged_experience_years(non_overlap)
    assert 1.4 <= years <= 1.6

    overlap = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        experience=[
            WorkExperience(
                title="Role A",
                company="Corp",
                start_date=datetime(2020, 1, 1),
                end_date=datetime(2022, 1, 1),
            ),
            WorkExperience(
                title="Role B",
                company="Corp",
                start_date=datetime(2021, 1, 1),
                end_date=datetime(2023, 1, 1),
            ),
        ],
    )
    # Calendar coverage Jan 2020 -> Jan 2023 = 3 years, not 4.
    assert merged_experience_years(overlap) == 3.0


def test_flag_inflated_duration_claims_over_two_years():
    """Over 2 years is flagged when merged experience is about one year."""
    from src.generation.cover_letter_grounding import flag_inflated_duration_claims

    profile = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        experience=[
            WorkExperience(
                title="AIAP Associate",
                company="AIAP",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2025, 1, 1),
            ),
        ],
    )
    letter = (
        "Over 2 years of hands-on experience deploying machine learning "
        "models into production environments prepared me for this role."
    )
    findings = flag_inflated_duration_claims(letter, profile)
    assert findings
    assert findings[0]["claimed_years"] == 2.0
    assert findings[0]["cap_years"] <= 1.5
    assert any("Inflated duration" in flag for flag in findings[0]["flags"])


def test_flag_inconsistent_percent_claims_52_to_78_as_46():
    """Calling a 52%->78% absolute gain 'nearly 46%' is hard-flagged."""
    from src.generation.cover_letter_grounding import (
        flag_inconsistent_percent_claims,
    )

    letter = (
        "I enhanced model accuracy by nearly 46%, from 52% to 78%, on the "
        "ranking evaluation set."
    )
    findings = flag_inconsistent_percent_claims(letter)
    assert len(findings) == 1
    assert findings[0]["claimed_pct"] == 46.0
    assert findings[0]["from_pct"] == 52.0
    assert findings[0]["to_pct"] == 78.0
    assert any("Inconsistent metric" in flag for flag in findings[0]["flags"])


def test_flag_inconsistent_percent_claims_accepts_absolute_or_relative():
    """26 pp absolute or ~50% relative from 52->78 are both accepted."""
    from src.generation.cover_letter_grounding import (
        flag_inconsistent_percent_claims,
    )

    absolute_ok = (
        "I enhanced model accuracy by nearly 26%, from 52% to 78%, on the "
        "ranking evaluation set."
    )
    relative_ok = (
        "I enhanced model accuracy by nearly 50%, from 52% to 78%, on the "
        "ranking evaluation set."
    )
    assert flag_inconsistent_percent_claims(absolute_ok) == []
    assert flag_inconsistent_percent_claims(relative_ok) == []


def test_filter_resume_supported_keywords_drops_jd_only():
    """Selector keywords absent from resume skills/tech/corpus are dropped."""
    from src.generation.cover_letter_grounding import (
        filter_resume_supported_keywords,
    )

    profile = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        skills=[Skill(name="Python", category=SkillCategory.PROGRAMMING_LANGUAGE)],
        projects=[
            Project(
                name="Job Raider",
                description="Automated applications",
                technologies=["FastAPI"],
            )
        ],
    )
    kept = filter_resume_supported_keywords(
        ["Python", "FastAPI", "TensorFlow", "AWS"],
        profile,
    )
    assert kept == ["Python", "FastAPI"]


def test_calc_grounding_penalty_includes_duration_and_metric():
    """Inflated duration and inconsistent metrics add hard-band penalties."""
    duration = [
        {
            "sentence": "Over 2 years of ML deployment",
            "claimed_years": 2.0,
            "cap_years": 1.0,
            "flags": [
                "Inflated duration: claimed 2 years exceeds resume cap of 1 years"
            ],
        }
    ]
    metrics = [
        {
            "sentence": "enhanced by nearly 46%, from 52% to 78%",
            "from_pct": 52.0,
            "to_pct": 78.0,
            "claimed_pct": 46.0,
            "flags": ["Inconsistent metric: claimed 46%"],
        }
    ]
    penalty, breakdown = calc_grounding_penalty(
        [],
        [],
        inflated_duration_claims=duration,
        inconsistent_percent_claims=metrics,
    )
    assert breakdown["inflated_duration"] == 1
    assert breakdown["inconsistent_metric"] == 1
    assert penalty == 20
    assert breakdown["weights"]["inflated_duration"] == 10
    assert breakdown["weights"]["inconsistent_metric"] == 10


def test_redact_unsupported_technologies_strips_jd_only_stack():
    """JD-only tools are removed; resume-supported names stay."""
    profile = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        skills=[
            Skill(name="Python", category=SkillCategory.PROGRAMMING_LANGUAGE),
        ],
    )
    text = "We need Python, TensorFlow, AWS, and Kubernetes. " "React is a plus."
    redacted = redact_unsupported_technologies(text, profile)
    lowered = redacted.lower()
    assert "python" in lowered
    assert "tensorflow" not in lowered
    assert "aws" not in lowered
    assert "kubernetes" not in lowered
    assert "react" not in lowered


def _ai_engineering_profile() -> UserProfile:
    """Resume with Python / LlamaIndex evaluation work and no facilities duties."""
    return UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Singapore"),
        summary="AI Associate building evaluation pipelines with Python and LlamaIndex",
        skills=[
            Skill(name="Python", category=SkillCategory.PROGRAMMING_LANGUAGE),
            Skill(name="LlamaIndex", category=SkillCategory.FRAMEWORK),
        ],
        experience=[
            WorkExperience(
                title="AI Associate",
                company="AIAP",
                start_date=datetime(2024, 1, 1),
                highlights=["Built evaluation pipelines with LlamaIndex"],
            )
        ],
        projects=[
            Project(
                name="Job Raider",
                description="LLM job matching",
                technologies=["Python", "LlamaIndex"],
                highlights=["Evaluation pipelines for ranking"],
            )
        ],
    )


def _facilities_job() -> JobListing:
    """Mismatched facilities / property JD used to catch analogical bridges."""
    return JobListing(
        title="Facilities Coordinator",
        company="Property Co",
        job_id="fac-1",
        source=JobSource.MANUAL,
        description=(
            "Coordinate vendors, manage work orders, inspect property, "
            "update CMMS records, oversee HVAC contractors, and report "
            "facility statistics."
        ),
        requirements=[
            JobRequirement(text="Manage work orders and vendor contracts"),
            JobRequirement(text="Property inspections and facilities reporting"),
        ],
    )


def test_facilities_jd_is_domain_mismatch_against_ai_resume():
    """Facilities duties share little vocabulary with an AI engineering resume."""
    profile = _ai_engineering_profile()
    job = _facilities_job()
    assert jd_resume_overlap_ratio(job, profile) < 0.15
    assert is_domain_mismatch(job, profile) is True


def test_python_jd_is_not_domain_mismatch_against_python_resume():
    """Overlapping software-engineer JDs must not enter mismatch mode."""
    profile = _ai_engineering_profile()
    job = JobListing(
        title="Python Engineer",
        company="TechStartup Inc",
        job_id="py-1",
        source=JobSource.MANUAL,
        description="Build Python evaluation pipelines with LlamaIndex.",
        requirements=[
            JobRequirement(text="Python and LlamaIndex evaluation pipelines"),
        ],
    )
    assert is_domain_mismatch(job, profile) is False


def test_flag_analogical_claims_facilities_bridge():
    """Resume-true ML facts mapped onto work orders / facility stats are flagged."""
    profile = _ai_engineering_profile()
    job = _facilities_job()
    letter = (
        "My LlamaIndex evaluation pipelines are similar to the tasks of "
        "managing work orders. Advanced math prepared me for managing "
        "facility statistics."
    )
    findings = flag_analogical_claims(letter, profile, job)
    assert findings
    joined = " ".join(
        f"{item['sentence']} {' '.join(item['flags'])}" for item in findings
    ).lower()
    assert "work" in joined or "orders" in joined or "facility" in joined
    assert any(
        "analogical claim" in flag.lower()
        for item in findings
        for flag in item["flags"]
    )


def test_flag_analogical_claims_allows_in_domain_prepared_me_for():
    """Applying to a matching title with resume-supported duties is not analogical."""
    profile = _ai_engineering_profile()
    job = JobListing(
        title="Python Engineer",
        company="TechStartup Inc",
        job_id="py-2",
        source=JobSource.MANUAL,
        description="Build Python evaluation pipelines with LlamaIndex.",
        requirements=[
            JobRequirement(text="Python and LlamaIndex evaluation pipelines"),
        ],
    )
    letter = (
        "My LlamaIndex evaluation pipelines prepared me for this "
        "Python Engineer role at TechStartup Inc."
    )
    assert flag_analogical_claims(letter, profile, job) == []


def test_flag_analogical_claims_nearby_tech_stack():
    """Django analogized onto a React SPA JD is an analogical claim."""
    profile = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        skills=[Skill(name="Python", category=SkillCategory.PROGRAMMING_LANGUAGE)],
        projects=[
            Project(
                name="Shop API",
                description="Django REST API",
                technologies=["Python", "Django"],
            )
        ],
    )
    job = JobListing(
        title="Frontend Engineer",
        company="WebCo",
        job_id="fe-1",
        source=JobSource.MANUAL,
        description="Build React SPA dashboards with TypeScript.",
        requirements=[JobRequirement(text="React SPA and TypeScript")],
    )
    letter = "My Django REST work is similar to React SPA development."
    findings = flag_analogical_claims(letter, profile, job)
    assert findings
    joined = " ".join(flag for item in findings for flag in item["flags"]).lower()
    assert "react" in joined or "typescript" in joined or "spa" in joined


def test_calc_grounding_penalty_includes_analogical_claims():
    """Analogical bridges use the hard-band penalty and are not double-counted."""
    sentence = (
        "My evaluation pipelines are similar to the tasks of managing work orders"
    )
    analogical = [
        {
            "sentence": sentence,
            "flags": [
                "Analogical claim: resume work is mapped onto JD-only duties (orders)"
            ],
        }
    ]
    penalty, breakdown = calc_grounding_penalty(
        [sentence],
        [],
        analogical_claims=analogical,
    )
    assert breakdown["analogical_claim"] == 1
    assert breakdown["soft_ungrounded"] == 0
    assert penalty == 12
    assert breakdown["weights"]["analogical_claim"] == 12


def test_non_claim_sentences_are_not_flagged() -> None:
    """Greetings, sign-offs, thanks, interest, values, and plans are not claims."""
    resume = ["Wrote internal notes for a billing desk"]
    letter = (
        "Hello. "
        "Good day. "
        "Sincerely, Alex Kim. "
        "Best regards. "
        "Thank you for your time. "
        "I look forward to a conversation about the opening. "
        "I am excited about the mission of careful editing. "
        "I value clear notes and a calm review. "
        "I enjoy pairing with the editor on a draft. "
        "I would spend the first month learning the review checklist. "
        "If Northwind hired me, I would ask how the desk files a correction."
    )
    flagged = flag_ungrounded_sentences(letter, resume)
    assert flagged == []


def test_plan_with_a_claim_is_still_flagged() -> None:
    """A plan that states an unsupported fact is still checked."""
    resume = ["Wrote internal notes for a billing desk"]
    letter = "I would bring ten years of Kubernetes experience to this desk."
    flagged = flag_ungrounded_sentences(letter, resume)
    assert any("kubernetes" in sentence.lower() for sentence in flagged)


def test_thanks_does_not_hide_the_following_claim() -> None:
    """A thanks sentence is skipped, and the next claim sentence is not."""
    resume = ["Wrote internal notes for a billing desk"]
    letter = "Thank you. At my last job I cut costs by 90%."
    flagged = flag_ungrounded_sentences(letter, resume)
    assert not any(sentence.lower().startswith("thank") for sentence in flagged)
    assert any("90" in sentence for sentence in flagged)


def test_leading_greeting_clause_does_not_hide_a_claim() -> None:
    """A greeting clause before the claim does not raise the overlap enough to hide it."""
    resume = ["The dear hiring partner keeps a quiet weekly note"]
    letter = "Dear Hiring Partner, I invented a private ledger for the vault."
    flagged = flag_ungrounded_sentences(letter, resume)
    assert any("invented" in sentence.lower() for sentence in flagged)


def _billing_profile(highlights: list[str] | None = None) -> UserProfile:
    """Profile whose narrative mentions a billing desk and no extra metrics."""
    return UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        summary="I kept notes for a billing desk and rewrote the nightly job.",
        experience=[
            WorkExperience(
                title="Analyst",
                company="Northwind Desk",
                start_date=datetime(2020, 1, 1),
                end_date=datetime(2022, 1, 1),
                description="I kept notes for a billing desk and rewrote the nightly job.",
                highlights=highlights or ["I kept notes for a billing desk."],
            )
        ],
    )


def test_unsupported_percent_and_multiplier_are_flagged() -> None:
    """A percent or multiplier absent from the profile is an ungrounded claim."""
    from src.generation.cover_letter_grounding import flag_unsupported_number_sentences

    profile = _billing_profile()
    flagged = flag_unsupported_number_sentences(
        "I cut costs by 90% for the billing desk. "
        "I shipped features 3x faster during that same job.",
        profile,
    )
    joined = " ".join(flagged).lower()
    assert "90%" in joined
    assert "3x" in joined
    worded = flag_unsupported_number_sentences(
        "I cut costs by 90 percent for the billing desk.",
        profile,
    )
    assert any("90 percent" in sentence.lower() for sentence in worded)


def test_supported_count_in_other_words_is_not_flagged() -> None:
    """four engineers is supported when the profile text says 4."""
    from src.generation.cover_letter_grounding import flag_unsupported_number_sentences

    profile = _billing_profile(["The rotation had 4 people on the desk."])
    flagged = flag_unsupported_number_sentences(
        "I joined a rotation of four engineers on the billing desk.",
        profile,
    )
    assert flagged == []


def test_percent_words_match_a_percent_sign() -> None:
    """ninety percent matches a profile value written as 90%."""
    from src.generation.cover_letter_grounding import flag_unsupported_number_sentences

    profile = _billing_profile(["The desk cut wait time by 90%."])
    flagged = flag_unsupported_number_sentences(
        "I cut wait time by ninety percent on that desk.",
        profile,
    )
    assert flagged == []


def test_multiplier_words_match_a_suffix() -> None:
    """3 times matches a profile value written as 3x."""
    from src.generation.cover_letter_grounding import flag_unsupported_number_sentences

    profile = _billing_profile(["The trial shipped features 3x faster."])
    flagged = flag_unsupported_number_sentences(
        "I shipped features 3 times faster in the trial.",
        profile,
    )
    assert flagged == []


def test_plan_count_without_a_past_verb_is_not_flagged() -> None:
    """A plan that says one test is not an unsupported achievement count."""
    from src.generation.cover_letter_grounding import flag_unsupported_number_sentences

    profile = _billing_profile()
    flagged = flag_unsupported_number_sentences(
        "A good early task on the desk is one note about the change.",
        profile,
    )
    assert flagged == []


def test_duration_and_calendar_year_are_not_number_checked() -> None:
    """A duration and a calendar year are outside the unsupported-number check."""
    from src.generation.cover_letter_grounding import flag_unsupported_number_sentences

    profile = _billing_profile(["I used Python on the billing desk."])
    flagged = flag_unsupported_number_sentences(
        "I have five years of Python experience. I joined the lab in 2021.",
        profile,
    )
    assert flagged == []


def test_ordinary_english_homonyms_are_not_technologies() -> None:
    """swift, spring, spark, and express in ordinary English are not technologies."""
    from src.generation.cover_letter_grounding import extract_technologies

    letter = (
        "I sent a swift reply during the spring semester. "
        "I want to spark curiosity and express my interest in the work."
    )
    found = extract_technologies(letter)
    assert "swift" not in found
    assert "spring" not in found
    assert "spark" not in found
    assert "express" not in found


def test_homonyms_count_in_a_technology_context() -> None:
    """Product names and nearby technology words still count as technologies."""
    from src.generation.cover_letter_grounding import extract_technologies

    letter = (
        "I built the service with Spring Boot and an Express server. "
        "I wrote the batch jobs with Apache Spark. "
        "I shipped the mobile client in Swift for iOS."
    )
    found = extract_technologies(letter)
    assert {"spring", "express", "spark", "swift"} <= found


def test_go_matches_only_in_a_technology_context() -> None:
    """Go is a technology in 'written in Go', not in 'go live' or 'go through'."""
    from src.generation.cover_letter_grounding import extract_technologies

    ordinary = "I am ready to go live, and I will go through the checklist."
    assert "golang" not in extract_technologies(ordinary)
    technical = "The worker is written in Go and it exposes Go services."
    assert "golang" in extract_technologies(technical)


def test_negated_technology_claims_are_not_treated_as_skills() -> None:
    """'have not run', 'have never used', and 'do not have' are disclaimers."""
    from src.generation.cover_letter_grounding import extract_claimed_technologies

    letter = (
        "I have not run Kubernetes. "
        "I have never used Terraform. "
        "I do not have Azure experience."
    )
    claimed = extract_claimed_technologies(letter)
    assert "kubernetes" not in claimed
    assert "terraform" not in claimed
    assert "azure" not in claimed
    later = extract_claimed_technologies(
        "I have not run Kubernetes. I have run Kubernetes in production."
    )
    assert "kubernetes" in later


def test_sql_is_supported_when_the_profile_has_a_sql_database() -> None:
    """SQL is allowed when the profile lists PostgreSQL, and not otherwise."""
    from src.generation.cover_letter_grounding import flag_fabricated_technologies

    profile = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        skills=[Skill(name="PostgreSQL", category=SkillCategory.TOOL)],
    )
    letter = "I wrote SQL for the nightly reports."
    assert "sql" not in flag_fabricated_technologies(letter, profile)
    bare = UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        skills=[Skill(name="Python", category=SkillCategory.PROGRAMMING_LANGUAGE)],
    )
    assert "sql" in flag_fabricated_technologies(letter, bare)


def _skill_year_profile(skill_name: str, years: float) -> UserProfile:
    """Profile whose only duration cap is one skill's years of experience."""
    return UserProfile(
        name="Alex",
        contact=ContactInfo(email="a@example.com", location="Remote"),
        skills=[
            Skill(
                name=skill_name,
                category=SkillCategory.PROGRAMMING_LANGUAGE,
                years_of_experience=years,
            )
        ],
    )


def test_duration_range_uses_the_top_against_the_cap() -> None:
    """A range is inflated when its top is longer than the skill cap."""
    from src.generation.cover_letter_grounding import flag_inflated_duration_claims

    profile = _skill_year_profile("FastAPI", 3.0)
    digit = flag_inflated_duration_claims(
        "I have 3-5 years of FastAPI experience.",
        profile,
    )
    words = flag_inflated_duration_claims(
        "I have three to five years of FastAPI experience.",
        profile,
    )
    assert digit and digit[0]["claimed_years"] == 5.0
    assert words and words[0]["claimed_years"] == 5.0


def test_word_range_above_the_cap_is_flagged() -> None:
    """'two to four years' is flagged when the cap is 2."""
    from src.generation.cover_letter_grounding import flag_inflated_duration_claims

    profile = _skill_year_profile("Python", 2.0)
    findings = flag_inflated_duration_claims(
        "I have two to four years of Python experience.",
        profile,
    )
    assert findings
    assert findings[0]["claimed_years"] == 4.0


def test_range_within_the_cap_is_not_flagged() -> None:
    """'three to four years' is inside a cap of 4."""
    from src.generation.cover_letter_grounding import flag_inflated_duration_claims

    profile = _skill_year_profile("Python", 4.0)
    findings = flag_inflated_duration_claims(
        "I have three to four years of Python experience.",
        profile,
    )
    assert findings == []


def test_single_duration_number_stays_that_number() -> None:
    """'over 5 years' is still a claim of 5, not a range."""
    from src.generation.cover_letter_grounding import flag_inflated_duration_claims

    profile = _skill_year_profile("Python", 5.0)
    findings = flag_inflated_duration_claims(
        "I have over 5 years of Python experience.",
        profile,
    )
    assert findings == []
