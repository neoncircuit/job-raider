"""
Job Raider - Metrics API Tests

Tests for the metrics API endpoints. These exercise the real routes
(/api/metrics/costs, /outcomes, /health, /summary) via the shared TestClient.
"""

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from src.metrics.cost_tracker import (
    get_cost_tracker,
    load_latest_cost_run,
    reset_cost_tracker,
)


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

    def test_pipeline_runs_counts_run_files(
        self, client: TestClient, tmp_path: Path, monkeypatch
    ) -> None:
        """pipeline_runs is the number of saved run files, not the call count."""
        (tmp_path / "cost_run_a.json").write_text("{}", encoding="utf-8")
        (tmp_path / "cost_run_b.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(
            "src.metrics.cost_tracker._default_metrics_dir",
            lambda: tmp_path,
        )
        reset_cost_tracker()
        for _ in range(5):
            get_cost_tracker().record_call(
                task_type="selection",
                provider="ollama",
                model="qwen2.5:3b",
                prompt_tokens=1,
                completion_tokens=1,
                latency_ms=1,
            )
        costs = client.get("/api/metrics/costs")
        assert costs.status_code == 200
        assert costs.json()["pipeline_runs"] == 2
        summary = client.get("/api/metrics/summary")
        assert summary.status_code == 200
        assert summary.json()["cost"]["pipeline_runs"] == 2
        reset_cost_tracker()

    def test_last_run_is_newest_file_by_time(
        self, client: TestClient, tmp_path: Path, monkeypatch
    ) -> None:
        """The last run is the newest file by mtime, not by name."""
        older = tmp_path / "cost_run_zzz.json"
        newer = tmp_path / "cost_run_aaa.json"
        older.write_text(
            json.dumps({"run_id": "zzz", "summary": {"total_calls": 0}, "calls": []}),
            encoding="utf-8",
        )
        newer.write_text(
            json.dumps({"run_id": "aaa", "summary": {"total_calls": 0}, "calls": []}),
            encoding="utf-8",
        )
        os.utime(older, (1_000, 1_000))
        os.utime(newer, (2_000, 2_000))
        monkeypatch.setattr(
            "src.metrics.cost_tracker._default_metrics_dir",
            lambda: tmp_path,
        )
        latest = load_latest_cost_run(tmp_path)
        assert latest is not None
        assert latest["run_id"] == "aaa"
        response = client.get("/api/metrics/costs")
        assert response.status_code == 200
        last_run = response.json()["last_run"]
        assert last_run is not None
        assert last_run["run_id"] == "aaa"

    def test_api_usd_is_cost_of_non_ollama_calls(self, client: TestClient) -> None:
        """api_usd is the cost of the non-Ollama calls."""
        reset_cost_tracker()
        get_cost_tracker().record_call(
            task_type="selection",
            provider="ollama",
            model="qwen2.5:3b",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=1,
        )
        get_cost_tracker().record_call(
            task_type="selection",
            provider="anthropic",
            model="claude-sonnet-4-6",
            prompt_tokens=1_000_000,
            completion_tokens=0,
            latency_ms=1,
        )
        costs = client.get("/api/metrics/costs")
        assert costs.status_code == 200
        assert costs.json()["api_costs_usd"] == 3.0
        summary = client.get("/api/metrics/summary")
        assert summary.status_code == 200
        assert summary.json()["cost"]["api_usd"] == 3.0
        reset_cost_tracker()

    def test_api_usd_is_none_when_a_cloud_call_has_no_price(
        self, client: TestClient
    ) -> None:
        """api_usd is None when any non-Ollama call has no price."""
        reset_cost_tracker()
        get_cost_tracker().record_call(
            task_type="selection",
            provider="anthropic",
            model="claude-not-in-catalog",
            prompt_tokens=10,
            completion_tokens=4,
            latency_ms=1,
        )
        costs = client.get("/api/metrics/costs")
        assert costs.status_code == 200
        assert costs.json()["api_costs_usd"] is None
        reset_cost_tracker()
