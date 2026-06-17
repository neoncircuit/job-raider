"""
Job Raider - Job Matcher

This module provides heuristic relevance scoring for matching
job listings against user profiles.

Author: Job Raider
Date: 2026-04-20
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ..models.job_listing import ExperienceLevel, JobListing
from ..models.user_profile import Skill as UserSkill
from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger


class ScoreCategory(str, Enum):
    """Categories of scoring criteria."""

    KEYWORD = "keyword"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    LOCATION = "location"
    PROJECTS = "projects"
    EDUCATION = "education"


@dataclass
class MatchScore:
    """Result of scoring a job listing."""

    job: JobListing
    total_score: int
    passed_threshold: bool
    breakdown: Dict[str, int]
    matched_keywords: List[str]
    missing_skills: List[str]
    recommendation: str  # "apply", "skip", "maybe"
    reasoning: str


class JobMatcher:
    """
    Score job relevance against user profile using heuristics.

    Implements a scoring algorithm with configurable weights and thresholds.
    """

    # Default scoring weights (total 100 points)
    DEFAULT_WEIGHTS = {
        ScoreCategory.KEYWORD: 30,
        ScoreCategory.SKILLS: 40,
        ScoreCategory.EXPERIENCE: 20,
        ScoreCategory.LOCATION: 10,
    }

    # Fresh graduate mode weights (prioritize potential over experience)
    FRESH_GRAD_WEIGHTS = {
        ScoreCategory.PROJECTS: 35,
        ScoreCategory.SKILLS: 30,
        ScoreCategory.EDUCATION: 20,
        ScoreCategory.EXPERIENCE: 10,
        ScoreCategory.LOCATION: 5,
    }

    # Threshold for "worth applying"
    DEFAULT_THRESHOLD = 60
    FRESH_GRAD_THRESHOLD = 50  # Lower threshold for fresh grads

    def __init__(
        self,
        weights: Optional[Dict[str, int]] = None,
        threshold: int = DEFAULT_THRESHOLD,
        min_skill_match: float = 0.5,
        fresh_grad_mode: bool = False,
    ):
        """
        Initialize the job matcher.

        Args:
            weights: Scoring weights for each category
            threshold: Minimum score to be considered "worth applying"
            min_skill_match: Minimum proportion of required skills to match
            fresh_grad_mode: Enable fresh graduate scoring mode
        """
        if fresh_grad_mode:
            self.weights = weights or self.FRESH_GRAD_WEIGHTS
            self.threshold = (
                threshold
                if threshold != self.DEFAULT_THRESHOLD
                else self.FRESH_GRAD_THRESHOLD
            )
        else:
            self.weights = weights or self.DEFAULT_WEIGHTS
            self.threshold = threshold

        self.fresh_grad_mode = fresh_grad_mode
        self.min_skill_match = min_skill_match

        self.logger = get_logger(Components.SCORING)

    def score_job(
        self,
        job: JobListing,
        profile: UserProfile,
    ) -> MatchScore:
        """
        Score a job listing against user profile.

        Args:
            job: Job listing to score
            profile: User profile to match against

        Returns:
            MatchScore with detailed breakdown
        """
        breakdown = {category.value: 0 for category in ScoreCategory}
        matched_keywords = []
        missing_skills = []

        if self.fresh_grad_mode:
            # Fresh grad mode: prioritize projects and education
            # 1. Projects/portfolio (0-35 points)
            proj_score = self._score_projects(job, profile)
            breakdown[ScoreCategory.PROJECTS.value] = proj_score

            # 2. Skills match (0-30 points)
            skills_score, missing = self._score_skills(job, profile)
            breakdown[ScoreCategory.SKILLS.value] = skills_score
            missing_skills.extend(missing)

            # 3. Education quality (0-20 points)
            edu_score = self._score_education(job, profile)
            breakdown[ScoreCategory.EDUCATION.value] = edu_score

            # 4. Experience alignment (0-10 points) - reduced weight
            exp_score = self._score_experience(job, profile)
            breakdown[ScoreCategory.EXPERIENCE.value] = exp_score

            # 5. Location fit (0-5 points) - reduced weight
            loc_score = self._score_location(job, profile)
            breakdown[ScoreCategory.LOCATION.value] = loc_score
        else:
            # Standard mode
            # 1. Keyword overlap (0-30 points)
            keyword_score, kw_matches = self._score_keywords(job, profile)
            breakdown[ScoreCategory.KEYWORD.value] = keyword_score
            matched_keywords.extend(kw_matches)

            # 2. Skills match (0-40 points)
            skills_score, missing = self._score_skills(job, profile)
            breakdown[ScoreCategory.SKILLS.value] = skills_score
            missing_skills.extend(missing)

            # 3. Experience alignment (0-20 points)
            exp_score = self._score_experience(job, profile)
            breakdown[ScoreCategory.EXPERIENCE.value] = exp_score

            # 4. Location fit (0-10 points)
            loc_score = self._score_location(job, profile)
            breakdown[ScoreCategory.LOCATION.value] = loc_score

        # Calculate total
        total_score = sum(breakdown.values())

        # 5. Apprenticeship constraint (bonus or filter)
        apprenticeship_bonus = self._apply_apprenticeship_constraint(job, profile)
        if apprenticeship_bonus:
            total_score += apprenticeship_bonus

        # Determine recommendation
        recommendation, reasoning = self._get_recommendation(
            total_score,
            breakdown,
            job,
            profile,
        )

        # Determine if apprenticeship filter blocks this job
        apprenticeship_blocked = self._is_apprenticeship_blocked(job, profile)

        return MatchScore(
            job=job,
            total_score=total_score,
            passed_threshold=(
                total_score >= self.threshold and not apprenticeship_blocked
            ),
            breakdown=breakdown,
            matched_keywords=matched_keywords,
            missing_skills=missing_skills,
            recommendation=recommendation,
            reasoning=reasoning,
        )

    def _score_keywords(
        self,
        job: JobListing,
        profile: UserProfile,
    ) -> tuple[int, List[str]]:
        """
        Score keyword overlap.

        Args:
            job: Job listing
            profile: User profile

        Returns:
            Tuple of (score, matched keywords)
        """
        target_keywords = {k.lower() for k in profile.targets.keywords}
        matched = set()

        # Check title
        for keyword in target_keywords:
            if keyword in job.title.lower():
                matched.add(keyword)

        # Check description
        if job.description:
            for keyword in target_keywords:
                if keyword in job.description.lower():
                    matched.add(keyword)

        # Check requirements
        for req in job.requirements:
            for keyword in target_keywords:
                if keyword in req.text.lower():
                    matched.add(keyword)

        # Calculate score (proportional to matches)
        weight = self.weights[ScoreCategory.KEYWORD]
        if target_keywords:
            score = int(weight * (len(matched) / len(target_keywords)))
        else:
            score = weight // 2  # Partial credit if no targets specified

        return score, list(matched)

    def _score_skills(
        self,
        job: JobListing,
        profile: UserProfile,
    ) -> tuple[int, List[str]]:
        """
        Score skill matching.

        Args:
            job: Job listing
            profile: User profile

        Returns:
            Tuple of (score, missing required skills)
        """
        user_skills = {s.name.lower() for s in profile.skills}
        job_required_skills = {s.name.lower() for s in job.skills if s.is_required}

        if not job_required_skills:
            # No specific skill requirements
            return self.weights[ScoreCategory.SKILLS], []

        matched = user_skills & job_required_skills
        missing = job_required_skills - user_skills

        # Calculate score based on proportion matched
        weight = self.weights[ScoreCategory.SKILLS]
        if job_required_skills:
            match_ratio = len(matched) / len(job_required_skills)
            score = int(weight * match_ratio)
        else:
            score = weight // 2

        return score, list(missing)

    def _score_experience(
        self,
        job: JobListing,
        profile: UserProfile,
    ) -> int:
        """
        Score experience level alignment.

        Args:
            job: Job listing
            profile: User profile

        Returns:
            Experience score (0-20)
        """
        weight = self.weights[ScoreCategory.EXPERIENCE]
        user_years = profile.years_of_experience

        # Define experience level mappings
        level_ranges = {
            ExperienceLevel.ENTRY: (0, 2),
            ExperienceLevel.MID: (2, 5),
            ExperienceLevel.SENIOR: (5, 10),
            ExperienceLevel.LEAD: (10, 15),
            ExperienceLevel.PRINCIPAL: (15, 20),
        }

        # Get expected range for job's level
        job_level = job.experience_level
        if job_level not in level_ranges:
            return weight // 2  # Partial credit for unspecified level

        min_years, max_years = level_ranges[job_level]

        # Score based on alignment
        if min_years <= user_years <= max_years:
            # Perfect match
            return weight
        elif user_years < min_years:
            # Underqualified
            if min_years - user_years <= 1:
                return int(weight * 0.7)  # Close enough
            elif min_years - user_years <= 2:
                return int(weight * 0.4)
            else:
                return int(weight * 0.1)  # Significantly under
        else:
            # Overqualified
            if user_years - max_years <= 2:
                return int(weight * 0.9)  # Slight overqualification is OK
            else:
                return int(weight * 0.5)  # Significant overqualification

    def _score_location(
        self,
        job: JobListing,
        profile: UserProfile,
    ) -> int:
        """
        Score location fit.

        Args:
            job: Job listing
            profile: User profile

        Returns:
            Location score (0-10)
        """
        weight = self.weights[ScoreCategory.LOCATION]

        # Remote preference
        if profile.targets.remote_preference and job.is_remote:
            return weight

        # Check if job location is in targets
        if job.location and profile.targets.locations:
            for target_loc in profile.targets.locations:
                if target_loc.lower() in job.location.lower():
                    return weight

        # Partial credit if remote optional
        if job.work_mode.value == "hybrid":
            return int(weight * 0.5)

        # No location match
        return int(weight * 0.2)

    def _score_projects(
        self,
        job: JobListing,
        profile: UserProfile,
    ) -> int:
        """
        Score projects and portfolio work (fresh grad mode).

        Args:
            job: Job listing
            profile: User profile

        Returns:
            Project score (0-35)
        """
        weight = self.weights.get(ScoreCategory.PROJECTS, 35)

        # Check if profile has project information
        if not profile.projects:
            return weight // 4  # Minimal credit if no projects listed

        projects = profile.projects
        project_count = len(projects)

        score = 0

        # Base score for having projects
        if project_count >= 3:
            score = int(weight * 0.25)
        elif project_count >= 1:
            score = int(weight * 0.12)

        # Bonus for relevant projects
        job_skills_lower = {skill.name.lower() for skill in job.skills}
        for project in projects:
            # Check project technologies and description
            proj_text = f"{project.name} {project.description or ''} {' '.join(project.technologies)}".lower()

            # Count matching skills
            matching_skills = 0
            for job_skill in job_skills_lower:
                if job_skill in proj_text:
                    matching_skills += 1

            if matching_skills >= 2:
                score += int(weight * 0.12)
            elif matching_skills >= 1:
                score += int(weight * 0.06)

        # Bonus for project quality indicators
        for project in projects:
            if project.url:  # Has GitHub/portfolio link
                score += int(weight * 0.03)
            if project.highlights:  # Has detailed achievements
                score += int(weight * 0.02)

        # Cap at weight
        return min(score, weight)

    def _score_education(
        self,
        job: JobListing,
        profile: UserProfile,
    ) -> int:
        """
        Score education quality (fresh grad mode).

        Args:
            job: Job listing
            profile: User profile

        Returns:
            Education score (0-20)
        """
        weight = self.weights.get(ScoreCategory.EDUCATION, 20)

        if not profile.education:
            return weight // 3  # Partial credit if no education info

        score = 0
        highest_degree_score = 0

        relevant_majors = [
            "computer science",
            "software engineering",
            "data science",
            "computer engineering",
            "information technology",
            "mathematics",
            "statistics",
            "physics",
            "electrical engineering",
            "informatics",
        ]

        for edu in profile.education:
            degree_lower = edu.degree.lower() if edu.degree else ""

            # Score degree level
            if (
                "bachelor" in degree_lower
                or "b.s." in degree_lower
                or "bs " in degree_lower
            ):
                degree_score = int(weight * 0.6)
            elif (
                "master" in degree_lower
                or "m.s." in degree_lower
                or "ms " in degree_lower
            ):
                degree_score = int(weight * 0.8)
            elif "phd" in degree_lower or "doctor" in degree_lower:
                degree_score = int(weight * 0.9)
            else:
                degree_score = int(weight * 0.3)

            # Bonus for relevant major (check both degree string and school)
            major_keywords = degree_lower + " " + edu.school.lower()
            if any(relevant in major_keywords for relevant in relevant_majors):
                degree_score += int(weight * 0.15)

            # Bonus for GPA
            if edu.gpa:
                if edu.gpa >= 3.5:
                    degree_score += int(weight * 0.1)
                elif edu.gpa >= 3.0:
                    degree_score += int(weight * 0.05)

            # Bonus for honors
            if edu.honors:
                degree_score += int(weight * 0.05)

            # Track highest degree score
            if degree_score > highest_degree_score:
                highest_degree_score = degree_score

        score = highest_degree_score
        return min(score, weight)

    def _apply_apprenticeship_constraint(
        self,
        job: JobListing,
        profile: UserProfile,
    ) -> int:
        """Apply apprenticeship boost to matching jobs.

        In boost mode, adds bonus points when the job aligns with the
        apprenticeship field. Returns 0 if no apprenticeship or if in
        filter mode.

        Args:
            job: Job listing to evaluate.
            profile: User profile with optional apprenticeship contract.

        Returns:
            Bonus points (0 or 20).
        """
        contract = profile.apprenticeship
        if not contract or not contract.is_active:
            return 0
        if profile.targets.constraint_mode != "boost":
            return 0

        if self._job_matches_field(job, contract.field):
            return 20

        return 0

    def _is_apprenticeship_blocked(
        self,
        job: JobListing,
        profile: UserProfile,
    ) -> bool:
        """Check if an apprenticeship filter constraint blocks this job.

        In filter mode, returns True when the job does NOT match the
        required apprenticeship field.

        Args:
            job: Job listing to evaluate.
            profile: User profile with optional apprenticeship contract.

        Returns:
            True if the job is blocked by the apprenticeship constraint.
        """
        contract = profile.apprenticeship
        if not contract or not contract.is_active:
            return False
        if profile.targets.constraint_mode != "filter":
            return False

        return not self._job_matches_field(job, contract.field)

    @staticmethod
    def _job_matches_field(job: JobListing, field: str) -> bool:
        """Check if a job listing matches a required field of work.

        Searches the job title, description, and requirements for
        keywords from the field string.

        Args:
            job: Job listing to check.
            field: Required field of work (e.g. 'AI/ML').

        Returns:
            True if the job matches the field.
        """
        field_terms = [
            term.lower().strip()
            for term in field.replace("/", " ").split()
            if term.strip()
        ]
        searchable = f"{job.title} {job.description or ''}".lower()
        for req in job.requirements:
            searchable += f" {req.text.lower()}"
        for skill in job.skills:
            searchable += f" {skill.name.lower()}"

        return any(term in searchable for term in field_terms)

    def _get_recommendation(
        self,
        total_score: int,
        breakdown: Dict[str, int],
        job: JobListing,
        profile: UserProfile,
    ) -> tuple[str, str]:
        """
        Generate recommendation and reasoning.

        Args:
            total_score: Total score
            breakdown: Score breakdown
            job: Job listing
            profile: User profile

        Returns:
            Tuple of (recommendation, reasoning)
        """
        if total_score >= self.threshold * 1.2:
            # Very strong match
            return (
                "apply",
                f"Strong match ({total_score}/100). Keywords and skills align well.",
            )
        elif total_score >= self.threshold:
            # Good match
            return "apply", f"Good match ({total_score}/100). Meets minimum threshold."
        elif total_score >= self.threshold * 0.7:
            # Maybe
            return (
                "maybe",
                f"Possible match ({total_score}/100). Some gaps but consider applying.",
            )
        else:
            # Poor match
            return "skip", f"Weak match ({total_score}/100). Missing key requirements."

    def rank_jobs(
        self,
        jobs: List[JobListing],
        profile: UserProfile,
        limit: Optional[int] = None,
    ) -> List[MatchScore]:
        """
        Score and rank multiple jobs.

        Args:
            jobs: List of job listings to score
            profile: User profile to match against
            limit: Maximum number of results to return

        Returns:
            List of MatchScore objects sorted by total_score
        """
        scores = [self.score_job(job, profile) for job in jobs]
        scores.sort(key=lambda s: s.total_score, reverse=True)

        if limit:
            scores = scores[:limit]

        return scores

    def get_top_jobs(
        self,
        jobs: List[JobListing],
        profile: UserProfile,
        n: int = 3,
    ) -> List[JobListing]:
        """
        Get top N jobs for a profile.

        Args:
            jobs: List of job listings
            profile: User profile
            n: Number of top jobs to return

        Returns:
            List of top N JobListing objects
        """
        scores = self.rank_jobs(jobs, profile, limit=n)
        return [score.job for score in scores if score.passed_threshold]


class SkillMatcher:
    """
    Specialized matcher for skill-based filtering.

    Provides more granular skill matching capabilities.
    """

    @staticmethod
    def get_skill_overlap(
        job: JobListing,
        profile: UserProfile,
    ) -> Dict[str, Any]:
        """
        Get detailed skill overlap analysis.

        Args:
            job: Job listing
            profile: User profile

        Returns:
            Dictionary with overlap details
        """
        user_skill_names = {s.name.lower() for s in profile.skills}
        job_skill_names = {s.name.lower() for s in job.skills}

        matched_skills = user_skill_names & job_skill_names
        missing_required = {
            s.name
            for s in job.skills
            if s.is_required and s.name.lower() not in user_skill_names
        }
        extra_skills = user_skill_names - job_skill_names

        return {
            "matched_count": len(matched_skills),
            "matched_skills": list(matched_skills),
            "missing_required_count": len(missing_required),
            "missing_required_skills": list(missing_required),
            "extra_skills_count": len(extra_skills),
            "extra_skills": list(extra_skills),
            "overlap_percentage": (
                len(matched_skills) / len(job_skill_names) * 100
                if job_skill_names
                else 0
            ),
        }

    @staticmethod
    def categorize_skill_match(
        job: JobListing,
        profile: UserProfile,
    ) -> str:
        """
        Categorize the skill match level.

        Args:
            job: Job listing
            profile: User profile

        Returns:
            Category: "excellent", "good", "partial", or "poor"
        """
        overlap = SkillMatcher.get_skill_overlap(job, profile)
        overlap_pct = overlap["overlap_percentage"]

        if overlap_pct >= 80:
            return "excellent"
        elif overlap_pct >= 60:
            return "good"
        elif overlap_pct >= 40:
            return "partial"
        else:
            return "poor"
