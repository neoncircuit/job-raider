"""
Job Raider - llmfit Client

llmfit (https://github.com/AlexsJones/llmfit, MIT) detects the CPU, RAM, and
GPU, and estimates the memory that each model needs. It is optional: when the
binary is missing, too old, slow, or gives bad output, every call here raises
``LlmfitUnavailable`` and the caller shows "not available".

The client runs only read-only subcommands (``system``, ``fit``, ``plan``),
with no shell and with a timeout. It parses only the fields that Job Raider
uses, so new fields in a later llmfit version do not break it.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

LLMFIT_MIN_VERSION: Tuple[int, int, int] = (1, 1, 20)
"""Oldest llmfit version whose JSON fields this client was checked against."""

LLMFIT_PATH_ENV = "LLMFIT_PATH"
"""Environment variable that can name the llmfit binary."""

READ_ONLY_SUBCOMMANDS = frozenset({"system", "fit", "plan"})
"""The only subcommands the client runs. None of them downloads or writes."""

DEFAULT_TIMEOUT_SECONDS = 20.0
"""``fit`` over the full catalog took 2.4 to 2.8 s in the MH-1 measure."""

LLAMA_CPP_RUNTIME = "llama.cpp"
"""llmfit runtime that matches Ollama, which runs GGUF files."""

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


class LlmfitUnavailable(Exception):
    """llmfit cannot give an answer. The message says why, for the UI."""


class _Lenient(BaseModel):
    """Base model that ignores fields this client does not use."""

    model_config = ConfigDict(extra="ignore")


class HardwareProfile(_Lenient):
    """Hardware that llmfit detected (``llmfit --json system``)."""

    has_gpu: bool = False
    gpu_name: Optional[str] = None
    gpu_vram_gb: Optional[float] = None
    backend: Optional[str] = None
    total_ram_gb: float = 0.0
    available_ram_gb: Optional[float] = None
    cpu_name: Optional[str] = None
    cpu_cores: Optional[int] = None


class CatalogModel(_Lenient):
    """One model row of ``llmfit --json fit``."""

    name: str
    ollama_name: Optional[str] = None
    runtime: str = ""
    best_quant: str = ""
    fit_level: str = ""
    memory_required_gb: float
    utilization_pct: Optional[float] = None
    estimated_tps: Optional[float] = None
    score: float = 0.0
    params_b: Optional[float] = None
    category: Optional[str] = None
    use_case: Optional[str] = None
    license: Optional[str] = None
    installed: bool = False


class QuantPlan(_Lenient):
    """Memory need of one model at one quantization (``llmfit plan``)."""

    model_name: str
    quantization: str
    context: int
    disk_size_gb: Optional[float] = None
    min_vram_gb: float = Field(description="Minimum VRAM for the GPU path")
    recommended_vram_gb: Optional[float] = None


def parse_version(text: str) -> Optional[Tuple[int, int, int]]:
    """
    Read a version number from ``llmfit -V`` output.

    Args:
        text: Output such as ``"llmfit 1.1.20"``.

    Returns:
        The version as a tuple of three ints, or None if there is none.
    """
    match = _VERSION_RE.search(text)
    if not match:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return (major, minor, patch)


def find_llmfit() -> Optional[str]:
    """
    Find the llmfit binary.

    The order is: the ``LLMFIT_PATH`` variable, the bin folder of the running
    Python (the backend ``.venv``, where ``setup.sh`` installs it), and PATH.

    Returns:
        The path of the binary, or None if llmfit is not installed.
    """
    configured = os.environ.get(LLMFIT_PATH_ENV)
    if configured:
        return configured if Path(configured).is_file() else None
    beside_python = Path(sys.executable).parent / "llmfit"
    if beside_python.is_file():
        return str(beside_python)
    return shutil.which("llmfit")


class LlmfitClient:
    """Run llmfit and parse its JSON output."""

    def __init__(
        self,
        binary: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        """
        Initialize the client.

        Args:
            binary: Path of the llmfit binary. None means ``find_llmfit()``.
            timeout: Seconds before a call is stopped.
        """
        self.binary = binary if binary is not None else find_llmfit()
        self.timeout = timeout

    def _run(self, args: Sequence[str]) -> str:
        """
        Run llmfit with the given arguments and return its standard output.

        Args:
            args: Arguments after the binary name.

        Returns:
            Standard output of a successful run.

        Raises:
            LlmfitUnavailable: llmfit is missing, fails, or is too slow.
        """
        if not self.binary:
            raise LlmfitUnavailable("llmfit is not installed")
        try:
            completed = subprocess.run(
                [self.binary, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise LlmfitUnavailable(
                f"llmfit did not answer within {self.timeout:g} s"
            ) from exc
        except OSError as exc:
            raise LlmfitUnavailable(f"llmfit could not start: {exc}") from exc
        if completed.returncode != 0:
            raise LlmfitUnavailable(f"llmfit exited with code {completed.returncode}")
        return completed.stdout

    def _run_json(self, global_args: Sequence[str], subcommand: Sequence[str]) -> Any:
        """
        Run one read-only subcommand with ``--json`` and parse the output.

        Args:
            global_args: Flags that go before the subcommand (such as
                ``["--memory", "6G"]``).
            subcommand: The subcommand and its own arguments.

        Returns:
            The parsed JSON value.

        Raises:
            LlmfitUnavailable: The subcommand is not allowed, llmfit fails,
                or the output is not JSON.
        """
        if not subcommand or subcommand[0] not in READ_ONLY_SUBCOMMANDS:
            raise LlmfitUnavailable(f"subcommand not allowed: {list(subcommand)}")
        output = self._run(["--json", *global_args, *subcommand])
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise LlmfitUnavailable("llmfit gave output that is not JSON") from exc

    def version(self) -> Tuple[int, int, int]:
        """
        Get the llmfit version, and check that it is new enough.

        Returns:
            The version tuple.

        Raises:
            LlmfitUnavailable: llmfit is missing, has no version, or is older
                than ``LLMFIT_MIN_VERSION``.
        """
        found = parse_version(self._run(["-V"]))
        if found is None:
            raise LlmfitUnavailable("llmfit did not report a version")
        if found < LLMFIT_MIN_VERSION:
            wanted = ".".join(str(part) for part in LLMFIT_MIN_VERSION)
            have = ".".join(str(part) for part in found)
            raise LlmfitUnavailable(
                f"llmfit {have} is older than {wanted}; update recommended"
            )
        return found

    def system(self) -> HardwareProfile:
        """
        Read the hardware.

        Returns:
            The detected hardware.

        Raises:
            LlmfitUnavailable: llmfit fails or the output has no system block.
        """
        data = self._run_json([], ["system"])
        try:
            return HardwareProfile.model_validate(data["system"])
        except (KeyError, TypeError, ValidationError) as exc:
            raise LlmfitUnavailable("llmfit system output has no system block") from exc

    def catalog(self, memory_gb: Optional[float] = None) -> List[CatalogModel]:
        """
        Score the whole catalog, keeping only llama.cpp rows (Ollama's format).

        Args:
            memory_gb: GPU memory to score against. None means the detected
                VRAM. Job Raider passes its safety budget here, so llmfit picks
                a quantization that fits the budget.

        Returns:
            The llama.cpp rows. Rows that do not parse are skipped.

        Raises:
            LlmfitUnavailable: llmfit fails or the output has no model list.
        """
        global_args: List[str] = []
        if memory_gb is not None:
            global_args = ["--memory", f"{memory_gb:.2f}G"]
        data = self._run_json(global_args, ["fit", "-n", "100000"])
        rows = data.get("models") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise LlmfitUnavailable("llmfit fit output has no model list")
        models: List[CatalogModel] = []
        for row in rows:
            try:
                model = CatalogModel.model_validate(row)
            except ValidationError:
                continue
            if model.runtime == LLAMA_CPP_RUNTIME:
                models.append(model)
        return models

    def plan(self, model_name: str, quantization: str, context: int) -> QuantPlan:
        """
        Get the memory need of one model at one quantization.

        Args:
            model_name: llmfit catalog name (such as ``Qwen/Qwen2.5-7B-Instruct``).
            quantization: Quantization of the installed file (such as ``Q4_K_M``).
            context: Context length in tokens.

        Returns:
            The plan for the GPU path.

        Raises:
            LlmfitUnavailable: llmfit fails or the output has no GPU path.
        """
        data = self._run_json(
            [],
            [
                "plan",
                model_name,
                "--quant",
                quantization,
                "--context",
                str(context),
            ],
        )
        return parse_plan(data)


def parse_plan(data: Dict[str, Any]) -> QuantPlan:
    """
    Read the GPU path of ``llmfit plan`` JSON.

    Args:
        data: Parsed ``plan`` output.

    Returns:
        The plan with the GPU minimum and recommended VRAM.

    Raises:
        LlmfitUnavailable: The output has no GPU path.
    """
    try:
        gpu = next(p for p in data["run_paths"] if p.get("path") == "gpu")
        return QuantPlan(
            model_name=data["model_name"],
            quantization=data["quantization"],
            context=int(data["context"]),
            disk_size_gb=data.get("disk_size_gb"),
            min_vram_gb=float(gpu["minimum"]["vram_gb"]),
            recommended_vram_gb=(gpu.get("recommended") or {}).get("vram_gb"),
        )
    except (KeyError, StopIteration, TypeError, ValueError) as exc:
        raise LlmfitUnavailable("llmfit plan output has no GPU path") from exc
