"""
Job Raider - DataDirectoryCheck tests

Ensures missing bind-mount data folders are created and reported healthy.
"""

from pathlib import Path

from src.health.health_check import DataDirectoryCheck, HealthStatus


class TestDataDirectoryCheck:
    """Self-healing data directory health check."""

    def test_creates_missing_directories(self, tmp_path: Path):
        """
        Missing expected dirs under a writable base are created.

        Args:
            tmp_path: Pytest temporary directory.
        """
        base = tmp_path / "data"
        base.mkdir()
        (base / "applications").mkdir()

        result = DataDirectoryCheck(base_dir=str(base)).check()

        assert result.status == HealthStatus.HEALTHY
        assert (base / "listings").is_dir()
        assert (base / "cache").is_dir()
        assert (base / "results").is_dir()
        assert (base / "settings").is_dir()
        assert "listings" in result.metadata.get("created_dirs", [])

    def test_healthy_when_all_present(self, tmp_path: Path):
        """
        All expected directories already present yields a healthy result.

        Args:
            tmp_path: Pytest temporary directory.
        """
        base = tmp_path / "data"
        check = DataDirectoryCheck(base_dir=str(base))
        for name in check.expected_dirs:
            (base / name).mkdir(parents=True)

        result = check.check()

        assert result.status == HealthStatus.HEALTHY
        assert result.metadata.get("created_dirs") == []
        assert set(result.metadata.get("existing_dirs", [])) == set(check.expected_dirs)
