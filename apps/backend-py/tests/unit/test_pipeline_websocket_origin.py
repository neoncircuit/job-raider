"""
Tests for Origin checks on the pipeline progress WebSocket.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


class TestPipelineWebSocketOrigin:
    """Refuse browser Origins that are not on the CORS allow list."""

    def test_refuses_evil_origin(self, client: TestClient) -> None:
        """
        A WebSocket with Origin http://evil.example is closed with 1008.

        Args:
            client: Shared FastAPI TestClient.

        Returns:
            None.
        """
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                "/api/pipeline/test-run/progress",
                headers={"Origin": "http://evil.example"},
            ) as ws:
                ws.receive_json()
        assert exc_info.value.code == 1008

    def test_allows_localhost_origin(self, client: TestClient) -> None:
        """
        A WebSocket with Origin http://localhost:3000 connects.

        Args:
            client: Shared FastAPI TestClient.

        Returns:
            None.
        """
        with client.websocket_connect(
            "/api/pipeline/test-run/progress",
            headers={"Origin": "http://localhost:3000"},
        ) as ws:
            message = ws.receive_json()
        assert message["type"] == "connected"
        assert message["run_id"] == "test-run"

    def test_allows_missing_origin(self, client: TestClient) -> None:
        """
        A WebSocket with no Origin header connects (non-browser clients).

        Args:
            client: Shared FastAPI TestClient.

        Returns:
            None.
        """
        with client.websocket_connect("/api/pipeline/test-run/progress") as ws:
            message = ws.receive_json()
        assert message["type"] == "connected"
