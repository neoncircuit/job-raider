"""
Tests for the shared API_KEY step of setup.sh (check_env).

Env files copied from Windows can have CRLF line endings. An empty
``API_KEY=`` line then holds a carriage return, and setup.sh must still see
the key as empty and generate one. A real key must reach the frontend file
without a carriage return.

Each test sources setup.sh in bash (the file runs ``main`` only when it is
executed), points ``BACKEND_DIR`` and ``PROJECT_ROOT`` at a temporary folder,
writes its own env files there, and runs ``check_env``. No real env file is
read, and no key is printed.
"""

import re
import shutil
import subprocess
from pathlib import Path
from typing import Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SETUP_SH = REPO_ROOT / "setup.sh"

GUARD = 'if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then'
CR = "\r"
KNOWN_KEY = "a" * 64

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="bash is not available"
)


def guard_is_present() -> bool:
    """
    Check, from the file text only, that sourcing setup.sh does not run main.

    Returns:
        True when the only call of ``main`` is ``main "$@"`` on the line after
        the guard.
    """
    lines = [line.strip() for line in SETUP_SH.read_text().splitlines()]
    if GUARD not in lines:
        return False
    after_guard = lines.index(GUARD) + 1
    calls = [n for n, line in enumerate(lines) if line in ("main", 'main "$@"')]
    return calls == [after_guard] and lines[after_guard] == 'main "$@"'


def env_files(tmp_path: Path) -> Tuple[Path, Path]:
    """
    Create the backend and frontend folders of a fake project.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        The paths of the backend ``.env`` and the frontend ``.env.local``.
    """
    backend = tmp_path / "apps" / "backend-py"
    frontend = tmp_path / "apps" / "frontend-ts"
    backend.mkdir(parents=True)
    frontend.mkdir(parents=True)
    return backend / ".env", frontend / ".env.local"


def write(path: Path, lines: list, newline: str) -> None:
    """
    Write env lines with the given line ending.

    Args:
        path: The file to write.
        lines: The lines, without line endings.
        newline: ``"\\r\\n"`` (Windows) or ``"\\n"`` (Unix).
    """
    path.write_bytes("".join(line + newline for line in lines).encode())


def run_check_env(tmp_path: Path) -> subprocess.CompletedProcess:
    """
    Source setup.sh and run check_env on the fake project in ``tmp_path``.

    Args:
        tmp_path: Pytest temporary directory with the fake project.

    Returns:
        The completed bash process.
    """
    if not guard_is_present():
        pytest.fail("setup.sh would run the whole setup when sourced; not sourced")
    script = f"""
source "{SETUP_SH}" > /dev/null
set +e
PROJECT_ROOT="{tmp_path}"
BACKEND_DIR="{tmp_path}/apps/backend-py"
check_env > /dev/null
echo "rc=$?"
"""
    completed = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "rc=0" in completed.stdout, completed.stderr
    return completed


def key_line(path: Path) -> str:
    """
    Return the raw value of the first ``API_KEY=`` line, with any carriage return.

    Args:
        path: The env file.

    Returns:
        The text after ``API_KEY=`` up to the line feed.
    """
    for line in path.read_bytes().decode().split("\n"):
        if line.startswith("API_KEY="):
            return line.split("=", 1)[1]
    raise AssertionError(f"no API_KEY line in {path.name}")


def test_crlf_empty_key_generates_one_shared_key(tmp_path: Path) -> None:
    """CRLF files with an empty key get one generated key, without a carriage return."""
    backend, frontend = env_files(tmp_path)
    write(backend, ["# backend", "API_KEY=", "ENVIRONMENT=development"], "\r\n")
    write(frontend, ["API_KEY="], "\r\n")

    run_check_env(tmp_path)

    backend_key = key_line(backend)
    assert re.fullmatch(r"[0-9a-f]{64}", backend_key), "no generated key in .env"
    assert key_line(frontend) == backend_key
    assert "ENVIRONMENT=development" in backend.read_text()


def test_crlf_real_key_is_synced_without_carriage_return(tmp_path: Path) -> None:
    """A real backend key in a CRLF file reaches the frontend without a carriage return."""
    backend, frontend = env_files(tmp_path)
    write(backend, [f"API_KEY={KNOWN_KEY}"], "\r\n")
    write(frontend, ["API_KEY="], "\r\n")

    run_check_env(tmp_path)

    assert key_line(backend).rstrip(CR) == KNOWN_KEY
    assert key_line(frontend) == KNOWN_KEY


def test_crlf_same_key_in_both_files_changes_nothing(tmp_path: Path) -> None:
    """When both CRLF files have the same real key, neither file changes."""
    backend, frontend = env_files(tmp_path)
    write(backend, [f"API_KEY={KNOWN_KEY}"], "\r\n")
    write(frontend, [f"API_KEY={KNOWN_KEY}"], "\r\n")
    before = (backend.read_bytes(), frontend.read_bytes())

    run_check_env(tmp_path)

    assert (backend.read_bytes(), frontend.read_bytes()) == before


def test_lf_empty_key_generates_one_shared_key(tmp_path: Path) -> None:
    """Unix files with an empty key get one generated key (unchanged behaviour)."""
    backend, frontend = env_files(tmp_path)
    write(backend, ["API_KEY="], "\n")
    write(frontend, ["API_KEY="], "\n")

    run_check_env(tmp_path)

    backend_key = key_line(backend)
    assert re.fullmatch(r"[0-9a-f]{64}", backend_key), "no generated key in .env"
    assert key_line(frontend) == backend_key
