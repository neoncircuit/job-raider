"""
Job Raider - Outcome Storage

This module defines the base of the outcome tracker. It declares the shared
state, and it reads and writes the application files.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .outcome_helpers import application_filename_stem
from .outcome_models import (
    ApplicationOutcome,
    ApplicationStatus,
    CustomApplicationStatus,
    InterviewEvent,
    InterviewStage,
    OfferDetails,
    Outcome,
)


class OutcomeStorage:
    """
    Shared state and file storage of the outcome tracker.

    ``OutcomeTracker.__init__`` sets each attribute. The mixins read them
    through ``self``, and these annotations give mypy their types.
    """

    storage_dir: Path
    custom_statuses_dir: Path
    logger: logging.Logger
    _outcomes: Dict[str, ApplicationOutcome]
    _custom_statuses: Dict[str, CustomApplicationStatus]

    def get_application(self, application_id: str) -> Optional[ApplicationOutcome]:
        """
        Get application outcome by ID.

        Reloads from disk first so multi-worker API processes see peer writes.

        Args:
            application_id: Application ID

        Returns:
            ApplicationOutcome or None if not found
        """
        self._reload_cache()
        return self._outcomes.get(application_id)

    def _reload_cache(self) -> None:
        """
        Rebuild in-memory outcomes from disk.

        Required when uvicorn runs multiple workers: each process has its own
        OutcomeTracker cache, but all share ``data/applications/*.json``.
        """
        self._outcomes.clear()
        self._load_cache()

    def _load_cache(self) -> None:
        """Load outcomes from storage into cache."""
        for filepath in self.storage_dir.glob("*.json"):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)

                outcome = self._deserialize_outcome(data)
                if outcome:
                    self._outcomes[outcome.application_id] = outcome

            except Exception as e:
                self.logger.warning(f"Failed to load outcome from {filepath}: {str(e)}")
                continue

    def _save_outcome(self, outcome: ApplicationOutcome) -> None:
        """Save outcome to file."""
        filepath = (
            self.storage_dir
            / f"{application_filename_stem(outcome.application_id)}.json"
        )

        data = self._serialize_outcome(outcome)

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _serialize_outcome(self, outcome: ApplicationOutcome) -> Dict[str, Any]:
        """Serialize outcome to dict."""
        return {
            "application_id": outcome.application_id,
            "job_title": outcome.job_title,
            "company": outcome.company,
            "applied_date": outcome.applied_date.isoformat(),
            "current_status": outcome.current_status.value,
            "final_outcome": (
                outcome.final_outcome.value if outcome.final_outcome else None
            ),
            "interviews": [
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
            "offer": {
                "salary_min": outcome.offer.salary_min if outcome.offer else None,
                "salary_max": outcome.offer.salary_max if outcome.offer else None,
                "salary_period": (
                    outcome.offer.salary_period if outcome.offer else "annual"
                ),
                "bonus": outcome.offer.bonus if outcome.offer else None,
                "equity": outcome.offer.equity if outcome.offer else None,
                "benefits": outcome.offer.benefits if outcome.offer else [],
                "notes": outcome.offer.notes if outcome.offer else "",
            },
            "timeline_notes": outcome.timeline_notes,
            "metadata": outcome.metadata,
            "custom_status_id": outcome.custom_status_id,
            "external_application_details": outcome.external_application_details,
            "is_bookmarked": outcome.is_bookmarked,
            "is_hidden": outcome.is_hidden,
            "bookmark_date": (
                outcome.bookmark_date.isoformat() if outcome.bookmark_date else None
            ),
            "hidden_date": (
                outcome.hidden_date.isoformat() if outcome.hidden_date else None
            ),
            "status_history": list(outcome.status_history),
        }

    def _deserialize_outcome(
        self, data: Dict[str, Any]
    ) -> Optional[ApplicationOutcome]:
        """Deserialize dict to outcome."""
        try:
            interviews = []
            for i_data in data.get("interviews", []):
                interviews.append(
                    InterviewEvent(
                        stage=InterviewStage(i_data["stage"]),
                        scheduled_date=(
                            datetime.fromisoformat(i_data["scheduled_date"])
                            if i_data.get("scheduled_date")
                            else None
                        ),
                        completed_date=(
                            datetime.fromisoformat(i_data["completed_date"])
                            if i_data.get("completed_date")
                            else None
                        ),
                        feedback=i_data.get("feedback"),
                        outcome=i_data.get("outcome"),
                    )
                )

            offer_data = data.get("offer", {})
            offer = (
                OfferDetails(
                    salary_min=offer_data.get("salary_min"),
                    salary_max=offer_data.get("salary_max"),
                    salary_period=offer_data.get("salary_period", "annual"),
                    bonus=offer_data.get("bonus"),
                    equity=offer_data.get("equity"),
                    benefits=offer_data.get("benefits", []),
                    notes=offer_data.get("notes", ""),
                )
                if offer_data
                else None
            )

            return ApplicationOutcome(
                application_id=data["application_id"],
                job_title=data["job_title"],
                company=data["company"],
                applied_date=datetime.fromisoformat(data["applied_date"]),
                current_status=ApplicationStatus(data["current_status"]),
                final_outcome=(
                    Outcome(data["final_outcome"])
                    if data.get("final_outcome")
                    else None
                ),
                interviews=interviews,
                offer=offer,
                timeline_notes=data.get("timeline_notes", []),
                metadata=data.get("metadata", {}),
                custom_status_id=data.get("custom_status_id"),
                external_application_details=data.get("external_application_details"),
                is_bookmarked=data.get("is_bookmarked", False),
                is_hidden=data.get("is_hidden", False),
                bookmark_date=(
                    datetime.fromisoformat(data["bookmark_date"])
                    if data.get("bookmark_date")
                    else None
                ),
                hidden_date=(
                    datetime.fromisoformat(data["hidden_date"])
                    if data.get("hidden_date")
                    else None
                ),
                status_history=[
                    str(item)
                    for item in data.get("status_history", [])
                    if item is not None and str(item).strip()
                ],
            )

        except Exception as e:
            self.logger.error(f"Failed to deserialize outcome: {str(e)}")
            return None
