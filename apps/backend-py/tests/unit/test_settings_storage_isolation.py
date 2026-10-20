"""
Prove pytest never points settings storage at the real data/settings dir.

Step 2 review R6: an autouse fixture must redirect ``get_storage()`` to a
temporary directory so PUT/reset/ollama-defaults cannot rewrite the
developer's ``user_settings.json`` (which may hold cloud API keys).
"""

from __future__ import annotations

from pathlib import Path

from src.api.settings import get_storage


def test_get_storage_uses_pytest_temporary_directory(tmp_path: Path) -> None:
    """
    ``get_storage().settings_file`` must live under the pytest temp tree.

    Args:
        tmp_path: Pytest temporary directory (also used by the autouse fixture).

    Returns:
        None.
    """
    storage = get_storage()
    settings_file = storage.settings_file.resolve()
    tmp_root = tmp_path.resolve()
    assert settings_file.is_relative_to(
        tmp_root
    ), f"settings_file={settings_file} is not under tmp_path={tmp_root}"
    repo_settings = (Path("data") / "settings" / "user_settings.json").resolve()
    assert settings_file != repo_settings
