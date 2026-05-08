"""
Job Raider - Profile Management API Routes

API endpoints for resume upload and profile management.

Author: Job Raider
Date: 2026-04-21
"""

import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from ...models.user_profile import UserProfile, ApprenticeshipContract
from ...models.job_listing import JobListing
from ...extractors.resume_parser import ResumeParser
from ...generation.resume_analyzer import ResumeAnalyzer
from ...llm.router import LLMRouter
from ...utils.logger import get_logger, Components
from ..models.requests import ProfileUpdateRequest
from ..models.responses import ProfileResponse, ErrorResponse

router = APIRouter()
logger = get_logger(Components.SCRAPERS)


def _update_apprenticeship(profile: UserProfile, request: ProfileUpdateRequest) -> None:
    """Apply apprenticeship updates from a profile update request.

    If apprenticeship_field is provided, creates or updates the contract.
    If apprenticeship_field is an empty string, clears the contract.
    If no apprenticeship fields are present in the request, does nothing.

    Args:
        profile: The user profile to update.
        request: The update request containing apprenticeship fields.
    """
    from ...extractors.resume_parser import ResumeParser

    has_apprenticeship_fields = any([
        request.apprenticeship_field is not None,
        request.apprenticeship_duration_months is not None,
        request.apprenticeship_employer is not None,
        request.apprenticeship_start_date is not None,
        request.apprenticeship_end_date is not None,
        request.apprenticeship_is_active is not None,
    ])

    if not has_apprenticeship_fields:
        return

    # Empty string clears the apprenticeship
    if request.apprenticeship_field == "":
        profile.apprenticeship = None
        return

    # Build or update apprenticeship contract
    field = request.apprenticeship_field or (
        profile.apprenticeship.field if profile.apprenticeship else None
    )
    if not field:
        return

    parser = ResumeParser()
    profile.apprenticeship = ApprenticeshipContract(
        field=field,
        duration_months=(
            request.apprenticeship_duration_months
            if request.apprenticeship_duration_months is not None
            else (profile.apprenticeship.duration_months if profile.apprenticeship else None)
        ),
        employer=(
            request.apprenticeship_employer
            if request.apprenticeship_employer is not None
            else (profile.apprenticeship.employer if profile.apprenticeship else None)
        ),
        start_date=(
            parser._parse_date(request.apprenticeship_start_date)
            if request.apprenticeship_start_date is not None
            else (profile.apprenticeship.start_date if profile.apprenticeship else None)
        ),
        end_date=(
            parser._parse_date(request.apprenticeship_end_date)
            if request.apprenticeship_end_date is not None
            else (profile.apprenticeship.end_date if profile.apprenticeship else None)
        ),
        is_active=(
            request.apprenticeship_is_active
            if request.apprenticeship_is_active is not None
            else (profile.apprenticeship.is_active if profile.apprenticeship else True)
        ),
    )

# Profile storage (use database in production)
stored_profiles: Dict[str, Dict[str, Any]] = {}

# Active profile ID (single user for now)
active_profile_id: str = None

# Upload directory - resolve relative to project root so it works
# regardless of the working directory (local dev vs Docker container)
_BASE_DIR = Path(__file__).resolve().parents[3]  # backend-py/
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(_BASE_DIR / "data" / "profiles")))
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except PermissionError:
    logger.warning(f"Cannot create upload directory {UPLOAD_DIR}, falling back to /tmp/job-raider/profiles")
    UPLOAD_DIR = Path("/tmp/job-raider/profiles")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload", response_model=Dict[str, str])
async def upload_resume(
    file: UploadFile = File(..., description="Resume file (PDF or DOCX)"),
):
    """
    Upload and parse a resume to create user profile.

    Accepts PDF or DOCX resume files, parses them to extract
    user profile data, and stores the profile for use in pipeline runs.

    Args:
        file: Uploaded resume file

    Returns:
        Dict with profile_id and resume_path
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".docx", ".doc"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PDF and DOCX files are supported.",
        )

    # Generate unique filename
    profile_id = f"profile_{uuid.uuid4().hex[:12]}"
    filename = f"{profile_id}{ext}"
    filepath = UPLOAD_DIR / filename

    # Save uploaded file
    try:
        with filepath.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Parse resume
    try:
        llm_router = LLMRouter()
        parser = ResumeParser(llm_router=llm_router)
        profile = parser.parse_file(str(filepath))

        # Store profile
        stored_profiles[profile_id] = {
            "profile": profile,
            "resume_path": str(filepath),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        # Set as active profile
        global active_profile_id
        active_profile_id = profile_id

        logger.info(f"Created profile {profile_id} from uploaded resume")

        return {
            "profile_id": profile_id,
            "resume_path": str(filepath),
            "message": "Resume uploaded and parsed successfully",
        }

    except Exception as e:
        logger.error(f"Failed to parse resume: {e}", exc_info=True)
        # Clean up uploaded file on parse failure
        if filepath.exists():
            filepath.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse resume: {str(e)}",
        )


@router.get("/", response_model=Dict[str, Any])
async def get_profile():
    """
    Get the current active user profile.

    Returns the profile data that will be used for pipeline runs.

    Returns:
        User profile data
    """
    if not active_profile_id:
        raise HTTPException(
            status_code=404,
            detail="No active profile found. Upload a resume first.",
        )

    if active_profile_id not in stored_profiles:
        raise HTTPException(
            status_code=404,
            detail="Active profile not found in storage.",
        )

    profile_data = stored_profiles[active_profile_id]
    profile = profile_data["profile"]

    return {
        "profile_id": active_profile_id,
        "resume_path": profile_data["resume_path"],
        "contact_info": {
            "name": profile.name,
            "email": profile.contact.email,
            "phone": profile.contact.phone,
            "location": profile.contact.location,
            "linkedin_url": str(profile.contact.linkedin) if profile.contact.linkedin else None,
            "github_url": str(profile.contact.github) if profile.contact.github else None,
            "portfolio_url": str(profile.contact.portfolio) if profile.contact.portfolio else None,
            "website_url": str(profile.contact.website) if profile.contact.website else None,
        },
        "summary": profile.summary,
        "core_skills": profile.core_skills,
        "target_job": {
            "keywords": profile.targets.keywords,
            "locations": profile.targets.locations,
            "experience_levels": [
                e.value if hasattr(e, "value") else e
                for e in profile.targets.experience_levels
            ],
            "remote_preference": profile.targets.remote_preference,
            "salary_min": profile.targets.salary_min,
            "industries": profile.targets.industries,
            "constraint_mode": profile.targets.constraint_mode,
        },
        "skills": [
            {
                "name": s.name,
                "category": s.category.value if hasattr(s.category, "value") else s.category,
                "proficiency": s.proficiency.value if s.proficiency and hasattr(s.proficiency, "value") else s.proficiency,
                "years_of_experience": s.years_of_experience,
            }
            for s in profile.skills
        ],
        "projects": [
            {
                "name": p.name,
                "description": p.description,
                "technologies": p.technologies,
                "url": str(p.url) if p.url else None,
                "start_date": p.start_date.isoformat() if p.start_date else None,
                "end_date": p.end_date.isoformat() if p.end_date else None,
                "highlights": p.highlights,
                "role": p.role,
            }
            for p in profile.projects
        ],
        "work_experience": [
            {
                "company": we.company,
                "title": we.title,
                "location": we.location,
                "start_date": we.start_date.isoformat() if we.start_date else None,
                "end_date": we.end_date.isoformat() if we.end_date else None,
                "current": we.current,
                "description": we.description,
                "highlights": we.highlights,
                "technologies": we.technologies,
            }
            for we in profile.experience
        ],
        "education": [
            {
                "institution": e.school,
                "degree": e.degree,
                "field_of_study": e.description,
                "graduation_date": e.end_date.isoformat() if e.end_date else None,
                "gpa": e.gpa,
                "honors": e.honors,
                "coursework": e.coursework,
            }
            for e in profile.education
        ],
        "certifications": [
            {
                "name": c.name,
                "issuer": c.issuer,
                "issue_date": c.issue_date.isoformat() if c.issue_date else None,
                "expiration_date": c.expiration_date.isoformat() if c.expiration_date else None,
                "credential_id": c.credential_id,
            }
            for c in profile.certifications
        ],
        "languages": profile.languages,
        "years_of_experience": profile.years_of_experience,
        # Application-specific fields
        "visa_status": profile.visa_status.value if profile.visa_status and hasattr(profile.visa_status, "value") else profile.visa_status,
        "visa_expiration_date": profile.visa_expiration_date.isoformat() if profile.visa_expiration_date else None,
        "salary_expectation_min": profile.salary_expectation_min,
        "salary_expectation_max": profile.salary_expectation_max,
        "salary_currency": profile.salary_currency,
        "notice_period_weeks": profile.notice_period_weeks,
        "willing_to_relocate": profile.willing_to_relocate,
        "preferred_work_locations": profile.preferred_work_locations,
        "apprenticeship": (
            {
                "field": profile.apprenticeship.field,
                "duration_months": profile.apprenticeship.duration_months,
                "employer": profile.apprenticeship.employer,
                "start_date": profile.apprenticeship.start_date.isoformat() if profile.apprenticeship.start_date else None,
                "end_date": profile.apprenticeship.end_date.isoformat() if profile.apprenticeship.end_date else None,
                "is_active": profile.apprenticeship.is_active,
            }
            if profile.apprenticeship
            else None
        ),
        "created_at": profile_data["created_at"].isoformat(),
        "updated_at": profile_data["updated_at"].isoformat(),
    }


@router.put("/")
async def update_profile(request: ProfileUpdateRequest):
    """
    Update the active user profile.

    Allows editing specific fields of the user profile.

    Args:
        request: Profile update request

    Returns:
        Updated profile data
    """
    if not active_profile_id:
        raise HTTPException(
            status_code=404,
            detail="No active profile found. Upload a resume first.",
        )

    profile_data = stored_profiles[active_profile_id]
    profile = profile_data["profile"]

    # Update contact info
    if request.name is not None:
        profile.name = request.name
    if request.email is not None:
        profile.contact.email = request.email
    if request.phone is not None:
        profile.contact.phone = request.phone
    if request.location is not None:
        profile.contact.location = request.location
    if request.linkedin_url is not None:
        profile.contact.linkedin = request.linkedin_url
    if request.github_url is not None:
        profile.contact.github = request.github_url
    if request.portfolio_url is not None:
        profile.contact.portfolio = request.portfolio_url

    # Update target job
    if request.target_keywords is not None:
        profile.targets.keywords = request.target_keywords
    if request.target_locations is not None:
        profile.targets.locations = request.target_locations
    if request.remote_preference is not None:
        profile.targets.remote_preference = request.remote_preference
    if request.salary_min is not None:
        profile.targets.salary_min = request.salary_min
    if request.constraint_mode is not None:
        if request.constraint_mode in ("filter", "boost"):
            profile.targets.constraint_mode = request.constraint_mode

    # Update apprenticeship contract
    _update_apprenticeship(profile, request)

    # Update timestamp
    profile_data["updated_at"] = datetime.now()

    logger.info(f"Updated profile {active_profile_id}")

    return {"message": "Profile updated successfully"}


@router.get("/export")
async def export_profile():
    """
    Export the active profile as JSON.

    Returns:
        Profile data in JSON format
    """
    if not active_profile_id:
        raise HTTPException(
            status_code=404,
            detail="No active profile found. Upload a resume first.",
        )

    profile_data = stored_profiles[active_profile_id]
    profile = profile_data["profile"]

    # Convert to dict (Pydantic model)
    return profile.model_dump()


@router.post("/analyze")
async def analyze_resume(
    file: UploadFile = File(..., description="Resume file (PDF or DOCX)"),
    job_description: str = Form(default=None, description="Optional job description for comparison"),
):
    """
    Analyze a resume and provide AI-powered insights.

    Accepts PDF or DOCX resume files and provides general analysis
    or job-specific analysis if a job description is provided.

    Args:
        file: Uploaded resume file
        job_description: Optional job description for comparison

    Returns:
        Resume analysis results with scores and recommendations
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".docx", ".doc"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PDF and DOCX files are supported.",
        )

    # Save uploaded file temporarily
    temp_filepath = UPLOAD_DIR / f"temp_{uuid.uuid4().hex[:12]}{ext}"

    try:
        # Save uploaded file
        with temp_filepath.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        # Parse resume with LLM for full extraction
        llm_router = LLMRouter()
        parser = ResumeParser(llm_router=llm_router)
        profile = parser.parse_file(str(temp_filepath))

        # Create analyzer
        analyzer = ResumeAnalyzer(llm_router)

        # Run analysis
        if job_description:
            # Job-specific analysis
            from ...models.job_listing import JobRequirement, JobResponsibility, Skill

            job = JobListing(
                title="Target Position",
                company="Target Company",
                location="Not specified",
                description=job_description[:2000],
                requirements=[JobRequirement(text=job_description[:500])],
                responsibilities=[JobResponsibility(text="Review job description")],
                skills=[Skill(name="skill")] if True else [],
            )

            analysis = analyzer.analyze_job_specific(profile, job, resume_path=file.filename)
        else:
            # General analysis
            analysis = analyzer.analyze_general(profile, resume_path=file.filename)

        logger.info(f"Completed resume analysis for: {file.filename}")

        # Return analysis results
        return {
            "overall_score": analysis.overall_score,
            "competitive_edge": analysis.competitive_edge,
            "summary": analysis.summary,
            "key_strengths": analysis.key_strengths,
            "key_improvements": analysis.key_improvements,
            "skills_assessment": [
                {
                    "skill_name": s.skill_name,
                    "proficiency_level": s.proficiency_level,
                    "years_experience": s.years_experience,
                    "is_industry_relevant": s.is_industry_relevant,
                    "improvement_suggestions": s.improvement_suggestions,
                }
                for s in analysis.skills_assessment
            ],
            "experience_insights": [
                {
                    "company": e.company,
                    "title": e.title,
                    "period": e.period,
                    "strengths": e.strengths,
                    "gaps": e.gaps,
                    "achievements_to_highlight": e.achievements_to_highlight,
                }
                for e in analysis.experience_insights
            ],
            "project_insights": [
                {
                    "name": p.name,
                    "technologies": p.technologies,
                    "impact_score": p.impact_score,
                    "strengths": p.strengths,
                    "improvements": p.improvements,
                }
                for p in analysis.project_insights
            ],
            "resume_improvements": analysis.resume_improvements,
            "skill_gaps": analysis.skill_gaps,
            "next_steps": analysis.next_steps,
            "target_alignment_score": analysis.target_alignment_score,
            "competitive_advantages": analysis.competitive_advantages,
            "competitive_gaps": analysis.competitive_gaps,
            "analyzed_at": analysis.analyzed_at.isoformat(),
            "analysis_type": analysis.analysis_type,
        }

    except Exception as e:
        logger.error(f"Failed to analyze resume: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze resume: {str(e)}")

    finally:
        # Clean up temporary file
        if temp_filepath.exists():
            temp_filepath.unlink()
