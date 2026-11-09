"""
Tests for the llmfit step of setup.sh (Step 6, MH-5).

Each test sources setup.sh in bash (the file runs ``main`` only when it is
executed, not when it is sourced), replaces ``pip`` with a shell function,
and calls the llmfit functions. Nothing is installed.

Safety: sourcing a setup.sh without the guard runs the whole setup (pip,
npm, Playwright, Ollama). So each test checks the guard in the file text
first, and does not source the file when the guard is missing.
"""

import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SETUP_SH = REPO_ROOT / "setup.sh"

GUARD = 'if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then'

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


def run_setup(args: List[str], pip_rc: int, tmp_path: Path) -> Tuple[int, str, str]:
    """
    Source setup.sh, parse the arguments, and run the llmfit step.

    Args:
        args: Arguments for ``parse_args`` (such as ``["--no-llmfit"]``).
        pip_rc: Exit code of the fake ``pip``.
        tmp_path: Folder for the fake ``pip`` log.

    Returns:
        Exit code of bash, its output, and the fake ``pip`` log.
    """
    if not guard_is_present():
        pytest.fail("setup.sh would run the whole setup when sourced; not sourced")
    log = tmp_path / "pip.log"
    script = f"""
source "{SETUP_SH}" > /dev/null
set +e
pip() {{ echo "pip $*" >> "{log}"; return {pip_rc}; }}
parse_args {" ".join(args)} || exit $?
install_llmfit
echo "rc=$?"
printf '%s\\n' "${{CHECK_RESULTS[@]}}"
"""
    completed = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    pip_log = log.read_text() if log.exists() else ""
    return completed.returncode, completed.stdout + completed.stderr, pip_log


def test_setup_runs_main_only_when_executed() -> None:
    """The guard keeps ``source setup.sh`` from running the setup."""
    assert guard_is_present()


def test_installs_the_pinned_llmfit_by_default(tmp_path: Path) -> None:
    """Without a flag, setup installs requirements-optional.txt."""
    code, out, pip_log = run_setup([], 0, tmp_path)
    assert code == 0
    assert "requirements-optional.txt" in pip_log
    assert pip_log.startswith("pip install -r ")
    assert "PASS|llmfit" in out


def test_no_llmfit_skips_the_install(tmp_path: Path) -> None:
    """--no-llmfit runs no pip command and records a warning."""
    code, out, pip_log = run_setup(["--no-llmfit"], 0, tmp_path)
    assert code == 0
    assert pip_log == ""
    assert "WARN|llmfit (skipped" in out


def test_a_failed_install_does_not_stop_setup(tmp_path: Path) -> None:
    """A pip failure gives a warning, and the step still returns 0."""
    code, out, pip_log = run_setup([], 1, tmp_path)
    assert code == 0
    assert "rc=0" in out
    assert "WARN|llmfit (install failed" in out
    assert pip_log != ""


def test_an_unknown_option_stops_with_usage(tmp_path: Path) -> None:
    """A wrong flag exits with code 2 before any install."""
    code, out, pip_log = run_setup(["--no-llmfitt"], 0, tmp_path)
    assert code == 2
    assert "Unknown option: --no-llmfitt" in out
    assert "--no-llmfit" in out
    assert pip_log == ""


def test_the_pin_matches_the_client_minimum() -> None:
    """The pinned version is the version that the client was checked against."""
    from src.hardware.llmfit_client import LLMFIT_MIN_VERSION

    pinned = (
        REPO_ROOT / "apps" / "backend-py" / "requirements-optional.txt"
    ).read_text()
    wanted = ".".join(str(part) for part in LLMFIT_MIN_VERSION)
    assert f"llmfit=={wanted}" in pinned
