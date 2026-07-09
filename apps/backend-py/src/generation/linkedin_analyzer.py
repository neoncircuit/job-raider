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
from ..utils.logger import Components, get_logger


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
    ) -> LinkedInProfileAnalysis:
        """
        Analyze a LinkedIn profile and provide inbound attraction insights.

        Args:
            input_data: LinkedIn profile input (raw text and/or structured fields)

        Returns:
            LinkedInProfileAnalysis with assessment and recommendations
        """
        profile_context = self._prepare_profile_context(input_data)

        user_content = self.linkedin_template["user"].replace(
            "{{profile_context}}", profile_context
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

        try:
            response = self.llm_router.generate(
                messages=messages,
                task_type=TaskType.LINKEDIN_ANALYSIS,
                temperature=0.3,
                max_tokens=2500,
            )

            llm_result = self._parse_llm_analysis(response.content)
        except Exception as e:
            self.logger.error(f"LinkedIn analysis LLM failed: {str(e)}")
            llm_result = self._rule_based_analysis(input_data)

        return self._build_analysis(llm_result)

    async def analyze_async(
        self,
        input_data: LinkedInProfileInput,
    ) -> LinkedInProfileAnalysis:
        """
        Analyze a LinkedIn profile asynchronously.

        Args:
            input_data: LinkedIn profile input (raw text and/or structured fields)

        Returns:
            LinkedInProfileAnalysis with assessment and recommendations
        """
        profile_context = self._prepare_profile_context(input_data)

        user_content = self.linkedin_template["user"].replace(
            "{{profile_context}}", profile_context
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

        try:
            response = await self.llm_router.generate_async(
                messages=messages,
                task_type=TaskType.LINKEDIN_ANALYSIS,
                temperature=0.3,
                max_tokens=2500,
            )

            llm_result = self._parse_llm_analysis(response.content)
        except Exception as e:
            self.logger.error(f"LinkedIn analysis LLM failed: {str(e)}")
            llm_result = self._rule_based_analysis(input_data)

        return self._build_analysis(llm_result)

    def _prepare_profile_context(self, input_data: LinkedInProfileInput) -> str:
        """
        Prepare formatted profile context for the LLM.

        Args:
            input_data: LinkedIn profile input

        Returns:
            Formatted profile string
        """
        parts = []

        if input_data.raw_text:
            parts.append("RAW PROFILE TEXT:")
            parts.append(input_data.raw_text)
            parts.append("")

        if input_data.headline:
            parts.append(f"Headline: {input_data.headline}")

        if input_data.summary:
            parts.append(f"Summary/About: {input_data.summary}")

        if input_data.industry:
            parts.append(f"Industry: {input_data.industry}")

        if input_data.career_goals:
            parts.append(f"Career Goals: {input_data.career_goals}")

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
                    parts.append(f"  Description: {entry['description']}")

        if input_data.education_entries:
            parts.append("\nEducation:")
            for entry in input_data.education_entries[:5]:
                school = entry.get("school", "N/A")
                degree = entry.get("degree", "N/A")
                parts.append(f"- {degree} from {school}")

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

    def _rule_based_analysis(self, input_data: LinkedInProfileInput) -> Dict[str, Any]:
        """
        Generate a rule-based analysis when the LLM is unavailable.

        Computes basic scores from provided data (profile length, headline/summary/
        skills presence, keyword density) and returns a valid analysis dict.

        Args:
            input_data: LinkedIn profile input

        Returns:
            Dictionary with analysis data
        """
        score = 50.0
        section_scores: List[Dict[str, Any]] = []
        insights: List[Dict[str, Any]] = []
        keyword_recommendations: List[str] = []
        action_plan: List[str] = []
        generated_headline_options: List[str] = []
        summary_rewrite_suggestions: List[str] = []

        # Headline scoring
        if input_data.headline:
            headline_score = min(100, 60 + len(input_data.headline) // 2)
            if len(input_data.headline) < 40:
                headline_score = 50
                insights.append(
                    {
                        "category": "headline",
                        "observation": "Headline is shorter than recommended.",
                        "recommendation": "Expand headline to 80-120 characters with keywords.",
                        "priority": "medium",
                    }
                )
            section_scores.append(
                {
                    "section_name": "Headline",
                    "score": headline_score,
                    "weight": 0.25,
                    "feedback": "Headline present. Consider adding target role keywords.",
                }
            )
        else:
            score -= 15
            section_scores.append(
                {
                    "section_name": "Headline",
                    "score": 20,
                    "weight": 0.25,
                    "feedback": "No headline provided. Add a keyword-rich headline.",
                }
            )
            insights.append(
                {
                    "category": "headline",
                    "observation": "No headline detected.",
                    "recommendation": "Add a headline with your target role and key skills.",
                    "priority": "high",
                }
            )
            action_plan.append("Write a compelling headline with target role keywords.")

        # Summary scoring
        if input_data.summary:
            summary_score = min(100, 50 + len(input_data.summary) // 5)
            section_scores.append(
                {
                    "section_name": "Summary/About",
                    "score": summary_score,
                    "weight": 0.25,
                    "feedback": "Summary present. Ensure it includes keywords and a call to action.",
                }
            )
        else:
            score -= 15
            section_scores.append(
                {
                    "section_name": "Summary/About",
                    "score": 20,
                    "weight": 0.25,
                    "feedback": "No summary provided. Write an About section with your value proposition.",
                }
            )
            insights.append(
                {
                    "category": "summary",
                    "observation": "No summary/About section detected.",
                    "recommendation": "Add a 3-5 paragraph About section with keywords and achievements.",
                    "priority": "high",
                }
            )
            action_plan.append("Write a keyword-rich About section.")

        # Experience scoring
        if input_data.experience_entries:
            exp_score = min(100, 50 + len(input_data.experience_entries) * 10)
            section_scores.append(
                {
                    "section_name": "Experience",
                    "score": exp_score,
                    "weight": 0.25,
                    "feedback": f"{len(input_data.experience_entries)} experience entries. Ensure each has quantified achievements.",
                }
            )
        else:
            score -= 10
            section_scores.append(
                {
                    "section_name": "Experience",
                    "score": 30,
                    "weight": 0.25,
                    "feedback": "No experience entries. Add detailed work history with achievements.",
                }
            )
            insights.append(
                {
                    "category": "experience",
                    "observation": "No experience entries provided.",
                    "recommendation": "Add at least 2-3 detailed experience entries with metrics.",
                    "priority": "high",
                }
            )

        # Skills scoring
        if input_data.skills:
            skills_score = min(100, 40 + len(input_data.skills) * 2)
            section_scores.append(
                {
                    "section_name": "Skills",
                    "score": skills_score,
                    "weight": 0.15,
                    "feedback": f"{len(input_data.skills)} skills listed. Ensure top skills are endorsed.",
                }
            )
            keyword_recommendations.extend(input_data.skills[:5])
        else:
            score -= 10
            section_scores.append(
                {
                    "section_name": "Skills",
                    "score": 20,
                    "weight": 0.15,
                    "feedback": "No skills listed. Add at least 10 relevant skills.",
                }
            )
            insights.append(
                {
                    "category": "skills",
                    "observation": "No skills detected.",
                    "recommendation": "Add 10-15 relevant skills and request endorsements.",
                    "priority": "high",
                }
            )

        # Education scoring
        if input_data.education_entries:
            section_scores.append(
                {
                    "section_name": "Education",
                    "score": 80,
                    "weight": 0.10,
                    "feedback": "Education section present. Good for credibility.",
                }
            )
        else:
            section_scores.append(
                {
                    "section_name": "Education",
                    "score": 50,
                    "weight": 0.10,
                    "feedback": "No education entries. Add relevant degrees or certifications.",
                }
            )

        # Generate headline options if missing
        if not input_data.headline and input_data.target_roles:
            role = input_data.target_roles[0]
            generated_headline_options = [
                f"{role} | Driving Results Through Innovation",
                f"Experienced {role} | Open to New Opportunities",
                f"{role} Specializing in {input_data.industry or 'the Industry'}",
            ]

        # Generate summary rewrite suggestions if summary is short
        if input_data.summary and len(input_data.summary) < 200:
            summary_rewrite_suggestions = [
                "Expand your summary to 3-5 paragraphs.",
                "Include a clear value proposition in the first sentence.",
                "Add keywords relevant to your target roles.",
            ]

        # Competitive edge assessment
        if score >= 80:
            competitive_edge = "Strong competitive positioning for inbound attraction."
        elif score >= 60:
            competitive_edge = "Good positioning with room for improvement."
        else:
            competitive_edge = (
                "Needs significant improvement to attract inbound interest."
            )

        return {
            "overall_score": max(0, min(100, score)),
            "summary": (
                f"LinkedIn profile analysis based on provided data. "
                f"Overall score: {max(0, min(100, score)):.0f}/100. "
                f"Focus on improving headline, summary, and skills for better inbound attraction."
            ),
            "section_scores": section_scores,
            "insights": insights,
            "keyword_recommendations": keyword_recommendations,
            "action_plan": action_plan,
            "generated_headline_options": generated_headline_options,
            "summary_rewrite_suggestions": summary_rewrite_suggestions,
            "competitive_edge": competitive_edge,
            "metadata": {"analysis_version": "1.0", "analysis_type": "rule_based"},
        }

    def _build_analysis(self, llm_result: Dict[str, Any]) -> LinkedInProfileAnalysis:
        """
        Build a LinkedInProfileAnalysis from a dictionary result.

        Args:
            llm_result: Dictionary with analysis data

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

        return LinkedInProfileAnalysis(
            overall_score=llm_result.get("overall_score", 50),
            summary=llm_result.get(
                "summary",
                "LinkedIn profile analysis completed.",
            ),
            section_scores=section_scores,
            insights=insights,
            keyword_recommendations=llm_result.get("keyword_recommendations", []),
            action_plan=llm_result.get("action_plan", []),
            generated_headline_options=llm_result.get("generated_headline_options", []),
            summary_rewrite_suggestions=llm_result.get(
                "summary_rewrite_suggestions", []
            ),
            competitive_edge=llm_result.get("competitive_edge", ""),
            metadata=llm_result.get("metadata", {}),
        )
