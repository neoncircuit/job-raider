"""
Job Raider - LinkedIn Profile Analyzer

This module implements AI-powered LinkedIn profile analysis that provides
actionable recommendations for inbound attraction: making the profile
discoverable to recruiters and hiring managers.

Author: Job Raider
Date: 2026-06-25
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..llm.base import Message, MessageType
from ..llm.router import LLMRouter, TaskType
from ..models.linkedin_analysis import (
    InboundAttractionInsight,
    LinkedInProfileAnalysis,
    LinkedInProfileInput,
    ProfileSectionScore,
)
from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger
from ..utils.text_normalizer import (
    normalize_linkedin_profile_text,
    normalize_user_prose,
)
from .career_stage import (
    CareerStageContext,
    format_stored_profile_context,
    infer_career_stage,
    is_internship_like,
)


class LinkedInAnalyzer:
    """
    AI-powered LinkedIn profile analyzer.

    Analyzes a LinkedIn profile to provide actionable insights for
    inbound attraction: optimizing the profile so recruiters and hiring
    managers discover and reach out to the candidate.

    Strategy: The LLM is used for qualitative assessments (scores,
    summaries, recommendations) based solely on the provided profile data.
    A rule-based fallback ensures the analyzer always returns a valid
    result even when the LLM is unavailable.
    """

    def __init__(self, llm_router: LLMRouter):
        """
        Initialize the LinkedIn profile analyzer.

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

        with open(config_path, "r", encoding="utf-8") as f:
            templates = yaml.safe_load(f)

        self.linkedin_template = templates["prompts"]["linkedin_analysis"]

    def analyze(
        self,
        input_data: LinkedInProfileInput,
        user_profile: Optional[UserProfile] = None,
    ) -> LinkedInProfileAnalysis:
        """
        Analyze a LinkedIn profile and provide inbound attraction insights.

        Args:
            input_data: LinkedIn profile input (raw text and/or structured fields)
            user_profile: Optional stored Job Raider profile for career-stage context

        Returns:
            LinkedInProfileAnalysis with assessment and recommendations
        """
        messages, stage_ctx = self._build_messages(input_data, user_profile)

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.LINKEDIN_ANALYSIS,
                temperature=0.3,
                max_tokens=3000,
            )

            llm_result = self._parse_llm_analysis(response.content)
        except Exception as e:
            self.logger.error(f"LinkedIn analysis LLM failed: {str(e)}")
            llm_result = self._rule_based_analysis(input_data, stage_ctx)

        return self._build_analysis(llm_result, stage_ctx)

    async def analyze_async(
        self,
        input_data: LinkedInProfileInput,
        user_profile: Optional[UserProfile] = None,
    ) -> LinkedInProfileAnalysis:
        """
        Analyze a LinkedIn profile asynchronously.

        Args:
            input_data: LinkedIn profile input (raw text and/or structured fields)
            user_profile: Optional stored Job Raider profile for career-stage context

        Returns:
            LinkedInProfileAnalysis with assessment and recommendations
        """
        messages, stage_ctx = self._build_messages(input_data, user_profile)

        try:
            response = await self.llm_router.generate_async(
                messages=messages,
                task_type=TaskType.LINKEDIN_ANALYSIS,
                temperature=0.3,
                max_tokens=3000,
            )

            llm_result = self._parse_llm_analysis(response.content)
        except Exception as e:
            self.logger.error(f"LinkedIn analysis LLM failed: {str(e)}")
            llm_result = self._rule_based_analysis(input_data, stage_ctx)

        return self._build_analysis(llm_result, stage_ctx)

    def _build_messages(
        self,
        input_data: LinkedInProfileInput,
        user_profile: Optional[UserProfile] = None,
    ) -> tuple[List[Message], CareerStageContext]:
        """
        Assemble LLM messages with career-stage framing.

        Args:
            input_data: LinkedIn profile input
            user_profile: Optional stored Job Raider profile

        Returns:
            Tuple of (messages, CareerStageContext)
        """
        stage_ctx = infer_career_stage(input_data, user_profile)
        profile_context = self._prepare_profile_context(input_data)
        stored_context = format_stored_profile_context(user_profile)
        user_content = (
            self.linkedin_template["user"]
            .replace("{{career_stage_guidance}}", stage_ctx.guidance)
            .replace("{{stored_profile_context}}", stored_context)
            .replace("{{profile_context}}", profile_context)
        )
        messages = [
            Message(
                role=MessageType.SYSTEM,
                content=self.linkedin_template["system"],
            ),
            Message(
                role=MessageType.USER,
                content=user_content,
            ),
        ]
        return messages, stage_ctx

    def _prepare_profile_context(self, input_data: LinkedInProfileInput) -> str:
        """
        Prepare formatted profile context for the LLM.

        Args:
            input_data: LinkedIn profile input

        Returns:
            Formatted profile string
        """
        parts = []
        prose_max = 8000

        if input_data.raw_text:
            parts.append("RAW PROFILE TEXT:")
            parts.append(normalize_linkedin_profile_text(input_data.raw_text))
            parts.append("")

        if input_data.headline:
            parts.append(f"Headline: {input_data.headline}")

        if input_data.summary:
            summary = normalize_user_prose(input_data.summary, max_chars=prose_max)
            parts.append(f"Summary/About: {summary}")

        if input_data.industry:
            parts.append(f"Industry: {input_data.industry}")

        if input_data.career_goals:
            goals = normalize_user_prose(input_data.career_goals, max_chars=prose_max)
            parts.append(f"Career Goals: {goals}")

        if input_data.target_roles:
            parts.append(f"Target Roles: {', '.join(input_data.target_roles)}")

        if input_data.experience_entries:
            parts.append("\nExperience:")
            for entry in input_data.experience_entries[:10]:
                title = entry.get("title", "N/A")
                company = entry.get("company", "N/A")
                dates = entry.get("dates", "")
                parts.append(f"- {title} at {company} ({dates})")
                if entry.get("description"):
                    desc = normalize_user_prose(
                        entry["description"], max_chars=prose_max
                    )
                    parts.append(f"  Description: {desc}")

        if input_data.education_entries:
            parts.append("\nEducation:")
            for entry in input_data.education_entries[:5]:
                school = entry.get("school", "N/A")
                degree = entry.get("degree", "N/A")
                dates = (
                    entry.get("dates")
                    or entry.get("end_date")
                    or entry.get("end_year")
                    or ""
                )
                date_suffix = f" ({dates})" if dates else ""
                field = entry.get("field") or ""
                field_suffix = f", {field}" if field else ""
                parts.append(f"- {degree}{field_suffix} from {school}{date_suffix}")

        if input_data.skills:
            parts.append(f"\nSkills: {', '.join(input_data.skills[:30])}")

        return "\n".join(parts)

    def _extract_json(self, response_content: str) -> Dict[str, Any]:
        """
        Extract a JSON object from an LLM response.

        Strips markdown fences when present, then locates the first balanced
        JSON object by counting braces while respecting string literals.

        Args:
            response_content: Raw LLM response that may contain markdown or
                surrounding explanatory text.

        Returns:
            Parsed JSON dictionary.

        Raises:
            ValueError: If no valid JSON object can be extracted.
        """
        cleaned = response_content.strip()

        # Try fenced markdown JSON first.
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Find the first '{' and balance braces.
        start = cleaned.find("{")
        if start == -1:
            raise ValueError("No JSON object found in analysis response")

        depth = 0
        end: Optional[int] = None
        in_string = False
        escape = False
        for i, char in enumerate(cleaned[start:], start=start):
            if in_string:
                if escape:
                    escape = False
                    continue
                if char == "\\":
                    escape = True
                    continue
                if char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        if end is None:
            raise ValueError("Unbalanced JSON object in analysis response")

        return json.loads(cleaned[start:end])

    def _parse_llm_analysis(self, response_content: str) -> Dict[str, Any]:
        """
        Parse LLM response into a dictionary.

        Extracts all fields needed to construct a LinkedInProfileAnalysis.

        Args:
            response_content: Raw LLM response

        Returns:
            Dictionary with analysis data

        Raises:
            ValueError: If JSON cannot be extracted or parsed
        """
        try:
            data = self._extract_json(response_content)
        except ValueError as e:
            raise ValueError("Failed to extract JSON from analysis response") from e

        return {
            "overall_score": data.get("overall_score", 50),
            "summary": data.get("summary", ""),
            "section_scores": data.get("section_scores", []),
            "insights": data.get("insights", []),
            "keyword_recommendations": data.get("keyword_recommendations", []),
            "action_plan": data.get("action_plan", []),
            "generated_headline_options": data.get("generated_headline_options", []),
            "summary_rewrite_suggestions": data.get("summary_rewrite_suggestions", []),
            "competitive_edge": data.get("competitive_edge", ""),
            "metadata": data.get("metadata", {}),
        }

    def _rule_based_analysis(
        self,
        input_data: LinkedInProfileInput,
        stage_ctx: Optional[CareerStageContext] = None,
    ) -> Dict[str, Any]:
        """
        Generate a rule-based analysis when the LLM is unavailable.

        Computes basic scores from provided data (profile length, headline/summary/
        skills presence) and returns a valid analysis dict. Scoring copy follows
        the inferred career stage.

        Args:
            input_data: LinkedIn profile input
            stage_ctx: Precomputed career-stage context, if available

        Returns:
            Dictionary with analysis data
        """
        stage_ctx = stage_ctx or infer_career_stage(input_data)
        early = stage_ctx.stage == "early_career"
        intern_seeking = early and stage_ctx.intern_seeking
        score = 50.0
        section_scores: List[Dict[str, Any]] = []
        insights: List[Dict[str, Any]] = []
        keyword_recommendations: List[str] = []
        action_plan: List[str] = []
        generated_headline_options: List[str] = []
        summary_rewrite_suggestions: List[str] = []

        headline_weight = 0.25
        summary_weight = 0.20 if early else 0.25
        experience_weight = 0.25
        skills_weight = 0.20 if early else 0.15
        education_weight = 0.10

        intern_count = sum(
            1
            for entry in input_data.experience_entries
            if is_internship_like(str(entry.get("title") or ""))
        )

        # Headline scoring
        if input_data.headline:
            headline_score = min(100, 60 + len(input_data.headline) // 2)
            if len(input_data.headline) < 40:
                headline_score = 50
                rec = (
                    "State the degree or domain and the intern role you want."
                    if intern_seeking
                    else (
                        "State the degree or domain and the full-time junior "
                        "or entry role you want."
                        if early
                        else "Expand headline to 80-120 characters with keywords."
                    )
                )
                insights.append(
                    {
                        "category": "headline",
                        "observation": "Headline is shorter than recommended.",
                        "recommendation": rec,
                        "priority": "medium",
                    }
                )
            feedback = (
                "Headline present. Keep it aimed at intern-role discovery."
                if intern_seeking
                else (
                    "Headline present. Keep it aimed at full-time junior or "
                    "entry-role discovery."
                    if early
                    else "Headline present. Consider adding target role keywords."
                )
            )
            section_scores.append(
                {
                    "section_name": "Headline",
                    "score": headline_score,
                    "weight": headline_weight,
                    "feedback": feedback,
                }
            )
        else:
            score -= 15
            headline_feedback = (
                "No headline provided. Add an intern-role headline with domain keywords."
                if intern_seeking
                else (
                    "No headline provided. Add a first full-time junior or "
                    "entry headline with domain keywords."
                    if early
                    else "No headline provided. Add a keyword-rich headline."
                )
            )
            section_scores.append(
                {
                    "section_name": "Headline",
                    "score": 20,
                    "weight": headline_weight,
                    "feedback": headline_feedback,
                }
            )
            insights.append(
                {
                    "category": "headline",
                    "observation": "No headline detected.",
                    "recommendation": (
                        "Add a headline that names your field and the intern "
                        "role you want."
                        if intern_seeking
                        else (
                            "Add a headline that names your field and the "
                            "full-time junior or entry role you want."
                            if early
                            else "Add a headline with your target role and key skills."
                        )
                    ),
                    "priority": "high",
                }
            )
            action_plan.append(
                "Write an intern-role headline with domain keywords."
                if intern_seeking
                else (
                    "Write a first full-time junior or entry headline with "
                    "domain keywords."
                    if early
                    else "Write a compelling headline with target role keywords."
                )
            )

        # Summary scoring
        if input_data.summary:
            summary_score = min(100, 50 + len(input_data.summary) // 5)
            summary_feedback = (
                "Summary present. Keep it honest: projects, internships, and "
                "coursework. Do not invent tenure."
                if intern_seeking
                else (
                    "Summary present. Keep it honest: completed training, "
                    "projects, and coursework toward a full-time first role. "
                    "Do not invent tenure."
                    if early
                    else (
                        "Summary present. Ensure it includes keywords and a "
                        "call to action."
                    )
                )
            )
            section_scores.append(
                {
                    "section_name": "Summary/About",
                    "score": summary_score,
                    "weight": summary_weight,
                    "feedback": summary_feedback,
                }
            )
        else:
            score -= 10 if early else 15
            section_scores.append(
                {
                    "section_name": "Summary/About",
                    "score": 30 if early else 20,
                    "weight": summary_weight,
                    "feedback": (
                        "No summary provided. Write a short About that names "
                        "your degree, internships, and the intern role you want."
                        if intern_seeking
                        else (
                            "No summary provided. Write a short About that names "
                            "your degree, completed training, and the full-time "
                            "junior or entry role you want."
                            if early
                            else (
                                "No summary provided. Write an About section with "
                                "your value proposition."
                            )
                        )
                    ),
                }
            )
            insights.append(
                {
                    "category": "summary",
                    "observation": "No summary/About section detected.",
                    "recommendation": (
                        "Write 2-3 honest sentences about your studies, "
                        "projects, and the intern role you are targeting. Do "
                        "not invent years of experience."
                        if intern_seeking
                        else (
                            "Write 2-3 honest sentences about your studies, "
                            "completed training, and the full-time role you "
                            "are targeting. Do not invent years of experience."
                            if early
                            else (
                                "Add a 3-5 paragraph About section with keywords "
                                "and achievements."
                            )
                        )
                    ),
                    "priority": "high",
                }
            )
            action_plan.append(
                "Write an honest About section from internships, projects, "
                "and coursework."
                if intern_seeking
                else (
                    "Write an honest About section from completed training, "
                    "projects, and coursework."
                    if early
                    else "Write a keyword-rich About section."
                )
            )

        # Experience / internships / projects
        if input_data.experience_entries:
            exp_score = min(100, 50 + len(input_data.experience_entries) * 10)
            if intern_seeking:
                exp_feedback = (
                    f"{len(input_data.experience_entries)} entries "
                    f"({intern_count} internships). Detail projects and intern "
                    "work. Do not invent full-time leadership metrics."
                )
            elif early:
                exp_feedback = (
                    f"{len(input_data.experience_entries)} entries "
                    f"({intern_count} internships or traineeships). Frame "
                    "completed training as evidence for a full-time junior "
                    "role. Do not invent full-time leadership metrics."
                )
            else:
                exp_feedback = (
                    f"{len(input_data.experience_entries)} experience entries. "
                    "Ensure each has quantified achievements."
                )
            section_scores.append(
                {
                    "section_name": "Experience",
                    "score": exp_score,
                    "weight": experience_weight,
                    "feedback": exp_feedback,
                }
            )
        else:
            if intern_seeking:
                score -= 5
                exp_feedback = (
                    "No internships yet. Feature projects, coursework, and "
                    "campus or volunteer work as evidence."
                )
                exp_rec = (
                    "Add internships, projects, or relevant coursework with "
                    "concrete outcomes. A long full-time history is not required."
                )
            elif early:
                score -= 5
                exp_feedback = (
                    "No full-time roles yet. Feature completed training, "
                    "projects, and coursework as evidence for a junior role."
                )
                exp_rec = (
                    "Add projects or relevant coursework with concrete "
                    "outcomes. Do not treat internships as the next step."
                )
            else:
                score -= 10
                exp_feedback = (
                    "No experience entries. Add detailed work history with "
                    "achievements."
                )
                exp_rec = "Add at least 2-3 detailed experience entries with metrics."
            section_scores.append(
                {
                    "section_name": "Experience",
                    "score": 45 if early else 30,
                    "weight": experience_weight,
                    "feedback": exp_feedback,
                }
            )
            insights.append(
                {
                    "category": "experience",
                    "observation": "No experience entries provided.",
                    "recommendation": exp_rec,
                    "priority": "high",
                }
            )

        # Skills scoring
        if input_data.skills:
            skills_score = min(100, 40 + len(input_data.skills) * 2)
            skills_feedback = (
                f"{len(input_data.skills)} skills listed. Prefer skills that "
                "match intern or graduate postings."
                if intern_seeking
                else (
                    f"{len(input_data.skills)} skills listed. Prefer skills that "
                    "match junior or entry postings."
                    if early
                    else (
                        f"{len(input_data.skills)} skills listed. Keep them aligned "
                        "to target roles."
                    )
                )
            )
            section_scores.append(
                {
                    "section_name": "Skills",
                    "score": skills_score,
                    "weight": skills_weight,
                    "feedback": skills_feedback,
                }
            )
            keyword_recommendations.extend(input_data.skills[:5])
        else:
            score -= 10
            section_scores.append(
                {
                    "section_name": "Skills",
                    "score": 20,
                    "weight": skills_weight,
                    "feedback": (
                        "No skills listed. Add skills that match intern or "
                        "graduate roles."
                        if intern_seeking
                        else (
                            "No skills listed. Add skills that match junior or "
                            "entry roles."
                            if early
                            else "No skills listed. Add at least 10 relevant skills."
                        )
                    ),
                }
            )
            insights.append(
                {
                    "category": "skills",
                    "observation": "No skills detected.",
                    "recommendation": (
                        "Add 8-12 skills that appear on intern and graduate "
                        "job posts you want."
                        if intern_seeking
                        else (
                            "Add 8-12 skills that appear on junior and entry "
                            "job posts you want."
                            if early
                            else "Add 10-15 relevant skills for your target roles."
                        )
                    ),
                    "priority": "high",
                }
            )

        # Education scoring
        if input_data.education_entries:
            edu_score = 85 if early else 80
            edu_feedback = (
                "Education is a primary signal for first-role search. Include "
                "dates, coursework, and activities."
                if early
                else "Education section present. Good for credibility."
            )
            section_scores.append(
                {
                    "section_name": "Education",
                    "score": edu_score,
                    "weight": education_weight,
                    "feedback": edu_feedback,
                }
            )
        else:
            section_scores.append(
                {
                    "section_name": "Education",
                    "score": 40 if early else 50,
                    "weight": education_weight,
                    "feedback": (
                        "No education entries. Add degree, dates, and relevant "
                        "coursework."
                        if early
                        else (
                            "No education entries. Add relevant degrees or "
                            "certifications."
                        )
                    ),
                }
            )

        # Generate headline options if missing
        if not input_data.headline and input_data.target_roles:
            role = input_data.target_roles[0]
            industry = input_data.industry or "your field"
            if intern_seeking:
                generated_headline_options = [
                    f"{role} | Graduate seeking intern role",
                    f"{industry} graduate | Open to intern and junior {role} roles",
                    f"{role} candidate | Projects and internships",
                ]
            elif early:
                generated_headline_options = [
                    f"{role} | Graduate seeking first full-time role",
                    f"{industry} graduate | Open to junior and entry {role} roles",
                    f"{role} candidate | Completed training and projects",
                ]
            else:
                generated_headline_options = [
                    f"{role} | Driving Results Through Innovation",
                    f"{role} | Open to New Opportunities",
                    f"{role} Specializing in {industry}",
                ]

        # Generate summary rewrite suggestions if summary is short
        if input_data.summary and len(input_data.summary) < 200:
            if intern_seeking:
                summary_rewrite_suggestions = [
                    "Open with the degree and the intern role you want. Do not "
                    "invent years of experience.",
                    "Name 2-3 projects or internships with concrete outcomes.",
                    "List skills that match intern or graduate job posts.",
                ]
            elif early:
                summary_rewrite_suggestions = [
                    "Open with the degree and the full-time junior or entry "
                    "role you want. Do not invent years of experience.",
                    "Name completed training, projects, or coursework with "
                    "concrete outcomes. Do not recommend internships.",
                    "List skills that match junior or entry job posts.",
                ]
            else:
                summary_rewrite_suggestions = [
                    "Expand your summary to 3-5 paragraphs.",
                    "Include a clear value proposition in the first sentence.",
                    "Add keywords relevant to your target roles.",
                ]

        if score >= 80:
            competitive_edge = "Strong competitive positioning for inbound attraction."
        elif score >= 60:
            competitive_edge = "Good positioning with room for improvement."
        else:
            competitive_edge = (
                "Needs significant improvement to attract inbound interest."
            )

        if intern_seeking:
            framing = "Framed as early-career intern-seeking. "
        elif early:
            framing = "Framed as early-career full-time first role. "
        else:
            framing = "Framed as experienced hire. "
        return {
            "overall_score": max(0, min(100, score)),
            "summary": (
                f"LinkedIn profile analysis based on provided data. "
                f"{framing}"
                f"Overall score: {max(0, min(100, score)):.0f}/100. "
                f"Focus on improving headline, summary, and skills for better "
                f"inbound attraction."
            ),
            "section_scores": section_scores,
            "insights": insights,
            "keyword_recommendations": keyword_recommendations,
            "action_plan": action_plan,
            "generated_headline_options": generated_headline_options,
            "summary_rewrite_suggestions": summary_rewrite_suggestions,
            "competitive_edge": competitive_edge,
            "career_stage": stage_ctx.stage,
            "intern_seeking": intern_seeking if early else False,
            "career_stage_label": stage_ctx.label,
            "metadata": {
                "analysis_version": "1.1",
                "analysis_type": "rule_based",
                **stage_ctx.as_metadata(),
            },
        }

    def _build_analysis(
        self,
        llm_result: Dict[str, Any],
        stage_ctx: Optional[CareerStageContext] = None,
    ) -> LinkedInProfileAnalysis:
        """
        Build a LinkedInProfileAnalysis from a dictionary result.

        Args:
            llm_result: Dictionary with analysis data
            stage_ctx: Inferred career-stage context to attach to the result

        Returns:
            LinkedInProfileAnalysis instance
        """
        section_scores = [
            ProfileSectionScore(
                section_name=s.get("section_name", "Unknown"),
                score=s.get("score", 50),
                weight=s.get("weight", 0.2),
                feedback=s.get("feedback", ""),
            )
            for s in llm_result.get("section_scores", [])
        ]

        insights = [
            InboundAttractionInsight(
                category=i.get("category", "general"),
                observation=i.get("observation", ""),
                recommendation=i.get("recommendation", ""),
                priority=i.get("priority", "medium"),
            )
            for i in llm_result.get("insights", [])
        ]

        metadata = dict(llm_result.get("metadata") or {})
        career_stage = llm_result.get("career_stage")
        if stage_ctx is not None:
            metadata.update(stage_ctx.as_metadata())
            career_stage = stage_ctx.stage

        intern_seeking = llm_result.get("intern_seeking")
        career_stage_label = llm_result.get("career_stage_label")
        if stage_ctx is not None:
            intern_seeking = stage_ctx.intern_seeking
            career_stage_label = stage_ctx.label

        return LinkedInProfileAnalysis(
            overall_score=llm_result.get("overall_score", 50),
            summary=llm_result.get(
                "summary",
                "LinkedIn profile analysis completed.",
            ),
            career_stage=career_stage,
            intern_seeking=intern_seeking,
            career_stage_label=career_stage_label,
            section_scores=section_scores,
            insights=insights,
            keyword_recommendations=llm_result.get("keyword_recommendations", []),
            action_plan=llm_result.get("action_plan", []),
            generated_headline_options=llm_result.get("generated_headline_options", []),
            summary_rewrite_suggestions=llm_result.get(
                "summary_rewrite_suggestions", []
            ),
            competitive_edge=llm_result.get("competitive_edge", ""),
            metadata=metadata,
        )
