"""
Unit tests for profile API routes.

Tests cover:
- LinkedIn profile analysis with and without a profile URL
- LinkedIn people search
- Graceful degradation when LinkedIn credentials/session are unavailable

Author: Job Raider
Date: 2026-06-28
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_analyzer():
    """Mock LinkedInAnalyzer with a minimal analysis response."""
    from src.models.linkedin_analysis import LinkedInProfileAnalysis

    analyzer = MagicMock()
    analyzer.analyze_async = AsyncMock(
        return_value=LinkedInProfileAnalysis(
            overall_score=72,
            summary="Strong profile.",
            analyzed_at=datetime(2026, 6, 28, 12, 0, 0),
        )
    )
    return analyzer


@pytest.fixture
def mock_session():
    """Mock LinkedInSession with sample search results."""
    session = MagicMock()
    session.fetch_profile_text.return_value = "Fetched LinkedIn profile text"
    session.search_people.return_value = [
        {
            "name": "Jane Doe",
            "headline": "Software Engineer at TechCorp",
            "profile_url": "https://www.linkedin.com/in/janedoe",
            "location": "San Francisco, CA",
        },
        {
            "name": "John Smith",
            "headline": "Product Manager",
            "profile_url": "https://www.linkedin.com/in/johnsmith",
            "location": None,
        },
    ]
    return session


@pytest.fixture
def client(mock_analyzer, mock_session):
    """FastAPI test client with mocked LinkedIn analyzer and session."""
    with patch(
        "src.api.routes.profile._get_linkedin_analyzer", return_value=mock_analyzer
    ), patch(
        "src.api.routes.profile._get_linkedin_session", return_value=mock_session
    ), patch(
        "src.api.routes.profile.stored_profiles", {}, create=True
    ), patch(
        "src.api.routes.profile.active_profile_id", None, create=True
    ):
        from src.api.auth import verify_api_key
        from src.api.main import app

        app.dependency_overrides[verify_api_key] = lambda: None
        tc = TestClient(app, raise_server_exceptions=False)
        yield tc
        app.dependency_overrides.clear()


class TestAnalyzeLinkedIn:
    """Tests for POST /api/profile/analyze-linkedin."""

    def test_analyze_with_profile_url_fetches_content(self, client, mock_analyzer):
        """Should fetch LinkedIn content and merge it into raw_text."""
        resp = client.post(
            "/api/profile/analyze-linkedin",
            json={"profile_url": "https://www.linkedin.com/in/testuser"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] == 72
        assert "summary" in data

        mock_analyzer.analyze_async.assert_called_once()
        call_args = mock_analyzer.analyze_async.call_args
        passed_input = call_args.args[0]
        assert passed_input.profile_url == "https://www.linkedin.com/in/testuser"
        assert "FETCHED LINKEDIN PROFILE" in passed_input.raw_text
        assert "Fetched LinkedIn profile text" in passed_input.raw_text

    def test_analyze_without_profile_url_uses_provided_text(
        self, client, mock_analyzer
    ):
        """Should analyze using raw_text when no profile_url is provided."""
        resp = client.post(
            "/api/profile/analyze-linkedin",
            json={"raw_text": "Pasted profile text"},
        )

        assert resp.status_code == 200
        mock_analyzer.analyze_async.assert_called_once()
        passed_input = mock_analyzer.analyze_async.call_args.args[0]
        assert passed_input.raw_text == "Pasted profile text"
        assert passed_input.profile_url is None

    def test_analyze_with_empty_input_returns_422(self, client):
        """Should reject empty input with a validation error."""
        resp = client.post(
            "/api/profile/analyze-linkedin",
            json={},
        )
        assert resp.status_code == 422


class TestAnalyzeLinkedInNoSession:
    """Tests for analyze-linkedin when LinkedIn session is unavailable."""

    @pytest.fixture
    def client_no_session(self, mock_analyzer):
        """Client configured with no available LinkedIn session."""
        with patch(
            "src.api.routes.profile._get_linkedin_analyzer", return_value=mock_analyzer
        ), patch(
            "src.api.routes.profile._get_linkedin_session", return_value=None
        ), patch(
            "src.api.routes.profile.stored_profiles", {}, create=True
        ), patch(
            "src.api.routes.profile.active_profile_id", None, create=True
        ):
            from src.api.auth import verify_api_key
            from src.api.main import app

            app.dependency_overrides[verify_api_key] = lambda: None
            tc = TestClient(app, raise_server_exceptions=False)
            yield tc
            app.dependency_overrides.clear()

    def test_analyze_with_url_but_no_session_still_succeeds(
        self, client_no_session, mock_analyzer
    ):
        """Should fall back to provided data when session cannot be started."""
        resp = client_no_session.post(
            "/api/profile/analyze-linkedin",
            json={"profile_url": "https://www.linkedin.com/in/testuser"},
        )

        assert resp.status_code == 200
        passed_input = mock_analyzer.analyze_async.call_args.args[0]
        assert passed_input.raw_text is None or passed_input.raw_text == ""


class TestSearchLinkedIn:
    """Tests for POST /api/profile/search-linkedin."""

    def test_search_returns_results(self, client):
        """Should return parsed people search results."""
        resp = client.post(
            "/api/profile/search-linkedin",
            json={"keywords": "software engineer", "limit": 5},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["results"]) == 2
        assert data["results"][0]["name"] == "Jane Doe"
        assert (
            data["results"][0]["profile_url"] == "https://www.linkedin.com/in/janedoe"
        )


class TestSearchLinkedInNoSession:
    """Tests for search-linkedin when LinkedIn session is unavailable."""

    @pytest.fixture
    def client_no_session(self, mock_analyzer):
        """Client configured with no available LinkedIn session."""
        with patch(
            "src.api.routes.profile._get_linkedin_analyzer", return_value=mock_analyzer
        ), patch(
            "src.api.routes.profile._get_linkedin_session", return_value=None
        ), patch(
            "src.api.routes.profile.stored_profiles", {}, create=True
        ), patch(
            "src.api.routes.profile.active_profile_id", None, create=True
        ):
            from src.api.auth import verify_api_key
            from src.api.main import app

            app.dependency_overrides[verify_api_key] = lambda: None
            tc = TestClient(app, raise_server_exceptions=False)
            yield tc
            app.dependency_overrides.clear()

    def test_search_without_credentials_returns_503(self, client_no_session):
        """Should return 503 when LinkedIn credentials/session are unavailable."""
        resp = client_no_session.post(
            "/api/profile/search-linkedin",
            json={"keywords": "software engineer"},
        )

        assert resp.status_code == 503
        assert "LinkedIn search is unavailable" in resp.json()["message"]


class TestExportProfilePdf:
    """Tests for GET /api/profile/export.pdf."""

    @pytest.fixture
    def pdf_client(self, tmp_path):
        """Test client with an active profile and isolated PDF output dir."""
        from src.models.user_profile import ContactInfo, UserProfile

        profile = UserProfile(
            name="Alex Chen",
            contact=ContactInfo(email="alex@example.com", location="Remote"),
            summary="Builder of APIs.",
        )
        stored = {
            "prof_pdf": {
                "profile": profile,
                "resume_path": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        }

        with patch(
            "src.api.routes.profile.stored_profiles", stored, create=True
        ), patch(
            "src.api.routes.profile.active_profile_id", "prof_pdf", create=True
        ), patch(
            "src.api.routes.profile.ProfileFormatter"
        ) as mock_formatter_cls:
            from src.api.auth import verify_api_key
            from src.api.main import app
            from src.generation.profile_formatter import FormattedProfile

            pdf_path = tmp_path / "profile_Alex_Chen_test.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 test")
            mock_formatter = MagicMock()
            mock_formatter.format_pdf.return_value = FormattedProfile(
                pdf_path=str(pdf_path),
                success=True,
                sections_included=["Identity", "Summary"],
            )
            mock_formatter_cls.return_value = mock_formatter

            app.dependency_overrides[verify_api_key] = lambda: None
            tc = TestClient(app, raise_server_exceptions=False)
            yield tc, mock_formatter
            app.dependency_overrides.clear()

    def test_export_pdf_returns_file(self, pdf_client):
        """Should stream application/pdf for the active profile."""
        client, mock_formatter = pdf_client
        resp = client.get("/api/profile/export.pdf")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        assert resp.content.startswith(b"%PDF")
        mock_formatter.format_pdf.assert_called_once()

    def test_export_pdf_without_profile_returns_404(self, client):
        """Should 404 when no active profile exists."""
        resp = client.get("/api/profile/export.pdf")
        assert resp.status_code == 404
