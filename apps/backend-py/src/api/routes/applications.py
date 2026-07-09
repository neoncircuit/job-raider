"""
Job Raider - Application Tracking API Routes

API endpoints for job application tracking, quick actions, and dashboard.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from ...metrics.outcome_tracker import ApplicationStatus, OutcomeTracker
from ...utils.logger import Components, get_logger
from ..models.requests import (
    CreateCustomStatusRequest,
    JobActionRequest,
    SetCustomStatusRequest,
    TrackExternalApplicationRequest,
    UpdateApplicationStatusRequest,
)
from ..models.responses import (
    ApplicationDetailResponse,
    CustomStatusResponse,
    DashboardResponse,
    JobActionResponse,
)

router = APIRouter()
logger = get_logger(Components.SCRAPERS)

# Global tracker instance
outcome_tracker = OutcomeTracker()


@router.post("/actions", response_model=JobActionResponse)
async def perform_job_action(request: JobActionRequest) -> JobActionResponse:
    """
    Perform quick action on a job (save, hide, etc.).
    """
    if request.action == "save":
        title = (
            request.metadata.get("title", "Unknown") if request.metadata else "Unknown"
        )
        company = (
            request.metadata.get("company", "Unknown")
            if request.metadata
            else "Unknown"
        )
        source_url = request.metadata.get("source_url") if request.metadata else None

        outcome = outcome_tracker.save_job(
            job_id=request.job_id,
            job_title=title,
            company=company,
            source_url=source_url,
            metadata=request.metadata,
        )
        return JobActionResponse(
            success=True,
            job_id=request.job_id,
            action="save",
            new_status=ApplicationStatus.SAVED_BOOKMARKED.value,
            message="Job saved successfully",
        )

    elif request.action == "unsave":
        success = outcome_tracker.unsave_job(request.job_id)
        if success:
            return JobActionResponse(
                success=True,
                job_id=request.job_id,
                action="unsave",
                message="Job unsaved",
            )
        raise HTTPException(status_code=404, detail="Job not found")

    elif request.action == "hide":
        success = outcome_tracker.mark_not_interested(
            job_id=request.job_id,
            reason=request.note,
        )
        if success:
            return JobActionResponse(
                success=True,
                job_id=request.job_id,
                action="hide",
                new_status=ApplicationStatus.NOT_INTERESTED.value,
                message="Job hidden",
            )
        raise HTTPException(status_code=404, detail="Job not found")

    elif request.action == "unhide":
        success = outcome_tracker.unhide_job(request.job_id)
        if success:
            return JobActionResponse(
                success=True,
                job_id=request.job_id,
                action="unhide",
                message="Job unhidden",
            )
        raise HTTPException(status_code=404, detail="Job not found")

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")


@router.post("/external")
async def track_external_application(
    request: TrackExternalApplicationRequest,
) -> Dict[str, Any]:
    """
    Track an application made outside the system.
    """
    app_date = None
    if request.application_date:
        try:
            app_date = datetime.fromisoformat(request.application_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    outcome = outcome_tracker.track_external_application(
        job_id=request.job_id,
        job_title=request.job_title,
        company=request.company,
        application_date=app_date,
        application_method=request.application_method,
        metadata=request.metadata,
    )

    return {
        "success": True,
        "application_id": outcome.application_id,
        "status": outcome.current_status.value,
        "message": "External application tracked successfully",
    }


@router.post("/statuses/custom", response_model=CustomStatusResponse)
async def create_custom_status(
    request: CreateCustomStatusRequest,
) -> CustomStatusResponse:
    """
    Create a new custom application status.
    """
    status = outcome_tracker.create_custom_status(
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon,
    )

    return CustomStatusResponse(
        status_id=status.status_id,
        name=status.name,
        description=status.description,
        color=status.color,
        icon=status.icon,
        is_active=status.is_active,
        created_at=status.created_at,
        usage_count=0,
    )


@router.get("/statuses/custom", response_model=List[CustomStatusResponse])
async def get_custom_statuses(active_only: bool = True) -> List[CustomStatusResponse]:
    """
    Get all custom statuses.
    """
    statuses = outcome_tracker.get_custom_statuses(active_only=active_only)

    # Calculate usage counts
    usage_counts = {}
    for outcome in outcome_tracker.get_all_applications():
        if outcome.custom_status_id:
            usage_counts[outcome.custom_status_id] = (
                usage_counts.get(outcome.custom_status_id, 0) + 1
            )

    return [
        CustomStatusResponse(
            status_id=s.status_id,
            name=s.name,
            description=s.description,
            color=s.color,
            icon=s.icon,
            is_active=s.is_active,
            created_at=s.created_at,
            usage_count=usage_counts.get(s.status_id, 0),
        )
        for s in statuses
    ]


@router.post("/statuses/set")
async def set_custom_status(request: SetCustomStatusRequest) -> Dict[str, Any]:
    """
    Set a custom status on an application.
    """
    success = outcome_tracker.set_custom_status(
        job_id=request.job_id,
        custom_status_id=request.custom_status_id,
        note=request.note,
    )

    if success:
        outcome = outcome_tracker.get_application(request.job_id)
        return {
            "success": True,
            "job_id": request.job_id,
            "custom_status_id": request.custom_status_id,
            "status": "custom",
            "message": "Custom status set successfully",
        }

    raise HTTPException(status_code=404, detail="Job or custom status not found")


@router.put("/status")
async def update_application_status(
    request: UpdateApplicationStatusRequest,
) -> Dict[str, Any]:
    """
    Update application status.
    """
    try:
        status = ApplicationStatus(request.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    success = outcome_tracker.update_status(
        application_id=request.job_id,
        status=status,
        note=request.note,
    )

    if success:
        return {
            "success": True,
            "job_id": request.job_id,
            "new_status": request.status,
            "message": "Status updated successfully",
        }

    raise HTTPException(status_code=404, detail="Job not found")


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    status: Optional[str] = None,
    company: Optional[str] = None,
    days: Optional[int] = None,
    include_hidden: bool = False,
    include_bookmarked: bool = True,
    include_external: bool = True,
) -> DashboardResponse:
    """
    Get application dashboard with filtering.
    """
    # Get base applications
    status_filter = ApplicationStatus(status) if status else None
    applications = outcome_tracker.get_all_applications(
        status=status_filter,
        company=company,
        days=days,
    )

    # Apply additional filters
    if not include_hidden:
        applications = [a for a in applications if not a.is_hidden]
    if not include_bookmarked:
        applications = [a for a in applications if not a.is_bookmarked]
    if not include_external:
        applications = [
            a
            for a in applications
            if a.current_status != ApplicationStatus.APPLIED_ELSEWHERE
        ]

    # Get custom statuses
    custom_statuses = outcome_tracker.get_custom_statuses()

    # Build summary
    summary = {
        "total_applications": len(applications),
        "bookmarked": len(outcome_tracker.get_bookmarked_jobs()),
        "hidden": len(outcome_tracker.get_hidden_jobs()),
        "external": len(outcome_tracker.get_external_applications()),
        "by_status": {},
    }

    for app in applications:
        status_key = app.current_status.value
        summary["by_status"][status_key] = summary["by_status"].get(status_key, 0) + 1

    # Convert applications to dict format
    apps_data = []
    for app in applications:
        custom_status = None
        if app.custom_status_id:
            cs = outcome_tracker._custom_statuses.get(app.custom_status_id)
            if cs:
                custom_status = CustomStatusResponse(
                    status_id=cs.status_id,
                    name=cs.name,
                    description=cs.description,
                    color=cs.color,
                    icon=cs.icon,
                    is_active=cs.is_active,
                    created_at=cs.created_at,
                )

        apps_data.append(
            {
                "application_id": app.application_id,
                "job_title": app.job_title,
                "company": app.company,
                "applied_date": app.applied_date.isoformat(),
                "current_status": app.current_status.value,
                "custom_status": custom_status.model_dump() if custom_status else None,
                "is_bookmarked": app.is_bookmarked,
                "is_hidden": app.is_hidden,
                "final_outcome": app.final_outcome.value if app.final_outcome else None,
                "interview_count": app.interview_count,
                "days_since_application": app.days_since_application,
            }
        )

    return DashboardResponse(
        applications=apps_data,
        summary=summary,
        custom_statuses=[
            CustomStatusResponse(
                status_id=cs.status_id,
                name=cs.name,
                description=cs.description,
                color=cs.color,
                icon=cs.icon,
                is_active=cs.is_active,
                created_at=cs.created_at,
            )
            for cs in custom_statuses
        ],
        filters_applied={
            "status": status,
            "company": company,
            "days": days,
            "include_hidden": include_hidden,
            "include_bookmarked": include_bookmarked,
            "include_external": include_external,
        },
    )


@router.get("/{job_id}", response_model=ApplicationDetailResponse)
async def get_application_details(job_id: str) -> ApplicationDetailResponse:
    """
    Get detailed information for a specific application.
    """
    outcome = outcome_tracker.get_application(job_id)

    if not outcome:
        raise HTTPException(status_code=404, detail="Application not found")

    custom_status = None
    if outcome.custom_status_id:
        cs = outcome_tracker._custom_statuses.get(outcome.custom_status_id)
        if cs:
            custom_status = CustomStatusResponse(
                status_id=cs.status_id,
                name=cs.name,
                description=cs.description,
                color=cs.color,
                icon=cs.icon,
                is_active=cs.is_active,
                created_at=cs.created_at,
            )

    return ApplicationDetailResponse(
        application_id=outcome.application_id,
        job_title=outcome.job_title,
        company=outcome.company,
        applied_date=outcome.applied_date,
        current_status=outcome.current_status.value,
        custom_status=custom_status,
        is_bookmarked=outcome.is_bookmarked,
        is_hidden=outcome.is_hidden,
        external_application_details=outcome.external_application_details,
        final_outcome=outcome.final_outcome.value if outcome.final_outcome else None,
        interviews=[
            {
                "stage": i.stage.value,
                "scheduled_date": (
                    i.scheduled_date.isoformat() if i.scheduled_date else None
                ),
                "completed_date": (
                    i.completed_date.isoformat() if i.completed_date else None
                ),
                "feedback": i.feedback,
                "outcome": i.outcome,
            }
            for i in outcome.interviews
        ],
        offer=(
            {
                "salary_min": outcome.offer.salary_min,
                "salary_max": outcome.offer.salary_max,
                "salary_period": outcome.offer.salary_period,
                "bonus": outcome.offer.bonus,
                "equity": outcome.offer.equity,
                "benefits": outcome.offer.benefits,
                "notes": outcome.offer.notes,
            }
            if outcome.offer
            else None
        ),
        timeline_notes=outcome.timeline_notes,
        metadata=outcome.metadata,
    )
