"""
Job Raider - Resume Selector

This module implements the small-model selection stage of the
two-model resume generation approach.

Author: Job Raider
Date: 2026-04-20
"""

from dataclasses import dataclass
from typing import Dict, List

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.job_listing import JobListing
from ..models.user_profile import Project, UserProfile
from ..utils.logger import Components, get_logger


@dataclass
class SelectionOutput:
    """Output from the selection stage."""

    selected_projects: List[Dict[str, str]]
    keywords_to_emphasize: List[str]
    key_achievements: List[str]
    summary_suggestion: str
    raw_response: str


class ResumeSelector:
    """
    Select relevant content from user profile for a job application.

    Uses a small, fast model (qwen2.5:3b) to identify:
    - 3 most relevant projects to highlight
    - 5 most important keywords to emphasize
    - Key achievements that align with job requirements
    """

    def __init__(self, llm_router: LLMRouter):
        """
        Initialize the resume selector.

        Args:
            llm_router: LLM router for model selection
        """
        self.llm_router = llm_router
        self.logger = get_logger(Components.GENERATION)

    def select(
        self,
        job: JobListing,
        profile: UserProfile,
    ) -> SelectionOutput:
        """
        Select relevant content for a job application.

        Args:
            job: Target job listing
            profile: User profile

        Returns:
            SelectionOutput with selected content
        """
        # Prepare job requirements summary
        job_requirements = self._extract_requirements(job)

        # Prepare profile summary
        profile_summary = self._summarize_profile(profile)

        # Prepare prompt
        messages = [
            Message(
                role=MessageType.SYSTEM,
                content="You are a resume strategist. Select the most relevant content from a candidate's profile to emphasize for a specific job application. Be selective and strategic.",
            ),
            Message(
                role=MessageType.USER,
                content=f"""Given this job and candidate profile, select:
1. The 3 most relevant projects to highlight
2. The 5 most important keywords to emphasize in the resume
3. Key achievements that align with the job requirements

JOB REQUIREMENTS:
{job_requirements}

CANDIDATE PROFILE:
{profile_summary}

Return a JSON object:
{{
  "selected_projects": [
    {{"name": "Project 1", "reason": "Why this project is relevant"}},
    {{"name": "Project 2", "reason": "..."}},
    {{"name": "Project 3", "reason": "..."}}
  ],
  "keywords_to_emphasize": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "key_achievements": ["achievement1", "achievement2"],
  "summary_suggestion": "2-3 sentence professional summary emphasizing fit"
}}""",
            ),
        ]

        try:
            # Use small model for selection
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.SELECTION,
                temperature=0.5,
                max_tokens=1000,
            )

            # Parse JSON response
            import json
            import re

            json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
            if not json_match:
                raise ValueError("Failed to extract JSON from selection response")

            data = json.loads(json_match.group(0))

            return SelectionOutput(
                selected_projects=data.get("selected_projects", []),
                keywords_to_emphasize=data.get("keywords_to_emphasize", []),
                key_achievements=data.get("key_achievements", []),
                summary_suggestion=data.get("summary_suggestion", ""),
                raw_response=response.content,
            )

        except Exception as e:
            self.logger.error(f"Selection failed: {str(e)}")
            # Fall back to rule-based selection
            return self._fallback_selection(job, profile)

    def _extract_requirements(self, job: JobListing) -> str:
        """
        Extract key requirements from job listing.

        Args:
            job: Job listing

        Returns:
            Formatted requirements string
        """
        parts = []

        parts.append(f"Title: {job.title}")
        parts.append(f"Company: {job.company}")

        if job.description:
            parts.append(f"\nDescription:\n{job.description[:500]}")

        if job.requirements:
            parts.append("\nRequirements:")
            for req in job.requirements[:10]:
                parts.append(f"- {req.text}")

        if job.skills:
            parts.append("\nRequired Skills:")
            for skill in job.skills[:10]:
                parts.append(f"- {skill.name}")

        return "\n".join(parts)

    def _summarize_profile(self, profile: UserProfile) -> str:
        """
        Summarize user profile for selection.

        Args:
            profile: User profile

        Returns:
            Formatted profile summary
        """
        parts = []

        # Basic info
        parts.append(f"Name: {profile.name}")
        parts.append(f"Summary: {profile.summary or 'Not specified'}")

        # Experience
        if profile.experience:
            parts.append(f"\nExperience: {profile.years_of_experience} years total")
            parts.append(
                f"Current Position: {profile.current_position.title if profile.current_position else 'N/A'}"
            )

        # Skills
        if profile.skills:
            parts.append(f"\nSkills: {', '.join(s.name for s in profile.skills[:20])}")

        # Projects
        if profile.projects:
            parts.append("\nProjects:")
            for project in profile.projects[:10]:
                technologies = (
                    ", ".join(project.technologies) if project.technologies else "N/A"
                )
                parts.append(f"- {project.name} ({technologies})")
                if project.description:
                    parts.append(f"  {project.description}")

        # Education
        if profile.education:
            parts.append("\nEducation:")
            for edu in profile.education:
                parts.append(f"- {edu.degree} from {edu.school}")

        return "\n".join(parts)

    def _fallback_selection(
        self,
        job: JobListing,
        profile: UserProfile,
    ) -> SelectionOutput:
        """
        Rule-based fallback selection.

        Args:
            job: Job listing
            profile: User profile

        Returns:
            SelectionOutput with rule-based selections
        """
        # Select projects with matching technologies
        job_skills = {s.name.lower() for s in job.skills}
        matched_projects = []

        for project in profile.projects:
            project_techs = {t.lower() for t in project.technologies}
            overlap = job_skills & project_techs

            if overlap and len(matched_projects) < 3:
                matched_projects.append(
                    {
                        "name": project.name,
                        "reason": f"Matches skills: {', '.join(overlap)}",
                    }
                )

        # Fill with most recent if needed
        if len(matched_projects) < 3:
            for project in profile.recent_projects:
                if project.name not in [p["name"] for p in matched_projects]:
                    matched_projects.append(
                        {
                            "name": project.name,
                            "reason": "Recent project",
                        }
                    )
                    if len(matched_projects) >= 3:
                        break

        # Select keywords from job requirements
        keywords = []
        for skill in job.skills[:5]:
            keywords.append(skill.name)

        # Add core skills if needed
        if len(keywords) < 5:
            for skill in profile.core_skills[:5]:
                if skill not in keywords:
                    keywords.append(skill)
                    if len(keywords) >= 5:
                        break

        return SelectionOutput(
            selected_projects=matched_projects[:3],
            keywords_to_emphasize=keywords[:5],
            key_achievements=[],
            summary_suggestion=f"{profile.name} - {profile.current_position.title if profile.current_position else 'Professional'}",
            raw_response="",
        )


class ProjectSelector:
    """
    Specialized selector for project relevance.

    Provides more detailed project scoring and selection.
    """

    def score_project_relevance(
        self,
        project: Project,
        job: JobListing,
        profile: UserProfile,
    ) -> float:
        """
        Score a project's relevance to a job.

        Args:
            project: Project to score
            job: Target job
            profile: User profile

        Returns:
            Relevance score (0-1)
        """
        score = 0.0
        job_skills = {s.name.lower() for s in job.skills}
        project_techs = {t.lower() for t in project.technologies}

        # Technology overlap (50% weight)
        if job_skills:
            overlap = project_techs & job_skills
            score += 0.5 * (len(overlap) / len(job_skills))

        # Recency bonus (20% weight)
        if project.start_date:
            months_ago = (
                project.end_date
                or __import__("datetime").datetime.now() - project.start_date
            ).days / 30
            if months_ago < 6:
                score += 0.2
            elif months_ago < 12:
                score += 0.1

        # Relevance to job title (30% weight)
        title_lower = job.title.lower()
        project_lower = project.name.lower()

        title_words = set(title_lower.split())
        project_words = set(project_lower.split())

        if title_words & project_words:
            score += 0.3

        return min(score, 1.0)

    def select_top_projects(
        self,
        profile: UserProfile,
        job: JobListing,
        n: int = 3,
    ) -> List[Project]:
        """
        Select top N most relevant projects.

        Args:
            profile: User profile
            job: Target job
            n: Number of projects to select

        Returns:
            List of selected projects
        """
        if not profile.projects:
            return []

        # Score all projects
        scored_projects = []
        for project in profile.projects:
            score = self.score_project_relevance(project, job, profile)
            scored_projects.append((project, score))

        # Sort by score and return top N
        scored_projects.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in scored_projects[:n]]
