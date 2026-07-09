"""
Job Raider - Applied Jobs Tracker

Tracks which LinkedIn job IDs have been applied to, using local JSON storage.

Author: Job Raider
Date: 2026-05-04
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set

from ..utils.logger import Components, get_logger


class AppliedJobsTracker:
    """
    Track which job IDs have been applied to via local JSON storage.

    Stores applied job IDs with metadata (title, company, timestamp)
    in a single JSON file for cross-session persistence.
    """

    def __init__(self, storage_dir: str = "data/applied_jobs") -> None:
        """
        Initialize the applied jobs tracker.

        Args:
            storage_dir: Directory for storing applied job data.
        """
        self.logger = get_logger(Components.SUBMISSION)
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._storage_file = self.storage_dir / "applied_ids.json"
        self._applied_data: Dict[str, Dict[str, Any]] = self._load_applied_data()

    def is_applied(self, job_id: str) -> bool:
        """
        Check if a job has already been applied to.

        Args:
            job_id: Unique job identifier.

        Returns:
            True if the job has been recorded as applied.
        """
        return job_id in self._applied_data

    def mark_applied(
        self,
        job_id: str,
        job_title: str,
        company: str,
        source: str = "linkedin",
    ) -> None:
        """
        Record that a job application has been submitted.

        Args:
            job_id: Unique job identifier.
            job_title: Title of the job.
            company: Company name.
            source: Platform where the application was submitted.
        """
        self._applied_data[job_id] = {
            "title": job_title,
            "company": company,
            "source": source,
            "applied_at": datetime.now().isoformat(),
        }
        self._save_applied_data()
        self.logger.info(f"Marked job {job_id} as applied ({job_title} at {company})")

    def get_all_applied_ids(self) -> Set[str]:
        """
        Get all applied job IDs.

        Returns:
            Set of all job IDs that have been applied to.
        """
        return set(self._applied_data.keys())

    def get_applied_data(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for an applied job.

        Args:
            job_id: Unique job identifier.

        Returns:
            Dict with title, company, source, applied_at or None if not found.
        """
        return self._applied_data.get(job_id)

    def remove_applied(self, job_id: str) -> None:
        """
        Remove a job from the applied tracking (e.g., if application failed).

        Args:
            job_id: Unique job identifier to remove.
        """
        if job_id in self._applied_data:
            del self._applied_data[job_id]
            self._save_applied_data()
            self.logger.info(f"Removed job {job_id} from applied tracking")

    def sync_ids(self, job_ids: Set[str], source: str = "linkedin_scrape") -> int:
        """
        Sync external applied IDs into local tracking.

        Useful for importing IDs scraped from LinkedIn's "My Jobs > Applied" page.

        Args:
            job_ids: Set of job IDs confirmed as applied externally.
            source: Source of the applied status.

        Returns:
            Number of newly tracked IDs.
        """
        new_count = 0
        for job_id in job_ids:
            if job_id not in self._applied_data:
                self._applied_data[job_id] = {
                    "title": "Unknown",
                    "company": "Unknown",
                    "source": source,
                    "applied_at": datetime.now().isoformat(),
                }
                new_count += 1
        if new_count > 0:
            self._save_applied_data()
            self.logger.info(f"Synced {new_count} new applied job IDs from {source}")
        return new_count

    def _load_applied_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Load applied job data from JSON file.

        Returns:
            Dict mapping job IDs to application metadata.
        """
        if self._storage_file.exists():
            try:
                with open(self._storage_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                self.logger.warning(f"Failed to load applied jobs data: {e}")
        return {}

    def _save_applied_data(self) -> None:
        """
        Persist applied job data to JSON file.
        """
        try:
            with open(self._storage_file, "w", encoding="utf-8") as f:
                json.dump(self._applied_data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            self.logger.error(f"Failed to save applied jobs data: {e}")
