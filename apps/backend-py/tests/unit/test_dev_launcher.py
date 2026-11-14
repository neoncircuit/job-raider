"""
Guard how ``scripts/dev.sh`` starts the backend API.

Auth requires ``API_KEY`` (Step 2.3). Native runs must therefore load
``apps/backend-py/.env``, the same way Compose uses ``env_file``. The test
runs the real script in a copy of the repository layout, with a stub
``python3`` that records the arguments it receives.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
DEV_SH = REPO_ROOT / "scripts" / "dev.sh"


def _run_dev_sh_api(tmp_path: Path, mode: str = "api") -> tuple[Path, List[str]]:
    """
    Run ``dev.sh api`` (or another backend mode) in a temporary repository layout.

    Args:
        tmp_path: Pytest temporary directory.
        mode: The dev.sh mode to run, ``api`` (make dev) or ``app-api`` (make app).

    Returns:
        Tuple of (backend directory, arguments the stub ``python3`` received).
    """
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is required to run scripts/dev.sh")

    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(DEV_SH, root / "scripts" / "dev.sh")
    shutil.copy(DEV_SH.parent / "find_python.sh", root / "scripts" / "find_python.sh")

    backend_dir = root / "apps" / "backend-py"
    venv_bin = backend_dir / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    args_file = tmp_path / "python-args.txt"
    stub = venv_bin / "python3"
    stub.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "{args_file}"\n')
    stub.chmod(0o755)

    # This test is about how the API starts, not about the dependency checks
    # (tests/unit/test_dev_deps.py), so it skips them as mprocs does.
    result = subprocess.run(
        [bash, str(root / "scripts" / "dev.sh"), mode],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "DEV_DEPS_CHECKED": "1"},
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


def test_dev_sh_api_keeps_auto_reload(tmp_path: Path) -> None:
    """``dev.sh api`` (make dev) still reloads on changes in src and config."""
    backend_dir, args = _run_dev_sh_api(tmp_path)

    assert "--reload" in args
    reload_dirs = [args[i + 1] for i, a in enumerate(args) if a == "--reload-dir"]
    assert reload_dirs == [str(backend_dir / "src"), str(backend_dir / "config")]


def test_dev_sh_app_api_runs_without_reload(tmp_path: Path) -> None:
    """``dev.sh app-api`` (make app) has no reloader but keeps host and env file."""
    backend_dir, args = _run_dev_sh_api(tmp_path, mode="app-api")

    assert args[:2] == ["-m", "uvicorn"]
    assert "--reload" not in args
    assert "--reload-dir" not in args
    assert _flag_value(args, "--host") == "127.0.0.1"
    assert _flag_value(args, "--port") == "8000"
    assert Path(_flag_value(args, "--env-file")).resolve() == backend_dir / ".env"


def _run_dev_sh_app_frontend(tmp_path: Path, built: bool) -> List[str]:
    """
    Run ``dev.sh app-frontend`` with a stub ``npm`` that records each call.

    Args:
        tmp_path: Pytest temporary directory.
        built: True to create a production build that is newer than the source.

    Returns:
        One line per ``npm`` call, with the arguments separated by spaces.
    """
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is required to run scripts/dev.sh")

    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(DEV_SH, root / "scripts" / "dev.sh")
    shutil.copy(DEV_SH.parent / "find_python.sh", root / "scripts" / "find_python.sh")
    frontend_dir = root / "apps" / "frontend-ts"
    (frontend_dir / "src").mkdir(parents=True)
    source = frontend_dir / "src" / "page.tsx"
    source.write_text("export {};\n")
    (frontend_dir / "package.json").write_text("{}\n")
    if built:
        build_id = frontend_dir / ".next" / "BUILD_ID"
        build_id.parent.mkdir()
        build_id.write_text("build\n")
        # The build is newer than every source file.
        for path in (source, frontend_dir / "package.json"):
            os.utime(path, (1_000_000_000, 1_000_000_000))

    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    calls_file = tmp_path / "npm-calls.txt"
    npm = stub_bin / "npm"
    npm.write_text(f'#!/bin/sh\necho "$*" >> "{calls_file}"\n')
    npm.chmod(0o755)

    result = subprocess.run(
        [bash, str(root / "scripts" / "dev.sh"), "app-frontend"],
        capture_output=True,
        text=True,
        timeout=60,
        env={
            **os.environ,
            "DEV_DEPS_CHECKED": "1",
            "PATH": f"{stub_bin}{os.pathsep}{os.environ['PATH']}",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return calls_file.read_text().splitlines()


def test_dev_sh_app_frontend_builds_when_there_is_no_build(tmp_path: Path) -> None:
    """``dev.sh app-frontend`` builds first when no production build exists."""
    calls = _run_dev_sh_app_frontend(tmp_path, built=False)

    assert calls == ["run build", "run start -- --hostname 127.0.0.1 --port 3000"]


def test_dev_sh_app_frontend_reuses_a_current_build(tmp_path: Path) -> None:
    """``dev.sh app-frontend`` skips the build when it is newer than the source."""
    calls = _run_dev_sh_app_frontend(tmp_path, built=True)

    assert calls == ["run start -- --hostname 127.0.0.1 --port 3000"]
