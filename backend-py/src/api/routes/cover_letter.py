"""
Job Raider - Cover Letter API Routes

Standalone routes for the dedicated Cover Letter tab:
- Generate a tailored cover letter from a manually pasted job description.
- Export an existing cover letter to DOCX or PDF.

Author: Job Raider
Date: 2026-06-29
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...generation.cover_letter_formatter import (
    CoverLetterExportOptions,
    CoverLetterFormatter,
)
from ...generation.cover_letter_service import generate_cover_letter_for_profile
from ...models.job_listing import JobListing, JobSource
from ...models.user_profile import UserProfile
from ...utils.logger import Components, get_logger
from ..models.requests import CoverLetterExportRequest, ManualCoverLetterRequest
from ..models.responses import CoverLetterResponse
from .profile import active_profile_id, stored_profiles

router = APIRouter()
logger = get_logger(Components.SCRAPERS)


def _require_active_profile() -> Dict[str, Any]:
    """
    Return the raw stored profile dict for the active profile.

    Raises:
        HTTPException: If no active profile exists or the stored entry is missing.
    """
    if not active_profile_id:
        raise HTTPException(
            status_code=400,
            detail="No active profile found. Upload a resume first.",
        )

    profile = stored_profiles.get(active_profile_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Profile {active_profile_id} not found",
        )

    return profile


@router.post("/manual", response_model=CoverLetterResponse)
async def generate_manual_cover_letter(
    request: ManualCoverLetterRequest,
    deep: bool = False,
):
    """
    Generate a tailored cover letter from a pasted job description.

    This endpoint is intended for the "other" category of jobs discovered
    outside the platform's scrapers. It reuses the same selector, writer,
    and validator as the job-specific cover-letter endpoint.

    Args:
        request: Manual job details including title, company, and description.
        deep: If True, run LLM-powered validation.

    Returns:
        Generated cover letter and validation results.
    """
    profile = _require_active_profile()
    user_profile = UserProfile(**profile["profile"])

    job_listing = JobListing(
        title=request.title,
        company=request.company,
        job_id=f"manual-{uuid.uuid4().hex[:12]}",
        source=JobSource.MANUAL,
        description=request.description,
        location=request.location,
    )

    try:
        return await generate_cover_letter_for_profile(
            job_listing, user_profile, deep=deep
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Manual cover-letter generation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Cover letter generation failed: {exc}",
        )


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

    if active_profile_id:
        profile = stored_profiles.get(active_profile_id)
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
