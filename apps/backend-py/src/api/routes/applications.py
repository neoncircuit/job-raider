"""
Job Raider - Application Tracking API Routes

API endpoints for job application tracking, quick actions, and dashboard.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from ...metrics.outcome_tracker import (
    ApplicationOutcome,
    ApplicationStatus,
    OutcomeTracker,
)
from ...models.job_listing import JobListing
from ...scrapers.listing_lifecycle import listing_status_for_job_id
from ...scrapers.storage import JobListingStorage
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

# Interview prep and cover-letter routes require at least 50 characters of JD.
_MIN_PREP_DESCRIPTION_CHARS = 50


def _listing_catalog() -> Dict[str, JobListing]:
    """
    Load the canonical job listing catalog for lifecycle joins.

    Isolated so tests can point it at a temp catalog.

    Returns:
        Listings keyed by job_id.
    """
    return JobListingStorage().load_catalog()


def _description_text(metadata: Dict[str, Any]) -> str:
    """
    Return the stored job-description string from application metadata.

    Args:
        metadata: Application metadata mapping.

    Returns:
        Stripped description, or an empty string.
    """
    raw = metadata.get("description")
    if isinstance(raw, str):
        return raw.strip()
    return ""


def _clean_description(raw: str) -> str:
    """
    Normalize a pasted or scraped job description for storage.

    Args:
        raw: Raw description text.

    Returns:
        Cleaned description text.
    """
    from ...extractors.paste_job import clean_pasted_job_description

    return clean_pasted_job_description(raw)


def _clean_listing_url(raw: Any) -> Optional[str]:
    """
    Normalize an optional listing URL for storage and display.

    Empty values are dropped. Scheme-less hosts get ``https://``.
    Non-http schemes are rejected so cards never render an unsafe href.

    Args:
        raw: User-pasted or scraped URL value.

    Returns:
        An http(s) URL string, or None when the value is empty or unsafe.
    """
    if not isinstance(raw, str):
        return None
    url = raw.strip()
    if not url or len(url) > 2048:
        return None
    lowered = url.lower()
    if lowered.startswith(("javascript:", "data:", "file:", "vbscript:")):
        return None
    if url.startswith(("http://", "https://")):
        return url
    if "://" in url.split("/", 1)[0]:
        return None
    return f"https://{url}"


def _apply_cleaned_source_url(metadata: Dict[str, Any]) -> None:
    """
    Clean ``source_url`` on metadata in place, or drop it when invalid.

    Args:
        metadata: Application metadata mapping that may include source_url.
    """
    if "source_url" not in metadata:
        return
    cleaned = _clean_listing_url(metadata.get("source_url"))
    if cleaned:
        metadata["source_url"] = cleaned
    else:
        metadata.pop("source_url", None)


def _resolve_source_url(
    metadata: Dict[str, Any],
    listing: Optional[JobListing] = None,
) -> Optional[str]:
    """
    Return a safe listing URL from metadata, or the catalog listing.

    Args:
        metadata: Application metadata mapping.
        listing: Optional catalog listing for the same job_id.

    Returns:
        An http(s) URL, or None when neither source has a usable URL.
    """
    cleaned = _clean_listing_url(metadata.get("source_url"))
    if cleaned:
        return cleaned
    if listing is not None and listing.source_url:
        return _clean_listing_url(str(listing.source_url))
    return None


def _has_prep_description(
    metadata: Dict[str, Any],
    catalog_description: str = "",
) -> bool:
    """
    Return whether a description is long enough for interview prep.

    Args:
        metadata: Application metadata mapping.
        catalog_description: Optional catalog listing description.

    Returns:
        True when stored or catalog text has at least 50 characters.
    """
    if len(_description_text(metadata)) >= _MIN_PREP_DESCRIPTION_CHARS:
        return True
    return len(catalog_description.strip()) >= _MIN_PREP_DESCRIPTION_CHARS


def _backfill_description_from_catalog(
    outcome: ApplicationOutcome,
    catalog: Dict[str, JobListing],
) -> bool:
    """
    Copy a catalog job description onto the application when metadata has none.

    Args:
        outcome: Application outcome to update.
        catalog: Listings keyed by job_id.

    Returns:
        True when a description was written to metadata.
    """
    metadata = outcome.metadata or {}
    if len(_description_text(metadata)) >= _MIN_PREP_DESCRIPTION_CHARS:
        return False
    listing = catalog.get(outcome.application_id)
    if listing is None:
        return False
    raw = (listing.description or "").strip()
    if len(raw) < _MIN_PREP_DESCRIPTION_CHARS:
        return False
    cleaned = _clean_description(raw)
    if len(cleaned) < _MIN_PREP_DESCRIPTION_CHARS:
        return False
    patch: Dict[str, Any] = {"description": cleaned}
    if listing.source_url and not metadata.get("source_url"):
        patch["source_url"] = str(listing.source_url)
    outcome_tracker.update_status(
        application_id=outcome.application_id,
        status=outcome.current_status,
        metadata=patch,
    )
    return True


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

        outcome_tracker.save_job(
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

    elif request.action == "untrack":
        success = outcome_tracker.delete_application(request.job_id)
        if success:
            return JobActionResponse(
                success=True,
                job_id=request.job_id,
                action="untrack",
                message="Application removed",
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

    When a pasted job description is included in metadata, it is normalized
    before storage so interview prep later sees cleaned text. An optional
    listing URL in metadata is cleaned the same way (scheme added, unsafe
    schemes dropped).
    """
    app_date = None
    if request.application_date:
        try:
            app_date = datetime.fromisoformat(request.application_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    metadata = dict(request.metadata or {})
    _apply_cleaned_source_url(metadata)
    raw_description = metadata.get("description")
    if isinstance(raw_description, str) and raw_description.strip():
        metadata["description"] = _clean_description(raw_description)
    elif len(_description_text(metadata)) < _MIN_PREP_DESCRIPTION_CHARS:
        listing = _listing_catalog().get(request.job_id)
        listing_desc = (listing.description or "").strip() if listing else ""
        if len(listing_desc) >= _MIN_PREP_DESCRIPTION_CHARS:
            metadata["description"] = _clean_description(listing_desc)
            if (
                listing is not None
                and listing.source_url
                and not metadata.get("source_url")
            ):
                metadata["source_url"] = str(listing.source_url)

    outcome = outcome_tracker.track_external_application(
        job_id=request.job_id,
        job_title=request.job_title,
        company=request.company,
        application_date=app_date,
        application_method=request.application_method,
        metadata=metadata or None,
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
        outcome_tracker.get_application(request.job_id)
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
    Update application status, or restore the previous status.

    When ``revert`` is true, ignore ``status`` and pop the stored history
    stack. Remove / untrack stays a separate delete action.
    """
    if request.revert:
        if outcome_tracker.get_application(request.job_id) is None:
            raise HTTPException(status_code=404, detail="Job not found")
        restored = outcome_tracker.revert_status(request.job_id)
        if restored is None:
            raise HTTPException(status_code=400, detail="Nothing to revert")
        return {
            "success": True,
            "job_id": request.job_id,
            "new_status": restored.value,
            "message": "Status reverted successfully",
        }

    if not request.status:
        raise HTTPException(status_code=400, detail="Status is required")

    try:
        status = ApplicationStatus(request.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    extra_metadata = dict(request.metadata or {})
    _apply_cleaned_source_url(extra_metadata)
    raw_description = extra_metadata.get("description")
    if isinstance(raw_description, str) and raw_description.strip():
        extra_metadata["description"] = _clean_description(raw_description)

    success = outcome_tracker.update_status(
        application_id=request.job_id,
        status=status,
        note=request.note,
        metadata=extra_metadata or None,
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
    catalog = _listing_catalog()

    # Build summary
    summary = {
        "total_applications": len(applications),
        "bookmarked": len(outcome_tracker.get_bookmarked_jobs()),
        "hidden": len(outcome_tracker.get_hidden_jobs()),
        "external": len(outcome_tracker.get_external_applications()),
        "expired": 0,
        "by_status": {},
    }

    for app in applications:
        status_key = app.current_status.value
        summary["by_status"][status_key] = summary["by_status"].get(status_key, 0) + 1
        if listing_status_for_job_id(app.application_id, catalog) == "expired":
            summary["expired"] += 1

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

        metadata = app.metadata or {}
        listing = catalog.get(app.application_id)
        catalog_description = (listing.description or "").strip() if listing else ""
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
                "source_url": _resolve_source_url(metadata, listing),
                "listing_status": listing_status_for_job_id(
                    app.application_id, catalog
                ),
                "has_job_description": _has_prep_description(
                    metadata, catalog_description
                ),
                "previous_status": app.previous_status,
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

    When the stored metadata has no job description, copy one from the
    listing catalog so interview prep can run for Jobs-originated rows.
    """
    outcome = outcome_tracker.get_application(job_id)

    if not outcome:
        raise HTTPException(status_code=404, detail="Application not found")

    catalog = _listing_catalog()
    if _backfill_description_from_catalog(outcome, catalog):
        outcome = outcome_tracker.get_application(job_id) or outcome

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
        listing_status=listing_status_for_job_id(outcome.application_id, catalog),
        source_url=_resolve_source_url(
            outcome.metadata or {}, catalog.get(outcome.application_id)
        ),
        previous_status=outcome.previous_status,
    )
