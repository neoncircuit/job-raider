"""
Tests for pasted JD → structured JobListing helper and matcher honesty.
"""

from src.extractors.paste_job import build_job_listing_from_paste
from src.models.job_listing import JobListing, JobSource
from src.models.user_profile import ContactInfo, UserProfile
from src.models.user_profile import Skill as ProfileSkill
from src.scoring.matcher import JobMatcher, ScoreCategory

MESSY_PASTE = """
<div class="jobs-description">
We are hiring a Senior Python Engineer.&nbsp;
<br/><br/>
Requirements:
• 5+ years Python experience
• Strong Docker and Kubernetes skills
• Experience with React and TypeScript

Responsibilities:
• Build backend services
• Own production deployments

We are an equal opportunity employer and celebrate diversity.
</div>
"""


class TestBuildJobListingFromPaste:
    """Paste helper normalizes and extracts structure without LLM."""

    def test_strips_html_and_boilerplate(self) -> None:
        """HTML crumbs and EEO boilerplate are removed from description."""
        job = build_job_listing_from_paste(
            title="Senior Python Engineer",
            company="Acme",
            description=MESSY_PASTE,
            location="Remote",
            job_id="manual-test-1",
        )

        assert job.source == JobSource.MANUAL
        assert job.title == "Senior Python Engineer"
        assert job.company == "Acme"
        assert job.location == "Remote"
        assert job.job_id == "manual-test-1"
        assert "<div" not in (job.description or "")
        assert "&nbsp;" not in (job.description or "")
        assert "equal opportunity" not in (job.description or "").lower()
        assert "Python" in (job.description or "")

    def test_extracts_skills_from_paste_body(self) -> None:
        """Rule-based skill patterns populate job.skills from the paste."""
        job = build_job_listing_from_paste(
            title="Engineer",
            company="Acme",
            description=MESSY_PASTE,
        )
        skill_names = {s.name.lower() for s in job.skills}
        assert "python" in skill_names
        assert "docker" in skill_names
        assert "kubernetes" in skill_names
        assert "react" in skill_names
        assert "typescript" in skill_names

    def test_extracts_requirements_section(self) -> None:
        """Requirements section bullets become JobRequirement entries."""
        job = build_job_listing_from_paste(
            title="Engineer",
            company="Acme",
            description=MESSY_PASTE,
        )
        req_text = " ".join(r.text.lower() for r in job.requirements)
        assert "python" in req_text
        assert len(job.requirements) >= 1


class TestMatcherPasteHonesty:
    """Empty structured skills must not award full skills weight."""

    def _profile_with_skills(self, *names: str) -> UserProfile:
        """Build a minimal profile for matcher tests."""
        return UserProfile(
            name="Tester",
            contact=ContactInfo(email="t@example.com", location="Remote"),
            skills=[ProfileSkill(name=n) for n in names],
        )

    def test_empty_skills_without_overlap_is_mid_not_full(self) -> None:
        """No structured skills and no description hits → mid weight, not full."""
        matcher = JobMatcher()
        weight = matcher.weights[ScoreCategory.SKILLS]
        job = JobListing(
            title="Mystery Role",
            company="Co",
            job_id="j1",
            source=JobSource.MANUAL,
            description="A generalist role with unclear tooling.",
            skills=[],
        )
        profile = self._profile_with_skills("python", "docker", "kubernetes")
        score, missing = matcher._score_skills(job, profile)

        assert score == weight // 2
        assert missing == []
        assert score < weight

    def test_description_overlap_scores_below_full_weight(self) -> None:
        """Profile skills mentioned in description raise score but stay capped."""
        matcher = JobMatcher()
        weight = matcher.weights[ScoreCategory.SKILLS]
        job = JobListing(
            title="Python Engineer",
            company="Co",
            job_id="j2",
            source=JobSource.MANUAL,
            description="We need Python and Docker experience. Kubernetes is a plus.",
            skills=[],
        )
        profile = self._profile_with_skills("python", "docker", "kubernetes", "cobol")
        score, _missing = matcher._score_skills(job, profile)

        assert score > weight // 2
        assert score < weight
