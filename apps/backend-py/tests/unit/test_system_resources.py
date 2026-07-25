"""
Job Raider - System resources tests

Unit tests for the CPU / RAM / GPU snapshot helper and the public
GET /api/health/resources endpoint.

Author: Job Raider
Date: 2026-07-24
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.health.system_resources import get_system_resources


class TestSystemResources:
    """Tests for get_system_resources and the health resources route."""

    def test_get_system_resources_with_psutil_and_gpu(self):
        """Snapshot includes CPU, RAM, and primary GPU when available."""
        mock_mem = SimpleNamespace(
            used=8 * 1024 * 1024 * 1024,
            total=16 * 1024 * 1024 * 1024,
            percent=50.0,
        )
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = 42.0
        mock_psutil.virtual_memory.return_value = mock_mem

        gpu = SimpleNamespace(
            name="Mock GPU",
            utilization_percent=33.0,
            memory_used_mb=2048,
            memory_total_mb=8192,
            memory_usage_percent=0.25,
            temperature_celsius=55.0,
        )
        monitor = MagicMock()
        monitor.has_gpu.return_value = True
        monitor.get_all_gpu_info.return_value = [gpu]

        with (
            patch.dict("sys.modules", {"psutil": mock_psutil}),
            patch(
                "src.health.system_resources.get_gpu_monitor",
                return_value=monitor,
            ),
        ):
            data = get_system_resources()

        assert data["cpu"]["percent"] == 42.0
        assert data["ram"]["percent"] == 50.0
        assert data["ram"]["used_mb"] == 8192.0
        assert data["ram"]["total_mb"] == 16384.0
        assert data["gpu"] is not None
        assert data["gpu"]["name"] == "Mock GPU"
        assert data["gpu"]["utilization_percent"] == 33.0
        assert data["gpu"]["memory_percent"] == 25.0

    def test_get_system_resources_without_gpu(self):
        """GPU section is null when no NVIDIA device is present."""
        mock_mem = SimpleNamespace(
            used=1024 * 1024 * 1024,
            total=4 * 1024 * 1024 * 1024,
            percent=25.0,
        )
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = 10.0
        mock_psutil.virtual_memory.return_value = mock_mem

        monitor = MagicMock()
        monitor.has_gpu.return_value = False

        with (
            patch.dict("sys.modules", {"psutil": mock_psutil}),
            patch(
                "src.health.system_resources.get_gpu_monitor",
                return_value=monitor,
            ),
        ):
            data = get_system_resources()

        assert data["cpu"]["percent"] == 10.0
        assert data["gpu"] is None

    def test_health_resources_endpoint(self, client: TestClient):
        """GET /api/health/resources returns the resource snapshot shape."""
        fake = {
            "cpu": {"percent": 12.5},
            "ram": {"used_mb": 1000.0, "total_mb": 8000.0, "percent": 12.5},
            "gpu": None,
        }
        with patch(
            "src.health.system_resources.get_system_resources",
            return_value=fake,
        ):
            response = client.get("/api/health/resources")
        assert response.status_code == 200
        assert response.json() == fake
