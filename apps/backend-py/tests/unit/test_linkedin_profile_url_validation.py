"""
Step 2 review R4: bad LinkedIn profile_url must return 422 before a session opens.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.models.linkedin_analysis import LinkedInProfileAnalysis


@pytest.fixture
def mock_analyzer():
    """
    Mock LinkedInAnalyzer with a minimal analysis response.

    Returns:
        MagicMock analyzer with ``analyze_async``.
    """
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
def client(mock_analyzer):
    """
    TestClient with analyzer mocked and session patched for assert_not_called.

    Args:
        mock_analyzer: Fixture analyzer.

    Yields:
        FastAPI TestClient.
    """
    with (
        patch(
            "src.api.routes.profile._get_linkedin_analyzer",
            return_value=mock_analyzer,
        ),
        patch("src.api.routes.profile._get_linkedin_session") as mock_session,
        patch("src.api.routes.profile.stored_profiles", {}, create=True),
        patch("src.api.routes.profile.active_profile_id", None, create=True),
    ):
        from src.api.auth import verify_api_key
        from src.api.main import app

        app.dependency_overrides[verify_api_key] = lambda: None
        tc = TestClient(app, raise_server_exceptions=False)
        tc.mock_session = mock_session  # type: ignore[attr-defined]
        yield tc
        app.dependency_overrides.clear()


class TestLinkedInProfileUrlValidation:
    """POST /api/profile/analyze-linkedin rejects unsafe profile URLs."""

    def test_rejects_file_http_and_non_linkedin_urls(self, client: TestClient) -> None:
        """
        Bad URLs return 422 and never open a LinkedIn session.

        Args:
            client: Fixture TestClient.

        Returns:
            None.
        """
        bad_urls = [
            "file:///etc/passwd",
            "http://www.linkedin.com/in/x",
            "https://evil.example/in/x",
        ]
        for url in bad_urls:
            response = client.post(
                "/api/profile/analyze-linkedin",
                json={"profile_url": url},
            )
            assert response.status_code == 422, (
                f"expected 422 for {url!r}, got {response.status_code}: "
                f"{response.text}"
            )
        client.mock_session.assert_not_called()  # type: ignore[attr-defined]

    def test_valid_url_with_raw_text_does_not_return_422(
        self, client: TestClient, mock_analyzer
    ) -> None:
        """
        A valid https LinkedIn /in/ URL with raw_text is accepted.

        Args:
            client: Fixture TestClient.
            mock_analyzer: Fixture analyzer.

        Returns:
            None.
        """
        # Session unavailable so fetch is skipped; analysis still runs.
        client.mock_session.return_value = None  # type: ignore[attr-defined]
        response = client.post(
            "/api/profile/analyze-linkedin",
            json={
                "profile_url": "https://www.linkedin.com/in/someone",
                "raw_text": "Jane Doe\nEngineer",
            },
        )
        assert response.status_code == 200, response.text
        mock_analyzer.analyze_async.assert_called_once()
