"""
HTTP client for the Job Raider FastAPI backend.

Provides typed methods for every backend endpoint with centralized
error handling, configurable timeouts, and file upload support.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from config.settings import Settings

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Raised when the backend returns an error response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API Error {status_code}: {detail}")


class ConnectionError(Exception):
    """Raised when the backend is unreachable."""


class APIClient:
    """HTTP client for the Job Raider FastAPI backend.

    Wraps all REST endpoints with typed methods, error handling,
    and configurable timeouts. Designed to be stored as a singleton
    in Streamlit session state.

    Args:
        base_url: Base URL of the FastAPI backend (e.g. http://localhost:8000).
        timeout: Default request timeout in seconds.
        search_timeout: Timeout for job search requests (scraping is slow).
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
        search_timeout: int | None = None,
    ) -> None:
        settings = Settings()
        self.base_url = (base_url or settings.BACKEND_API_URL).rstrip("/")
        self.timeout = timeout or settings.REQUEST_TIMEOUT_SEC
        self.search_timeout = search_timeout or settings.SEARCH_TIMEOUT_SEC
        self._session = requests.Session()

    def _request(
        self,
        method: str,
        path: str,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute an HTTP request and return parsed JSON.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: URL path relative to base_url (e.g. /api/health).
            timeout: Request timeout override in seconds.
            **kwargs: Additional arguments passed to requests.

        Returns:
            Parsed JSON response as a dictionary.

        Raises:
            ConnectionError: If the backend is unreachable.
            APIError: If the backend returns a 4xx or 5xx response.
        """
        url = f"{self.base_url}{path}"
        try:
            response = self._session.request(
                method, url, timeout=timeout or self.timeout, **kwargs
            )
        except requests.exceptions.ConnectionError as exc:
            raise ConnectionError(
                f"Backend unreachable at {self.base_url}"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise ConnectionError(
                f"Request to {url} timed out"
            ) from exc

        if response.status_code >= 400:
            detail = ""
            try:
                body = response.json()
                detail = body.get("detail", body.get("message", response.text))
            except ValueError:
                detail = response.text
            raise APIError(response.status_code, detail)

        if response.status_code == 204:
            return {}
        return response.json()

    # -- Health & Version --

    def get_health(self) -> Dict[str, Any]:
        """Get system health check status.

        Returns:
            Health check response with status, checks, and summary.
        """
        return self._request("GET", "/api/health")

    def get_version(self) -> Dict[str, str]:
        """Get API version information.

        Returns:
            Version dict with 'version' and 'name' keys.
        """
        return self._request("GET", "/api/version")

    # -- Pipeline --

    def start_pipeline(self, request: Dict[str, Any]) -> str:
        """Start a new pipeline run.

        Args:
            request: Pipeline configuration (keywords, locations, sources, etc.).

        Returns:
            The run_id of the started pipeline.
        """
        result = self._request("POST", "/api/pipeline/start", json=request)
        return result["run_id"]

    def get_pipeline_status(self, run_id: str) -> Dict[str, Any]:
        """Get current status of a pipeline run.

        Args:
            run_id: The pipeline run identifier.

        Returns:
            Status dict with stage, progress, counters, and timestamps.
        """
        return self._request("GET", f"/api/pipeline/status/{run_id}")

    def get_pipeline_results(self, run_id: str) -> Dict[str, Any]:
        """Get completed results of a pipeline run.

        Args:
            run_id: The pipeline run identifier.

        Returns:
            Full results dict with stage breakdowns and summary metrics.
        """
        return self._request("GET", f"/api/pipeline/results/{run_id}")

    def cancel_pipeline(self, run_id: str) -> Dict[str, Any]:
        """Cancel a running pipeline.

        Args:
            run_id: The pipeline run identifier.

        Returns:
            Cancellation confirmation dict.
        """
        return self._request("DELETE", f"/api/pipeline/{run_id}")

    def get_pipeline_history(self, limit: int = 20) -> Dict[str, Any]:
        """Get pipeline run history.

        Args:
            limit: Maximum number of runs to return.

        Returns:
            Dict with 'runs' list and 'total' count.
        """
        return self._request("GET", "/api/pipeline/history", params={"limit": limit})

    # -- Jobs --

    def search_jobs(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Search for jobs without running the full pipeline.

        Args:
            request: Search parameters (keywords, locations, sources, etc.).

        Returns:
            Dict with 'total' count and 'jobs' list.
        """
        return self._request(
            "POST", "/api/jobs/search", json=request, timeout=self.search_timeout
        )

    def get_sources(self) -> Dict[str, Any]:
        """Get available job scraper sources.

        Returns:
            Dict with 'sources' list of source name strings.
        """
        return self._request("GET", "/api/jobs/sources")

    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get details for a specific job.

        Args:
            job_id: The job identifier.

        Returns:
            Full job listing dict.
        """
        return self._request("GET", f"/api/jobs/{job_id}")

    def score_job(self, job_id: str) -> Dict[str, Any]:
        """Score a job's relevance against the user profile.

        Args:
            job_id: The job identifier.

        Returns:
            Scoring result with relevance score and breakdown.
        """
        return self._request("POST", f"/api/jobs/{job_id}/score")

    def apply_to_job(self, job_id: str, dry_run: bool = True) -> Dict[str, Any]:
        """Apply to a specific job.

        Args:
            job_id: The job identifier.
            dry_run: If True, simulate the application.

        Returns:
            Application result dict.
        """
        return self._request(
            "POST", f"/api/jobs/{job_id}/apply", json={"dry_run": dry_run}
        )

    # -- Profile --

    def upload_resume(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Upload and parse a resume file (PDF or DOCX).

        Args:
            file_bytes: Raw file content.
            filename: Original filename with extension.

        Returns:
            Dict with profile_id, resume_path, and message.
        """
        files = {"file": (filename, file_bytes)}
        return self._request("POST", "/api/profile/upload", files=files)

    def get_profile(self) -> Dict[str, Any]:
        """Get the current user profile.

        Returns:
            Full profile dict with contact info, skills, experience, etc.
        """
        return self._request("GET", "/api/profile/")

    def update_profile(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile fields.

        Args:
            updates: Dict of profile fields to update.

        Returns:
            Update confirmation dict.
        """
        return self._request("PUT", "/api/profile/", json=updates)

    def export_profile(self) -> Dict[str, Any]:
        """Export the full user profile as a dictionary.

        Returns:
            Complete profile data.
        """
        return self._request("GET", "/api/profile/export")

    def analyze_resume(
        self,
        file_bytes: bytes,
        filename: str,
        job_description: str | None = None,
    ) -> Dict[str, Any]:
        """Analyze a resume and provide AI-powered insights.

        Args:
            file_bytes: Raw file content.
            filename: Original filename with extension.
            job_description: Optional job description for comparison.

        Returns:
            Analysis results with scores, strengths, improvements, and recommendations.
        """
        files = {"file": (filename, file_bytes)}
        data = {}
        if job_description:
            data["job_description"] = job_description

        return self._request("POST", "/api/profile/analyze", files=files, data=data)

    # -- Metrics --

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get combined metrics summary (costs, outcomes, health, recent calls).

        Returns:
            Summary dict with cost, outcomes, health, and recent_calls sections.
        """
        return self._request("GET", "/api/metrics/summary")

    def get_cost_metrics(self) -> Dict[str, Any]:
        """Get cost tracking metrics.

        Returns:
            Cost metrics dict with total_usd, per_application, etc.
        """
        return self._request("GET", "/api/metrics/costs")

    def get_outcome_metrics(self) -> Dict[str, Any]:
        """Get application outcome metrics.

        Returns:
            Outcome dict with application counts and conversion rates.
        """
        return self._request("GET", "/api/metrics/outcomes")

    def get_health_metrics(self) -> Dict[str, Any]:
        """Get system health metrics.

        Returns:
            Health check response with status and individual check results.
        """
        return self._request("GET", "/api/metrics/health")

    # -- Applications --

    def save_job(
        self, job_id: str, metadata: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Save/bookmark a job for later review.

        Args:
            job_id: The job identifier.
            metadata: Optional dict with title, company, source_url, etc.

        Returns:
            Action confirmation dict with success status and new status.
        """
        return self._request(
            "POST",
            "/api/applications/actions",
            json={"job_id": job_id, "action": "save", "metadata": metadata},
        )

    def unsave_job(self, job_id: str) -> Dict[str, Any]:
        """Remove a job from saved bookmarks.

        Args:
            job_id: The job identifier.

        Returns:
            Action confirmation dict.
        """
        return self._request(
            "POST",
            "/api/applications/actions",
            json={"job_id": job_id, "action": "unsave"},
        )

    def hide_job(self, job_id: str, reason: str | None = None) -> Dict[str, Any]:
        """Mark a job as not interested (hidden from results).

        Args:
            job_id: The job identifier.
            reason: Optional reason for hiding.

        Returns:
            Action confirmation dict.
        """
        return self._request(
            "POST",
            "/api/applications/actions",
            json={"job_id": job_id, "action": "hide", "note": reason},
        )

    def unhide_job(self, job_id: str) -> Dict[str, Any]:
        """Restore a previously hidden job.

        Args:
            job_id: The job identifier.

        Returns:
            Action confirmation dict.
        """
        return self._request(
            "POST",
            "/api/applications/actions",
            json={"job_id": job_id, "action": "unhide"},
        )

    def get_application_dashboard(
        self,
        status: str | None = None,
        company: str | None = None,
        days: int | None = None,
        include_hidden: bool = False,
        include_bookmarked: bool = True,
        include_external: bool = True,
    ) -> Dict[str, Any]:
        """Get the application tracking dashboard with optional filters.

        Args:
            status: Filter by application status string.
            company: Filter by company name.
            days: Only include applications from the last N days.
            include_hidden: Include hidden/not-interested jobs.
            include_bookmarked: Include bookmarked jobs.
            include_external: Include externally tracked applications.

        Returns:
            Dashboard dict with applications list, summary, and custom statuses.
        """
        params: Dict[str, Any] = {
            "include_hidden": include_hidden,
            "include_bookmarked": include_bookmarked,
            "include_external": include_external,
        }
        if status:
            params["status"] = status
        if company:
            params["company"] = company
        if days is not None:
            params["days"] = days
        return self._request("GET", "/api/applications/dashboard", params=params)

    def get_application_detail(self, job_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific tracked application.

        Args:
            job_id: The job identifier.

        Returns:
            Full application detail with timeline, interviews, and offer info.
        """
        return self._request("GET", f"/api/applications/{job_id}")

    def track_external_application(
        self,
        job_id: str,
        job_title: str,
        company: str,
        application_date: str | None = None,
        application_method: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Track an application made outside the system.

        Args:
            job_id: Unique identifier for the job.
            job_title: Title of the job.
            company: Company name.
            application_date: ISO format date string (e.g. "2026-04-25").
            application_method: How the application was submitted.
            metadata: Additional application details.

        Returns:
            Tracking confirmation with application_id and status.
        """
        body: Dict[str, Any] = {
            "job_id": job_id,
            "job_title": job_title,
            "company": company,
        }
        if application_date:
            body["application_date"] = application_date
        if application_method:
            body["application_method"] = application_method
        if metadata:
            body["metadata"] = metadata
        return self._request("POST", "/api/applications/external", json=body)

    def create_custom_status(
        self,
        name: str,
        description: str = "",
        color: str = "#4A90E2",
        icon: str = "",
    ) -> Dict[str, Any]:
        """Create a custom application status.

        Args:
            name: Status name (e.g. "Phone Screen Scheduled").
            description: Description of the status.
            color: Hex color code for display.
            icon: Emoji or icon identifier.

        Returns:
            Created status dict with status_id.
        """
        return self._request(
            "POST",
            "/api/applications/statuses/custom",
            json={
                "name": name,
                "description": description,
                "color": color,
                "icon": icon,
            },
        )

    def get_custom_statuses(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all custom application statuses.

        Args:
            active_only: Only return active statuses.

        Returns:
            List of custom status dicts.
        """
        return self._request(
            "GET",
            "/api/applications/statuses/custom",
            params={"active_only": active_only},
        )

    def set_custom_status(
        self,
        job_id: str,
        custom_status_id: str,
        note: str | None = None,
    ) -> Dict[str, Any]:
        """Set a custom status on an application.

        Args:
            job_id: The job identifier.
            custom_status_id: The custom status identifier.
            note: Optional note about the status change.

        Returns:
            Status update confirmation.
        """
        body: Dict[str, Any] = {
            "job_id": job_id,
            "custom_status_id": custom_status_id,
        }
        if note:
            body["note"] = note
        return self._request("POST", "/api/applications/statuses/set", json=body)

    def update_application_status(
        self,
        job_id: str,
        status: str,
        note: str | None = None,
    ) -> Dict[str, Any]:
        """Update the status of a tracked application.

        Args:
            job_id: The job identifier.
            status: New status string (must match ApplicationStatus enum).
            note: Optional note about the change.

        Returns:
            Status update confirmation.
        """
        body: Dict[str, Any] = {"job_id": job_id, "status": status}
        if note:
            body["note"] = note
        return self._request("PUT", "/api/applications/status", json=body)

    # -- Settings --

    def get_settings(self) -> Dict[str, Any]:
        """Get current user settings.

        Returns:
            Complete user settings configuration including routing,
            API config, model parameters, and cost limits.
        """
        return self._request("GET", "/api/settings/")

    def update_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update user settings.

        Args:
            settings: New settings configuration to save.

        Returns:
            Updated settings as saved on the backend.
        """
        return self._request("PUT", "/api/settings/", json=settings)

    def reset_settings(self) -> Dict[str, Any]:
        """Reset settings to defaults.

        Returns:
            Default settings configuration.
        """
        return self._request("POST", "/api/settings/reset")

    def get_available_models(self) -> Dict[str, list]:
        """Get list of available models by provider.

        Returns:
            Dict mapping provider names to lists of available model names.
        """
        return self._request("GET", "/api/settings/models")

    def get_model_info(self, provider: str, model: str) -> Dict[str, Any]:
        """Get detailed information about a specific model.

        Args:
            provider: Provider name (anthropic or ollama).
            model: Model name.

        Returns:
            Model information including parameters, use cases, etc.
        """
        return self._request("GET", f"/api/settings/models/{provider}/{model}")

    def validate_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings without saving them.

        Args:
            settings: Settings configuration to validate.

        Returns:
            Validation results with success status and any errors/warnings.
        """
        return self._request("POST", "/api/settings/validate", json=settings)

    # -- Semantic Search / RAG --

    def semantic_search(
        self,
        query: str,
        n_results: int = 20,
        min_similarity: float = 0.3,
    ) -> Dict[str, Any]:
        """Search jobs using RAG-powered semantic similarity.

        Sends a natural-language query to the backend which embeds it
        and retrieves the most similar jobs from the vector store.

        Args:
            query: Natural language description of the ideal job.
            n_results: Maximum number of results to return.
            min_similarity: Minimum cosine similarity threshold (0.0-1.0).

        Returns:
            Dict with 'total' count, 'jobs' list, and 'query' echo.
        """
        return self._request(
            "POST",
            "/api/jobs/search/semantic",
            json={
                "query": query,
                "n_results": n_results,
                "min_similarity": min_similarity,
            },
        )

    def get_job_similarity(self, job_id: str) -> Dict[str, Any]:
        """Get semantic similarity scores for a specific job.

        Retrieves heuristic, semantic, and combined similarity metrics
        comparing the job against the user's profile.

        Args:
            job_id: The job identifier.

        Returns:
            Dict with heuristic_score, semantic_score, combined_score,
            and explanation details.
        """
        return self._request("GET", f"/api/jobs/{job_id}/similarity")
