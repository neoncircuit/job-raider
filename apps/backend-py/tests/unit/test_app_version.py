"""
Tests for product version loading from the monorepo VERSION file.
"""

from pathlib import Path

from src.utils.app_version import clear_app_version_cache, get_app_version


def test_get_app_version_reads_repo_root_file():
    """VERSION at the monorepo root is returned as the product version."""
    clear_app_version_cache()
    # apps/backend-py/tests/unit/test_app_version.py → repo root is parents[4]
    root_version = Path(__file__).resolve().parents[4] / "VERSION"
    assert root_version.is_file()
    expected = root_version.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    assert get_app_version() == expected
    assert expected.count(".") >= 2


def test_get_app_version_env_override(tmp_path, monkeypatch):
    """JOB_RAIDER_VERSION_FILE overrides discovery when the file exists."""
    override = tmp_path / "VERSION"
    override.write_text("9.9.9-test\n", encoding="utf-8")
    monkeypatch.setenv("JOB_RAIDER_VERSION_FILE", str(override))
    clear_app_version_cache()
    assert get_app_version() == "9.9.9-test"
    monkeypatch.delenv("JOB_RAIDER_VERSION_FILE", raising=False)
    clear_app_version_cache()
