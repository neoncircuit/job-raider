"""
Tests for the free-ports task: ``scripts/dev.sh`` picks free ports.

When the default port is in use (for example by another project), the
backend and the frontend start on the next free port, the frontend gets the
backend address for its proxy and its WebSocket, ``make app`` builds again
when the backend port changed, and the backend allows the Origin of the
chosen frontend port. The tests run the real script in a temporary
repository layout, with stubs that record their arguments and environment,
and use free high ports so that a running app on this machine does not
change the result.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from contextlib import ExitStack, closing
from pathlib import Path
from typing import Dict, Iterator, List, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
DEV_SH = REPO_ROOT / "scripts" / "dev.sh"


def free_port_block(size: int = 3) -> int:
    """
    Find the first port of ``size`` free ports in a row on 127.0.0.1.

    Args:
        size: How many ports in a row must be free.

    Returns:
        The first port of the block.
    """
    for _ in range(50):
        with closing(socket.socket()) as probe:
            probe.bind(("127.0.0.1", 0))
            start = probe.getsockname()[1]
        if start + size >= 65535:
            continue
        if all(_is_free(start + i) for i in range(size)):
            return start
    pytest.skip("no block of free ports found")


def _is_free(port: int) -> bool:
    """
    Tell whether nothing listens on a loopback port.

    Args:
        port: The port.

    Returns:
        True when a connect is refused.
    """
    with closing(socket.socket()) as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def listen_on(stack: ExitStack, port: int) -> None:
    """
    Hold a listening socket on a loopback port until the stack closes.

    Args:
        stack: The exit stack that closes the socket.
        port: The port to occupy.
    """
    sock = stack.enter_context(closing(socket.socket()))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen(1)


def make_repo(tmp_path: Path) -> Path:
    """
    Copy the start scripts into a temporary repository layout with stubs.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        The repository root.
    """
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(DEV_SH, root / "scripts" / "dev.sh")
    shutil.copy(DEV_SH.parent / "find_python.sh", root / "scripts" / "find_python.sh")
    venv_bin = root / "apps" / "backend-py" / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    python = venv_bin / "python3"
    python.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$@" > "{tmp_path}/python-args.txt"\n'
        f'echo "FRONTEND_PORT=$FRONTEND_PORT" > "{tmp_path}/python-env.txt"\n'
    )
    python.chmod(0o755)
    frontend = root / "apps" / "frontend-ts"
    (frontend / "src").mkdir(parents=True)
    (frontend / "src" / "page.tsx").write_text("export {};\n")
    (frontend / "package.json").write_text("{}\n")
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    npm = stub_bin / "npm"
    npm.write_text(
        f'#!/bin/sh\necho "$*" >> "{tmp_path}/npm-calls.txt"\n'
        f'echo "BACKEND_API_URL=$BACKEND_API_URL '
        f'NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL" >> "{tmp_path}/npm-env.txt"\n'
    )
    npm.chmod(0o755)
    return root


def mark_built(root: Path, backend_port: Optional[str]) -> None:
    """
    Create a production build that is newer than the source.

    Args:
        root: Repository root.
        backend_port: The backend port stamped for the build, or None for
            no stamp (a build from before this change).
    """
    frontend = root / "apps" / "frontend-ts"
    next_dir = frontend / ".next"
    next_dir.mkdir()
    (next_dir / "BUILD_ID").write_text("build\n")
    if backend_port is not None:
        (next_dir / "job-raider-backend-port").write_text(f"{backend_port}\n")
    for path in (frontend / "src" / "page.tsx", frontend / "package.json"):
        os.utime(path, (1_000_000_000, 1_000_000_000))


def run_dev_sh(
    tmp_path: Path, root: Path, mode: str, env: Dict[str, str]
) -> subprocess.CompletedProcess:
    """
    Run ``dev.sh`` in the temporary layout.

    Args:
        tmp_path: Pytest temporary directory (holds the stubs).
        root: Repository root.
        mode: The dev.sh mode.
        env: Extra environment variables.

    Returns:
        The finished process.
    """
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is required to run scripts/dev.sh")
    base = {
        k: v
        for k, v in os.environ.items()
        if k
        not in (
            "FRONTEND_PORT",
            "BACKEND_PORT",
            "BACKEND_API_URL",
            "NEXT_PUBLIC_WS_URL",
        )
    }
    return subprocess.run(
        [bash, str(root / "scripts" / "dev.sh"), mode],
        capture_output=True,
        text=True,
        timeout=60,
        env={
            **base,
            "DEV_DEPS_CHECKED": "1",
            "PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}",
            **env,
        },
    )


def flag(args: List[str], name: str) -> str:
    """
    Return the value after a command-line flag.

    Args:
        args: Recorded arguments.
        name: The flag, for example ``--port``.

    Returns:
        The value.
    """
    assert name in args, args
    return args[args.index(name) + 1]


def lines(path: Path) -> List[str]:
    """
    Read the lines of a stub record file.

    Args:
        path: The record file.

    Returns:
        Its lines, or an empty list when it does not exist.
    """
    return path.read_text().splitlines() if path.exists() else []


@pytest.fixture
def ports() -> Iterator[int]:
    """A block of three free ports; yields the first one."""
    yield free_port_block()


# --- Backend port -----------------------------------------------------------


def test_backend_moves_to_the_next_port_when_the_start_port_is_taken(
    tmp_path: Path, ports: int
) -> None:
    """With the start port taken, uvicorn starts on the next port."""
    root = make_repo(tmp_path)
    with ExitStack() as stack:
        listen_on(stack, ports)
        result = run_dev_sh(
            tmp_path, root, "app-api", {"BACKEND_PORT_START": str(ports)}
        )

    assert result.returncode == 0, result.stdout + result.stderr
    assert flag(lines(tmp_path / "python-args.txt"), "--port") == str(ports + 1)
    assert f"Port {ports} is in use" in result.stdout


def test_backend_keeps_a_free_start_port(tmp_path: Path, ports: int) -> None:
    """With the start port free, uvicorn starts on it."""
    root = make_repo(tmp_path)
    result = run_dev_sh(tmp_path, root, "app-api", {"BACKEND_PORT_START": str(ports)})

    assert result.returncode == 0, result.stdout + result.stderr
    assert flag(lines(tmp_path / "python-args.txt"), "--port") == str(ports)


def test_a_port_set_by_the_user_is_used_as_given(tmp_path: Path, ports: int) -> None:
    """``BACKEND_PORT`` is used without a search, also when it is taken."""
    root = make_repo(tmp_path)
    with ExitStack() as stack:
        listen_on(stack, ports)
        result = run_dev_sh(tmp_path, root, "app-api", {"BACKEND_PORT": str(ports)})

    assert result.returncode == 0, result.stdout + result.stderr
    assert flag(lines(tmp_path / "python-args.txt"), "--port") == str(ports)


def test_no_free_port_in_the_range_stops_with_a_message(
    tmp_path: Path, ports: int
) -> None:
    """When every port of the range is taken, the start stops with a clear message."""
    root = make_repo(tmp_path)
    with ExitStack() as stack:
        listen_on(stack, ports)
        result = run_dev_sh(
            tmp_path,
            root,
            "app-api",
            {"BACKEND_PORT_START": str(ports), "DEV_PORT_SPAN": "0"},
        )

    assert result.returncode != 0
    assert "No free port" in result.stdout + result.stderr
    assert lines(tmp_path / "python-args.txt") == []


# --- Frontend port and backend address --------------------------------------


def test_frontend_moves_to_the_next_port_when_the_start_port_is_taken(
    tmp_path: Path, ports: int
) -> None:
    """With the start port taken, Next.js starts on the next port."""
    root = make_repo(tmp_path)
    mark_built(root, None)
    with ExitStack() as stack:
        listen_on(stack, ports)
        result = run_dev_sh(
            tmp_path,
            root,
            "app-frontend",
            {"FRONTEND_PORT_START": str(ports), "BACKEND_PORT": "8000"},
        )

    assert result.returncode == 0, result.stdout + result.stderr
    assert lines(tmp_path / "npm-calls.txt") == [
        f"run start -- --hostname 127.0.0.1 --port {ports + 1}"
    ]


def test_frontend_gets_the_backend_address(tmp_path: Path, ports: int) -> None:
    """The frontend proxy and WebSocket use the chosen backend port."""
    root = make_repo(tmp_path)
    mark_built(root, "8123")
    result = run_dev_sh(
        tmp_path,
        root,
        "app-frontend",
        {"FRONTEND_PORT": str(ports), "BACKEND_PORT": "8123"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert lines(tmp_path / "npm-env.txt") == [
        "BACKEND_API_URL=http://127.0.0.1:8123 NEXT_PUBLIC_WS_URL=ws://127.0.0.1:8123"
    ]


def test_a_changed_backend_port_rebuilds_the_frontend(
    tmp_path: Path, ports: int
) -> None:
    """``make app`` builds again when the build has another backend port."""
    root = make_repo(tmp_path)
    mark_built(root, "8000")
    result = run_dev_sh(
        tmp_path,
        root,
        "app-frontend",
        {"FRONTEND_PORT": str(ports), "BACKEND_PORT": "8123"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert lines(tmp_path / "npm-calls.txt")[0] == "run build"
    stamp = root / "apps" / "frontend-ts" / ".next" / "job-raider-backend-port"
    assert stamp.read_text().strip() == "8123"


def test_an_old_build_counts_as_backend_port_8000(tmp_path: Path, ports: int) -> None:
    """A build without a port stamp is reused when the backend port is 8000."""
    root = make_repo(tmp_path)
    mark_built(root, None)
    result = run_dev_sh(
        tmp_path,
        root,
        "app-frontend",
        {"FRONTEND_PORT": str(ports), "BACKEND_PORT": "8000"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert lines(tmp_path / "npm-calls.txt") == [
        f"run start -- --hostname 127.0.0.1 --port {ports}"
    ]


def test_backend_gets_the_frontend_port(tmp_path: Path, ports: int) -> None:
    """The backend process sees ``FRONTEND_PORT`` for its Origin check."""
    root = make_repo(tmp_path)
    result = run_dev_sh(
        tmp_path,
        root,
        "app-api",
        {"BACKEND_PORT": str(ports), "FRONTEND_PORT": "3005"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert lines(tmp_path / "python-env.txt") == ["FRONTEND_PORT=3005"]


# --- Backend Origin check ---------------------------------------------------


def test_cors_origins_add_the_frontend_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """``FRONTEND_PORT`` adds its two loopback origins to the defaults."""
    from src.api.main import _parse_cors_origins

    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("FRONTEND_PORT", "3001")

    origins = _parse_cors_origins()

    assert "http://localhost:3001" in origins
    assert "http://127.0.0.1:3001" in origins
    assert "http://localhost:3000" in origins


def test_cors_origins_add_the_frontend_port_to_a_set_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``FRONTEND_PORT`` is also added when ``CORS_ALLOWED_ORIGINS`` is set."""
    from src.api.main import _parse_cors_origins

    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("FRONTEND_PORT", "3002")

    assert _parse_cors_origins() == [
        "http://localhost:3000",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ]


@pytest.mark.parametrize("value", ["", "abc", "0", "70000", "3000; evil"])
def test_cors_origins_ignore_a_bad_frontend_port(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """A missing or bad ``FRONTEND_PORT`` adds no origin."""
    from src.api.main import _parse_cors_origins

    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("FRONTEND_PORT", value)

    assert _parse_cors_origins() == ["http://localhost:3000"]
