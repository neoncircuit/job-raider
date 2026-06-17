"""
Job Raider - Metrics API Tests

Tests for the metrics API endpoints. These exercise the real routes
(/api/metrics/costs, /outcomes, /health, /summary) via the shared TestClient.
"""

from fastapi.testclient import TestClient


class TestMetricsAPI:
    """Test metrics API endpoints."""

    def test_get_costs(self, client: TestClient):
        """GET /api/metrics/costs returns cost metrics."""
        response = client.get("/api/metrics/costs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_outcomes(self, client: TestClient):
        """GET /api/metrics/outcomes returns outcome metrics."""
        response = client.get("/api/metrics/outcomes")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_summary(self, client: TestClient):
        """GET /api/metrics/summary returns aggregated metrics."""
        response = client.get("/api/metrics/summary")
        assert response.status_code == 200
        data = response.json()
        # Summary aggregates cost, outcome, and health sections.
        assert "cost" in data
        assert "outcomes" in data
        assert "health" in data

    def test_get_health(self, client: TestClient):
        """GET /api/metrics/health returns the system health report."""
        response = client.get("/api/metrics/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checks" in data
