"""
Job Raider - Structured LLM Output

Output models for the LLM tasks that answer in JSON, and one strict parser
(Step 3.7). Each model is the contract of one call site: the router sends
the model's JSON schema to Ollama as ``format``, and the call site checks
the answer with ``parse_structured``. The parser uses no regex.

Author: Job Raider
Date: 2026-10-31
"""

import json
from typing import Dict, List, Literal, Optional, Type, TypeVar

from pydantic import BaseModel, Field, ValidationError

T = TypeVar("T", bound=BaseModel)

Recommendation = Literal["approve", "needs_revision", "reject"]


class StructuredOutputError(ValueError):
    """An LLM answer that is not valid JSON for the expected output model."""

    def __init__(self, reason: str, detail: str) -> None:
        """
        Keep the reason and the detail of the failure.

        Args:
            reason: ``not_json``, ``not_object``, or ``schema``.
            detail: A short description of the problem.
        """
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def strip_code_fence(content: str) -> str:
    """
    Remove one Markdown code fence around an answer, if there is one.

    Args:
        content: The raw LLM answer.

    Returns:
        The text inside the fence, or the stripped answer when it has no fence.
    """
    text = content.strip()
    if not text.startswith("```"):
        return text
    first_newline = text.find("\n")
    if first_newline == -1:
        return text
    body = text[first_newline + 1 :].rstrip()
    if body.endswith("```"):
        body = body[: -len("```")]
    return body.strip()


def parse_structured(content: str, model: Type[T]) -> T:
    """
    Parse a whole LLM answer as one JSON object and validate it.

    Args:
        content: The raw LLM answer. A code fence around it is allowed;
            other text around the JSON is not.
        model: The output model of the task.

    Returns:
        The validated model instance.

    Raises:
        StructuredOutputError: When the answer is not JSON (``not_json``),
            not a JSON object (``not_object``), or does not match the model
            (``schema``).
    """
    text = strip_code_fence(content)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError("not_json", str(exc)) from exc
    if not isinstance(data, dict):
        raise StructuredOutputError("not_object", type(data).__name__)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise StructuredOutputError("schema", f"{exc.error_count()} errors") from exc


def extract_braced_object(content: str) -> Optional[str]:
    """
    Return the text from the first ``{`` to the last ``}`` of an answer.

    This is what the old regex ``\\{.*\\}`` found. Only the eval suite uses
    it, to count the answers that only the old parsing could rescue.

    Args:
        content: The raw LLM answer.

    Returns:
        The braced text, or ``None`` when there is no ``{`` before a ``}``.
    """
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end < start:
        return None
    return content[start : end + 1]


class SelectedProject(BaseModel):
    """One profile project that the selector picks."""

    name: str
    reason: str


class SelectionAnswer(BaseModel):
    """Answer of the selection task (``selector.py``)."""

    selected_projects: List[SelectedProject]
    keywords_to_emphasize: List[str]
    key_achievements: List[str]
    summary_suggestion: str


class WrittenExperience(BaseModel):
    """One experience entry of a written resume."""

    title: str
    company: str
    dates: str
    highlights: List[str]


class WrittenProject(BaseModel):
    """One project entry of a written resume."""

    name: str
    description: str
    technologies: List[str]
    highlights: List[str]


class WrittenEducation(BaseModel):
    """One education entry of a written resume."""

    degree: str
    school: str
    year: str


class ResumeWritingAnswer(BaseModel):
    """Answer of the resume writing task (``resume_writer.py``)."""

    summary: str
    skills: List[str]
    experience: List[WrittenExperience]
    projects: List[WrittenProject]
    education: List[WrittenEducation]


class ResumeValidationAnswer(BaseModel):
    """Answer of the LLM resume validation (``validator.py``)."""

    is_valid: bool
    missing_projects: List[str]
    missing_keywords: List[str]
    fabricated_content: List[str]
    date_inconsistencies: List[str]
    overall_score: int = Field(ge=0, le=100)
    recommendation: Recommendation


class ResumeAnalysisAnswer(BaseModel):
    """Answer of the general and job-specific resume analysis (``resume_analyzer.py``)."""

    overall_score: int = Field(ge=0, le=100)
    summary: str
    key_strengths: List[str]
    key_improvements: List[str]
    resume_improvements: List[str]
    skill_gaps: List[str]
    next_steps: List[str]
    target_alignment_score: Optional[int] = Field(default=None, ge=0, le=100)
    competitive_advantages: List[str] = Field(default_factory=list)
    competitive_gaps: List[str] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)


class CoverLetterReviewAnswer(BaseModel):
    """Answer of the cover letter review (``cover_letter_reviewer.py``)."""

    critique: str
    rewrite_needed: bool


class CoverLetterValidationAnswer(BaseModel):
    """Answer of the LLM cover letter validation (``cover_letter_validator.py``)."""

    structure_score: int = Field(ge=0, le=100)
    content_score: int = Field(ge=0, le=100)
    tone_score: int = Field(ge=0, le=100)
    overall_score: int = Field(ge=0, le=100)
    is_valid: bool
    recommendation: Recommendation
    issues: List[str]


class ParsedBasics(BaseModel):
    """Contact basics of a parsed resume."""

    name: str
    email: Optional[str]
    phone: Optional[str]
    location: Optional[str]
    linkedin: Optional[str]
    github: Optional[str]


class ParsedSkills(BaseModel):
    """Skills of a parsed resume, by group."""

    programming_languages: List[str]
    frameworks: List[str]
    tools: List[str]
    databases: List[str]
    cloud: List[str]
    domains: List[str]


class ParsedExperience(BaseModel):
    """One experience entry of a parsed resume."""

    title: str
    company: str
    location: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    highlights: List[str]


class ParsedProject(BaseModel):
    """One project entry of a parsed resume."""

    name: str
    description: Optional[str]
    technologies: List[str]
    url: Optional[str]
    highlights: List[str]


class ParsedEducation(BaseModel):
    """One education entry of a parsed resume."""

    degree: str
    school: str
    location: Optional[str]
    graduation_year: Optional[str]
    gpa: Optional[str]


class ParsedCertification(BaseModel):
    """One certification of a parsed resume."""

    name: str
    issuer: Optional[str]
    date: Optional[str]


class ParsedTargetJob(BaseModel):
    """Target job preferences inferred from a parsed resume."""

    keywords: List[str]
    locations: List[str]
    experience_levels: List[str]
    remote_preference: Optional[bool]
    industries: List[str]


class ParsedApprenticeship(BaseModel):
    """Apprenticeship or traineeship obligation of a parsed resume."""

    field: Optional[str]
    duration_months: Optional[int]
    employer: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    is_active: Optional[bool]


class ResumeParsingAnswer(BaseModel):
    """Answer of the LLM resume parser (``resume_parser.py``)."""

    basics: ParsedBasics
    summary: Optional[str]
    skills: ParsedSkills
    experience: List[ParsedExperience]
    projects: List[ParsedProject]
    education: List[ParsedEducation]
    certifications: List[ParsedCertification]
    target_job: ParsedTargetJob
    apprenticeship: Optional[ParsedApprenticeship]


class JDExtractionAnswer(BaseModel):
    """Answer of the LLM job description extractor (``jd_extractor.py``)."""

    title: str
    company: str
    location: Optional[str]
    requirements: List[str]
    responsibilities: List[str]
    skills: List[str]
    experience_level: Optional[str]
    salary_range: Optional[str]


class ClassifiedSkill(BaseModel):
    """One skill requirement of a classified job."""

    name: str
    proficiency: str
    is_required: bool
    category: str


class JobClassificationAnswer(BaseModel):
    """Answer of the LLM job classifier (``job_classifier.py``)."""

    industry: str
    role_category: str
    company_size: str
    company_stage: Optional[str]
    work_pace: str
    team_structure: str
    technical_skills: List[ClassifiedSkill]
    soft_skills: List[ClassifiedSkill]
    domain_skills: List[ClassifiedSkill]
    experience_level_confidence: float = Field(ge=0, le=1)
    actual_experience_years: Optional[List[float]]
    management_level: Optional[str]
    impact_scope: Optional[str]
    classification_confidence: float = Field(ge=0, le=1)
    tags: List[str]
    red_flags: List[str]


class PrepSheetAnswer(BaseModel):
    """Answer of the interview prep sheet (``api/routes/cover_letter.py``)."""

    likely_questions: List[str]
    gaps_to_address: List[str]
    talking_points: List[str]


class ScoreExplanationAnswer(BaseModel):
    """Answer of the match-score explanation (``api/routes/cover_letter.py``)."""

    strengths: List[str]
    concerns: List[str]
    improvements: List[str]


class LinkedInSectionScore(BaseModel):
    """Score of one LinkedIn profile section."""

    section_name: str
    score: int = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=1)
    feedback: str


class LinkedInInsight(BaseModel):
    """One observation and recommendation about a LinkedIn profile."""

    category: str
    observation: str
    recommendation: str
    priority: Literal["high", "medium", "low"]


class LinkedInAnalysisAnswer(BaseModel):
    """Answer of the LinkedIn profile analysis (``linkedin_analyzer.py``)."""

    overall_score: int = Field(ge=0, le=100)
    summary: str
    section_scores: List[LinkedInSectionScore]
    insights: List[LinkedInInsight]
    keyword_recommendations: List[str]
    action_plan: List[str]
    generated_headline_options: List[str]
    summary_rewrite_suggestions: List[str]
    competitive_edge: str
    metadata: Dict[str, str] = Field(default_factory=dict)


class AssessmentOption(BaseModel):
    """One option of a multiple-choice assessment question."""

    label: str
    text: str
    is_correct: bool


class AssessmentQuestion(BaseModel):
    """One generated assessment question."""

    question_type: Literal["conceptual", "scenario", "coding", "system_design"]
    answer_format: Literal["freeform", "multiple_choice"]
    difficulty: Literal["beginner", "intermediate", "advanced", "expert"]
    topic: str
    question_text: str
    options: List[AssessmentOption] = Field(default_factory=list)
    correct_answer_hint: str = ""
    time_limit_seconds: Optional[int] = None


class AssessmentQuestionsAnswer(BaseModel):
    """Answer of the assessment question generation (``assessment/engine.py``).

    The questions are inside an object, because Ollama's ``format`` and
    ``parse_structured`` take one JSON object.
    """

    questions: List[AssessmentQuestion]


class AssessmentScoreAnswer(BaseModel):
    """Answer of the free-form and multiple-choice answer scoring (``assessment/engine.py``)."""

    score: float = Field(ge=0, le=100)
    feedback: str
    strengths: List[str]
    improvements: List[str]
    model_answer: str
    is_correct: Optional[bool] = None


class TrustAnalysisAnswer(BaseModel):
    """Answer of the deep trust analysis (``scoring/trust_analyzer.py``)."""

    summary: str
    additional_indicators: List[str]
    confidence_adjustment: float = Field(ge=-0.1, le=0.2)


class FormQuestionAnswer(BaseModel):
    """Answer of the form-question fallback (``linkedin/answer_engine.py``).

    The model writes ``NEEDS_MANUAL_REVIEW`` as the answer when the profile
    does not give one.
    """

    answer: str
    confidence: Literal["high", "medium", "low"]
    reasoning: str


OUTPUT_MODELS: Dict[str, Type[BaseModel]] = {
    "selection": SelectionAnswer,
    "resume_writing": ResumeWritingAnswer,
    "resume_validation": ResumeValidationAnswer,
    "resume_analysis": ResumeAnalysisAnswer,
    "cover_letter_review": CoverLetterReviewAnswer,
    "cover_letter_validation": CoverLetterValidationAnswer,
    "resume_parsing": ResumeParsingAnswer,
    "jd_extraction": JDExtractionAnswer,
    "job_classification": JobClassificationAnswer,
}
