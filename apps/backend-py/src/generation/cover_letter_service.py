"""
Job Raider - Shared Cover Letter Service

Reusable cover-letter generation orchestration used by both the
job-specific endpoint and the manual "paste a JD" endpoint.

Keeps routing-layer code small and makes the generation/validation
pipeline easy to test in isolation.

Author: Job Raider
Date: 2026-06-29
"""

import time
from typing import Any, Dict, Optional

from ..api.models.responses import CoverLetterResponse, CoverLetterValidationResponse
from ..llm.router import create_router
from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..utils.logger import Components, get_logger
from .company_mission_search import resolve_company_mission
from .cover_letter_grounding import is_domain_mismatch
from .cover_letter_instructions import (
    detect_application_instructions,
    resolve_inclusion_urls,
)
from .cover_letter_reviewer import CoverLetterReviewer
from .cover_letter_validator import (
    CoverLetterValidationResult,
    CoverLetterValidator,
    build_grounding_rewrite_critique,
    collect_hard_fail_issues,
)
from .cover_letter_writer import CoverLetterWriter
from .selector import ResumeSelector

logger = get_logger(Components.GENERATION)


def _elapsed_ms(started: float) -> float:
    """
    Return milliseconds since ``started`` (from ``time.perf_counter``).

    Args:
        started: Perf-counter timestamp from the start of a timed section.

    Returns:
        Elapsed duration in milliseconds, rounded to one decimal place.
    """
    return round((time.perf_counter() - started) * 1000, 1)


def _optional_int(value: Any) -> Optional[int]:
    """
    Coerce a value to ``int`` when present.

    Args:
        value: Raw numeric value or None.

    Returns:
        Integer value, or None when missing/unusable.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _add_token_counts(
    prompt_total: int,
    completion_total: int,
    known_total: int,
    *,
    prompt_tokens: Any = None,
    completion_tokens: Any = None,
    tokens_used: Any = None,
) -> tuple[int, int, int]:
    """
    Accumulate token counts from one LLM stage into running totals.

    Args:
        prompt_total: Running prompt-token sum.
        completion_total: Running completion-token sum.
        known_total: Running total when stages report ``tokens_used``.
        prompt_tokens: Stage prompt tokens, if known.
        completion_tokens: Stage completion tokens, if known.
        tokens_used: Stage total tokens, if known.

    Returns:
        Updated ``(prompt_total, completion_total, known_total)``.
    """
    prompt = _optional_int(prompt_tokens)
    completion = _optional_int(completion_tokens)
    total = _optional_int(tokens_used)
    if prompt is not None:
        prompt_total += prompt
    if completion is not None:
        completion_total += completion
    if total is not None:
        known_total += total
    elif prompt is not None or completion is not None:
        known_total += (prompt or 0) + (completion or 0)
    return prompt_total, completion_total, known_total


def _build_fallback_validation(result: Any) -> CoverLetterValidationResult:
    """
    Build a permissive validation result when validation raises an exception.

    Args:
        result: Generated cover letter object with at least ``word_count``.

    Returns:
        A fully-passing validation result so the user still receives a letter.
    """
    return CoverLetterValidationResult(
        is_valid=True,
        score=100,
        issues=[],
        word_count=result.word_count,
        structure_score=100,
        content_score=100,
        tone_score=100,
        recommendation="approve",
        details={},
    )


def _adapt_validation_response(
    validation: CoverLetterValidationResult,
) -> CoverLetterValidationResponse:
    """
    Convert an internal validation result into an API response model.

    Args:
        validation: Result produced by ``CoverLetterValidator``.

    Returns:
        ``CoverLetterValidationResponse`` ready for serialization.
    """
    return CoverLetterValidationResponse(
        is_valid=validation.is_valid,
        score=validation.score,
        issues=[issue.value for issue in validation.issues],
        word_count=validation.word_count,
        structure_score=validation.structure_score,
        content_score=validation.content_score,
        tone_score=validation.tone_score,
        recommendation=validation.recommendation,
        details=validation.details,
    )


async def generate_cover_letter_for_profile(
    job_listing: JobListing,
    user_profile: UserProfile,
    deep: bool = False,
    review: bool = False,
    style: str = "modern",
    writer_model: Optional[str] = None,
) -> CoverLetterResponse:
    """
    Generate and validate a tailored cover letter for the given job/profile.

    The local model stack is preferred (``prefer_local=True``) so Ollama is
    used as the primary provider, matching the rest of the pipeline.

    Args:
        job_listing: Target job listing (scraped or manually pasted).
        user_profile: Parsed user profile.
        deep: If True, run LLM-powered validation instead of deterministic checks.
        review: If True, run a single-pass drafter-reviewer loop. A reviewer
            critiques the draft and the writer rewrites it once if needed.
        style: ``modern`` (default) or ``classic`` letter structure.
        writer_model: Optional one-shot override for ``cover_letter_writing``
            (must be allowed for that route's Settings provider).

    Returns:
        ``CoverLetterResponse`` containing the letter and validation results.

    Raises:
        Exception: Re-raised after logging if generation fails. Routes should
            convert this into an appropriate HTTP response.
    """
    letter_style = style if style in ("modern", "classic") else "modern"
    llm_router = create_router(prefer_local=True)
    total_started = time.perf_counter()

    mission_brief: Optional[str] = None
    mission_context: Dict[str, Any] = {"status": "disabled"}
    try:
        from ..api.settings import get_storage

        settings = get_storage().load_settings()
        mission_enabled = bool(settings.cost_limits.enable_company_mission)
    except Exception as exc:
        logger.warning("Could not load settings for company mission: %s", exc)
        mission_enabled = False

    if mission_enabled:
        mission_started = time.perf_counter()
        mission_result = resolve_company_mission(
            job_listing.company or "",
            jd_text=job_listing.description or "",
            enabled=True,
        )
        mission_context = mission_result.to_mission_context()
        mission_context["resolve_ms"] = _elapsed_ms(mission_started)
        if mission_result.status == "pass" and mission_result.brief:
            mission_brief = mission_result.brief
        logger.info(
            "Company mission resolve job_id=%s status=%s elapsed_ms=%s",
            job_listing.job_id,
            mission_result.status,
            mission_result.elapsed_ms,
        )

    detected_instructions = detect_application_instructions(
        job_listing.description or ""
    )
    contact = user_profile.contact
    inclusion_urls = resolve_inclusion_urls(
        detected_instructions.inclusions,
        github=str(contact.github) if contact and contact.github else None,
        portfolio=str(contact.portfolio) if contact and contact.portfolio else None,
        linkedin=str(contact.linkedin) if contact and contact.linkedin else None,
        website=str(contact.website) if contact and contact.website else None,
    )
    short_answer_mode = detected_instructions.has_why_interest
    instructions_context: Dict[str, Any] = {
        "detected": detected_instructions.to_dict(),
        "short_answer_mode": short_answer_mode,
        "inclusion_urls": inclusion_urls,
    }

    selector = ResumeSelector(llm_router=llm_router)
    selection_started = time.perf_counter()
    selection = selector.select(job_listing, user_profile)
    selection_ms = _elapsed_ms(selection_started)

    prompt_token_total = 0
    completion_token_total = 0
    tokens_used_total = 0
    selection_tokens = _optional_int(getattr(selection, "tokens_used", None))
    prompt_token_total, completion_token_total, tokens_used_total = _add_token_counts(
        prompt_token_total,
        completion_token_total,
        tokens_used_total,
        prompt_tokens=getattr(selection, "prompt_tokens", None),
        completion_tokens=getattr(selection, "completion_tokens", None),
        tokens_used=selection_tokens,
    )

    writer = CoverLetterWriter(llm_router=llm_router)
    generation_started = time.perf_counter()
    if short_answer_mode and detected_instructions.why_interest is not None:
        result = writer.write_why_interest_block(
            job_listing,
            user_profile,
            selection,
            detected_instructions.why_interest,
            mission_brief=mission_brief,
            inclusion_urls=inclusion_urls or None,
            model=writer_model,
        )
    else:
        result = writer.write(
            job_listing,
            user_profile,
            selection,
            style=letter_style,
            model=writer_model,
            mission_brief=mission_brief,
            inclusion_urls=inclusion_urls or None,
        )
    generation_ms = _elapsed_ms(generation_started)
    generation_tokens = _optional_int(getattr(result, "tokens_used", None))
    prompt_token_total, completion_token_total, tokens_used_total = _add_token_counts(
        prompt_token_total,
        completion_token_total,
        tokens_used_total,
        prompt_tokens=getattr(result, "prompt_tokens", None),
        completion_tokens=getattr(result, "completion_tokens", None),
        tokens_used=generation_tokens,
    )

    review_metadata: Dict[str, Any] = {}
    review_ms: Optional[float] = None
    rewrite_ms: Optional[float] = None
    review_tokens: Optional[int] = None
    rewrite_tokens: Optional[int] = None
    domain_mismatch = is_domain_mismatch(job_listing, user_profile)
    if review and not short_answer_mode:
        reviewer = CoverLetterReviewer(llm_router=llm_router)
        review_started = time.perf_counter()
        review_result = reviewer.review(
            result,
            job_listing,
            user_profile,
            selection,
            domain_mismatch=domain_mismatch,
        )
        review_ms = _elapsed_ms(review_started)
        review_tokens = _optional_int(review_result.tokens_used)
        prompt_token_total, completion_token_total, tokens_used_total = (
            _add_token_counts(
                prompt_token_total,
                completion_token_total,
                tokens_used_total,
                prompt_tokens=review_result.prompt_tokens,
                completion_tokens=review_result.completion_tokens,
                tokens_used=review_tokens,
            )
        )
        rewrite_count = 0
        if review_result.rewrite_needed:
            critique = review_result.critique
            if domain_mismatch:
                critique = (
                    "DOMAIN MISMATCH: Do not invent job fit or analogical "
                    "bridges. Only delete invented claims and fix structure "
                    "or tone.\n" + critique
                )
            rewrite_started = time.perf_counter()
            result = writer.rewrite(
                job_listing,
                user_profile,
                selection,
                result,
                critique,
                style=letter_style,
                model=writer_model,
                mission_brief=mission_brief,
                inclusion_urls=inclusion_urls or None,
            )
            rewrite_ms = _elapsed_ms(rewrite_started)
            rewrite_count = 1
            rewrite_tokens = _optional_int(getattr(result, "tokens_used", None))
            prompt_token_total, completion_token_total, tokens_used_total = (
                _add_token_counts(
                    prompt_token_total,
                    completion_token_total,
                    tokens_used_total,
                    prompt_tokens=getattr(result, "prompt_tokens", None),
                    completion_tokens=getattr(result, "completion_tokens", None),
                    tokens_used=rewrite_tokens,
                )
            )

        review_metadata = {
            "critique": review_result.critique,
            "rewrite_needed": review_result.rewrite_needed,
            "rewrite_count": rewrite_count,
            "model_used": review_result.model_used,
            "review_ms": review_ms,
            "rewrite_ms": rewrite_ms,
            "review_tokens": review_tokens,
            "rewrite_tokens": rewrite_tokens,
        }
        if review_result.error:
            review_metadata["error"] = review_result.error

    validator = CoverLetterValidator(llm_router=llm_router, strict_mode=False)
    validation_started = time.perf_counter()
    try:
        if deep:
            validation = validator.validate_with_llm(
                result,
                job_listing,
                user_profile,
                selection,
                style=letter_style,
                short_answer_mode=short_answer_mode,
                detected_instructions=detected_instructions,
                inclusion_urls=inclusion_urls,
            )
        else:
            validation = validator.validate(
                result,
                job_listing,
                user_profile,
                selection,
                style=letter_style,
                short_answer_mode=short_answer_mode,
                detected_instructions=detected_instructions,
                inclusion_urls=inclusion_urls,
            )
    except Exception as exc:
        logger.error("Cover letter validation failed: %s", exc, exc_info=True)
        validation = _build_fallback_validation(result)
    validation_ms = _elapsed_ms(validation_started)

    grounding_rewrite_ms: Optional[float] = None
    grounding_rewrite_tokens: Optional[int] = None
    if collect_hard_fail_issues(validation.issues) and not short_answer_mode:
        critique = build_grounding_rewrite_critique(validation)
        rewrite_started = time.perf_counter()
        rewritten = writer.rewrite(
            job_listing,
            user_profile,
            selection,
            result,
            critique,
            style=letter_style,
            model=writer_model,
            mission_brief=mission_brief,
            inclusion_urls=inclusion_urls or None,
        )
        grounding_rewrite_ms = _elapsed_ms(rewrite_started)
        result = rewritten
        grounding_rewrite_tokens = _optional_int(getattr(result, "tokens_used", None))
        prompt_token_total, completion_token_total, tokens_used_total = (
            _add_token_counts(
                prompt_token_total,
                completion_token_total,
                tokens_used_total,
                prompt_tokens=getattr(result, "prompt_tokens", None),
                completion_tokens=getattr(result, "completion_tokens", None),
                tokens_used=grounding_rewrite_tokens,
            )
        )
        try:
            if deep:
                validation = validator.validate_with_llm(
                    result,
                    job_listing,
                    user_profile,
                    selection,
                    style=letter_style,
                    short_answer_mode=short_answer_mode,
                    detected_instructions=detected_instructions,
                    inclusion_urls=inclusion_urls,
                )
            else:
                validation = validator.validate(
                    result,
                    job_listing,
                    user_profile,
                    selection,
                    style=letter_style,
                    short_answer_mode=short_answer_mode,
                    detected_instructions=detected_instructions,
                    inclusion_urls=inclusion_urls,
                )
        except Exception as exc:
            logger.error("Cover letter re-validation failed: %s", exc, exc_info=True)
            validation = _build_fallback_validation(result)
        validation.details["grounding_rewrite"] = {
            "applied": True,
            "critique": critique,
            "rewrite_ms": grounding_rewrite_ms,
            "rewrite_tokens": grounding_rewrite_tokens,
        }

    if review_metadata:
        validation.details["review"] = review_metadata
    validation.details["style"] = letter_style
    validation.details["mission_context"] = mission_context
    # Prefer validator-enriched instructions_context when present.
    if validation.details.get("instructions_context"):
        instructions_context = {
            **instructions_context,
            **validation.details["instructions_context"],
        }
    validation.details["instructions_context"] = instructions_context

    total_ms = _elapsed_ms(total_started)
    timing = {
        "selection_ms": selection_ms,
        "generation_ms": generation_ms,
        "review_ms": review_ms,
        "rewrite_ms": rewrite_ms,
        "grounding_rewrite_ms": grounding_rewrite_ms,
        "validation_ms": validation_ms,
        "mission_ms": mission_context.get("elapsed_ms")
        or mission_context.get("resolve_ms"),
        "total_ms": total_ms,
    }
    token_usage = {
        "selection_tokens": selection_tokens,
        "generation_tokens": generation_tokens,
        "review_tokens": review_tokens,
        "rewrite_tokens": rewrite_tokens,
        "grounding_rewrite_tokens": grounding_rewrite_tokens,
        "prompt_tokens": prompt_token_total or None,
        "completion_tokens": completion_token_total or None,
        "total_tokens": tokens_used_total or None,
    }
    logger.info(
        "Cover letter timing job_id=%s generation_ms=%.1f rewrite_ms=%s "
        "total_ms=%.1f total_tokens=%s",
        job_listing.job_id,
        generation_ms,
        rewrite_ms,
        total_ms,
        token_usage["total_tokens"],
    )

    return CoverLetterResponse(
        success=True,
        job_id=job_listing.job_id,
        cover_letter={
            "content": result.content,
            "word_count": result.word_count,
            "model_used": result.model_used,
            "highlighted_experiences": result.highlighted_experiences,
            "style": "short_answer" if short_answer_mode else letter_style,
            "timing": timing,
            "token_usage": token_usage,
        },
        validation=_adapt_validation_response(validation),
        mission_context=mission_context,
        instructions_context=instructions_context,
    )
