"""Tests for the handoff runner (``scripts/run_handoff.py``).

Each test makes a small git repository in a temporary folder and a handoff
that writes into it, so the runner never touches this repository.
"""

import subprocess
from pathlib import Path
from typing import List

import pytest

from scripts import run_handoff as runner

FENCE = "`" * 3
GREET = 'MESSAGE = "hello"\n'
EDIT = '<<<<<<< OLD\nMESSAGE = "hello"\n=======\nMESSAGE = "hi"\n>>>>>>> NEW\n'


def git(repo: Path, *args: str) -> str:
    """Run git in a repository.

    Args:
        repo: The repository.
        *args: The git arguments.

    Returns:
        The standard output.
    """
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout


def make_repo(tmp_path: Path) -> Path:
    """Make a repository with two committed files.

    Args:
        tmp_path: The pytest temporary folder.

    Returns:
        The repository root.
    """
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "runner@example.com")
    git(repo, "config", "user.name", "Runner Test")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / "app" / "greet.py").write_text(GREET, encoding="utf-8")
    (repo / "app" / "twice.py").write_text("VALUE = 1\nVALUE = 1\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "start")
    return repo


def block(info: str, body: str) -> str:
    """Build one fenced block.

    Args:
        info: The info string after the opening fence.
        body: The block text, ending with a newline.

    Returns:
        The fenced block.
    """
    return f"{FENCE}{info}\n{body}{FENCE}\n\n"


def handoff(
    red: str = "grep -q hi app/greet.py",
    check: str = "grep -q hi greet.py",
    edit_info: str = "python edit=app/greet.py",
    edit_body: str = EDIT,
    new_info: str = "text new=app/notes.txt",
    commit: str = "text commit",
) -> str:
    """Build a handoff: a new file, a red command, an edit, a check, a commit.

    Args:
        red: The red command (must fail before the edit).
        check: The check command (runs in ``app``).
        edit_info: The info string of the edit block.
        edit_body: The text of the edit block.
        new_info: The info string of the new-file block.
        commit: The info string of the commit block.

    Returns:
        The handoff text.
    """
    return (
        "# MH-X: say hi\n\nSome text for people.\n\n"
        + block(new_info, "say hi\n")
        + block("bash red", red + "\n")
        + block(edit_info, edit_body)
        + block("bash check cwd=app", check + "\n")
        + block("mermaid", "graph LR\n    A --> B\n")
        + block(commit, "feat: say hi\n\nThe greeting is shorter.\n")
    )


def write_handoff(tmp_path: Path, text: str) -> Path:
    """Write a handoff file outside the repository.

    Args:
        tmp_path: The pytest temporary folder.
        text: The handoff text.

    Returns:
        The handoff path.
    """
    path = tmp_path / "mh-x.md"
    path.write_text(text, encoding="utf-8")
    return path


def commit_count(repo: Path) -> int:
    """Count the commits of a repository.

    Args:
        repo: The repository.

    Returns:
        The number of commits.
    """
    return int(git(repo, "rev-list", "--count", "HEAD").strip())


def assert_untouched(repo: Path) -> None:
    """Check that a run left the repository as it was.

    Args:
        repo: The repository.
    """
    assert (repo / "app" / "greet.py").read_text(encoding="utf-8") == GREET
    assert not (repo / "app" / "notes.txt").exists()
    assert commit_count(repo) == 1


def test_parse_reads_only_the_runner_blocks() -> None:
    """Blocks without a runner attribute are skipped; each action is read."""
    steps = runner.parse_handoff(handoff())

    assert [step.kind for step in steps] == ["new", "red", "edit", "check", "commit"]
    assert steps[0].path == "app/notes.txt"
    assert steps[0].text == "say hi\n"
    assert steps[1].text == "grep -q hi app/greet.py"
    assert steps[1].cwd == "."
    assert steps[2].old == 'MESSAGE = "hello"\n'
    assert steps[2].new == 'MESSAGE = "hi"\n'
    assert steps[3].cwd == "app"
    assert steps[4].text == "feat: say hi\n\nThe greeting is shorter."


def test_a_full_run_applies_the_handoff_and_commits(tmp_path: Path) -> None:
    """The red command fails, the check passes, and one commit has the two files."""
    repo = make_repo(tmp_path)

    code = runner.main([str(write_handoff(tmp_path, handoff())), "--repo", str(repo)])

    assert code == 0
    assert (repo / "app" / "greet.py").read_bytes() == b'MESSAGE = "hi"\n'
    assert (repo / "app" / "notes.txt").read_text(encoding="utf-8") == "say hi\n"
    assert commit_count(repo) == 2
    assert git(repo, "log", "-1", "--format=%B").strip() == (
        "feat: say hi\n\nThe greeting is shorter."
    )
    changed = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert sorted(changed) == ["app/greet.py", "app/notes.txt"]


def test_the_repository_of_the_handoff_is_found(tmp_path: Path) -> None:
    """Without --repo, the runner uses the repository that holds the handoff."""
    repo = make_repo(tmp_path)
    path = repo / "mh-x.md"
    path.write_text(handoff(), encoding="utf-8")

    assert runner.main([str(path)]) == 0
    assert commit_count(repo) == 2
    assert "mh-x.md" in git(repo, "status", "--short")


def test_a_dry_run_writes_nothing(tmp_path: Path) -> None:
    """--dry-run validates and prints the plan only."""
    repo = make_repo(tmp_path)

    code = runner.main(
        [str(write_handoff(tmp_path, handoff())), "--repo", str(repo), "--dry-run"]
    )

    assert code == 0
    assert_untouched(repo)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            handoff(edit_body=EDIT.replace('"hello"', '"nope"', 1)),
            "occurs 0 times",
        ),
        (
            handoff(
                edit_info="python edit=app/twice.py",
                edit_body="<<<<<<< OLD\nVALUE = 1\n=======\nVALUE = 2\n>>>>>>> NEW\n",
            ),
            "occurs 2 times",
        ),
        (handoff(edit_info="python edit=app/missing.py"), "does not exist"),
        (handoff(new_info="text new=app/greet.py"), "exists with other text"),
        (handoff(new_info="text new=../outside.txt"), "inside the repository"),
        (
            handoff(new_info="text new=apps/backend-py/data/x.json"),
            "never writes here",
        ),
        (handoff(new_info="text new=app/.env"), "never writes .env files"),
        (handoff(commit="text"), "exactly one commit block"),
        (handoff(edit_body="MESSAGE = 'hi'\n"), "one OLD/NEW pair"),
    ],
    ids=[
        "old text missing",
        "old text twice",
        "file missing",
        "new file exists",
        "outside the repository",
        "data folder",
        "env file",
        "no commit",
        "bad edit block",
    ],
)
def test_a_bad_handoff_stops_before_any_write(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    text: str,
    message: str,
) -> None:
    """Each validation problem stops the run with a clear message."""
    repo = make_repo(tmp_path)

    code = runner.main([str(write_handoff(tmp_path, text)), "--repo", str(repo)])

    assert code == 1
    assert message in capsys.readouterr().out
    assert_untouched(repo)


def test_a_failed_check_restores_every_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A check that fails restores the edited and the new file; no commit."""
    repo = make_repo(tmp_path)

    code = runner.main(
        [str(write_handoff(tmp_path, handoff(check="false"))), "--repo", str(repo)]
    )

    assert code == 1
    assert "nothing committed" in capsys.readouterr().out
    assert_untouched(repo)


def test_a_passing_red_command_restores_every_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A red command that passes means the test proves nothing; nothing stays."""
    repo = make_repo(tmp_path)

    code = runner.main(
        [str(write_handoff(tmp_path, handoff(red="true"))), "--repo", str(repo)]
    )

    assert code == 1
    assert "must fail" in capsys.readouterr().out
    assert_untouched(repo)


def test_staged_files_stop_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The runner does not mix its commit with files that are already staged."""
    repo = make_repo(tmp_path)
    (repo / "other.txt").write_text("mine\n", encoding="utf-8")
    git(repo, "add", "other.txt")

    code = runner.main([str(write_handoff(tmp_path, handoff())), "--repo", str(repo)])

    assert code == 1
    assert "staged" in capsys.readouterr().out
    assert_untouched(repo)


def test_other_changes_in_a_file_to_edit_stop_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file to edit with other changes is left as the user has it."""
    repo = make_repo(tmp_path)
    changed = GREET + "EXTRA = 1\n"
    (repo / "app" / "greet.py").write_text(changed, encoding="utf-8")

    code = runner.main([str(write_handoff(tmp_path, handoff())), "--repo", str(repo)])

    assert code == 1
    assert "has other changes" in capsys.readouterr().out
    assert (repo / "app" / "greet.py").read_text(encoding="utf-8") == changed
    assert not (repo / "app" / "notes.txt").exists()


def test_a_new_file_with_the_same_text_is_kept(tmp_path: Path) -> None:
    """A new file that already has the handoff text (an earlier try) is committed."""
    repo = make_repo(tmp_path)
    (repo / "app" / "notes.txt").write_text("say hi\n", encoding="utf-8")

    code = runner.main([str(write_handoff(tmp_path, handoff())), "--repo", str(repo)])

    assert code == 0
    changed: List[str] = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert "app/notes.txt" in changed


def test_a_file_with_crlf_line_ends_is_edited_and_written_with_lf(
    tmp_path: Path,
) -> None:
    """Line-end-only changes do not stop the run, and the edit writes LF."""
    repo = make_repo(tmp_path)
    (repo / "app" / "greet.py").write_bytes(GREET.replace("\n", "\r\n").encode())

    code = runner.main([str(write_handoff(tmp_path, handoff())), "--repo", str(repo)])

    assert code == 0
    assert (repo / "app" / "greet.py").read_bytes() == b'MESSAGE = "hi"\n'
