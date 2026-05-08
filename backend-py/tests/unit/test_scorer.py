# Unit tests for scoring module
# Author: Job Raider
# Date: 2026-04-21

import pytest
from datetime import datetime

from src.scoring.matcher import JobMatcher, MatchScore
from src.scoring.filter import JobFilter
from src.models.user_profile import (
    UserProfile,
    ContactInfo,
    Skill,
    SkillCategory,
    ProficiencyLevel,
    Project,
    TargetJob,
    WorkExperience,
)
from src.models.job_listing import JobListing, JobSource, JobRequirement, Skill as JobSkill
from src.models.job_listing import ExperienceLevel


class TestJobMatcher:
    """Tests for JobMatcher class."""

    def test_initialization(self):
        """Test matcher initialization."""
        matcher = JobMatcher()
        assert matcher is not None

    def test_match_perfect_fit(self, sample_user_profile, sample_job_listing):
        """Test matching with perfect fit job."""
        matcher = JobMatcher()
        score = matcher.score_job(sample_job_listing, sample_user_profile)

        assert score is not None
        assert score.total_score > 60  # Should be high for a good fit
        assert score.breakdown["keyword"] > 0
        assert score.breakdown["skills"] > 0

    def test_match_partial_fit(self, sample_user_profile):
        """Test matching with partial fit job."""
        job = JobListing(
            title="Java Developer",  # Different tech stack
            company="Tech Corp",
            location="Remote",
            description="Java developer position",
            requirements=[JobRequirement(text="5+ years Java experience")],
            skills=[JobSkill(name="java"), JobSkill(name="spring")],
            source=JobSource.LINKEDIN,
            job_id="job_java",
        )

        matcher = JobMatcher()
        score = matcher.score_job(job, sample_user_profile)

        assert score is not None
        assert score.total_score < 70  # Should be lower for partial fit
        assert score.breakdown["skills"] < 30  # Lower skill match

    def test_score_breakdown(self, sample_user_profile, sample_job_listing):
        """Test score breakdown components."""
        matcher = JobMatcher()
        score = matcher.score_job(sample_job_listing, sample_user_profile)

        # Verify all breakdown components are present
        assert "keyword" in score.breakdown
        assert "skills" in score.breakdown
        assert "experience" in score.breakdown
        assert "location" in score.breakdown

        # Verify total matches sum
        total = sum(score.breakdown.values())
        assert abs(total - score.total_score) <= 5

    def test_keyword_matching(self, sample_user_profile):
        """Test keyword matching logic."""
        job = JobListing(
            title="Python Backend Developer",  # Has target keywords
            company="Tech Corp",
            location="Remote",
            description="Backend developer with Python",
            skills=[JobSkill(name="python")],
            source=JobSource.LINKEDIN,
            job_id="job_python",
        )

        matcher = JobMatcher()
        score = matcher.score_job(job, sample_user_profile)

        assert score.breakdown["keyword"] > 10  # Should match some keywords

    def test_location_matching(self, sample_user_profile, sample_job_listing):
        """Test location matching logic."""
        # Test with preferred location
        sample_job_listing.location = "Remote"
        matcher = JobMatcher()
        score = matcher.score_job(sample_job_listing, sample_user_profile)

        assert score.breakdown["location"] >= 5  # Remote should match

        # Test with non-preferred location
        sample_job_listing.location = "London, UK"
        score2 = matcher.score_job(sample_job_listing, sample_user_profile)

        assert score2.breakdown["location"] < score.breakdown["location"]


class TestJobFilter:
    """Tests for JobFilter class."""

    def test_initialization(self):
        """Test filter initialization."""
        filter = JobFilter()
        assert filter is not None

    def test_filter_by_keywords(self, sample_user_profile, sample_job_listings):
        """Test filtering by keywords."""
        from src.models.job_listing import JobListingCollection

        collection = JobListingCollection(listings=sample_job_listings)
        job_filter = JobFilter(keywords=["python", "engineer"])
        filtered = job_filter.filter_collection(collection)

        assert len(filtered.listings) <= len(sample_job_listings)
        for job in filtered.listings:
            has_keyword = any(
                kw in job.title.lower() or
                (job.description and kw in job.description.lower())
                for kw in ["python", "engineer"]
            )
            assert has_keyword

    def test_filter_by_profile(self, sample_user_profile, sample_job_listings):
        """Test filtering by user profile."""
        from src.models.job_listing import JobListingCollection

        collection = JobListingCollection(listings=sample_job_listings)
        job_filter = JobFilter()
        filtered = job_filter.filter_by_profile(collection, sample_user_profile)

        assert len(filtered.listings) <= len(sample_job_listings)

    def test_quick_filter_reject_patterns(self, sample_job_listings):
        """Test quick filter rejection patterns."""
        from src.scoring.filter import QuickFilter
        from src.models.job_listing import JobListingCollection

        # Add a job matching a reject pattern (e.g., "vice president")
        vp_job = JobListing(
            title="Vice President of Engineering",
            company="Big Corp",
            location="Remote",
            description="Leadership role",
            skills=[],
            source=JobSource.MANUAL,
            job_id="vp_1",
        )

        all_jobs = sample_job_listings + [vp_job]
        collection = JobListingCollection(listings=all_jobs)

        quick_filter = QuickFilter()
        filtered = quick_filter.filter_collection(collection)

        # VP job should be filtered out by QuickFilter reject patterns
        assert vp_job not in filtered.listings
        # Legitimate jobs should remain
        assert len(filtered.listings) == len(sample_job_listings)


@pytest.mark.unit
class TestMatchScore:
    """Tests for MatchScore dataclass."""

    def test_match_score_creation(self):
        """Test creating a MatchScore."""
        from src.models.job_listing import JobListing, JobSource

        job = JobListing(
            title="Test Job",
            company="Test Co",
            location="Remote",
            source=JobSource.MANUAL,
            job_id="test_score",
        )

        score = MatchScore(
            job=job,
            total_score=75,
            passed_threshold=True,
            breakdown={"keyword": 25, "skills": 30, "experience": 15, "location": 5},
            matched_keywords=["python", "engineer"],
            missing_skills=[],
            recommendation="apply",
            reasoning="Good match",
        )

        assert score.total_score == 75
        assert score.breakdown["keyword"] == 25
        assert score.breakdown["skills"] == 30
        assert score.passed_threshold is True
        assert len(score.matched_keywords) == 2

    def test_match_score_details(self):
        """Test MatchScore details."""
        from src.models.job_listing import JobListing, JobSource

        job = JobListing(
            title="Test Job",
            company="Test Co",
            location="Remote",
            source=JobSource.MANUAL,
            job_id="test_score2",
        )

        score = MatchScore(
            job=job,
            total_score=80,
            passed_threshold=True,
            breakdown={"keyword": 25, "skills": 35, "experience": 15, "location": 5},
            matched_keywords=["python", "django"],
            missing_skills=["React"],
            recommendation="apply",
            reasoning="Strong match",
        )

        assert len(score.matched_keywords) == 2
        assert "React" in score.missing_skills
