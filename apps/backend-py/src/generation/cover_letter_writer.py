"""
Job Raider - Cover Letter Writer

This module implements the large-model cover letter writing stage.
Generates tailored cover letters (200-300 words) that connect the
candidate's relevant experience to the target job requirements.

Reuses the SelectionOutput from ResumeSelector to ensure the cover
letter and resume tell a consistent story.

Author: Job Raider
Date: 2026-05-13
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger
from .selector import SelectionOutput


@dataclass
class GeneratedCoverLetter:
    """Generated cover letter with metadata."""

    content: str
    highlighted_experiences: List[Dict[str, str]]
    word_count: int
    model_used: str


class CoverLetterWriter:
    """
    Generate tailored cover letters using a large model.

    Takes the same SelectionOutput used for resume generation and produces
    a concise cover letter (200-300 words) that connects 2-3 relevant
    experiences to the job requirements.
    """

    def __init__(self, llm_router: LLMRouter):
        """
        Initialize the cover letter writer.

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
    ) -> GeneratedCoverLetter:
        """
        Generate a tailored cover letter for a job application.

        Args:
            job: Target job listing
            profile: User profile
            selection: Selection output from selector stage

        Returns:
            GeneratedCoverLetter with the letter content and metadata
        """
        job_context = self._prepare_job_context(job)
        profile_context = self._prepare_profile_context(profile)
        selection_context = self._prepare_selection_context(selection)

        messages = [
            Message(
                role=MessageType.SYSTEM,
                content=(
                    "You are a professional cover letter writer. Write a concise, "
                    "tailored cover letter for a job application.\n\n"
                    "RULES:\n"
                    "1. The letter MUST be between 200 and 300 words\n"
                    "2. Connect 2-3 specific experiences from the candidate's "
                    "background to the job requirements\n"
                    "3. Mention the company and role by name\n"
                    "4. Do NOT use generic phrases or templates\n"
                    "5. Be direct and confident in tone\n"
                    "6. Do NOT include headers, addresses, or date lines\n"
                    "7. Start with a strong opening paragraph\n"
                    "8. End with a brief call to action\n"
                    "9. Return ONLY the letter body as plain text, no JSON"
                ),
            ),
            Message(
                role=MessageType.USER,
                content=(
                    f"Write a cover letter for the following job application:\n\n"
                    f"TARGET JOB:\n{job_context}\n\n"
                    f"SELECTION STRATEGY:\n{selection_context}\n\n"
                    f"CANDIDATE PROFILE:\n{profile_context}"
                ),
            ),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.COVER_LETTER_WRITING,
                temperature=0.7,
                max_tokens=600,
            )

            content = response.content.strip()
            word_count = len(content.split())
            model_used = self.llm_router.routes[
                TaskType.COVER_LETTER_WRITING
            ].primary_model

            highlighted = self._extract_highlighted_experiences(content, selection)

            self.logger.info(
                "Cover letter generated: %d words, model=%s",
                word_count,
                model_used,
            )

            return GeneratedCoverLetter(
                content=content,
                highlighted_experiences=highlighted,
                word_count=word_count,
                model_used=model_used,
            )

        except Exception as e:
            self.logger.error("Cover letter writing failed: %s", str(e))
            return self._fallback_cover_letter(job, profile, selection)

    def rewrite(
        self,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
        draft: GeneratedCoverLetter,
        critique: str,
    ) -> GeneratedCoverLetter:
        """
        Rewrite a cover letter draft using a reviewer critique.

        Args:
            job: Target job listing.
            profile: Candidate profile.
            selection: Selection output from selector stage.
            draft: The original generated cover letter.
            critique: Actionable feedback from the reviewer.

        Returns:
            ``GeneratedCoverLetter`` with the rewritten content and metadata.
        """
        job_context = self._prepare_job_context(job)
        profile_context = self._prepare_profile_context(profile)
        selection_context = self._prepare_selection_context(selection)

        messages = [
            Message(
                role=MessageType.SYSTEM,
                content=(
                    "You are a professional cover letter writer. Rewrite the "
                    "draft cover letter based on the editor's critique."
                    "\n\n"
                    "RULES:\n"
                    "1. The letter MUST be between 200 and 300 words\n"
                    "2. Connect 2-3 specific experiences from the candidate's "
                    "background to the job requirements\n"
                    "3. Mention the company and role by name\n"
                    "4. Do NOT use generic phrases or templates\n"
                    "5. Be direct and confident in tone\n"
                    "6. Do NOT include headers, addresses, or date lines\n"
                    "7. Start with a strong opening paragraph\n"
                    "8. End with a brief call to action\n"
                    "9. Return ONLY the letter body as plain text, no JSON"
                ),
            ),
            Message(
                role=MessageType.USER,
                content=(
                    f"Rewrite the following cover letter for the job application:\n\n"
                    f"TARGET JOB:\n{job_context}\n\n"
                    f"SELECTION STRATEGY:\n{selection_context}\n\n"
                    f"CANDIDATE PROFILE:\n{profile_context}\n\n"
                    f"ORIGINAL DRAFT:\n{draft.content}\n\n"
                    f"EDITOR CRITIQUE:\n{critique}"
                ),
            ),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.COVER_LETTER_WRITING,
                temperature=0.7,
                max_tokens=600,
            )

            content = response.content.strip()
            word_count = len(content.split())
            model_used = self.llm_router.routes[
                TaskType.COVER_LETTER_WRITING
            ].primary_model

            highlighted = self._extract_highlighted_experiences(content, selection)

            self.logger.info(
                "Cover letter rewritten: %d words, model=%s",
                word_count,
                model_used,
            )

            return GeneratedCoverLetter(
                content=content,
                highlighted_experiences=highlighted,
                word_count=word_count,
                model_used=model_used,
            )

        except Exception as e:
            self.logger.error("Cover letter rewrite failed: %s", str(e))
            return self._fallback_cover_letter(job, profile, selection)

    def _prepare_job_context(self, job: JobListing) -> str:
        """
        Prepare job context for the prompt.

        Args:
            job: Target job listing

        Returns:
            Formatted job context string
        """
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
        """
        Prepare profile context for the prompt.

        Args:
            profile: User profile

        Returns:
            Formatted profile context string
        """
        parts = []
        parts.append(f"Name: {profile.name}")
        parts.append(f"Email: {profile.contact.email}")
        parts.append(f"Location: {profile.contact.location}")

        if profile.summary:
            parts.append(f"\nProfessional Summary:\n{profile.summary}")

        if profile.skills:
            parts.append(f"\nSkills: {', '.join(s.name for s in profile.skills)}")

        if profile.experience:
            parts.append("\nWork Experience:")
            for exp in profile.experience:
                dates = (
                    f"{exp.start_date.strftime('%b %Y')} - "
                    f"{exp.end_date.strftime('%b %Y') if exp.end_date else 'Present'}"
                )
                parts.append(f"\n{exp.title} at {exp.company}")
                parts.append(f"  {dates}")
                for highlight in exp.highlights[:5]:
                    parts.append(f"  - {highlight}")

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

        if profile.education:
            parts.append("\nEducation:")
            for edu in profile.education:
                year = edu.end_date.year if edu.end_date else ""
                parts.append(
                    f"- {edu.degree} from {edu.school} "
                    f"{'(' + str(year) + ')' if year else ''}"
                )

        return "\n".join(parts)

    def _prepare_selection_context(self, selection: SelectionOutput) -> str:
        """
        Prepare selection context for the prompt.

        Args:
            selection: Selection output from selector stage

        Returns:
            Formatted selection context string
        """
        parts = []

        if selection.selected_projects:
            parts.append("SELECTED PROJECTS (emphasize these):")
            for proj in selection.selected_projects:
                parts.append(f"- {proj['name']}: {proj['reason']}")

        if selection.keywords_to_emphasize:
            parts.append("\nKEYWORDS TO WEAVE IN:")
            parts.append(", ".join(selection.keywords_to_emphasize))

        if selection.key_achievements:
            parts.append("\nKEY ACHIEVEMENTS:")
            for achievement in selection.key_achievements:
                parts.append(f"- {achievement}")

        return "\n".join(parts)

    def _extract_highlighted_experiences(
        self,
        content: str,
        selection: SelectionOutput,
    ) -> List[Dict[str, str]]:
        """
        Identify which selected projects appear in the cover letter.

        Args:
            content: Generated cover letter text
            selection: Selection output to check against

        Returns:
            List of dicts with project name and reason
        """
        highlighted = []
        content_lower = content.lower()

        for proj in selection.selected_projects:
            if proj["name"].lower() in content_lower:
                highlighted.append(proj)

        return highlighted

    def _fallback_cover_letter(
        self,
        job: JobListing,
        profile: UserProfile,
        selection: SelectionOutput,
    ) -> GeneratedCoverLetter:
        """
        Template-based fallback when LLM generation fails.

        Args:
            job: Target job listing
            profile: User profile
            selection: Selection output

        Returns:
            GeneratedCoverLetter with template-based content
        """
        title = job.title
        company = job.company

        projects_text = ""
        if selection.selected_projects:
            project_parts = []
            for proj in selection.selected_projects[:2]:
                project_parts.append(
                    f"My work on {proj['name']} has given me direct experience "
                    f"that aligns with this role"
                )
            projects_text = " ".join(project_parts)

        keywords_text = ""
        if selection.keywords_to_emphasize:
            keywords_text = (
                f"My expertise in "
                f"{', '.join(selection.keywords_to_emphasize[:3])} "
                f"makes me a strong fit for this position."
            )

        content = (
            f"I am writing to express my strong interest in the {title} "
            f"position at {company}. With my background and experience, "
            f"I am confident I can make a meaningful contribution to your team.\n\n"
            f"{projects_text}\n\n"
            f"{keywords_text}\n\n"
            f"I would welcome the opportunity to discuss how my skills "
            f"and experience align with {company}'s goals. "
            f"Thank you for considering my application."
        )

        return GeneratedCoverLetter(
            content=content,
            highlighted_experiences=selection.selected_projects[:2],
            word_count=len(content.split()),
            model_used="template_fallback",
        )
