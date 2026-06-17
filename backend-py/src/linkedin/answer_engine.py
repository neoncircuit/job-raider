"""
Job Raider - Question Answer Engine

Generates answers for LinkedIn Easy Apply form questions using a cascading
strategy: rule-based matching, answer bank lookup, then LLM fallback.

Author: Job Raider
Date: 2026-05-04
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml
from pydantic import BaseModel, Field

from ..models.user_profile import (
    Education,
    Skill,
    UserProfile,
    VisaStatus,
    WorkExperience,
)
from ..utils.logger import Components, get_logger
from .form_models import (
    AnswerConfidence,
    FormQuestion,
    ParsedForm,
    QuestionAnswer,
    QuestionType,
)


class AnswerBank(BaseModel):
    """Pre-configured answers for common or custom questions."""

    answers: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of lowercase question text to answer string",
    )

    def load_from_file(self, path: str) -> None:
        """
        Load answers from a YAML file.

        Args:
            path: Path to YAML file with question-answer pairs.
        """
        file_path = Path(path)
        if not file_path.exists():
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for key, value in data.items():
                self.answers[key.lower().strip()] = str(value)
        except (yaml.YAMLError, OSError) as e:
            logger = get_logger(Components.LLM)
            logger.warning(f"Failed to load answer bank from {path}: {e}")

    def save_to_file(self, path: str) -> None:
        """
        Save current answers to a YAML file.

        Args:
            path: Path to save the answer bank.
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(self.answers, f, default_flow_style=False)
        except OSError as e:
            logger = get_logger(Components.LLM)
            logger.warning(f"Failed to save answer bank to {path}: {e}")

    def lookup(self, question_text: str) -> Optional[str]:
        """
        Look up an answer by question text.

        Args:
            question_text: The question to find an answer for.

        Returns:
            Answer string, or None if not found.
        """
        normalized = question_text.lower().strip()
        return self.answers.get(normalized)


class RuleMatcher:
    """A single rule that maps question keywords to a profile-derived answer."""

    keywords: List[str]
    answer_fn: Callable[[UserProfile], Optional[str]]
    description: str

    def __init__(
        self,
        keywords: List[str],
        answer_fn: Callable[[UserProfile], Optional[str]],
        description: str = "",
    ) -> None:
        """
        Initialize a rule matcher.

        Args:
            keywords: Keywords to match in question text.
            answer_fn: Function that extracts the answer from a UserProfile.
            description: Human-readable description of what this rule answers.
        """
        self.keywords = [k.lower() for k in keywords]
        self.answer_fn = answer_fn
        self.description = description

    def matches(self, question_text: str) -> bool:
        """
        Check if this rule matches the given question.

        Args:
            question_text: The question text to check.

        Returns:
            True if any keyword is found in the question text.
        """
        q_lower = question_text.lower()
        return any(kw in q_lower for kw in self.keywords)

    def get_answer(self, profile: UserProfile) -> Optional[str]:
        """
        Get the answer from the user profile.

        Args:
            profile: The user's profile data.

        Returns:
            Answer string, or None if the profile lacks the data.
        """
        return self.answer_fn(profile)


class QuestionAnswerEngine:
    """
    Generate answers for LinkedIn Easy Apply questions.

    Uses a three-tier cascading strategy:
    1. Rule-based matching (HIGH confidence) - deterministic from profile fields
    2. Answer bank lookup (HIGH confidence) - pre-configured by the user
    3. LLM fallback (MEDIUM/LOW confidence) - generated from profile context
    """

    VISA_STATUS_MAP: Dict[VisaStatus, str] = {
        VisaStatus.CITIZEN: "I am a citizen",
        VisaStatus.PERMANENT_RESIDENT: "I am a permanent resident (green card holder)",
        VisaStatus.H1B: "I have an H-1B visa",
        VisaStatus.OTHER_VISA: "I have a valid work visa",
        VisaStatus.NEED_SPONSORSHIP: "I require visa sponsorship",
        VisaStatus.STUDENT_VISA: "I have a student visa (OPT/CPT)",
        VisaStatus.NOT_SPECIFIED: "Prefer not to specify",
    }

    def __init__(
        self,
        user_profile: UserProfile,
        llm_router: Optional[Any] = None,
        answer_bank_path: Optional[str] = None,
    ) -> None:
        """
        Initialize the answer engine.

        Args:
            user_profile: The user's profile data.
            llm_router: Optional LLM router for fallback question answering.
            answer_bank_path: Optional path to YAML file with pre-configured answers.
        """
        self.profile = user_profile
        self.llm_router = llm_router
        self.logger = get_logger(Components.LLM)
        self.answer_bank = AnswerBank()
        if answer_bank_path:
            self.answer_bank.load_from_file(answer_bank_path)
        self._rules = self._build_rules()

    def answer_question(self, question: FormQuestion) -> QuestionAnswer:
        """
        Generate an answer for a single form question.

        Tries rule-based matching first, then answer bank, then LLM.

        Args:
            question: The form question to answer.

        Returns:
            QuestionAnswer with the generated answer and confidence level.
        """
        # Tier 1: Rule-based matching
        rule_answer = self._try_rule_based(question)
        if rule_answer:
            return rule_answer

        # Tier 2: Answer bank
        bank_answer = self._try_answer_bank(question)
        if bank_answer:
            return bank_answer

        # Tier 3: LLM fallback
        llm_answer = self._try_llm(question)
        if llm_answer:
            return llm_answer

        # No answer found
        return QuestionAnswer(
            question=question,
            answer_value="",
            confidence=AnswerConfidence.UNKNOWN,
            source="none",
            needs_review=True,
            reasoning="Could not generate an answer from any source",
        )

    def answer_form(self, parsed_form: ParsedForm) -> List[QuestionAnswer]:
        """
        Generate answers for all questions in a parsed form.

        Args:
            parsed_form: The complete parsed form.

        Returns:
            List of QuestionAnswer objects, one per question.
        """
        answers: List[QuestionAnswer] = []

        for step in parsed_form.steps:
            for question in step.questions:
                if question.question_type.value == "file_upload":
                    # Skip file upload questions - handled separately
                    continue
                answer = self.answer_question(question)
                answers.append(answer)

        return answers

    def _try_rule_based(self, question: FormQuestion) -> Optional[QuestionAnswer]:
        """
        Try to answer using deterministic rules.

        Args:
            question: The form question.

        Returns:
            QuestionAnswer if a rule matches, else None.
        """
        for rule in self._rules:
            if rule.matches(question.question_text):
                answer_value = rule.get_answer(self.profile)
                if answer_value is not None:
                    return QuestionAnswer(
                        question=question,
                        answer_value=answer_value,
                        confidence=AnswerConfidence.HIGH,
                        source=f"rule:{rule.description}",
                        needs_review=False,
                    )
        return None

    def _try_answer_bank(self, question: FormQuestion) -> Optional[QuestionAnswer]:
        """
        Try to answer from the pre-configured answer bank.

        Args:
            question: The form question.

        Returns:
            QuestionAnswer if found in bank, else None.
        """
        answer = self.answer_bank.lookup(question.question_text)
        if answer is not None:
            return QuestionAnswer(
                question=question,
                answer_value=answer,
                confidence=AnswerConfidence.HIGH,
                source="answer_bank",
                needs_review=False,
            )
        return None

    def _try_llm(self, question: FormQuestion) -> Optional[QuestionAnswer]:
        """
        Fall back to LLM for uncommon questions.

        Args:
            question: The form question.

        Returns:
            QuestionAnswer from LLM, or None if LLM is unavailable.
        """
        if not self.llm_router:
            return None

        try:
            from ..llm.router import TaskType

            profile_summary = self._build_profile_summary()
            options_str = ", ".join(question.options) if question.options else "None"

            prompt = (
                f"QUESTION: {question.question_text}\n"
                f"QUESTION TYPE: {question.question_type.value}\n"
                f"OPTIONS: {options_str}\n\n"
                f"APPLICANT PROFILE SUMMARY:\n{profile_summary}"
            )

            response = self.llm_router.generate(
                task_type=TaskType.QUESTION_ANSWERING,
                prompt=prompt,
            )

            if not response:
                return None

            answer_text = response.strip()

            if "NEEDS_MANUAL_REVIEW" in answer_text:
                return QuestionAnswer(
                    question=question,
                    answer_value="",
                    confidence=AnswerConfidence.LOW,
                    source="llm",
                    needs_review=True,
                    reasoning="LLM indicated manual review is needed",
                )

            # Try to parse as JSON for structured response
            answer_value = answer_text
            confidence = AnswerConfidence.MEDIUM
            reasoning = None

            if "{" in answer_text:
                try:
                    import json

                    parsed = json.loads(answer_text[answer_text.index("{") :])
                    answer_value = parsed.get("answer", answer_text)
                    conf = parsed.get("confidence", "medium")
                    confidence = AnswerConfidence(conf)
                    reasoning = parsed.get("reasoning")
                except (json.JSONDecodeError, ValueError):
                    pass

            return QuestionAnswer(
                question=question,
                answer_value=answer_value,
                confidence=confidence,
                source="llm",
                needs_review=confidence
                in (AnswerConfidence.LOW, AnswerConfidence.UNKNOWN),
                reasoning=reasoning,
            )

        except Exception as e:
            self.logger.warning(f"LLM fallback failed for question: {e}")
            return None

    def _build_profile_summary(self) -> str:
        """
        Build a concise text summary of the user profile for LLM context.

        Returns:
            Profile summary string.
        """
        p = self.profile
        lines: List[str] = []

        lines.append(f"Name: {p.name}")
        lines.append(f"Email: {p.contact.email}")
        if p.contact.phone:
            lines.append(f"Phone: {p.contact.phone}")
        if p.contact.location:
            lines.append(f"Location: {p.contact.location}")

        if p.summary:
            lines.append(f"\nSummary: {p.summary}")

        if p.visa_status:
            visa_text = self.VISA_STATUS_MAP.get(p.visa_status, str(p.visa_status))
            lines.append(f"Work Authorization: {visa_text}")

        if p.salary_expectation_min or p.salary_expectation_max:
            salary = f"Salary Expectation: {p.salary_currency} "
            if p.salary_expectation_min and p.salary_expectation_max:
                salary += (
                    f"{p.salary_expectation_min:,.0f} - {p.salary_expectation_max:,.0f}"
                )
            elif p.salary_expectation_min:
                salary += f"{p.salary_expectation_min:,.0f}+"
            lines.append(salary)

        lines.append(f"Willing to Relocate: {'Yes' if p.willing_to_relocate else 'No'}")

        if p.notice_period_weeks is not None:
            lines.append(f"Notice Period: {p.notice_period_weeks} weeks")

        if p.languages:
            lines.append(f"Languages: {', '.join(p.languages)}")

        if p.experience:
            total_years = sum(e.duration_years for e in p.experience)
            lines.append(f"\nTotal Experience: {total_years:.1f} years")
            for exp in p.experience[:3]:
                lines.append(
                    f"  - {exp.title} at {exp.company} ({exp.duration_years:.1f} yrs)"
                )

        if p.education:
            edu = p.education[0]
            lines.append(f"\nHighest Education: {edu.degree} from {edu.school}")

        if p.skills:
            skill_names = [s.name for s in p.skills[:10]]
            lines.append(f"\nKey Skills: {', '.join(skill_names)}")

        return "\n".join(lines)

    def _build_rules(self) -> List[RuleMatcher]:
        """
        Build the list of rule matchers for common question patterns.

        Returns:
            List of RuleMatcher instances.
        """
        profile = self.profile
        rules: List[RuleMatcher] = []

        # Visa / work authorization
        rules.append(
            RuleMatcher(
                keywords=[
                    "visa",
                    "authorization",
                    "sponsor",
                    "work permit",
                    "legally authorized",
                    "right to work",
                ],
                answer_fn=lambda p: (
                    self.VISA_STATUS_MAP.get(p.visa_status) if p.visa_status else None
                ),
                description="visa_status",
            )
        )

        # Salary expectations
        def _salary_answer(p: UserProfile) -> Optional[str]:
            if p.salary_expectation_min and p.salary_expectation_max:
                return f"{p.salary_expectation_min:,.0f} - {p.salary_expectation_max:,.0f} {p.salary_currency}"
            elif p.salary_expectation_min:
                return f"{p.salary_expectation_min:,.0f}+ {p.salary_currency}"
            return None

        rules.append(
            RuleMatcher(
                keywords=[
                    "salary",
                    "compensation",
                    "pay expectation",
                    "expected salary",
                    "salary range",
                ],
                answer_fn=_salary_answer,
                description="salary_expectation",
            )
        )

        # Relocation
        rules.append(
            RuleMatcher(
                keywords=["relocate", "move", "willing to relocate", "relocation"],
                answer_fn=lambda p: "Yes" if p.willing_to_relocate else "No",
                description="relocation",
            )
        )

        # Notice period / start date
        def _notice_answer(p: UserProfile) -> Optional[str]:
            if p.notice_period_weeks is not None:
                if p.notice_period_weeks == 0:
                    return "Immediately available"
                return f"{p.notice_period_weeks} weeks notice"
            return None

        rules.append(
            RuleMatcher(
                keywords=[
                    "notice period",
                    "start date",
                    "when can you start",
                    "earliest start",
                    "available from",
                ],
                answer_fn=_notice_answer,
                description="notice_period",
            )
        )

        # Years of experience
        def _years_experience(p: UserProfile) -> Optional[str]:
            if p.experience:
                total = sum(e.duration_years for e in p.experience)
                return f"{total:.0f} years"
            return None

        rules.append(
            RuleMatcher(
                keywords=[
                    "years of experience",
                    "how many years",
                    "total experience",
                    "experience years",
                ],
                answer_fn=_years_experience,
                description="years_of_experience",
            )
        )

        # Phone number
        rules.append(
            RuleMatcher(
                keywords=[
                    "phone",
                    "phone number",
                    "contact number",
                    "telephone",
                    "mobile",
                ],
                answer_fn=lambda p: p.contact.phone,
                description="phone",
            )
        )

        # Email
        rules.append(
            RuleMatcher(
                keywords=["email", "email address", "e-mail"],
                answer_fn=lambda p: p.contact.email,
                description="email",
            )
        )

        # Location / address
        rules.append(
            RuleMatcher(
                keywords=[
                    "address",
                    "city",
                    "location",
                    "where do you live",
                    "current location",
                ],
                answer_fn=lambda p: p.contact.location,
                description="location",
            )
        )

        # Languages
        rules.append(
            RuleMatcher(
                keywords=["language", "languages", "speak", "fluent"],
                answer_fn=lambda p: ", ".join(p.languages) if p.languages else None,
                description="languages",
            )
        )

        # Education / degree
        def _education_answer(p: UserProfile) -> Optional[str]:
            if p.education:
                edu = p.education[0]
                parts = [edu.degree, edu.school]
                if edu.gpa:
                    parts.append(f"GPA: {edu.gpa}")
                return " - ".join(parts)
            return None

        rules.append(
            RuleMatcher(
                keywords=[
                    "education",
                    "degree",
                    "university",
                    "college",
                    "highest education",
                    "academic",
                ],
                answer_fn=_education_answer,
                description="education",
            )
        )

        # LinkedIn profile
        rules.append(
            RuleMatcher(
                keywords=["linkedin", "linkedin profile", "linkedin url"],
                answer_fn=lambda p: p.contact.linkedin,
                description="linkedin_url",
            )
        )

        # Name
        rules.append(
            RuleMatcher(
                keywords=["full name", "your name", "first name", "last name"],
                answer_fn=lambda p: p.name,
                description="name",
            )
        )

        # Experience with specific skill
        def _skill_experience(p: UserProfile) -> Optional[str]:
            # This is a special rule - handled in _try_rule_based override
            if p.skills:
                years_map = {
                    s.name.lower(): f"{s.years_of_experience} years"
                    for s in p.skills
                    if s.years_of_experience
                }
                return "; ".join(f"{k}: {v}" for k, v in years_map.items())
            return None

        rules.append(
            RuleMatcher(
                keywords=["experience with", "skill in", "proficiency in", "how long"],
                answer_fn=_skill_experience,
                description="skill_experience",
            )
        )

        return rules
