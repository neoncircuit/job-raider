"""
Tests for the dependency checks of scripts/dev.sh.

`make dev` creates, repairs, and updates the backend .venv and the frontend
node_modules before it starts the services. These tests read the script
only; the behaviour is checked by running `./scripts/dev.sh deps` (see the
task notes), because a real check installs packages.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = (REPO_ROOT / "scripts" / "dev.sh").read_text()


def test_backend_venv_is_rebuilt_when_broken() -> None:
    """A .venv whose Python fails, is too old, or has broken packages is created again."""
    assert '"$VENV_PYTHON" -c "import sys"' in SCRIPT
    assert '"$VENV_PYTHON" -c "import fastapi, uvicorn, pydantic, setuptools"' in SCRIPT
    assert SCRIPT.count('rm -rf "$BACKEND_DIR/.venv"') == 3


def test_requirements_changes_trigger_an_install() -> None:
    """The requirements files are hashed, and the hash is kept in the .venv."""
    assert (
        'files_sha256 "$BACKEND_DIR/requirements.txt" '
        '"$BACKEND_DIR/requirements-optional.txt"' in SCRIPT
    )
    assert (
        'BACKEND_STAMP="$BACKEND_DIR/.venv/.job-raider-requirements.sha256"' in SCRIPT
    )
    assert 'echo "$want" > "$BACKEND_STAMP"' in SCRIPT


def test_llmfit_stays_optional() -> None:
    """A failed llmfit install warns, and NO_LLMFIT=1 skips it."""
    assert '[ -z "${NO_LLMFIT:-}" ]' in SCRIPT
    assert '|| warn "llmfit could not be installed' in SCRIPT


def test_frontend_follows_the_lockfile() -> None:
    """npm ci runs when node_modules, next, or the lockfile hash disagree."""
    assert (
        'FRONTEND_STAMP="$FRONTEND_DIR/node_modules/.job-raider-lock.sha256"' in SCRIPT
    )
    assert '[ -x "$FRONTEND_DIR/node_modules/.bin/next" ]' in SCRIPT
    assert "npm ci --silent --no-audit --no-fund" in SCRIPT


def test_deps_mode_and_one_check_per_start() -> None:
    """`deps` only checks; mprocs processes do not repeat the checks."""
    assert "    deps)\n        ensure_backend\n        ensure_frontend\n" in SCRIPT
    assert "export DEV_DEPS_CHECKED=1" in SCRIPT
    assert SCRIPT.count('[ -n "${DEV_DEPS_CHECKED:-}" ] && return 0') == 2
