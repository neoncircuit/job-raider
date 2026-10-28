"""
Job Raider - Resume Writer

This module implements the large-model resume writing stage of the
two-model resume generation approach.

Author: Job Raider
Date: 2026-04-20
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger
from .selector import SelectionOutput


@dataclass
class GeneratedResume:
    """Generated resume with all sections."""

    summary: str
    skills: List[str]
    experience: List[Dict[str, Any]]
    projects: List[Dict[str, Any]]
    education: List[Dict[str, Any]]
    raw_response: str
    model_used: str
    provider_used: Optional[str] = None


def flatten_skills(value: Any) -> List[str]:
    """
    Flatten grouped skills into one list of skill names.

    Accepts a flat list, a dict of category lists, or a list of category
    objects, and returns the skill names in order. Blank entries and
    duplicates (in any letter case) are dropped, keeping the first spelling.

    Args:
        value: Skills as the writer model returned them.

    Returns:
        One flat list of skill names.
    """
    skills: List[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        name = candidate.strip()
        if not name:
            return
        key = name.casefold()
        if key in seen:
            return
        seen.add(key)
        skills.append(name)

    def walk(item: Any) -> None:
        if isinstance(item, str):
            add(item)
        elif isinstance(item, dict):
            if "skills" in item:
                walk(item["skills"])
            elif "name" in item:
                name = item["name"]
                if isinstance(name, str):
                    add(name)
            else:
                for child in item.values():
                    walk(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                walk(child)

    walk(value)
    return skills


def _project_key(name: Any) -> str:
    """
    Normalize a project name for matching.

    Args:
        name: Project name.

    Returns:
        The name in lower case, without a trailing "(...)" part, with
        single spaces.
    """
    text = re.sub(r"\s*\([^)]*\)\s*$", "", str(name or ""))
    return " ".join(text.lower().split())


def match_project_names(projects: Any, profile: UserProfile) -> List[Dict[str, Any]]:
    """
    Give each draft project the profile's name when the names match.

    Names match when they are equal after ``_project_key``. A name that
    matches no profile project stays. An item that is not a dict is
    dropped. The input list and its items are not changed.

    Args:
        projects: The ``projects`` value from the model.
        profile: The user profile.

    Returns:
        New project dicts.
    """
    by_key = {_project_key(project.name): project.name for project in profile.projects}
    result: List[Dict[str, Any]] = []
    for item in projects if isinstance(projects, list) else []:
        if not isinstance(item, dict):
            continue
        copy = dict(item)
        match = by_key.get(_project_key(copy.get("name")))
        if match:
            copy["name"] = match
        result.append(copy)
    return result


class ResumeWriter:
    """
    Generate tailored resumes using a large model.

    Takes selection output and rewrites resume sections to emphasize
    relevant projects, skills, and achievements for a specific job.
    """

    def __init__(self, llm_router: LLMRouter):
        """
        Initialize the resume writer.

        Args:
            llm_router: LLM router for model selection
        """
        self.llm_router = llm_router
        self.logger = get_logger(Components.GENERATION)

    def write(
        self,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
    ) -> GeneratedResume:
        """
        Generate a tailored resume for a job application.

        Args:
            job: Target job listing
            profile: User profile
            selection: Selection output from selector stage

        Returns:
            GeneratedResume with all sections
        """
        # Prepare context
        job_context = self._prepare_job_context(job)
        profile_context = self._prepare_profile_context(profile)
        selection_context = self._prepare_selection_context(selection)

        # Prepare prompt
        messages = [
            Message(
                role=MessageType.SYSTEM,
                content="""You are an expert resume writer. Rewrite a resume to emphasize specific projects,
skills, and keywords for a job application while maintaining factual accuracy.

CRITICAL RULES:
1. Never fabricate skills, experience, or achievements
2. All selected projects MUST appear in the output
3. All keywords MUST be naturally incorporated
4. Keep dates and facts exactly as provided
5. Use action verbs and quantify achievements where possible
6. Maintain professional tone throughout
7. "skills" is one flat list of skill names from the BASE RESUME. Do not group skills by category.""",
            ),
            Message(
                role=MessageType.USER,
                content=f"""Rewrite this resume to emphasize the following for the target job:

TARGET JOB:
{job_context}

SELECTION STRATEGY:
{selection_context}

BASE RESUME:
{profile_context}

Return a JSON object with the rewritten resume sections:
{{
  "summary": "Professional summary (2-3 sentences)",
  "skills": ["Skill 1", "Skill 2", ...],
  "experience": [
    {{
      "title": "Job Title",
      "company": "Company",
      "dates": "Date Range",
      "highlights": ["bullet1", "bullet2", ...]
    }}
  ],
  "projects": [
    {{
      "name": "Project Name",
      "description": "1-2 sentence description",
      "technologies": ["tech1", "tech2"],
      "highlights": ["achievement1", "achievement2"]
    }}
  ],
  "education": [
    {{
      "degree": "Degree",
      "school": "School",
      "year": "Year"
    }}
  ]
}}""",
            ),
        ]

        try:
            # Use large model for writing
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.RESUME_WRITING,
                temperature=0.7,
                max_tokens=2500,
            )

            # Parse JSON response
            import json
            import re

            json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
            if not json_match:
                raise ValueError("Failed to extract JSON from resume response")

            data = json.loads(json_match.group(0))

            return GeneratedResume(
                summary=data.get("summary", ""),
                skills=flatten_skills(data.get("skills", [])),
                experience=data.get("experience", []),
                projects=match_project_names(data.get("projects", []), profile),
                education=data.get("education", []),
                raw_response=response.content,
                model_used=self.llm_router.routes[
                    TaskType.RESUME_WRITING
                ].primary_model,
                provider_used=getattr(response, "provider", None),
            )

        except Exception as e:
            self.logger.error(f"Resume writing failed: {str(e)}")
            # Fall back to basic resume
            return self._fallback_resume(job, profile, selection)

    def _prepare_job_context(self, job: JobListing) -> str:
        """Prepare job context for the prompt."""
        parts = [
            f"Title: {job.title}",
            f"Company: {job.company}",
            f"Location: {job.location or 'Not specified'}",
        ]

        if job.description:
            parts.append(f"\nDescription:\n{job.description[:500]}")

        if job.requirements:
            parts.append("\nKey Requirements:")
            for req in job.requirements[:8]:
                parts.append(f"- {req.text}")

        if job.skills:
            parts.append("\nRequired Skills:")
            for skill in job.skills[:10]:
                parts.append(f"- {skill.name}")

        return "\n".join(parts)

    def _prepare_profile_context(self, profile: UserProfile) -> str:
        """Prepare profile context for the prompt."""
        parts = []

        # Basic info
        parts.append(f"Name: {profile.name}")
        parts.append(f"Email: {profile.contact.email}")
        parts.append(f"Location: {profile.contact.location}")

        if profile.summary:
            parts.append(f"\nProfessional Summary:\n{profile.summary}")

        # Skills
        if profile.skills:
            parts.append(f"\nSkills: {', '.join(s.name for s in profile.skills)}")

        # Experience
        if profile.experience:
            parts.append("\nWork Experience:")
            for exp in profile.experience:
                dates = f"{exp.start_date.strftime('%b %Y')} - {exp.end_date.strftime('%b %Y') if exp.end_date else 'Present'}"
                parts.append(f"\n{exp.title} at {exp.company}")
                parts.append(f"  {dates}")
                for highlight in exp.highlights[:5]:
                    parts.append(f"  - {highlight}")

        # Projects
        if profile.projects:
            parts.append("\nProjects:")
            for project in profile.projects:
                parts.append(f"\n{project.name}")
                if project.description:
                    parts.append(f"  {project.description}")
                if project.technologies:
                    parts.append(f"  Technologies: {', '.join(project.technologies)}")
                for highlight in project.highlights[:3]:
                    parts.append(f"  - {highlight}")

        # Education
        if profile.education:
            parts.append("\nEducation:")
            for edu in profile.education:
                year = edu.end_date.year if edu.end_date else ""
                parts.append(
                    f"- {edu.degree} from {edu.school} {'(' + str(year) + ')' if year else ''}"
                )

        return "\n".join(parts)

    def _prepare_selection_context(self, selection: SelectionOutput) -> str:
        """Prepare selection context for the prompt."""
        parts = []

        if selection.selected_projects:
            parts.append("SELECTED PROJECTS:")
            for proj in selection.selected_projects:
                parts.append(f"- {proj['name']}: {proj['reason']}")

        if selection.keywords_to_emphasize:
            parts.append("\nKEYWORDS TO EMPHASIZE:")
            parts.append(", ".join(selection.keywords_to_emphasize))

        if selection.key_achievements:
            parts.append("\nKEY ACHIEVEMENTS:")
            for achievement in selection.key_achievements:
                parts.append(f"- {achievement}")

        if selection.summary_suggestion:
            parts.append(f"\nSUGGESTED SUMMARY:\n{selection.summary_suggestion}")

        return "\n".join(parts)

    def _fallback_resume(
        self,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
    ) -> GeneratedResume:
        """
        Fallback resume generation using template-based approach.

        Args:
            job: Target job
            profile: User profile
            selection: Selection output

        Returns:
            GeneratedResume with basic content
        """
        # Generate summary
        summary = selection.summary_suggestion or (
            f"{profile.name} - {profile.current_position.title if profile.current_position else 'Professional'} "
            f"with expertise in {', '.join(skill.name for skill in profile.skills[:5])}"
        )

        # Generate skills list
        skills = list(
            set([s.name for s in profile.skills[:15]] + selection.keywords_to_emphasize)
        )

        # Generate experience
        experience = []
        for exp in profile.experience:
            dates = f"{exp.start_date.strftime('%b %Y')} - {exp.end_date.strftime('%b %Y') if exp.end_date else 'Present'}"
            experience.append(
                {
                    "title": exp.title,
                    "company": exp.company,
                    "dates": dates,
                    "highlights": exp.highlights[:5],
                }
            )

        # Generate projects
        projects = []
        for proj_name in selection.selected_projects:
            project = next(
                (p for p in profile.projects if p.name == proj_name["name"]), None
            )
            if project:
                projects.append(
                    {
                        "name": project.name,
                        "description": project.description or "",
                        "technologies": project.technologies,
                        "highlights": project.highlights[:3],
                    }
                )

        # Generate education
        education = []
        for edu in profile.education:
            education.append(
                {
                    "degree": edu.degree,
                    "school": edu.school,
                    "year": str(edu.end_date.year) if edu.end_date else "",
                }
            )

        return GeneratedResume(
            summary=summary,
            skills=skills,
            experience=experience,
            projects=projects,
            education=education,
            raw_response="",
            model_used="template_fallback",
        )


class ResumeSection:
    """Individual resume section."""

    SUMMARY = "summary"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    PROJECTS = "projects"
    EDUCATION = "education"
