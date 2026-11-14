"""
Tests for scripts/find_python.sh (used by setup.sh and scripts/dev.sh).

A fresh machine can have an old default ``python3`` (Ubuntu 22.04: 3.10)
next to a newer versioned Python, or no suitable Python at all. Each test
sources the helper in bash with a PATH that holds only stub Pythons (shell
scripts that report a version) and the few tools the helper needs, so the
real Pythons on this machine are not seen. Nothing is downloaded or installed.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
FIND_PYTHON = REPO_ROOT / "scripts" / "find_python.sh"
TOOLS = (
    "tr",
    "cut",
    "sort",
    "head",
    "mkdir",
    "chmod",
    "uname",
    "mktemp",
    "sha256sum",
    "grep",
    "rm",
    "tar",
    "mv",
)

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="bash is not available"
)

# Bash function that stands in for the uv install: it creates a stub
# Python 3.11 where uv would put it.
FAKE_INSTALL = (
    "install_repo_python() { "
    'd="$1/.tools/python/cpython-3.11.9-linux-x86_64-gnu/bin"; mkdir -p "$d"; '
    'printf \'#!/bin/sh\\necho 3.11\\n\' > "$d/python3"; chmod +x "$d/python3"; }; '
)


def _run(
    tmp_path: Path,
    pythons: Dict[str, str],
    command: str,
    required: str = "3.11",
    extra_stubs: Dict[str, str] | None = None,
) -> Tuple[int, str, Path]:
    """
    Source find_python.sh with stub Pythons and run a bash command.

    Args:
        tmp_path: Pytest temporary directory.
        pythons: Stub command name to the version it reports, for example
            ``{"python3": "3.10.12"}``. The version ``"broken"`` makes the
            stub fail.
        command: Bash command to run after sourcing; ``$ROOT`` is the project root.
        required: Content of the temporary ``.python-version``.
        extra_stubs: Other stub commands, name to shell script body.

    Returns:
        Tuple of (exit code, combined stdout and stderr, project root).
    """
    root = tmp_path / "root"
    root.mkdir()
    (root / ".python-version").write_text(f"{required}\n")
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    for tool in TOOLS:
        found = shutil.which(tool)
        assert found, f"{tool} is required"
        (stub_bin / tool).symlink_to(found)
    for name, version in pythons.items():
        stub = stub_bin / name
        if version == "broken":
            stub.write_text("#!/bin/sh\nexit 1\n")
        else:
            short = ".".join(version.split(".")[:2])
            stub.write_text(
                "#!/bin/sh\n"
                f'if [ "$1" = "--version" ]; then echo "Python {version}"; '
                f"else echo {short}; fi\n"
            )
        stub.chmod(0o755)
    for name, body in (extra_stubs or {}).items():
        stub = stub_bin / name
        stub.write_text(f"#!/bin/sh\n{body}\n")
        stub.chmod(0o755)
    bash = shutil.which("bash")
    assert bash
    result = subprocess.run(
        [bash, "-c", f'source "{FIND_PYTHON}"; ROOT="{root}"; {command}'],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PATH": str(stub_bin)},
    )
    return result.returncode, result.stdout + result.stderr, root


def test_old_default_python_alone_is_refused(tmp_path: Path) -> None:
    """Only python3 3.10: find_python finds nothing."""
    code, out, _ = _run(tmp_path, {"python3": "3.10.12"}, 'find_python "$ROOT"')
    assert code == 1
    assert out == ""


def test_versioned_python_is_picked_over_old_default(tmp_path: Path) -> None:
    """python3 3.10 next to python3.12: python3.12 is picked."""
    code, out, _ = _run(
        tmp_path,
        {"python3": "3.10.12", "python3.12": "3.12.3"},
        'find_python "$ROOT"',
    )
    assert code == 0
    assert out.strip().endswith("/python3.12")


def test_default_python_is_used_when_new_enough(tmp_path: Path) -> None:
    """python3 3.12 alone (Ubuntu 24.04): python3 is picked."""
    code, out, _ = _run(tmp_path, {"python3": "3.12.3"}, 'find_python "$ROOT"')
    assert code == 0
    assert out.strip().endswith("/python3")


def test_newest_suitable_python_wins(tmp_path: Path) -> None:
    """python3.11 and python3.13: python3.13 is picked."""
    code, out, _ = _run(
        tmp_path,
        {"python3.11": "3.11.9", "python3.13": "3.13.1"},
        'find_python "$ROOT"',
    )
    assert code == 0
    assert out.strip().endswith("/python3.13")


def test_broken_python_is_skipped(tmp_path: Path) -> None:
    """A python3.12 that does not run is skipped for a working python3.11."""
    code, out, _ = _run(
        tmp_path,
        {"python3.12": "broken", "python3.11": "3.11.9"},
        'find_python "$ROOT"',
    )
    assert code == 0
    assert out.strip().endswith("/python3.11")


def test_required_version_comes_from_python_version_file(tmp_path: Path) -> None:
    """With .python-version 3.12, python3.11 is not enough."""
    code, _, _ = _run(
        tmp_path, {"python3.11": "3.11.9"}, 'find_python "$ROOT"', required="3.12"
    )
    assert code == 1


def test_ensure_python_uses_a_system_python_without_installing(
    tmp_path: Path,
) -> None:
    """A suitable system Python is used; the in-repository install does not run."""
    code, out, root = _run(
        tmp_path,
        {"python3": "3.10.12", "python3.12": "3.12.3"},
        "install_repo_python() { echo INSTALL-CALLED >&2; return 1; }; "
        'ensure_python "$ROOT"',
    )
    assert code == 0
    assert out.strip().endswith("/python3.12")
    assert "INSTALL-CALLED" not in out
    assert not (root / ".tools").exists()


def test_ensure_python_installs_into_the_repository_when_none_fits(
    tmp_path: Path,
) -> None:
    """Only python3 3.10: the install runs and its .tools Python is picked."""
    code, out, root = _run(
        tmp_path, {"python3": "3.10.12"}, FAKE_INSTALL + 'ensure_python "$ROOT"'
    )
    assert code == 0
    # stdout (the path) and stderr (progress) are joined; take the path line.
    picked = Path(next(line for line in out.splitlines() if line.startswith("/")))
    assert picked == (
        root
        / ".tools"
        / "python"
        / "cpython-3.11.9-linux-x86_64-gnu"
        / "bin"
        / "python3"
    )
    assert "No Python 3.11 or newer found on this machine." in out


def test_ensure_python_fails_when_the_install_fails(tmp_path: Path) -> None:
    """When the install fails, ensure_python fails too."""
    code, _, _ = _run(
        tmp_path,
        {"python3": "3.10.12"},
        'install_repo_python() { return 1; }; ensure_python "$ROOT"',
    )
    assert code == 1


def test_uv_download_with_a_wrong_checksum_is_refused(tmp_path: Path) -> None:
    """A uv archive that does not match the pinned SHA-256 is not installed."""
    fake_curl = (
        'while [ -n "$1" ]; do if [ "$1" = "-o" ]; then shift; '
        'echo not-uv > "$1"; fi; shift; done'
    )
    code, out, root = _run(
        tmp_path,
        {"python3": "3.10.12"},
        'install_repo_python "$ROOT"',
        extra_stubs={"curl": fake_curl},
    )
    assert code == 1
    assert "does not match its SHA-256" in out
    assert not (root / ".tools" / "bin" / "uv").exists()
    # The temporary download folder is removed.
    assert not list((root / ".tools").glob("download.*"))


def test_install_help_names_the_versions_and_commands(tmp_path: Path) -> None:
    """The help text names the required and found versions and the commands."""
    code, out, _ = _run(tmp_path, {"python3": "3.10.12"}, 'python_install_help "$ROOT"')
    assert code == 0
    assert "Python 3.11 or newer is required (found: Python 3.10.12)." in out
    assert "sudo add-apt-repository -y ppa:deadsnakes/ppa" in out
    assert "sudo apt install -y python3.12 python3.12-venv" in out


def test_uv_install_stays_inside_the_repository() -> None:
    """The uv call keeps its cache and Pythons in .tools and adds no ~/.local/bin links."""
    script = FIND_PYTHON.read_text()
    assert 'UV_CACHE_DIR="$root/.tools/cache"' in script
    assert 'UV_PYTHON_INSTALL_DIR="$root/.tools/python"' in script
    assert "python install --no-bin" in script
    assert ".tools/" in (REPO_ROOT / ".gitignore").read_text().splitlines()


def test_scripts_use_the_helper_not_plain_python3() -> None:
    """setup.sh and dev.sh create the .venv with the Python the helper gives."""
    setup = (REPO_ROOT / "setup.sh").read_text()
    dev = (REPO_ROOT / "scripts" / "dev.sh").read_text()
    for script in (setup, dev):
        assert 'source "$PROJECT_ROOT/scripts/find_python.sh"' in script
        assert "python3 -m venv" not in script
    assert 'PYTHON_BIN="$(ensure_python "$PROJECT_ROOT")"' in setup
    assert '"$PYTHON_BIN" -m venv "$VENV_DIR"' in setup
    assert 'python_bin="$(ensure_python "$PROJECT_ROOT")"' in dev
    # dev.sh creates the .venv again when it was made with an older Python.
    assert 'python_meets "$VENV_PYTHON" "$(python_required_version' in dev
