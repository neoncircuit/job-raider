"""
Tests for the llmfit client (Step 6, MH-2).

A small fake ``llmfit`` script answers like the real binary, so the tests run
the real subprocess path without llmfit installed. The fixtures use made-up
hardware values.
"""

import json
import stat
import sys
from pathlib import Path
from typing import List

import pytest

from src.hardware import llmfit_client
from src.hardware.llmfit_client import (
    LLAMA_CPP_RUNTIME,
    LlmfitClient,
    LlmfitUnavailable,
    find_llmfit,
    parse_plan,
    parse_version,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "llmfit"

FAKE_LLMFIT = """\
import json, os, sys, time
from pathlib import Path

args = sys.argv[1:]
Path(os.environ["FAKE_LLMFIT_ARGV"]).write_text(json.dumps(args))
mode = os.environ.get("FAKE_LLMFIT_MODE", "ok")
fixtures = Path(os.environ["FAKE_LLMFIT_FIXTURES"])
if mode == "fail":
    sys.exit(2)
if mode == "slow":
    time.sleep(5)
if args == ["-V"]:
    print({"ok": "llmfit 1.1.20", "old": "llmfit 1.1.6"}.get(mode, "no version"))
    sys.exit(0)
if mode == "notjson":
    print("not json")
    sys.exit(0)
for name in ("system", "fit", "plan"):
    if name in args:
        print((fixtures / f"{name}.json").read_text())
        sys.exit(0)
sys.exit(2)
"""


@pytest.fixture
def fake_llmfit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Write a fake llmfit binary and point the fake at the fixtures.

    Args:
        tmp_path: Temporary folder for this test.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        Path of the fake binary.
    """
    binary = tmp_path / "bin" / "llmfit"
    binary.parent.mkdir()
    binary.write_text(f"#!{sys.executable}\n{FAKE_LLMFIT}")
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("FAKE_LLMFIT_ARGV", str(tmp_path / "argv.json"))
    monkeypatch.setenv("FAKE_LLMFIT_FIXTURES", str(FIXTURES))
    monkeypatch.setenv("FAKE_LLMFIT_MODE", "ok")
    return binary


def last_argv(tmp_path: Path) -> List[str]:
    """
    Read the arguments of the last fake llmfit run.

    Args:
        tmp_path: Temporary folder of the test.

    Returns:
        The arguments after the binary name.
    """
    return json.loads((tmp_path / "argv.json").read_text())


class TestFindLlmfit:
    """Finding the binary."""

    def test_uses_the_configured_path(
        self, fake_llmfit: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLMFIT_PATH wins when it names a file."""
        monkeypatch.setenv("LLMFIT_PATH", str(fake_llmfit))
        assert find_llmfit() == str(fake_llmfit)

    def test_a_configured_path_that_is_missing_gives_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A wrong LLMFIT_PATH does not fall back to another binary."""
        monkeypatch.setenv("LLMFIT_PATH", str(tmp_path / "missing"))
        assert find_llmfit() is None

    def test_prefers_the_binary_beside_python(
        self, fake_llmfit: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The backend .venv bin folder comes before PATH."""
        monkeypatch.delenv("LLMFIT_PATH", raising=False)
        monkeypatch.setattr(
            llmfit_client.sys, "executable", str(fake_llmfit.parent / "python")
        )
        monkeypatch.setattr(llmfit_client.shutil, "which", lambda _: "/elsewhere")
        assert find_llmfit() == str(fake_llmfit)

    def test_falls_back_to_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without a configured path or a .venv binary, PATH is used."""
        monkeypatch.delenv("LLMFIT_PATH", raising=False)
        monkeypatch.setattr(llmfit_client.sys, "executable", str(tmp_path / "python"))
        monkeypatch.setattr(llmfit_client.shutil, "which", lambda _: "/usr/bin/llmfit")
        assert find_llmfit() == "/usr/bin/llmfit"


class TestRun:
    """Running the binary safely."""

    def test_missing_binary_is_unavailable(self) -> None:
        """No binary gives a clear reason, not a crash."""
        client = LlmfitClient(binary="")
        with pytest.raises(LlmfitUnavailable, match="not installed"):
            client.system()

    def test_non_zero_exit_is_unavailable(
        self, fake_llmfit: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed run gives the exit code."""
        monkeypatch.setenv("FAKE_LLMFIT_MODE", "fail")
        with pytest.raises(LlmfitUnavailable, match="exited with code 2"):
            LlmfitClient(binary=str(fake_llmfit)).system()

    def test_output_that_is_not_json_is_unavailable(
        self, fake_llmfit: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Text output gives "not JSON"."""
        monkeypatch.setenv("FAKE_LLMFIT_MODE", "notjson")
        with pytest.raises(LlmfitUnavailable, match="not JSON"):
            LlmfitClient(binary=str(fake_llmfit)).system()

    def test_a_slow_run_is_stopped(
        self, fake_llmfit: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The timeout stops a run that hangs."""
        monkeypatch.setenv("FAKE_LLMFIT_MODE", "slow")
        with pytest.raises(LlmfitUnavailable, match="did not answer"):
            LlmfitClient(binary=str(fake_llmfit), timeout=0.5).system()

    def test_only_read_only_subcommands_run(self, fake_llmfit: Path) -> None:
        """A subcommand outside the allow list never starts the binary."""
        client = LlmfitClient(binary=str(fake_llmfit))
        with pytest.raises(LlmfitUnavailable, match="not allowed"):
            client._run_json([], ["serve"])


class TestVersion:
    """The version check."""

    def test_parse_version(self) -> None:
        """The first x.y.z in the text is the version."""
        assert parse_version("llmfit 1.1.20") == (1, 1, 20)
        assert parse_version("llmfit") is None

    def test_a_new_enough_version_passes(self, fake_llmfit: Path) -> None:
        """1.1.20 is the minimum."""
        assert LlmfitClient(binary=str(fake_llmfit)).version() == (1, 1, 20)

    def test_an_old_version_asks_for_an_update(
        self, fake_llmfit: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """1.1.6 (the version found in /usr/local/bin) is too old."""
        monkeypatch.setenv("FAKE_LLMFIT_MODE", "old")
        with pytest.raises(LlmfitUnavailable, match="update recommended"):
            LlmfitClient(binary=str(fake_llmfit)).version()

    def test_no_version_is_unavailable(
        self, fake_llmfit: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Output without a version number is not trusted."""
        monkeypatch.setenv("FAKE_LLMFIT_MODE", "garbage")
        with pytest.raises(LlmfitUnavailable, match="did not report a version"):
            LlmfitClient(binary=str(fake_llmfit)).version()


class TestParse:
    """Parsing the JSON output."""

    def test_system(self, fake_llmfit: Path, tmp_path: Path) -> None:
        """The system block parses, and --json comes first."""
        profile = LlmfitClient(binary=str(fake_llmfit)).system()
        assert profile.gpu_name == "Example GPU"
        assert profile.gpu_vram_gb == 12.0
        assert profile.has_gpu is True
        assert profile.total_ram_gb == 32.0
        assert last_argv(tmp_path) == ["--json", "system"]

    def test_catalog_keeps_llama_cpp_rows_and_skips_bad_rows(
        self, fake_llmfit: Path
    ) -> None:
        """vLLM rows and rows without a memory need are left out."""
        rows = LlmfitClient(binary=str(fake_llmfit)).catalog()
        assert [r.name for r in rows] == [
            "example/Chat-7B-Instruct",
            "example/Coder-3B",
            "example/Big-14B",
            "example/Embed-Large",
        ]
        assert all(r.runtime == LLAMA_CPP_RUNTIME for r in rows)

    def test_catalog_passes_the_budget_before_the_subcommand(
        self, fake_llmfit: Path, tmp_path: Path
    ) -> None:
        """--memory is a global flag, so it comes before fit."""
        LlmfitClient(binary=str(fake_llmfit)).catalog(memory_gb=9.0)
        assert last_argv(tmp_path) == [
            "--json",
            "--memory",
            "9.00G",
            "fit",
            "-n",
            "100000",
        ]

    def test_plan_reads_the_gpu_path(self, fake_llmfit: Path, tmp_path: Path) -> None:
        """The plan gives the GPU minimum for the installed quantization."""
        plan = LlmfitClient(binary=str(fake_llmfit)).plan(
            "example/Chat-7B-Instruct", "Q4_K_M", 8192
        )
        assert plan.quantization == "Q4_K_M"
        assert plan.min_vram_gb == 5.35
        assert plan.recommended_vram_gb == 7.1
        assert last_argv(tmp_path) == [
            "--json",
            "plan",
            "example/Chat-7B-Instruct",
            "--quant",
            "Q4_K_M",
            "--context",
            "8192",
        ]

    def test_plan_without_a_gpu_path_is_unavailable(self) -> None:
        """A plan with only CPU paths gives no VRAM need."""
        data = json.loads((FIXTURES / "plan.json").read_text())
        data["run_paths"] = [p for p in data["run_paths"] if p["path"] != "gpu"]
        with pytest.raises(LlmfitUnavailable, match="no GPU path"):
            parse_plan(data)
