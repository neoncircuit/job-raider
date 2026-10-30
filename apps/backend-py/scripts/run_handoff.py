#!/usr/bin/env python3
"""
Job Raider - Apply a micro-handoff without an agent (the handoff runner)

Reads a micro-handoff (Markdown) and applies, in document order, the fenced
blocks whose info string has a runner attribute after the language word:

- ``new=<path>``: create the file with the block text;
- ``edit=<path>``: one ``<<<<<<< OLD`` / ``=======`` / ``>>>>>>> NEW`` pair;
  the old text must occur exactly once;
- ``red``: run the command; it must fail (the test is written first);
- ``check``: run the command; it must pass;
- ``commit``: the commit message (exactly one block).

``cwd=<dir>`` sets the folder of a command. Paths are relative to the
repository root. Blocks without a runner attribute (Mermaid, examples) are
skipped. Everything is validated before the first write. When the red
command passes, a check fails, or the commit fails, every file is restored
and nothing is committed. See ``docs/handoff-runner.md``.

Usage (from apps/backend-py, in WSL):

    .venv/bin/python scripts/run_handoff.py ../../tasks/active/TASK/MH.md --dry-run

Author: Job Raider
Date: 2026-10-30
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Optional, Sequence, Tuple

FENCE_RE = re.compile(r"^```([^\n`]*)\n(.*?)^```[ \t]*$", re.M | re.S)
EDIT_RE = re.compile(
    r"\A<<<<<<< OLD\n(.*?)^=======\n(.*?)^>>>>>>> NEW[ \t]*\n?\Z", re.M | re.S
)
FILE_KINDS = ("new", "edit")
COMMAND_KINDS = ("red", "check")
FORBIDDEN_PREFIXES = ("apps/backend-py/data/", ".git/")
DEFAULT_TIMEOUT = 1800
OUTPUT_LINES = 12


@dataclass
class Step:
    """One runner block of a handoff."""

    kind: str
    line: int
    text: str = ""
    path: str = ""
    cwd: str = "."
    old: str = ""
    new: str = ""


def parse_handoff(text: str) -> List[Step]:
    """
    Read the runner blocks of a handoff in document order.

    Args:
        text: The handoff (Markdown).

    Returns:
        One step for each fenced block with a runner attribute. The text of
        a ``new`` step is the block text; the text of a command or commit
        step is the stripped block text.

    Raises:
        ValueError: When a block has two actions, an edit block is not one
            OLD/NEW pair, or a command or commit block is empty.
    """
    normalized = text.replace("\r\n", "\n")
    steps: List[Step] = []
    for match in FENCE_RE.finditer(normalized):
        line = normalized.count("\n", 0, match.start()) + 1
        attributes = match.group(1).split()[1:]
        body = match.group(2)
        options = dict(item.split("=", 1) for item in attributes if "=" in item)
        flags = [item for item in attributes if "=" not in item]
        actions = [kind for kind in FILE_KINDS if kind in options] + [
            flag for flag in flags if flag in (*COMMAND_KINDS, "commit")
        ]
        if not actions:
            continue
        if len(actions) > 1:
            raise ValueError(f"line {line}: one block has two actions: {actions}")
        kind = actions[0]
        step = Step(kind=kind, line=line, cwd=options.get("cwd", "."))
        if kind == "new":
            step.path, step.text = options["new"], body
        elif kind == "edit":
            pair = EDIT_RE.match(body)
            if pair is None or not pair.group(1):
                raise ValueError(f"line {line}: an edit block needs one OLD/NEW pair")
            step.path, step.old, step.new = (
                options["edit"],
                pair.group(1),
                pair.group(2),
            )
        else:
            step.text = body.strip()
            if not step.text:
                raise ValueError(f"line {line}: the {kind} block is empty")
        steps.append(step)
    return steps


def path_problem(relative: str) -> Optional[str]:
    """
    Say why the runner must not write to a path.

    Args:
        relative: A path relative to the repository root.

    Returns:
        The reason, or None when the path is allowed.
    """
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        return f"{relative}: the path must stay inside the repository"
    if any(pure.as_posix().startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        return f"{relative}: the runner never writes here"
    if pure.name.startswith(".env") and not pure.name.endswith(".example"):
        return f"{relative}: the runner never writes .env files"
    return None


def read_text(path: Path) -> str:
    """
    Read a file as UTF-8 text with LF line ends.

    Args:
        path: The file.

    Returns:
        The text, with each CRLF changed to LF.
    """
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def plan_handoff(steps: Sequence[Step], root: Path) -> List[str]:
    """
    Check every step in memory before anything is written.

    Args:
        steps: The parsed steps.
        root: The repository root.

    Returns:
        The paths that the handoff writes, in first-use order.

    Raises:
        ValueError: With every problem found, one for each line.
    """
    problems: List[str] = []
    if sum(1 for step in steps if step.kind == "commit") != 1:
        problems.append("the handoff needs exactly one commit block")
    if not any(step.kind in FILE_KINDS for step in steps):
        problems.append("the handoff has no new or edit block")
    current: Dict[str, Optional[str]] = {}
    for step in steps:
        if step.kind in COMMAND_KINDS:
            if path_problem(step.cwd) or not (root / step.cwd).is_dir():
                problems.append(
                    f"line {step.line}: cwd {step.cwd!r} is not a repository folder"
                )
            continue
        if step.kind not in FILE_KINDS:
            continue
        reason = path_problem(step.path)
        if reason:
            problems.append(f"line {step.line}: {reason}")
            continue
        if step.path not in current:
            target = root / step.path
            current[step.path] = read_text(target) if target.is_file() else None
        text = current[step.path]
        if step.kind == "new":
            if text is not None and text != step.text:
                problems.append(f"line {step.line}: {step.path} exists with other text")
            current[step.path] = step.text
        elif text is None:
            problems.append(f"line {step.line}: {step.path} does not exist")
        else:
            count = text.count(step.old)
            if count != 1:
                problems.append(
                    f"line {step.line}: the old text occurs {count} times "
                    f"in {step.path}"
                )
            else:
                current[step.path] = text.replace(step.old, step.new, 1)
    if problems:
        raise ValueError("\n".join(problems))
    return list(current)


def git(root: Path, *args: str, stdin: Optional[str] = None) -> Tuple[int, str]:
    """
    Run git in the repository.

    Args:
        root: The repository root.
        *args: The git arguments.
        stdin: Text for the standard input, or None.

    Returns:
        The exit code and the combined output.
    """
    result = subprocess.run(
        ["git", *args], cwd=root, input=stdin, capture_output=True, text=True
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def check_git(root: Path, steps: Sequence[Step]) -> None:
    """
    Stop when the commit would mix in other work.

    Args:
        root: The repository root.
        steps: The parsed steps.

    Raises:
        ValueError: When files are staged, or when a file to edit is not
            tracked or has changes other than line ends.
    """
    problems: List[str] = []
    if git(root, "diff", "--cached", "--quiet")[0] != 0:
        problems.append("files are staged; commit or unstage them first")
    created = {step.path for step in steps if step.kind == "new"}
    edited = {step.path for step in steps if step.kind == "edit"} - created
    for path in sorted(edited):
        if git(root, "ls-files", "--error-unmatch", "--", path)[0] != 0:
            problems.append(f"{path} is not tracked by git")
        elif git(root, "diff", "--ignore-cr-at-eol", "--quiet", "--", path)[0] != 0:
            problems.append(f"{path} has other changes; commit or discard them first")
    if problems:
        raise ValueError("\n".join(problems))


def run_command(step: Step, root: Path, timeout: int) -> Tuple[int, str]:
    """
    Run one red or check command with bash.

    Args:
        step: The command step.
        root: The repository root.
        timeout: The limit in seconds.

    Returns:
        The exit code (124 on a timeout) and the last lines of the output.
    """
    try:
        result = subprocess.run(
            ["bash", "-c", step.text],
            cwd=root / step.cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout} seconds"
    lines = [line for line in (result.stdout + result.stderr).splitlines() if line]
    return result.returncode, "\n".join(lines[-OUTPUT_LINES:])


def restore(root: Path, saved: Dict[str, Optional[bytes]]) -> None:
    """
    Put every written file back as it was before the run.

    Args:
        root: The repository root.
        saved: The bytes of each written file before the run, by path
            (None for a file that did not exist).
    """
    for path, data in saved.items():
        target = root / path
        if data is None:
            target.unlink(missing_ok=True)
        else:
            target.write_bytes(data)


def apply_steps(
    steps: Sequence[Step],
    root: Path,
    timeout: int,
    saved: Dict[str, Optional[bytes]],
    out: Callable[[str], None],
) -> None:
    """
    Write the files and run the commands in document order.

    Args:
        steps: The parsed steps.
        root: The repository root.
        timeout: The limit of each command in seconds.
        saved: Filled with the bytes of each file before its first write.
        out: Prints one report line.

    Raises:
        RuntimeError: When the red command passes or a check fails.
    """
    for step in steps:
        if step.kind in FILE_KINDS:
            target = root / step.path
            if step.path not in saved:
                saved[step.path] = target.read_bytes() if target.is_file() else None
            if step.kind == "new":
                text = step.text
            else:
                text = read_text(target).replace(step.old, step.new, 1)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
            out(f"[{step.kind}] {step.path}")
        elif step.kind in COMMAND_KINDS:
            code, tail = run_command(step, root, timeout)
            good = code != 0 if step.kind == "red" else code == 0
            verdict = (
                "as expected"
                if good
                else ("passed, but it must fail" if step.kind == "red" else "failed")
            )
            out(f"[{step.kind}] ({step.cwd}) {step.text}")
            out(f"  exit {code}: {verdict}")
            for line in tail.splitlines():
                out(f"    {line}")
            if not good:
                raise RuntimeError(
                    f"line {step.line}: the {step.kind} command {verdict}"
                )


def run_handoff(
    steps: Sequence[Step],
    root: Path,
    timeout: int,
    out: Callable[[str], None] = print,
) -> str:
    """
    Apply the steps and commit the written files.

    Args:
        steps: The parsed and validated steps.
        root: The repository root.
        timeout: The limit of each command in seconds.
        out: Prints one report line.

    Returns:
        The short hash of the new commit.

    Raises:
        RuntimeError: When a command is not as expected or the commit fails.
            Every written file is restored first.
    """
    message = next(step.text for step in steps if step.kind == "commit")
    saved: Dict[str, Optional[bytes]] = {}
    try:
        apply_steps(steps, root, timeout, saved, out)
        code, output = git(root, "add", "--", *saved)
        if code != 0:
            raise RuntimeError(f"git add failed: {output}")
        code, output = git(root, "commit", "-q", "-F", "-", stdin=message + "\n")
        if code != 0:
            raise RuntimeError(f"git commit failed: {output}")
    except Exception:
        if saved:
            git(root, "reset", "-q", "--", *saved)
        restore(root, saved)
        raise
    return git(root, "rev-parse", "--short", "HEAD")[1]


def find_repo(handoff: Path) -> Path:
    """
    Find the git repository that holds the handoff.

    Args:
        handoff: The handoff file.

    Returns:
        The repository root.

    Raises:
        ValueError: When the handoff is not in a git repository.
    """
    code, output = git(handoff.resolve().parent, "rev-parse", "--show-toplevel")
    if code != 0:
        raise ValueError(f"{handoff} is not in a git repository; use --repo")
    return Path(output)


def describe(step: Step) -> str:
    """
    Describe one step in one line for the plan.

    Args:
        step: The step.

    Returns:
        The kind and the path, the command, or the commit subject.
    """
    if step.kind in FILE_KINDS:
        return f"{step.kind}: {step.path}"
    if step.kind in COMMAND_KINDS:
        return f"{step.kind}: ({step.cwd}) {step.text.splitlines()[0]}"
    return f"commit: {step.text.splitlines()[0]}"


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Validate a handoff, apply it, and commit.

    Args:
        argv: Command-line arguments (default: ``sys.argv[1:]``).

    Returns:
        0 when the handoff is committed (or the dry run is valid), 1 when
        the run stops.
    """
    parser = argparse.ArgumentParser(
        description="Apply a micro-handoff: write its files, run its red and "
        "check commands, and commit."
    )
    parser.add_argument("handoff", type=Path, help="The handoff file (Markdown)")
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Repository root (default: the repository of the handoff)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and print the plan only"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Seconds for each command (default {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args(argv)

    try:
        root = (args.repo or find_repo(args.handoff)).resolve()
        steps = parse_handoff(args.handoff.read_text(encoding="utf-8"))
        plan_handoff(steps, root)
        check_git(root, steps)
    except (OSError, ValueError) as exc:
        print(f"Stopped before any write:\n{exc}")
        return 1

    print(f"Handoff: {args.handoff}")
    for step in steps:
        print(f"  {describe(step)}")
    if args.dry_run:
        print("Dry run: the handoff is valid; nothing was written.")
        return 0
    try:
        commit_hash = run_handoff(steps, root, args.timeout)
    except (OSError, RuntimeError) as exc:
        print(f"Stopped; every file is restored and nothing committed:\n{exc}")
        return 1
    print(f"Committed {commit_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
