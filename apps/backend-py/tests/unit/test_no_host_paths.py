"""
Guard: tracked files contain no full host paths.

Full host paths in a public repository show the account name and the folder
layout of the developer's machine. Documentation writes paths relative to the
project root instead. This test reads every tracked text file (``git ls-files``)
and fails on a full host path. The failure message names the file, the line
number, and the rule.

Allowed: container paths (the ``jobraider`` home folder in the Docker image),
placeholders in angle brackets (for example a Windows user folder written as
``<user>``), wildcards, the Docker Desktop install path, and bare drive mounts
with no folder after them (for example a ``df`` call on the C: mount).

The patterns are built from parts, so this file does not match its own text.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import List, Optional, Pattern, Tuple

import pytest

# apps/backend-py/tests/unit/test_no_host_paths.py -> the project root is parents[4]
REPO_ROOT = Path(__file__).resolve().parents[4]

SKIP_NAMES = frozenset({"package-lock.json"})
SKIP_SUFFIXES = (".lock",)
BINARY_PROBE_BYTES = 8192

_S = r"[\\/]"  # a path separator, slash or backslash
_HOME = "ho" + "me"
_MNT = "m" + "nt"
_USERS = "Us" + "ers"
_REPO = "job" + "-raider"
_CONTAINER_USER = "job" + "raider"
_NAME = r"[A-Za-z0-9._-]+"
_PLACEHOLDER = r"<[^>\s]+>"

HOST_PATH_RULES: Tuple[Tuple[str, Pattern[str]], ...] = (
    (
        "account home folder",
        re.compile(
            rf"(?:(?<![\w.~-])|wsl(?:\.localhost|\$){_S}+{_NAME})"
            rf"{_S}{_HOME}{_S}(?!{_CONTAINER_USER}\b)(?!<){_NAME}"
        ),
    ),
    (
        "projects folder in a home folder",
        re.compile(rf"~/(?:personal-projects\b|{_NAME}/{_REPO}\b)"),
    ),
    (
        "Windows drive folder under the WSL mount",
        re.compile(
            rf"(?<![\w.-])/{_MNT}/[a-z]/"
            r"(?!Program(?:\\ | )Files/)"
            rf"(?!{_USERS}/(?:\*|{_PLACEHOLDER})/)"
            r"[A-Za-z0-9_]"
        ),
    ),
    (
        "Claude scratchpad folder",
        re.compile(r"/tmp/cl" + r"aude\b|Temp" + _S + r"cl" + r"aude" + _S),
    ),
    (
        "Windows user folder",
        re.compile(
            rf"(?<!\w)[A-Za-z]:{_S}+{_USERS}{_S}+(?!{_PLACEHOLDER})(?!\*)[A-Za-z0-9._-]"
        ),
    ),
    (
        "Windows drive path to the repository folder",
        re.compile(rf"(?<!\w)[A-Za-z]:{_S}+(?:{_NAME}{_S}+)*{_REPO}\b"),
    ),
)


def find_host_paths(text: str) -> List[Tuple[int, str]]:
    """Find full host paths in a text.

    Args:
        text: The text of one file.

    Returns:
        One ``(line_number, rule_name)`` pair for each line and rule that
        matches. Line numbers start at 1.
    """
    hits: List[Tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for name, pattern in HOST_PATH_RULES:
            if pattern.search(line):
                hits.append((number, name))
    return hits


def _tracked_files(root: Path) -> Optional[List[Path]]:
    """List the files that git tracks in the repository.

    Args:
        root: The project root.

    Returns:
        The tracked files as absolute paths, or ``None`` when ``root`` is not
        a git work tree (for example inside a Docker image).
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    names = [n for n in result.stdout.decode("utf-8").split("\0") if n]
    return [root / name for name in names]


def _read_text(path: Path) -> Optional[str]:
    """Read a tracked file as text.

    Args:
        path: The file to read.

    Returns:
        The text, or ``None`` for a skipped file (lock file, binary file, or a
        file that is tracked but missing from the work tree).
    """
    if path.name in SKIP_NAMES or path.suffix in SKIP_SUFFIXES:
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:BINARY_PROBE_BYTES]:
        return None
    return data.decode("utf-8", errors="ignore")


def test_tracked_files_contain_no_host_paths() -> None:
    """No tracked text file contains a full host path."""
    files = _tracked_files(REPO_ROOT)
    if files is None:
        pytest.skip("not a git work tree")
    problems: List[str] = []
    for path in files:
        text = _read_text(path)
        if text is None:
            continue
        relative = path.relative_to(REPO_ROOT).as_posix()
        for number, rule in find_host_paths(text):
            problems.append(f"{relative}:{number}: {rule}")
    assert not problems, (
        "Full host paths found. Write paths relative to the project root:\n"
        + "\n".join(problems)
    )


_BS = "\\"

BLOCKED_EXAMPLES = (
    "/" + _HOME + "/alex/projects",
    "cd ~/" + "personal-" + "projects/app",
    "~/code/" + _REPO,
    "find /" + _MNT + "/d/GitHub/app -name x",
    "/" + _MNT + "/c/" + _USERS + "/Alex/file",
    "/tmp/cl" + "aude/abc/scratchpad",
    "C:" + _BS + _USERS + _BS + "Alex" + _BS + "AppData",
    "C:/" + _USERS + "/Alex/.cursor/plan.md",
    "D:" + _BS + "GitHub" + _BS + _REPO,
    _BS * 2 + "wsl.localhost" + _BS + "Ubuntu" + _BS + _HOME + _BS + "alex",
)

ALLOWED_EXAMPLES = (
    "/" + _HOME + "/" + _CONTAINER_USER + "/.cache/ms-playwright",
    "apps/frontend-ts/tests/app/" + _HOME + "/page.test.tsx",
    "source ~/.nvm/nvm.sh",
    "df -h /" + _MNT + "/c",
    "the WSL path `/" + _MNT + "/d/...`",
    "/" + _MNT + "/c/Program" + _BS + " Files/Docker/docker.exe",
    "du -sh /" + _MNT + "/c/" + _USERS + "/*/AppData",
    "C:" + _BS + _USERS + _BS + "<user>" + _BS + "AppData",
    "find . -name __pycache__",
    "https://github.com/owner/" + _REPO,
)


@pytest.mark.parametrize("line", BLOCKED_EXAMPLES)
def test_find_host_paths_blocks_full_host_paths(line: str) -> None:
    """Each kind of full host path is found."""
    assert find_host_paths(line), line


@pytest.mark.parametrize("line", ALLOWED_EXAMPLES)
def test_find_host_paths_allows_safe_paths(line: str) -> None:
    """Container paths, placeholders, wildcards, and relative paths pass."""
    assert not find_host_paths(line), line
