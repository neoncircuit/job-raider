"""
Job Raider - Hardware Fit Rules

These pure functions decide whether a local model fits the user's safety
budget of GPU memory. llmfit gives the hardware and its estimates; the label
comes from Job Raider's own budget, because llmfit can call a model a good fit
when it fills almost all of the VRAM, and heavy GPU load has caused crashes.

Labels:

- ``fits``: the need is within the budget.
- ``over_budget``: the need is above the budget but within the total VRAM. The
  model can run, but it leaves less headroom than the user asked for.
- ``too_large``: the need is above the total VRAM.
- ``unknown``: there is no GPU or no estimate.
"""

import re
from enum import Enum
from typing import Dict, Iterable, List, Optional

from pydantic import BaseModel

from .llmfit_client import CatalogModel

DEFAULT_VRAM_HEADROOM_PERCENT = 75
"""Default share of the total VRAM that a model may use (user decision)."""

ROUGH_ALLOWANCE_GB = 1.0
"""Context and runtime memory added to a file size for a rough estimate.

A plan below the file size itself is not used: Ollama loads the whole
file, so such a plan is replaced with this rough estimate.

MH-1 measure: the Q4_K_M ``qwen2.5-coder:7b`` file is 4.42 GB in llmfit's
estimate, and its minimum VRAM at an 8,192-token context is 5.35 GB.
"""

BYTES_PER_GB = 1024**3
"""GB in this module means 1024**3 bytes (GiB), the unit of the VRAM that
nvidia-smi and llmfit report (8192 MiB is 8.0) and of the Size column in
Settings, so a file size and a budget compare in one unit."""

_LOW_QUANT_RE = re.compile(r"^(Q[23]_|IQ[123]_)", re.IGNORECASE)
_EMBEDDING_CATEGORY = "embedding"


class FitLabel(str, Enum):
    """Fit of one model against the safety budget."""

    FITS = "fits"
    OVER_BUDGET = "over_budget"
    TOO_LARGE = "too_large"
    UNKNOWN = "unknown"


class FitSource(str, Enum):
    """Where the memory need of a model comes from."""

    LLMFIT_PLAN = "llmfit_plan"
    ROUGH_ESTIMATE = "rough_estimate"
    NONE = "none"


class InstalledFit(BaseModel):
    """Fit result for one installed Ollama model."""

    name: str
    quantization: Optional[str] = None
    need_gb: Optional[float] = None
    label: FitLabel
    source: FitSource


class Suggestion(BaseModel):
    """A model that is not installed and fits the budget."""

    ollama_name: str
    category: Optional[str] = None
    params_b: Optional[float] = None
    memory_required_gb: float
    estimated_tps: Optional[float] = None
    score: float
    license: Optional[str] = None


def vram_budget_gb(total_vram_gb: Optional[float], headroom_percent: int) -> float:
    """
    Compute the safety budget of GPU memory.

    Args:
        total_vram_gb: Total VRAM from llmfit, or None when there is no GPU.
        headroom_percent: Share of the VRAM that a model may use, 1 to 100.

    Returns:
        The budget in GB, or 0.0 when there is no GPU.
    """
    if not total_vram_gb or total_vram_gb <= 0:
        return 0.0
    return round(total_vram_gb * headroom_percent / 100.0, 2)


def label_for(
    need_gb: Optional[float], budget_gb: float, total_vram_gb: Optional[float]
) -> FitLabel:
    """
    Label a memory need against the budget and the total VRAM.

    Args:
        need_gb: Memory the model needs, or None when it is not known.
        budget_gb: Safety budget from ``vram_budget_gb``.
        total_vram_gb: Total VRAM, or None when there is no GPU.

    Returns:
        The fit label.
    """
    if need_gb is None or not total_vram_gb or budget_gb <= 0:
        return FitLabel.UNKNOWN
    if need_gb <= budget_gb:
        return FitLabel.FITS
    if need_gb <= total_vram_gb:
        return FitLabel.OVER_BUDGET
    return FitLabel.TOO_LARGE


def rough_need_gb(size_bytes: Optional[int]) -> Optional[float]:
    """
    Estimate the memory need from the size of the model file.

    Args:
        size_bytes: File size that Ollama reports, or None.

    Returns:
        File size plus ``ROUGH_ALLOWANCE_GB``, in GB, or None without a size.
    """
    if not size_bytes or size_bytes <= 0:
        return None
    return round(size_bytes / BYTES_PER_GB + ROUGH_ALLOWANCE_GB, 2)


def label_installed(
    tag: str,
    quantization: Optional[str],
    size_bytes: Optional[int],
    plan_need_gb: Optional[float],
    budget_gb: float,
    total_vram_gb: Optional[float],
) -> InstalledFit:
    """
    Label one installed Ollama model.

    The llmfit plan for the installed quantization is used when there is one,
    unless it is below the file size itself: a plan can assume that part of
    the weights stays off the GPU, but Ollama loads the whole file. Otherwise
    the label uses a rough estimate: the file size plus ``ROUGH_ALLOWANCE_GB``.

    Args:
        tag: Ollama tag.
        quantization: Quantization of the installed file, from Ollama.
        size_bytes: File size from Ollama.
        plan_need_gb: Minimum VRAM from ``llmfit plan``, or None.
        budget_gb: Safety budget in GB.
        total_vram_gb: Total VRAM, or None when there is no GPU.

    Returns:
        The fit result with its source.
    """
    file_gb = size_bytes / BYTES_PER_GB if size_bytes and size_bytes > 0 else None
    if plan_need_gb is not None and (file_gb is None or plan_need_gb >= file_gb):
        need: Optional[float] = round(plan_need_gb, 2)
        source = FitSource.LLMFIT_PLAN
    else:
        need = rough_need_gb(size_bytes)
        source = FitSource.ROUGH_ESTIMATE if need is not None else FitSource.NONE
    return InstalledFit(
        name=tag,
        quantization=quantization,
        need_gb=need,
        label=label_for(need, budget_gb, total_vram_gb),
        source=source,
    )


def ollama_key(tag: str) -> str:
    """
    Normalize an Ollama tag for a match with llmfit's ``ollama_name``.

    Args:
        tag: Ollama tag such as ``mistral:latest``.

    Returns:
        The tag without a ``:latest`` suffix, in lower case.
    """
    key = tag.strip().lower()
    return key[: -len(":latest")] if key.endswith(":latest") else key


def catalog_by_ollama_name(catalog: Iterable[CatalogModel]) -> Dict[str, CatalogModel]:
    """
    Index catalog rows by their Ollama name, keeping the best score per name.

    Args:
        catalog: llama.cpp rows from ``LlmfitClient.catalog``.

    Returns:
        Map from the normalized Ollama name to the row.
    """
    index: Dict[str, CatalogModel] = {}
    for row in catalog:
        if not row.ollama_name:
            continue
        key = ollama_key(row.ollama_name)
        if key not in index or row.score > index[key].score:
            index[key] = row
    return index


def is_low_quant(quantization: str) -> bool:
    """
    Tell whether a quantization is below 4 bits.

    ``ollama pull`` gets the default tag, usually Q4_K_M. A row that fits the
    budget only at Q2 or Q3 says nothing about the default tag, so it is not
    a suggestion.

    Args:
        quantization: llmfit ``best_quant`` such as ``Q3_K_M``.

    Returns:
        True for Q2, Q3, and IQ1 to IQ3 quantizations.
    """
    return bool(_LOW_QUANT_RE.match(quantization.strip()))


def suggest_models(
    catalog: Iterable[CatalogModel],
    budget_gb: float,
    installed_tags: Iterable[str],
    max_params_billion: float,
    limit: int = 8,
) -> List[Suggestion]:
    """
    Pick models that are not installed and fit the budget.

    Call this with a catalog that llmfit scored against the budget
    (``LlmfitClient.catalog(memory_gb=budget)``).

    Args:
        catalog: llama.cpp rows from llmfit.
        budget_gb: Safety budget in GB.
        installed_tags: Ollama tags that are installed now.
        max_params_billion: The pull limit. Larger models are not suggested.
        limit: Maximum number of suggestions.

    Returns:
        Suggestions sorted by llmfit score, best first. Embedding models are
        left out, because the embedding model is a separate setting.
    """
    installed = {ollama_key(tag) for tag in installed_tags}
    picks: List[Suggestion] = []
    for key, row in sorted(
        catalog_by_ollama_name(catalog).items(), key=lambda item: -item[1].score
    ):
        if key in installed or row.installed:
            continue
        if (row.category or "").lower() == _EMBEDDING_CATEGORY:
            continue
        if row.params_b is not None and row.params_b >= max_params_billion:
            continue
        if is_low_quant(row.best_quant) or row.memory_required_gb > budget_gb:
            continue
        picks.append(
            Suggestion(
                ollama_name=key,
                category=row.category,
                params_b=row.params_b,
                memory_required_gb=row.memory_required_gb,
                estimated_tps=row.estimated_tps,
                score=row.score,
                license=row.license,
            )
        )
        if len(picks) >= limit:
            break
    return picks
