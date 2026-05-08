# Unit tests for data models
# Author: Job Raider
# Date: 2026-04-21

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.models.job_listing import (
    JobListing,
    JobSource,
    ExperienceLevel,
    JobType,
    WorkMode,
    SalaryRange,
    JobListingCollection,
    JobRequirement,
    JobResponsibility,
    Skill as JobSkill,
)
from src.models.user_profile import (
    UserProfile,
    ContactInfo,
    Skill,
    SkillCategory,
    ProficiencyLevel,
    Project,
    TargetJob,
)


class TestJobListing:
    """Tests for JobListing model."""

    def test_job_listing_creation(self):
        """Test creating a valid job listing."""
        job = JobListing(
            title="Software Engineer",
            company="Tech Corp",
            location="San Francisco, CA",
            description="Job description",
            requirements=[JobRequirement(text="Requirement 1")],
            responsibilities=[JobResponsibility(text="Responsibility 1")],
            skills=[JobSkill(name="python"), JobSkill(name="django")],
            source=JobSource.LINKEDIN,
            job_id="test_123",
        )

        assert job.title == "Software Engineer"
        assert job.company == "Tech Corp"
        assert job.source == JobSource.LINKEDIN
        assert job.job_id == "test_123"

    def test_job_listing_with_salary(self):
        """Test job listing with salary range."""
        job = JobListing(
            title="Engineer",
            company="Tech Corp",
            location="Remote",
            salary_range=SalaryRange(
                min_amount=100000,
                max_amount=150000,
                currency="USD",
                period="annual",
            ),
            source=JobSource.JSEARCH,
            job_id="test_456",
        )

        assert job.salary_range.min_amount == 100000
        assert job.salary_range.max_amount == 150000
        assert job.salary_range.period == "annual"

    def test_job_listing_defaults(self):
        """Test job listing with default values."""
        job = JobListing(
            title="Developer",
            company="Test Co",
            location="NYC",
            source=JobSource.OTHER,
            job_id="test_789",
        )

        # Should have empty lists for optional fields
        assert job.requirements == []
        assert job.responsibilities == []
        assert job.skills == []
        assert job.description is None


class TestJobListingCollection:
    """Tests for JobListingCollection."""

    def test_collection_creation(self, sample_job_listings):
        """Test creating a collection."""
        collection = JobListingCollection(listings=sample_job_listings)

        assert len(collection.listings) == len(sample_job_listings)

    def test_deduplicate(self):
        """Test deduplication logic."""
        from src.models.job_listing import JobListing, JobSource

        job1 = JobListing(
            title="Engineer",
            company="Tech Corp",
            location="Remote",
            source=JobSource.LINKEDIN,
            job_id="same_id",  # Same ID
        )

        job2 = JobListing(
            title="Developer",
            company="Tech Corp",
            location="Remote",
            source=JobSource.JSEARCH,
            job_id="same_id",  # Same ID
        )

        collection = JobListingCollection(listings=[job1, job2])
        deduplicated = collection.deduplicate()

        # Should remove duplicate (keep first)
        assert len(deduplicated.listings) == 1
        assert deduplicated.listings[0].job_id == "same_id"

    def test_filter_by_keywords(self, sample_job_listings):
        """Test filtering by keywords."""
        collection = JobListingCollection(listings=sample_job_listings)
        filtered = collection.filter_by_keywords(["python"])

        # All filtered jobs should contain "python" in title, description, or skills
        for job in filtered.listings:
            has_keyword = (
                "python" in job.title.lower() or
                (job.description and "python" in job.description.lower()) or
                any("python" in skill.name.lower() for skill in job.skills)
            )
            assert has_keyword


class TestUserProfile:
    """Tests for UserProfile model."""

    def test_profile_creation(self, sample_user_profile):
        """Test creating a user profile."""
        profile = sample_user_profile

        assert profile.name == "John Doe"
        assert profile.contact.email == "john.doe@example.com"
        assert len(profile.skills) > 0
        assert len(profile.experience) > 0

    def test_years_of_experience(self, sample_user_profile):
        """Test years of experience calculation."""
        profile = sample_user_profile

        # Should calculate from experience entries
        assert profile.years_of_experience > 0

    def test_target_job(self, sample_user_profile):
        """Test target job preferences."""
        profile = sample_user_profile

        assert len(profile.targets.keywords) > 0
        assert len(profile.targets.locations) > 0
        assert len(profile.targets.experience_levels) > 0

    def test_skill_categories(self, sample_user_profile):
        """Test skill categorization."""
        profile = sample_user_profile

        # Should have skills with categories
        programming_skills = [s for s in profile.skills if s.category == SkillCategory.PROGRAMMING_LANGUAGE]
        assert len(programming_skills) > 0


class TestSkill:
    """Tests for Skill model."""

    def test_skill_creation(self):
        """Test creating a skill."""
        skill = Skill(
            name="Python",
            proficiency=ProficiencyLevel.EXPERT,
            years_of_experience=5,
        )

        assert skill.name == "Python"
        assert skill.proficiency == ProficiencyLevel.EXPERT
        assert skill.years_of_experience == 5

    def test_proficiency_levels(self):
        """Test all proficiency levels."""
        levels = [
            ProficiencyLevel.BEGINNER,
            ProficiencyLevel.INTERMEDIATE,
            ProficiencyLevel.ADVANCED,
            ProficiencyLevel.EXPERT,
        ]

        for level in levels:
            skill = Skill(name="Test", proficiency=level)
            assert skill.proficiency == level


class TestProject:
    """Tests for Project model."""

    def test_project_creation(self):
        """Test creating a project."""
        project = Project(
            name="Test Project",
            description="A test project",
            technologies=["Python", "Django"],
            start_date="2023-01-01",
            end_date="2023-12-31",
            highlights=["Highlight 1", "Highlight 2"],
        )

        assert project.name == "Test Project"
        assert len(project.technologies) == 2
        assert len(project.highlights) == 2


class TestContactInfo:
    """Tests for ContactInfo model."""

    def test_contact_info_creation(self):
        """Test creating contact info."""
        contact = ContactInfo(
            email="jane@example.com",
            phone="555-5678",
            location="New York, NY",
            linkedin="https://linkedin.com/in/janedoe",
            github="https://github.com/janedoe",
        )

        assert contact.email == "jane@example.com"
        assert contact.phone == "555-5678"
        assert contact.location == "New York, NY"


class TestTargetJob:
    """Tests for TargetJob model."""

    def test_target_job_creation(self):
        """Test creating target job preferences."""
        target = TargetJob(
            keywords=["python", "engineer"],
            locations=["remote", "san francisco"],
            experience_levels=[
                ExperienceLevel.MID,
                ExperienceLevel.SENIOR,
            ],
        )

        assert "python" in target.keywords
        assert "remote" in target.locations
        assert ExperienceLevel.MID in target.experience_levels


@pytest.mark.unit
class TestEnums:
    """Tests for enum types."""

    def test_job_source_enum(self):
        """Test JobSource enum values."""
        assert JobSource.LINKEDIN.value == "linkedin"
        assert JobSource.JSEARCH.value == "jsearch"
        assert JobSource.MANUAL.value == "manual"
        assert JobSource.OTHER.value == "other"

    def test_experience_level_enum(self):
        """Test ExperienceLevel enum values."""
        assert ExperienceLevel.ENTRY.value == "Entry Level"
        assert ExperienceLevel.MID.value == "Mid Level"
        assert ExperienceLevel.SENIOR.value == "Senior"
        assert ExperienceLevel.LEAD.value == "Lead"
        assert ExperienceLevel.EXECUTIVE.value == "Executive"

    def test_job_type_enum(self):
        """Test JobType enum values."""
        assert JobType.FULL_TIME.value == "Full-time"
        assert JobType.PART_TIME.value == "Part-time"
        assert JobType.CONTRACT.value == "Contract"
        assert JobType.INTERNSHIP.value == "Internship"

    def test_work_mode_enum(self):
        """Test WorkMode enum values."""
        assert WorkMode.ON_SITE.value == "On-site"
        assert WorkMode.REMOTE.value == "Remote"
        assert WorkMode.HYBRID.value == "Hybrid"
