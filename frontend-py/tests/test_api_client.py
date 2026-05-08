"""
Tests for the APIClient class.

Validates all endpoint methods, error handling, timeout behavior,
and file upload functionality using mocked HTTP responses.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.api.client import APIClient, APIError, ConnectionError


@pytest.fixture
def client() -> APIClient:
    """Create an APIClient instance for testing."""
    return APIClient(base_url="http://localhost:8000", timeout=5, search_timeout=30)


@pytest.fixture
def mock_response() -> MagicMock:
    """Create a mock HTTP response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = 200
    resp.json.return_value = {}
    resp.text = ""
    return resp


class TestAPIClientHealth:
    """Tests for health and version endpoints."""

    def test_get_health(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {"status": "healthy"}
        client._session.request = MagicMock(return_value=mock_response)

        result = client.get_health()
        assert result == {"status": "healthy"}
        client._session.request.assert_called_once_with(
            "GET", "http://localhost:8000/api/health", timeout=5
        )

    def test_get_version(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {"version": "0.1.0", "name": "Job Raider API"}
        client._session.request = MagicMock(return_value=mock_response)

        result = client.get_version()
        assert result["version"] == "0.1.0"


class TestAPIClientPipeline:
    """Tests for pipeline endpoints."""

    def test_start_pipeline(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {"run_id": "abc-123"}
        client._session.request = MagicMock(return_value=mock_response)

        run_id = client.start_pipeline({"keywords": ["python"], "locations": ["remote"]})
        assert run_id == "abc-123"

    def test_get_pipeline_status(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {"run_id": "abc-123", "status": "running"}
        client._session.request = MagicMock(return_value=mock_response)

        result = client.get_pipeline_status("abc-123")
        assert result["status"] == "running"

    def test_cancel_pipeline(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {"run_id": "abc-123", "status": "cancelled"}
        client._session.request = MagicMock(return_value=mock_response)

        result = client.cancel_pipeline("abc-123")
        assert result["status"] == "cancelled"

    def test_get_pipeline_history(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {"runs": [], "total": 0}
        client._session.request = MagicMock(return_value=mock_response)

        result = client.get_pipeline_history(limit=10)
        assert result["total"] == 0


class TestAPIClientJobs:
    """Tests for job endpoints."""

    def test_search_jobs(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {"total": 5, "jobs": []}
        client._session.request = MagicMock(return_value=mock_response)

        result = client.search_jobs({"keywords": ["python"], "locations": ["remote"]})
        assert result["total"] == 5
        # Verify search timeout is used
        call_kwargs = client._session.request.call_args
        assert call_kwargs.kwargs.get("timeout") == 30

    def test_get_job(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {"job_id": "job-001", "title": "Engineer"}
        client._session.request = MagicMock(return_value=mock_response)

        result = client.get_job("job-001")
        assert result["job_id"] == "job-001"


class TestAPIClientProfile:
    """Tests for profile endpoints."""

    def test_upload_resume(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {
            "profile_id": "prof-1",
            "resume_path": "/data/resume.pdf",
            "message": "Success",
        }
        client._session.request = MagicMock(return_value=mock_response)

        result = client.upload_resume(b"fake-pdf-content", "resume.pdf")
        assert result["profile_id"] == "prof-1"

    def test_get_profile(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {"profile_id": "prof-1", "contact_info": {}}
        client._session.request = MagicMock(return_value=mock_response)

        result = client.get_profile()
        assert "profile_id" in result

    def test_update_profile(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {"message": "Profile updated successfully"}
        client._session.request = MagicMock(return_value=mock_response)

        result = client.update_profile({"name": "New Name"})
        assert "updated" in result["message"]


class TestAPIClientMetrics:
    """Tests for metrics endpoints."""

    def test_get_metrics_summary(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {"cost": {}, "outcomes": {}, "health": {}}
        client._session.request = MagicMock(return_value=mock_response)

        result = client.get_metrics_summary()
        assert "cost" in result

    def test_get_cost_metrics(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.json.return_value = {"total_cost_usd": 1.25}
        client._session.request = MagicMock(return_value=mock_response)

        result = client.get_cost_metrics()
        assert result["total_cost_usd"] == 1.25


class TestAPIClientErrors:
    """Tests for error handling."""

    def test_connection_error(self, client: APIClient) -> None:
        client._session.request = MagicMock(
            side_effect=requests.exceptions.ConnectionError("refused")
        )
        with pytest.raises(ConnectionError):
            client.get_health()

    def test_timeout_error(self, client: APIClient) -> None:
        client._session.request = MagicMock(
            side_effect=requests.exceptions.Timeout("timed out")
        )
        with pytest.raises(ConnectionError):
            client.get_health()

    def test_api_error_404(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.status_code = 404
        mock_response.json.return_value = {"detail": "Not found"}
        client._session.request = MagicMock(return_value=mock_response)

        with pytest.raises(APIError) as exc_info:
            client.get_job("nonexistent")
        assert exc_info.value.status_code == 404
        assert "Not found" in exc_info.value.detail

    def test_api_error_500(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.status_code = 500
        mock_response.json.return_value = {"detail": "Internal error"}
        client._session.request = MagicMock(return_value=mock_response)

        with pytest.raises(APIError) as exc_info:
            client.get_health()
        assert exc_info.value.status_code == 500

    def test_204_no_content(self, client: APIClient, mock_response: MagicMock) -> None:
        mock_response.status_code = 204
        client._session.request = MagicMock(return_value=mock_response)

        result = client.cancel_pipeline("run-1")
        assert result == {}
