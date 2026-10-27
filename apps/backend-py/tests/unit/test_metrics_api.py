"""
Job Raider - Metrics API Tests

Tests for the metrics API endpoints. These exercise the real routes
(/api/metrics/costs, /outcomes, /health, /summary) via the shared TestClient.
"""

from fastapi.testclient import TestClient

from src.metrics.cost_tracker import get_cost_tracker, reset_cost_tracker


class TestMetricsAPI:
    """Test metrics API endpoints."""

    def test_get_costs(self, client: TestClient):
        """GET /api/metrics/costs returns cost metrics."""
        response = client.get("/api/metrics/costs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "prompt_tokens" in data
        assert "pipeline_runs" in data
        assert isinstance(data["pipeline_runs"], int)

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
        assert "recent_calls" in data
        assert "prompt_tokens" in data["cost"]
        assert "total_tokens" in data["cost"]
        assert "estimated_counts" in data["cost"]
        assert "last_run" in data["cost"]
        assert "pipeline_runs" in data["cost"]

    def test_summary_recent_calls_include_token_flags(self, client: TestClient):
        """recent_calls includes token counts and cache/fallback/error flags."""
        reset_cost_tracker()
        get_cost_tracker().record_call(
            task_type="selection",
            provider="ollama",
            model="qwen2.5:3b",
            prompt_tokens=4,
            completion_tokens=6,
            tokens_estimated=True,
            cache_hit=False,
            fallback=False,
            error=False,
        )
        response = client.get("/api/metrics/summary")
        assert response.status_code == 200
        calls = response.json()["recent_calls"]
        assert len(calls) == 1
        assert calls[0]["prompt_tokens"] == 4
        assert calls[0]["completion_tokens"] == 6
        assert calls[0]["tokens_estimated"] is True
        assert calls[0]["cache_hit"] is False
        assert calls[0]["fallback"] is False
        assert calls[0]["error"] is False
        reset_cost_tracker()

    def test_get_health(self, client: TestClient):
        """GET /api/metrics/health returns the system health report."""
        response = client.get("/api/metrics/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checks" in data
