"""
Job Raider - Hardware Fit Service

This module joins the llmfit client, the fit rules, and the installed Ollama
models into one report for the Settings page, and checks a pull against the
safety budget. llmfit is slow (about 0.8 s per ``plan`` and 2.5 s per catalog
run), so the service caches the hardware and the catalog for each headroom
value, and caches each plan per model and quantization.
"""

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from ..api.ollama_admin import MAX_PARAMS_BILLION
from .fit import (
    FitLabel,
    FitSource,
    InstalledFit,
    Suggestion,
    catalog_by_ollama_name,
    label_for,
    label_installed,
    ollama_key,
    suggest_models,
    vram_budget_gb,
)
from .llmfit_client import (
    LLMFIT_MIN_VERSION,
    CatalogModel,
    HardwareProfile,
    LlmfitClient,
    LlmfitUnavailable,
)

CACHE_SECONDS = 600.0
"""How long the hardware and the catalog stay cached."""

PLAN_CONTEXT_TOKENS = 8192
"""Context length for each plan. The MH-1 measure used the same value."""

DEFAULT_PULL_QUANT = "Q4_K_M"
"""Quantization of most default Ollama tags, used when a tag names none."""

PLAN_WORKERS = 4
"""Plans that run at the same time. llmfit loads no model, so the load is small."""

INSTALL_HINT = (
    "llmfit is optional and recommended. Run ./setup.sh, or install it into the "
    "backend environment: apps/backend-py/.venv/bin/pip install "
    "llmfit==" + ".".join(str(part) for part in LLMFIT_MIN_VERSION)
)

_TAG_QUANT_RE = re.compile(r"(iq\d_[a-z0-9_]+|q\d_[a-z0-9_]+|f16|fp16|bf16)")


class HardwareFitReport(BaseModel):
    """Hardware fit for the Settings page."""

    available: bool
    reason: Optional[str] = None
    install_hint: Optional[str] = None
    llmfit_version: Optional[str] = None
    hardware: Optional[HardwareProfile] = None
    headroom_percent: int
    budget_gb: float = 0.0
    ollama_reachable: bool = True
    installed: List[InstalledFit] = Field(default_factory=list)
    suggestions: List[Suggestion] = Field(default_factory=list)


class PullCheck(BaseModel):
    """Fit of a model that the user wants to pull."""

    tag: str
    quantization: str
    label: FitLabel
    need_gb: Optional[float] = None
    budget_gb: float
    total_vram_gb: Optional[float] = None
    headroom_percent: int
    source: FitSource


@dataclass
class _Snapshot:
    """Cached llmfit results for one headroom value."""

    version: str
    hardware: HardwareProfile
    budget_gb: float
    catalog: List[CatalogModel]
    index: Dict[str, CatalogModel]
    created: float


def quant_from_tag(tag: str) -> str:
    """
    Read the quantization from an Ollama tag, such as ``llama3.1:8b-q8_0``.

    Args:
        tag: Ollama tag.

    Returns:
        The quantization in upper case, or ``DEFAULT_PULL_QUANT`` if the tag
        names none.
    """
    match = _TAG_QUANT_RE.search(tag.lower())
    if not match:
        return DEFAULT_PULL_QUANT
    found = match.group(1).upper()
    return "F16" if found == "FP16" else found


class HardwareFitService:
    """Build hardware fit reports with caching."""

    def __init__(
        self,
        client_factory: Callable[[], LlmfitClient] = LlmfitClient,
        max_params_billion: float = MAX_PARAMS_BILLION,
        cache_seconds: float = CACHE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        """
        Initialize the service.

        Args:
            client_factory: Makes an llmfit client. Tests pass a stub.
            max_params_billion: The pull limit; larger models are not suggested.
            cache_seconds: How long the hardware and the catalog stay cached.
            clock: Monotonic clock in seconds. Tests pass a fake clock.
        """
        self._client_factory = client_factory
        self._max_params_billion = max_params_billion
        self._cache_seconds = cache_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._snapshots: Dict[int, _Snapshot] = {}
        self._plans: Dict[Tuple[str, str], Optional[float]] = {}

    def _snapshot(
        self, client: LlmfitClient, headroom_percent: int, refresh: bool
    ) -> _Snapshot:
        """
        Get the hardware and the catalog for one headroom value.

        Args:
            client: llmfit client.
            headroom_percent: Share of the VRAM that a model may use.
            refresh: True to ignore the cache (also clears cached plans).

        Returns:
            The cached or new snapshot.

        Raises:
            LlmfitUnavailable: llmfit cannot answer.
        """
        with self._lock:
            if refresh:
                self._snapshots.clear()
                self._plans.clear()
            cached = self._snapshots.get(headroom_percent)
            if cached and self._clock() - cached.created < self._cache_seconds:
                return cached
        version = ".".join(str(part) for part in client.version())
        hardware = client.system()
        budget = vram_budget_gb(hardware.gpu_vram_gb, headroom_percent)
        catalog = client.catalog(memory_gb=budget if budget > 0 else None)
        snapshot = _Snapshot(
            version=version,
            hardware=hardware,
            budget_gb=budget,
            catalog=catalog,
            index=catalog_by_ollama_name(catalog),
            created=self._clock(),
        )
        with self._lock:
            self._snapshots[headroom_percent] = snapshot
        return snapshot

    def _plan_need(
        self, client: LlmfitClient, model_name: str, quantization: str
    ) -> Optional[float]:
        """
        Get the minimum VRAM of one model at one quantization, with a cache.

        Args:
            client: llmfit client.
            model_name: llmfit catalog name.
            quantization: Quantization of the file.

        Returns:
            Minimum VRAM in GB, or None when llmfit has no plan for it.
        """
        key = (model_name, quantization.upper())
        with self._lock:
            if key in self._plans:
                return self._plans[key]
        try:
            need: Optional[float] = client.plan(
                model_name, key[1], PLAN_CONTEXT_TOKENS
            ).min_vram_gb
        except LlmfitUnavailable:
            need = None
        with self._lock:
            self._plans[key] = need
        return need

    def report(
        self,
        headroom_percent: int,
        installed_models: Sequence[Mapping[str, Any]],
        ollama_reachable: bool,
        refresh: bool = False,
    ) -> HardwareFitReport:
        """
        Build the hardware fit report.

        Args:
            headroom_percent: Share of the VRAM that a model may use.
            installed_models: Models from ``ollama_admin.list_models`` (``name``,
                ``size``, ``quantization``).
            ollama_reachable: False when Ollama did not answer.
            refresh: True to run llmfit again instead of using the cache.

        Returns:
            The report. ``available`` is False, with a reason and an install
            hint, when llmfit cannot answer.
        """
        client = self._client_factory()
        try:
            snap = self._snapshot(client, headroom_percent, refresh)
        except LlmfitUnavailable as exc:
            return HardwareFitReport(
                available=False,
                reason=str(exc),
                install_hint=INSTALL_HINT,
                headroom_percent=headroom_percent,
                ollama_reachable=ollama_reachable,
            )

        def need_for(model: Mapping[str, Any]) -> Optional[float]:
            """Plan the installed quantization of a model that maps to llmfit."""
            row = snap.index.get(ollama_key(str(model["name"])))
            quant = model.get("quantization")
            if row is None or not quant:
                return None
            return self._plan_need(client, row.name, str(quant))

        with ThreadPoolExecutor(max_workers=PLAN_WORKERS) as pool:
            needs = list(pool.map(need_for, installed_models))

        total = snap.hardware.gpu_vram_gb
        installed = [
            label_installed(
                str(model["name"]),
                model.get("quantization"),
                model.get("size"),
                need,
                snap.budget_gb,
                total,
            )
            for model, need in zip(installed_models, needs)
        ]
        suggestions = suggest_models(
            snap.catalog,
            snap.budget_gb,
            [str(model["name"]) for model in installed_models],
            self._max_params_billion,
        )
        return HardwareFitReport(
            available=True,
            llmfit_version=snap.version,
            hardware=snap.hardware,
            headroom_percent=headroom_percent,
            budget_gb=snap.budget_gb,
            ollama_reachable=ollama_reachable,
            installed=installed,
            suggestions=suggestions,
        )

    def check_pull(self, tag: str, headroom_percent: int) -> Optional[PullCheck]:
        """
        Check a model that the user wants to pull against the budget.

        Args:
            tag: Ollama tag to pull.
            headroom_percent: Share of the VRAM that a model may use.

        Returns:
            The check, or None when llmfit cannot answer or does not know the
            tag. None means "no warning": the pull goes on as before.
        """
        client = self._client_factory()
        try:
            snap = self._snapshot(client, headroom_percent, refresh=False)
        except LlmfitUnavailable:
            return None
        row = snap.index.get(ollama_key(tag))
        if row is None:
            return None
        quant = quant_from_tag(tag)
        need = self._plan_need(client, row.name, quant)
        total = snap.hardware.gpu_vram_gb
        return PullCheck(
            tag=tag,
            quantization=quant,
            label=label_for(need, snap.budget_gb, total),
            need_gb=None if need is None else round(need, 2),
            budget_gb=snap.budget_gb,
            total_vram_gb=total,
            headroom_percent=headroom_percent,
            source=FitSource.LLMFIT_PLAN if need is not None else FitSource.NONE,
        )


_service: Optional[HardwareFitService] = None
_service_lock = threading.Lock()


def get_fit_service() -> HardwareFitService:
    """
    Get the process-wide service, so the cache is shared by all requests.

    Returns:
        The service.
    """
    global _service
    with _service_lock:
        if _service is None:
            _service = HardwareFitService()
        return _service
