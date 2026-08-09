"""
Job Raider - Cover Letter API Routes

Standalone routes for the dedicated Cover Letter tab:
- Generate a tailored cover letter from a manually pasted job description.
- Export an existing cover letter to DOCX or PDF.

Author: Job Raider
Date: 2026-06-29
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...extractors.paste_job import build_job_listing_from_paste
from ...generation.cover_letter_formatter import (
    CoverLetterExportOptions,
    CoverLetterFormatter,
)
from ...generation.cover_letter_service import (
    _adapt_validation_response,
    _build_fallback_validation,
    generate_cover_letter_for_profile,
)
from ...generation.cover_letter_validator import CoverLetterValidator
from ...generation.cover_letter_writer import GeneratedCoverLetter
from ...generation.selector import SelectionOutput
from ...llm.base import Message, MessageType
from ...llm.router import TaskType, create_router
from ...models.user_profile import UserProfile
from ...scoring.matcher import JobMatcher
from ...utils.logger import Components, get_logger
from ..models.requests import (
    CoverLetterExplainRequest,
    CoverLetterExportRequest,
    CoverLetterValidateRequest,
    ManualCoverLetterRequest,
)
from ..models.responses import (
    CoverLetterResponse,
    CoverLetterValidationResponse,
    JdMatchResponse,
    PrepSheetResponse,
    ScoreExplanationResponse,
)
from . import profile as profile_state

router = APIRouter()
logger = get_logger(Components.SCRAPERS)


def _manual_job_listing(request: ManualCoverLetterRequest):
    """
    Build a structured JobListing from a pasted cover-letter request.

    Args:
        request: Manual title, company, location, and description fields.

    Returns:
        Normalized ``JobListing`` with rule-extracted skills/requirements when
        present in the paste.
    """
    from ..settings import get_storage

    llm_router = None
    allow_llm_extract = False
    try:
        settings = get_storage().load_settings()
        if settings.cost_limits.enable_jd_llm_extract:
            allow_llm_extract = True
            llm_router = create_router(prefer_local=True)
    except Exception:
        pass

    return build_job_listing_from_paste(
        title=request.title,
        company=request.company,
        description=request.description,
        location=request.location,
        llm_router=llm_router,
        allow_llm_extract=allow_llm_extract,
    )


def _require_active_profile() -> Dict[str, Any]:
    """
    Return the raw stored profile dict for the active profile.

    Raises:
        HTTPException: If no active profile exists or the stored entry is missing.
    """
    if not profile_state.active_profile_id:
        raise HTTPException(
            status_code=400,
            detail="No active profile found. Upload a resume first.",
        )

    profile = profile_state.stored_profiles.get(profile_state.active_profile_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Profile {profile_state.active_profile_id} not found",
        )

    return profile


def _active_user_profile(profile: Dict[str, Any]) -> UserProfile:
    """
    Return a stored profile entry as a UserProfile instance.

    Resume parsing stores the parsed profile as a UserProfile object, but some
    callers historically assumed a plain dict. Accept either form so both work.

    Args:
        profile: A stored profile entry (as returned by _require_active_profile).

    Returns:
        The active profile as a UserProfile.
    """
    raw = profile["profile"]
    return raw if isinstance(raw, UserProfile) else UserProfile(**raw)


@router.post("/manual", response_model=CoverLetterResponse)
async def generate_manual_cover_letter(
    request: ManualCoverLetterRequest,
    deep: bool = False,
    review: bool = False,
):
    """
    Generate a tailored cover letter from a pasted job description.

    This endpoint is intended for the "other" category of jobs discovered
    outside the platform's scrapers. It reuses the same selector, writer,
    and validator as the job-specific cover-letter endpoint.

    Args:
        request: Manual job details including title, company, and description.
        deep: If True, run LLM-powered validation.
        review: If True, run a single-pass drafter-reviewer loop before
            validation.

    Returns:
        Generated cover letter and validation results.
    """
    profile = _require_active_profile()
    user_profile = _active_user_profile(profile)

    job_listing = _manual_job_listing(request)

    try:
        return await generate_cover_letter_for_profile(
            job_listing,
            user_profile,
            deep=deep,
            review=review,
            style=request.style,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Manual cover-letter generation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Cover letter generation failed: {exc}",
        )


# Common scam / fraudulent-posting signals scanned against the raw JD text.
# Framed as "flags to review", never a definitive verdict on the employer.
_SCAM_PATTERNS: List[Tuple[Any, str, str]] = [
    (
        re.compile(r"\b(registration|training|onboarding|processing)\s+fee\b", re.I),
        "high",
        "Asks for an upfront fee",
    ),
    (
        re.compile(
            r"\b(pay|purchase|buy)\b.{0,30}\b(equipment|starter kit|software|materials)\b",
            re.I,
        ),
        "high",
        "Requires you to pay for equipment or materials",
    ),
    (
        re.compile(
            r"\bwire\s+transfer\b|\bgift\s+cards?\b|\bmoneygram\b|\bwestern\s+union\b",
            re.I,
        ),
        "high",
        "Mentions wire transfer or gift cards",
    ),
    (
        re.compile(
            r"\b(bank\s+account|routing\s+number|social\s+security|ssn|passport\s+number|credit\s+card)\b",
            re.I,
        ),
        "high",
        "Requests bank or personal-identity details upfront",
    ),
    (
        re.compile(
            r"\b(reshipp?ing|package\s+forwarding|money\s+(transfer|mule)|payment\s+processing)\b",
            re.I,
        ),
        "high",
        "Reshipping or money-mule language",
    ),
    (
        re.compile(r"\b(telegram|whatsapp|signal)\b", re.I),
        "medium",
        "Directs contact to Telegram, WhatsApp, or Signal",
    ),
    (
        re.compile(r"@(gmail|yahoo|hotmail|outlook|proton(mail)?)\.com", re.I),
        "medium",
        "Uses a personal email domain instead of a company one",
    ),
    (
        re.compile(r"\bguaranteed\s+(income|job|salary|placement)\b", re.I),
        "medium",
        "Promises guaranteed income or placement",
    ),
    (
        re.compile(
            r"\bearn\s*\$?\d{3,}\b.{0,20}\b(a\s+)?(day|daily|week|weekly)\b", re.I
        ),
        "medium",
        "Advertises unusually high quick earnings",
    ),
    (
        re.compile(r"\bno\s+interview\b", re.I),
        "low",
        "Claims no interview is required",
    ),
    (
        re.compile(r"\b(immediate\s+start|start\s+today|urgent(ly)?\s+hiring)\b", re.I),
        "low",
        "High-pressure urgency",
    ),
]


def _scan_scam_flags(text: str) -> Tuple[str, List[str]]:
    """
    Scan a job description for common scam / fraud red flags.

    Args:
        text: The raw job description.

    Returns:
        A (risk_level, flags) tuple where risk_level is "low", "medium", or
        "high" and flags is a list of human-readable warnings to review.
    """
    flags: List[str] = []
    severities = set()
    for pattern, severity, message in _SCAM_PATTERNS:
        if pattern.search(text or ""):
            flags.append(message)
            severities.add(severity)
    if "high" in severities:
        level = "high"
    elif "medium" in severities:
        level = "medium"
    else:
        level = "low"
    return level, flags


@router.post("/assess", response_model=JdMatchResponse)
async def assess_job_match(request: ManualCoverLetterRequest):
    """
    Assess how well the active profile matches a pasted job description.

    Runs the heuristic JobMatcher (no LLM call) so the frontend can
    auto-assess on paste with low latency.

    Args:
        request: Manual job details including title, company, and description.

    Returns:
        Match score, verdict, category breakdown, and skill gaps.
    """
    profile = _require_active_profile()
    user_profile = _active_user_profile(profile)

    job_listing = _manual_job_listing(request)

    try:
        result = JobMatcher().score_job(job_listing, user_profile)
    except Exception as exc:
        logger.error("JD match assessment failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Assessment failed: {exc}",
        )

    scam_risk, scam_flags = _scan_scam_flags(job_listing.description or "")

    return JdMatchResponse(
        score=result.total_score,
        passed_threshold=result.passed_threshold,
        recommendation=result.recommendation,
        reasoning=result.reasoning,
        breakdown=result.breakdown,
        matched_keywords=result.matched_keywords,
        missing_skills=result.missing_skills,
        scam_risk=scam_risk,
        scam_flags=scam_flags,
    )


def _parse_json_object(raw: str) -> Dict[str, Any]:
    """
    Extract the first JSON object from an LLM response.

    Strips Markdown code fences and tolerates leading/trailing prose.

    Raises:
        ValueError: If no JSON object can be parsed.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")

    return json.loads(text[start : end + 1])


def _string_list(value: Any, limit: int = 10) -> List[str]:
    """Coerce an LLM-provided value into a bounded list of strings."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:limit]


@router.post("/prep", response_model=PrepSheetResponse)
async def generate_prep_sheet(request: ManualCoverLetterRequest):
    """
    Generate an interview prep sheet for a pasted job description.

    Uses the LLM router (local Qwen first, cloud fallback) to produce
    likely interview questions, honest gaps to prepare answers for, and
    talking points that lead with the profile's strengths.

    Args:
        request: Manual job details including title, company, and description.

    Returns:
        Prep sheet with likely questions, gaps, and talking points.
    """
    profile = _require_active_profile()
    raw = profile["profile"]
    raw_profile = raw.model_dump() if isinstance(raw, UserProfile) else raw
    job_listing = _manual_job_listing(request)

    profile_summary = json.dumps(
        {
            key: raw_profile.get(key)
            for key in ("name", "skills", "experience", "projects", "education")
            if raw_profile.get(key)
        },
        default=str,
    )[:4000]

    system_prompt = (
        "You are an interview preparation assistant. Compare the candidate "
        "profile against the job description and respond with ONLY a JSON "
        "object, no prose, in this exact shape: "
        '{"likely_questions": ["..."], "gaps_to_address": ["..."], '
        '"talking_points": ["..."]}. '
        "likely_questions: 5-7 interview questions this employer would "
        "plausibly ask for this role. gaps_to_address: honest gaps between "
        "the profile and the requirements, each with a one-line mitigation. "
        "talking_points: profile strengths to lead with, tied to the JD."
    )
    requirements_block = ""
    if job_listing.requirements:
        requirements_block = "\nRequirements:\n" + "\n".join(
            f"- {req.text}" for req in job_listing.requirements[:12]
        )
    skills_block = ""
    if job_listing.skills:
        skills_block = "\nSkills: " + ", ".join(s.name for s in job_listing.skills[:20])

    user_prompt = (
        f"Job: {job_listing.title} at {job_listing.company}\n"
        f"Location: {job_listing.location or 'unspecified'}\n\n"
        f"Job description:\n{(job_listing.description or '')[:6000]}"
        f"{requirements_block}{skills_block}\n\n"
        f"Candidate profile (JSON):\n{profile_summary}"
    )

    messages = [
        Message(role=MessageType.SYSTEM, content=system_prompt),
        Message(role=MessageType.USER, content=user_prompt),
    ]

    try:
        llm_router = create_router(prefer_local=True)
        response = await llm_router.generate_async(
            messages, task_type=TaskType.QUESTION_ANSWERING
        )
        parsed = _parse_json_object(response.content)
    except Exception as exc:
        logger.error("Prep sheet generation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Prep sheet generation failed: {exc}",
        )

    return PrepSheetResponse(
        success=True,
        likely_questions=_string_list(parsed.get("likely_questions")),
        gaps_to_address=_string_list(parsed.get("gaps_to_address")),
        talking_points=_string_list(parsed.get("talking_points")),
    )


async def _generate_explanation(
    system_prompt: str, user_prompt: str
) -> ScoreExplanationResponse:
    """
    Run the local-first LLM to produce a strengths/concerns/improvements object.

    Args:
        system_prompt: System instruction constraining the JSON output shape.
        user_prompt: The grounded context to explain.

    Returns:
        Parsed explanation with strengths, concerns, and improvements.
    """
    messages = [
        Message(role=MessageType.SYSTEM, content=system_prompt),
        Message(role=MessageType.USER, content=user_prompt),
    ]
    llm_router = create_router(prefer_local=True)
    response = await llm_router.generate_async(
        messages, task_type=TaskType.QUESTION_ANSWERING
    )
    parsed = _parse_json_object(response.content)
    return ScoreExplanationResponse(
        strengths=_string_list(parsed.get("strengths")),
        concerns=_string_list(parsed.get("concerns")),
        improvements=_string_list(parsed.get("improvements")),
    )


@router.post("/validate", response_model=CoverLetterValidationResponse)
async def validate_cover_letter(request: CoverLetterValidateRequest):
    """
    Validate an edited cover letter and return fresh quality metrics.

    Lets the user edit a generated letter and re-run the proofread/quality
    breakdown on their changes without regenerating. An empty selection is used
    so the deterministic checks (structure, tone, company/title mention, word
    count) run without an extra LLM selection call; deep mode adds an LLM review.

    Args:
        request: Edited cover letter content plus the originating job details.

    Returns:
        Fresh validation metrics for the supplied content.
    """
    profile = _require_active_profile()
    user_profile = _active_user_profile(profile)

    job_listing = _manual_job_listing(request)
    result = GeneratedCoverLetter(
        content=request.content,
        highlighted_experiences=[],
        word_count=len(request.content.split()),
        model_used="user-edited",
    )
    # Derive a lightweight selection from the profile's own projects (no LLM
    # call) so the content and accuracy checks actually run. An empty selection
    # would skip them and produce trivially perfect scores.
    profile_projects = getattr(user_profile, "projects", None) or []
    selection = SelectionOutput(
        selected_projects=[
            {"name": p.name} for p in profile_projects if getattr(p, "name", None)
        ],
        keywords_to_emphasize=[],
        key_achievements=[],
        summary_suggestion="",
        raw_response="",
    )

    try:
        validator = CoverLetterValidator(
            llm_router=create_router(prefer_local=True) if request.deep else None,
            strict_mode=False,
        )
        if request.deep:
            validation = validator.validate_with_llm(
                result,
                job_listing,
                user_profile,
                selection,
                style=request.style,
            )
        else:
            validation = validator.validate(
                result,
                job_listing,
                user_profile,
                selection,
                style=request.style,
            )
    except Exception as exc:
        logger.error("Cover letter validation failed: %s", exc, exc_info=True)
        validation = _build_fallback_validation(result)

    return _adapt_validation_response(validation)


@router.post("/explain-fit", response_model=ScoreExplanationResponse)
async def explain_job_fit(request: ManualCoverLetterRequest):
    """
    Explain, in plain language, why the job-fit score was given.

    Grounds an LLM explanation in the heuristic match result (score, matched
    keywords, missing skills) so the user understands the "why" behind the
    number. On-demand only (never on the auto-assess path).

    Args:
        request: Manual job details.

    Returns:
        Strengths, concerns, and improvements behind the fit score.
    """
    profile = _require_active_profile()
    user_profile = _active_user_profile(profile)

    job_listing = _manual_job_listing(request)
    raw = profile["profile"]
    raw_profile = raw.model_dump() if isinstance(raw, UserProfile) else raw
    profile_summary = json.dumps(
        {
            key: raw_profile.get(key)
            for key in ("name", "skills", "experience", "projects", "education")
            if raw_profile.get(key)
        },
        default=str,
    )[:3500]

    system_prompt = (
        "You explain WHY a job-fit score was given for a candidate. Respond with "
        "ONLY a JSON object, no prose, in this exact shape: "
        '{"strengths": ["..."], "concerns": ["..."], "improvements": ["..."]}. '
        "strengths: concrete reasons the candidate fits, grounded in their "
        "matched skills and experience. concerns: honest gaps or risks, grounded "
        "in the missing skills. improvements: specific actions that would raise "
        "the fit. 2-5 short items per list."
    )
    try:
        match = JobMatcher().score_job(job_listing, user_profile)
        user_prompt = (
            f"Job: {job_listing.title} at {job_listing.company}\n"
            f"Heuristic fit score: {match.total_score}/100 "
            f"(verdict: {match.recommendation})\n"
            f"Matched keywords: {', '.join(match.matched_keywords) or 'none'}\n"
            f"Missing skills: {', '.join(match.missing_skills) or 'none'}\n\n"
            f"Job description:\n{(job_listing.description or '')[:4000]}\n\n"
            f"Candidate profile (JSON):\n{profile_summary}"
        )
        explanation = await _generate_explanation(system_prompt, user_prompt)
        explanation.fit_score = int(match.total_score)
        return explanation
    except Exception as exc:
        logger.error("Fit explanation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Explanation failed: {exc}")


@router.post("/explain-letter", response_model=ScoreExplanationResponse)
async def explain_cover_letter(request: CoverLetterExplainRequest):
    """
    Explain, in plain language, why a cover letter is strong or weak.

    Produces an LLM review describing what works, what is weak or generic, and
    specific edits to improve it. On-demand (never run on every re-validation).

    Args:
        request: Cover letter content plus the originating job details.

    Returns:
        Strengths, concerns, and improvements for the letter.
    """
    job_listing = _manual_job_listing(request)
    system_prompt = (
        "You are a cover-letter reviewer. Respond with ONLY a JSON object, no "
        "prose, in this exact shape: "
        '{"strengths": ["..."], "concerns": ["..."], "improvements": ["..."]}. '
        "strengths: what makes this letter effective for the role. concerns: "
        "what is weak, generic, or missing. improvements: specific edits to make "
        "it stronger. 2-5 short items per list."
    )
    user_prompt = (
        f"Job: {job_listing.title} at {job_listing.company}\n\n"
        f"Job description:\n{(job_listing.description or '')[:3000]}\n\n"
        f"Cover letter:\n{request.content[:4000]}"
    )
    try:
        return await _generate_explanation(system_prompt, user_prompt)
    except Exception as exc:
        logger.error("Letter explanation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Explanation failed: {exc}")


@router.post("/export")
async def export_cover_letter(request: CoverLetterExportRequest):
    """
    Export a cover letter to DOCX or PDF.

    Sender details are optional in the request; when omitted and an active
    profile is available, the formatter falls back to the profile's contact
    information.

    Args:
        request: Export parameters including content, format, company, and title.

    Returns:
        FileResponse streaming the exported document.
    """
    options = CoverLetterExportOptions(
        sender_name=request.sender_name,
        sender_email=request.sender_email,
        sender_location=request.sender_location,
    )

    if profile_state.active_profile_id:
        profile = profile_state.stored_profiles.get(profile_state.active_profile_id)
        if profile:
            raw_profile = profile["profile"]
            contact = raw_profile.get("contact", {})
            options.sender_name = options.sender_name or raw_profile.get("name")
            options.sender_email = options.sender_email or contact.get("email")
            options.sender_location = options.sender_location or contact.get("location")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_company = request.company.replace(" ", "_")
    safe_title = request.title.replace(" ", "_")
    filename = f"cover_letter_{safe_company}_{safe_title}_{timestamp}"

    formatter = CoverLetterFormatter()
    result = formatter.format_letter(
        content=request.content,
        filename=filename,
        formats=[request.format],
        company=request.company,
        title=request.title,
        options=options,
    )

    if not result.success:
        raise HTTPException(
            status_code=500,
            detail="; ".join(result.errors),
        )

    file_path = result.docx_path or result.pdf_path
    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if request.format == "docx"
        else "application/pdf"
    )

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=Path(file_path).name,
    )
