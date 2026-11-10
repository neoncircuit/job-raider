"""
Tests for the `make dev` split view (mprocs).

`make dev` starts the backend and the frontend in mprocs when the pinned
binary is installed and the terminal is interactive; otherwise it falls back
to the plain mixed output. These tests read the files only; they start no
process.
"""

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_mprocs_config_runs_the_two_dev_services() -> None:
    """mprocs.yaml has one process each for the backend and the frontend."""
    config = yaml.safe_load((REPO_ROOT / "mprocs.yaml").read_text())
    procs = config["procs"]
    assert procs["backend"]["shell"] == "./scripts/dev.sh api"
    assert procs["frontend"]["shell"] == "./scripts/dev.sh frontend"


def test_mprocs_is_pinned_in_the_frontend_dev_dependencies() -> None:
    """npm ci installs one exact mprocs version with the frontend."""
    package = json.loads(
        (REPO_ROOT / "apps" / "frontend-ts" / "package.json").read_text()
    )
    assert package["devDependencies"]["mprocs"] == "0.9.6"


def test_dev_sh_uses_mprocs_only_when_it_can() -> None:
    """The split view needs the binary and a terminal, and DEV_PLAIN opts out."""
    script = (REPO_ROOT / "scripts" / "dev.sh").read_text()
    assert 'MPROCS_BIN="$FRONTEND_DIR/node_modules/.bin/mprocs"' in script
    assert '[ -t 1 ] && [ -x "$MPROCS_BIN" ] && [ -z "${DEV_PLAIN:-}" ]' in script
    assert 'exec "$MPROCS_BIN" --config "$PROJECT_ROOT/mprocs.yaml"' in script
    # The plain fallback stays.
    assert "start_api & start_frontend; wait" in script
