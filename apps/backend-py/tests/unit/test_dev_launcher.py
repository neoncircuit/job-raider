"""
Guard how ``scripts/dev.sh`` starts the backend API.

Auth requires ``API_KEY`` (Step 2.3). Native runs must therefore load
``apps/backend-py/.env``, the same way Compose uses ``env_file``. The test
runs the real script in a copy of the repository layout, with a stub
``python3`` that records the arguments it receives.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
DEV_SH = REPO_ROOT / "scripts" / "dev.sh"


def _run_dev_sh_api(tmp_path: Path) -> tuple[Path, List[str]]:
    """
    Run ``dev.sh api`` in a temporary repository layout.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Tuple of (backend directory, arguments the stub ``python3`` received).
    """
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is required to run scripts/dev.sh")

    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(DEV_SH, root / "scripts" / "dev.sh")

    backend_dir = root / "apps" / "backend-py"
    venv_bin = backend_dir / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    args_file = tmp_path / "python-args.txt"
    stub = venv_bin / "python3"
    stub.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "{args_file}"\n')
    stub.chmod(0o755)

    result = subprocess.run(
        [bash, str(root / "scripts" / "dev.sh"), "api"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return backend_dir.resolve(), args_file.read_text().splitlines()


def _flag_value(args: List[str], flag: str) -> str:
    """
    Return the value that follows a command-line flag.

    Args:
        args: Recorded command-line arguments.
        flag: Flag name, for example ``--host``.

    Returns:
        The argument after ``flag``.
    """
    assert flag in args, f"{flag} missing from uvicorn arguments: {args!r}"
    return args[args.index(flag) + 1]


def test_dev_sh_api_loads_backend_env_file(tmp_path: Path) -> None:
    """``dev.sh api`` passes ``apps/backend-py/.env`` to uvicorn."""
    backend_dir, args = _run_dev_sh_api(tmp_path)

    env_file = Path(_flag_value(args, "--env-file"))
    if not env_file.is_absolute():
        env_file = backend_dir / env_file
    assert env_file.resolve() == backend_dir / ".env"


def test_dev_sh_api_binds_loopback(tmp_path: Path) -> None:
    """``dev.sh api`` binds uvicorn to 127.0.0.1 only."""
    _, args = _run_dev_sh_api(tmp_path)

    assert args[:2] == ["-m", "uvicorn"]
    assert _flag_value(args, "--host") == "127.0.0.1"
