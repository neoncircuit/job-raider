"""
Job Raider - Resume Analyzer

This module implements AI-powered resume analysis that provides both
general feedback and job-specific gap analysis.

Author: Job Raider
Date: 2026-04-23
"""

import json
import re
from pathlib import Path
from typing import Optional

import yaml

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.job_listing import JobListing
from ..models.resume_analysis import (
    ExperienceInsight,
    ProjectInsight,
    ResumeAnalysis,
    SkillAssessment,
)
from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger


class ResumeAnalyzer:
    """
    AI-powered resume analyzer.

    Provides two modes of analysis:
    - General: Overall resume quality assessment
    - Job-specific: Alignment analysis with a target job

    Strategy: Profile-derived data (skills, experience, projects) is built
    directly from the parsed resume to ensure factual accuracy. The LLM is
    only used for qualitative assessments (scores, summaries, recommendations).
    """

    def __init__(self, llm_router: LLMRouter):
        """
        Initialize the resume analyzer.

        Args:
            llm_router: LLM router for model selection
        """
        self.llm_router = llm_router
        self.logger = get_logger(Components.GENERATION)
        self._load_templates()

    def _load_templates(self) -> None:
        """Load prompt templates from configuration."""
        config_path = (
            Path(__file__).parent.parent.parent / "config" / "prompt_templates.yaml"
        )

        with open(config_path, "r") as f:
            templates = yaml.safe_load(f)

        self.general_template = templates["prompts"]["resume_analysis_general"]
        self.job_specific_template = templates["prompts"][
            "resume_analysis_job_specific"
        ]

    def analyze_general(
        self,
        profile: UserProfile,
        resume_path: str = "",
    ) -> ResumeAnalysis:
        """
        Analyze resume quality independent of job targets.

        Args:
            profile: User profile from parsed resume
            resume_path: Path to the resume file

        Returns:
            ResumeAnalysis with general assessment
        """
        profile_context = self._prepare_profile_context(profile)

        user_content = self.general_template["user"].replace(
            "{{profile_context}}", profile_context
        )
        messages = [
            Message(
                role=MessageType.SYSTEM,
                content=self.general_template["system"],
            ),
            Message(
                role=MessageType.USER,
                content=user_content,
            ),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.RESUME_ANALYSIS,
                temperature=0.3,
                max_tokens=2500,
            )

            llm_result = self._parse_llm_assessment(response.content)
        except Exception as e:
            self.logger.error(f"General analysis failed: {str(e)}")
            llm_result = self._rule_based_assessment(profile)

        return ResumeAnalysis(
            resume_path=resume_path,
            analysis_type="general",
            overall_score=llm_result.get("overall_score", 50),
            summary=llm_result.get("summary", f"Analysis for {profile.name}."),
            key_strengths=llm_result.get("key_strengths", []),
            key_improvements=llm_result.get("key_improvements", []),
            skills_assessment=self._build_skills_assessment(profile),
            experience_insights=self._build_experience_insights(profile),
            project_insights=self._build_project_insights(profile),
            resume_improvements=llm_result.get("resume_improvements", []),
            skill_gaps=llm_result.get("skill_gaps", []),
            next_steps=llm_result.get("next_steps", []),
            metadata=llm_result.get("metadata", {}),
        )

    def analyze_job_specific(
        self,
        profile: UserProfile,
        job: JobListing,
        resume_path: str = "",
    ) -> ResumeAnalysis:
        """
        Analyze resume with respect to a specific job.

        Args:
            profile: User profile from parsed resume
            job: Target job listing
            resume_path: Path to the resume file

        Returns:
            ResumeAnalysis with job-specific assessment
        """
        job_context = self._prepare_job_context(job)
        profile_context = self._prepare_profile_context(profile)

        user_content = (
            self.job_specific_template["user"]
            .replace("{{job_context}}", job_context)
            .replace("{{profile_context}}", profile_context)
        )
        messages = [
            Message(
                role=MessageType.SYSTEM,
                content=self.job_specific_template["system"],
            ),
            Message(
                role=MessageType.USER,
                content=user_content,
            ),
        ]

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.RESUME_ANALYSIS,
                temperature=0.3,
                max_tokens=2500,
            )

            llm_result = self._parse_llm_assessment(response.content)
        except Exception as e:
            self.logger.error(f"Job-specific analysis failed: {str(e)}")
            llm_result = self._rule_based_job_assessment(profile, job)

        return ResumeAnalysis(
            resume_path=resume_path,
            analysis_type="job_specific",
            overall_score=llm_result.get("overall_score", 50),
            summary=llm_result.get("summary", f"Job-fit analysis for {job.title}."),
            key_strengths=llm_result.get("key_strengths", []),
            key_improvements=llm_result.get("key_improvements", []),
            skills_assessment=self._build_skills_assessment(profile),
            experience_insights=self._build_experience_insights(profile),
            project_insights=self._build_project_insights(profile),
            resume_improvements=llm_result.get("resume_improvements", []),
            skill_gaps=llm_result.get("skill_gaps", []),
            next_steps=llm_result.get("next_steps", []),
            target_alignment_score=llm_result.get("target_alignment_score"),
            competitive_advantages=llm_result.get("competitive_advantages", []),
            competitive_gaps=llm_result.get("competitive_gaps", []),
            metadata=llm_result.get("metadata", {}),
        )

    def _build_skills_assessment(self, profile: UserProfile) -> list[SkillAssessment]:
        """
        Build skills assessment directly from parsed profile data.

        Args:
            profile: User profile

        Returns:
            List of SkillAssessment objects
        """
        return [
            SkillAssessment(
                skill_name=s.name,
                proficiency_level=s.proficiency or "Intermediate",
                years_experience=s.years_of_experience,
                is_industry_relevant=True,
            )
            for s in profile.skills[:30]
        ]

    def _build_experience_insights(
        self, profile: UserProfile
    ) -> list[ExperienceInsight]:
        """
        Build experience insights directly from parsed profile data.

        Args:
            profile: User profile

        Returns:
            List of ExperienceInsight objects
        """
        return [
            ExperienceInsight(
                company=e.company,
                title=e.title,
                period=f"{e.start_date or 'N/A'} - {e.end_date or 'Present'}",
                strengths=[e.description] if e.description else [],
            )
            for e in profile.experience[:10]
        ]

    def _build_project_insights(self, profile: UserProfile) -> list[ProjectInsight]:
        """
        Build project insights directly from parsed profile data.

        Args:
            profile: User profile

        Returns:
            List of ProjectInsight objects
        """
        return [
            ProjectInsight(
                name=p.name,
                technologies=p.technologies or [],
                impact_score=50.0,
                strengths=[p.description] if p.description else [],
            )
            for p in profile.projects[:10]
        ]

    def _prepare_profile_context(self, profile: UserProfile) -> str:
        """
        Prepare formatted profile context for LLM.

        Args:
            profile: User profile

        Returns:
            Formatted profile string
        """
        parts = []

        parts.append(f"Name: {profile.name}")
        if profile.summary:
            parts.append(f"Summary: {profile.summary}")

        if profile.experience:
            parts.append(f"\nTotal Experience: {profile.years_of_experience} years")
            parts.append("\nWork Experience:")
            for exp in profile.experience[:10]:
                start = exp.start_date or ""
                end = exp.end_date or "Present"
                parts.append(f"- {exp.title} at {exp.company} ({start} - {end})")
                if exp.description:
                    parts.append(f"  Description: {exp.description}")

        if profile.skills:
            parts.append("\nSkills:")
            for skill in profile.skills[:30]:
                proficiency = f" ({skill.proficiency})" if skill.proficiency else ""
                years = (
                    f" - {skill.years_of_experience}y"
                    if skill.years_of_experience
                    else ""
                )
                parts.append(f"- {skill.name}{proficiency}{years}")

        if profile.projects:
            parts.append("\nProjects:")
            for project in profile.projects[:10]:
                technologies = (
                    ", ".join(project.technologies) if project.technologies else "N/A"
                )
                parts.append(f"- {project.name} ({technologies})")
                if project.description:
                    parts.append(f"  Description: {project.description}")

        if profile.education:
            parts.append("\nEducation:")
            for edu in profile.education:
                parts.append(f"- {edu.degree} from {edu.school}")

        return "\n".join(parts)

    def _prepare_job_context(self, job: JobListing) -> str:
        """
        Prepare formatted job context for LLM.

        Args:
            job: Job listing

        Returns:
            Formatted job string
        """
        parts = []

        parts.append(f"Title: {job.title}")
        parts.append(f"Company: {job.company}")
        parts.append(f"Location: {job.location}")

        if job.description:
            parts.append(f"\nDescription:\n{job.description[:500]}...")

        if job.requirements:
            parts.append("\nRequirements:")
            for req in job.requirements[:10]:
                parts.append(f"- {req.text}")

        if job.skills:
            parts.append("\nRequired Skills:")
            for skill in job.skills[:15]:
                parts.append(f"- {skill.name}")

        return "\n".join(parts)

    def _parse_llm_assessment(self, response_content: str) -> dict:
        """
        Parse LLM response for qualitative assessment fields only.

        Extracts scores, summaries, and recommendations from the LLM.
        Does NOT extract skills_assessment, experience_insights, or
        project_insights -- those are built from the parsed profile.

        Args:
            response_content: Raw LLM response

        Returns:
            Dictionary with qualitative assessment data
        """
        json_match = re.search(r"\{.*\}", response_content, re.DOTALL)
        if not json_match:
            raise ValueError("Failed to extract JSON from analysis response")

        data = json.loads(json_match.group(0))

        return {
            "overall_score": data.get("overall_score", 0),
            "summary": data.get("summary", ""),
            "key_strengths": data.get("key_strengths", []),
            "key_improvements": data.get("key_improvements", []),
            "resume_improvements": data.get("resume_improvements", []),
            "skill_gaps": data.get("skill_gaps", []),
            "next_steps": data.get("next_steps", []),
            "target_alignment_score": data.get("target_alignment_score"),
            "competitive_advantages": data.get("competitive_advantages", []),
            "competitive_gaps": data.get("competitive_gaps", []),
            "metadata": data.get("metadata", {}),
        }

    def _rule_based_assessment(self, profile: UserProfile) -> dict:
        """
        Generate a rule-based assessment when LLM is unavailable.

        Args:
            profile: User profile

        Returns:
            Dictionary with assessment data
        """
        score = 50.0
        strengths = []
        improvements = []

        if profile.skills:
            score += min(20, len(profile.skills))
            strengths.append(f"Has {len(profile.skills)} documented skills")
        else:
            improvements.append("Add skills section")

        if profile.experience:
            score += min(20, len(profile.experience) * 5)
            strengths.append(f"Has {len(profile.experience)} work experiences")
        else:
            improvements.append("Add work experience")

        if profile.projects:
            score += min(15, len(profile.projects) * 3)
            strengths.append(f"Has {len(profile.projects)} projects")
        else:
            improvements.append("Add projects to showcase work")

        if profile.summary:
            score += 5
            strengths.append("Has professional summary")
        else:
            improvements.append("Add professional summary")

        return {
            "overall_score": min(100, score),
            "summary": f"Analysis for {profile.name}. Resume has several strengths but also areas for improvement.",
            "key_strengths": strengths[:5],
            "key_improvements": improvements[:5],
            "resume_improvements": improvements,
            "skill_gaps": [],
            "next_steps": ["Review and address improvements listed above"],
        }

    def _rule_based_job_assessment(self, profile: UserProfile, job: JobListing) -> dict:
        """
        Generate a rule-based job-fit assessment when LLM is unavailable.

        Args:
            profile: User profile
            job: Target job listing

        Returns:
            Dictionary with assessment data
        """
        job_skills = {s.name.lower() for s in job.skills}
        profile_skills = {s.name.lower() for s in profile.skills}

        overlap = job_skills & profile_skills
        alignment_score = min(
            100, (len(overlap) / len(job_skills) * 100) if job_skills else 50
        )

        strengths = []
        gaps = []

        if overlap:
            strengths.append(
                f"Has {len(overlap)} matching skills from job requirements"
            )
        else:
            gaps.append("No matching skills found")

        missing_skills = list(job_skills - profile_skills)
        if missing_skills:
            gaps.append(f"Missing {len(missing_skills)} required skills")

        return {
            "overall_score": alignment_score,
            "target_alignment_score": alignment_score,
            "summary": f"Job-fit analysis for {job.title} at {job.company}.",
            "key_strengths": strengths[:5],
            "key_improvements": gaps[:5],
            "resume_improvements": gaps,
            "skill_gaps": [s.title() for s in missing_skills[:5]],
            "next_steps": ["Address skill gaps to improve alignment"],
            "competitive_advantages": strengths,
            "competitive_gaps": gaps,
        }
