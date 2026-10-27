"""
Job Raider - Cost Tracker

This module tracks API costs for LLM usage across the pipeline,
providing detailed cost analysis and optimization insights.

Author: Job Raider
Date: 2026-04-21
"""

import json
import os
import threading
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from ..utils.logger import Components, get_logger

_UNSET = object()
_cost_run_id: ContextVar[Optional[str]] = ContextVar("cost_run_id", default=None)
_PROCESS_TRACKER: Optional["ProcessCostTracker"] = None
_PROCESS_TRACKER_LOCK = threading.Lock()

_PRICE_CONFIG: Optional[Dict[str, Any]] = None


class ModelProvider(str, Enum):
    """LLM model providers."""

    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    OPENAI = "openai"


@dataclass
class ModelPrice:
    """Prices for one catalog model, in USD per million tokens."""

    input_per_million: float
    output_per_million: float
    cache_write_multiplier: float = 1.0
    cache_read_multiplier: float = 0.0
    long_prompt_tokens: Optional[int] = None
    long_input_per_million: Optional[float] = None
    long_output_per_million: Optional[float] = None


def reset_price_config_cache() -> None:
    """
    Clear the loaded price table.

    Tests call this when they replace the YAML.

    Returns:
        None.
    """
    global _PRICE_CONFIG
    _PRICE_CONFIG = None


def _price_config() -> Dict[str, Any]:
    """
    Load ``model_config.yaml`` once.

    Returns:
        The parsed model configuration.
    """
    global _PRICE_CONFIG
    if _PRICE_CONFIG is None:
        from ..config.loader import ConfigLoader

        _PRICE_CONFIG = ConfigLoader().load_model_config() or {}
    return _PRICE_CONFIG


def get_model_price(provider: str, model: str) -> Optional[ModelPrice]:
    """
    Read the catalog price for one provider and model.

    Ollama always has cost 0. A cloud model that is not in the table
    returns ``None``.

    Args:
        provider: Provider name (``anthropic``, ``gemini``, or ``ollama``).
        model: Model identifier.

    Returns:
        The price, or ``None`` when a cloud model has no row.
    """
    if provider == ModelProvider.OLLAMA.value or provider == "ollama":
        return ModelPrice(input_per_million=0.0, output_per_million=0.0)
    config = _price_config()
    provider_cfg = (config.get("models") or {}).get(provider) or {}
    model_cfg = (provider_cfg.get("models") or {}).get(model)
    if not model_cfg:
        return None
    write_mult = float(provider_cfg.get("cache_write_multiplier") or 1.0)
    read_mult = float(provider_cfg.get("cache_read_multiplier") or 0.0)
    long_threshold = model_cfg.get("long_prompt_tokens")
    return ModelPrice(
        input_per_million=float(model_cfg["cost_per_input"]),
        output_per_million=float(model_cfg["cost_per_output"]),
        cache_write_multiplier=write_mult,
        cache_read_multiplier=read_mult,
        long_prompt_tokens=int(long_threshold) if long_threshold else None,
        long_input_per_million=(
            float(model_cfg["long_cost_per_input"])
            if model_cfg.get("long_cost_per_input") is not None
            else None
        ),
        long_output_per_million=(
            float(model_cfg["long_cost_per_output"])
            if model_cfg.get("long_cost_per_output") is not None
            else None
        ),
    )


def calculate_usage_cost(
    price: ModelPrice,
    prompt_tokens: int,
    completion_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """
    Compute USD cost from a price row and token counts.

    Args:
        price: Catalog price.
        prompt_tokens: Uncached prompt tokens.
        completion_tokens: Completion tokens (including thinking tokens).
        cache_write_tokens: Prompt-cache write tokens.
        cache_read_tokens: Prompt-cache read tokens.

    Returns:
        Cost in USD.
    """
    input_rate = price.input_per_million
    output_rate = price.output_per_million
    if (
        price.long_prompt_tokens is not None
        and prompt_tokens > price.long_prompt_tokens
        and price.long_input_per_million is not None
        and price.long_output_per_million is not None
    ):
        input_rate = price.long_input_per_million
        output_rate = price.long_output_per_million
    input_cost = (prompt_tokens / 1_000_000) * input_rate
    output_cost = (completion_tokens / 1_000_000) * output_rate
    write_cost = (
        (cache_write_tokens / 1_000_000) * input_rate * price.cache_write_multiplier
    )
    read_cost = (
        (cache_read_tokens / 1_000_000) * input_rate * price.cache_read_multiplier
    )
    return input_cost + output_cost + write_cost + read_cost


def _catalog_provider(model_name: str) -> Optional[str]:
    """
    Return the catalog provider that lists ``model_name``.

    Args:
        model_name: Model identifier.

    Returns:
        Provider name, or ``None``.
    """
    models_root = _price_config().get("models") or {}
    for provider in (
        ModelProvider.ANTHROPIC.value,
        ModelProvider.GEMINI.value,
        ModelProvider.OLLAMA.value,
    ):
        listed = (models_root.get(provider) or {}).get("models") or {}
        if model_name in listed:
            return provider
    return None


def _price_for_named_model(model_name: str) -> Optional[ModelPrice]:
    """
    Find a catalog price by model name.

    Args:
        model_name: Model identifier.

    Returns:
        The matching price, or ``None``.
    """
    provider = _catalog_provider(model_name)
    if provider is None:
        return None
    return get_model_price(provider, model_name)


@dataclass
class CallRecord:
    """One router call: counts, names, flags, and time. No prompt or reply text."""

    timestamp: datetime
    run_id: str
    task_type: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    tokens_estimated: bool
    latency_ms: int
    cache_hit: bool
    fallback: bool
    error: bool
    cost_usd: Optional[float]


class ProcessCostTracker:
    """
    Process-wide, thread-safe recorder for router calls.

    Keeps the last 1000 records, totals since the process started, and
    every call of each open run until that run's summary is written.
    """

    def __init__(self) -> None:
        """Create empty totals and an empty recent-call buffer."""
        self._lock = threading.Lock()
        self._recent: deque[CallRecord] = deque(maxlen=1000)
        self._run_calls: Dict[str, List[CallRecord]] = {}
        self._totals: Dict[str, Any] = {
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_counts": 0,
            "cache_hits": 0,
            "fallbacks": 0,
            "errors": 0,
            "cost_usd": 0.0,
            "cost_unknown": 0,
        }

    def reset(self) -> None:
        """
        Clear records and totals. Tests call this between cases.

        Returns:
            None.
        """
        with self._lock:
            self._recent.clear()
            self._run_calls.clear()
            self._totals = {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_counts": 0,
                "cache_hits": 0,
                "fallbacks": 0,
                "errors": 0,
                "cost_usd": 0.0,
                "cost_unknown": 0,
            }

    def open_run(self, run_id: str) -> None:
        """
        Start a run bucket. Does not clear shared recent records.

        Args:
            run_id: Pipeline run identifier.

        Returns:
            None.
        """
        with self._lock:
            self._run_calls.setdefault(run_id, [])

    def close_run(self, run_id: str) -> List[CallRecord]:
        """
        Remove and return the records of one run.

        Args:
            run_id: Pipeline run identifier.

        Returns:
            The run's records, in order.
        """
        with self._lock:
            return self._run_calls.pop(run_id, [])

    def run_calls(self, run_id: str) -> List[CallRecord]:
        """
        Return a copy of one run's records.

        Args:
            run_id: Pipeline run identifier.

        Returns:
            The run's records.
        """
        with self._lock:
            return list(self._run_calls.get(run_id, []))

    def recent_calls(self) -> List[CallRecord]:
        """
        Return the last 1000 records.

        Returns:
            Recent records, oldest first.
        """
        with self._lock:
            return list(self._recent)

    def process_totals(self) -> Dict[str, Any]:
        """
        Return totals since the process started (or since the last reset).

        Returns:
            Counts, tokens, flags, and cost. ``cost_usd`` is ``None`` when
            any call had an unknown price.
        """
        with self._lock:
            totals: Dict[str, Any] = dict(self._totals)
        if totals["cost_unknown"]:
            totals["cost_usd"] = None
        return totals

    def record_call(
        self,
        *,
        task_type: str,
        provider: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: Optional[int] = None,
        tokens_estimated: bool = False,
        latency_ms: int = 0,
        cache_hit: bool = False,
        fallback: bool = False,
        error: bool = False,
        cost_usd: Any = _UNSET,
        run_id: Optional[str] = None,
    ) -> CallRecord:
        """
        Append one call record.

        Args:
            task_type: Router task type value.
            provider: Provider that served or was attempted.
            model: Model that served or was attempted.
            prompt_tokens: Prompt tokens.
            completion_tokens: Completion tokens.
            total_tokens: Total tokens, or ``None`` to sum prompt and completion.
            tokens_estimated: True when counts are a length estimate.
            latency_ms: Client-call time in milliseconds.
            cache_hit: True for a response-cache hit.
            fallback: True when the fallback served the call.
            error: True for a failed attempt.
            cost_usd: Cost, or ``_UNSET`` to compute from the price table.
            run_id: Pipeline run ID. Defaults to the current scope.

        Returns:
            The stored record.
        """
        if cache_hit or error:
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            tokens_estimated = False
            if cost_usd is _UNSET:
                cost_usd = 0.0
        else:
            if total_tokens is None:
                total_tokens = prompt_tokens + completion_tokens
            if cost_usd is _UNSET:
                price = get_model_price(provider, model)
                cost_usd = (
                    None
                    if price is None
                    else calculate_usage_cost(price, prompt_tokens, completion_tokens)
                )
        resolved_run = run_id if run_id is not None else (_cost_run_id.get() or "")
        record = CallRecord(
            timestamp=datetime.now(),
            run_id=resolved_run,
            task_type=task_type,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=int(total_tokens),
            tokens_estimated=tokens_estimated,
            latency_ms=latency_ms,
            cache_hit=cache_hit,
            fallback=fallback,
            error=error,
            cost_usd=cost_usd if cost_usd is not _UNSET else None,
        )
        with self._lock:
            self._recent.append(record)
            if resolved_run:
                self._run_calls.setdefault(resolved_run, []).append(record)
            self._totals["calls"] += 1
            self._totals["prompt_tokens"] += record.prompt_tokens
            self._totals["completion_tokens"] += record.completion_tokens
            self._totals["total_tokens"] += record.total_tokens
            if record.tokens_estimated:
                self._totals["estimated_counts"] += 1
            if record.cache_hit:
                self._totals["cache_hits"] += 1
            if record.fallback:
                self._totals["fallbacks"] += 1
            if record.error:
                self._totals["errors"] += 1
            if record.cost_usd is None:
                self._totals["cost_unknown"] += 1
            else:
                self._totals["cost_usd"] += record.cost_usd
        return record


def get_cost_tracker() -> ProcessCostTracker:
    """
    Return the process-wide cost tracker.

    Returns:
        The singleton tracker.
    """
    global _PROCESS_TRACKER
    if _PROCESS_TRACKER is None:
        with _PROCESS_TRACKER_LOCK:
            if _PROCESS_TRACKER is None:
                _PROCESS_TRACKER = ProcessCostTracker()
    return _PROCESS_TRACKER


def reset_cost_tracker() -> None:
    """
    Replace the process-wide tracker with an empty instance.

    Tests call this so a patched method cannot leak into the next case.

    Returns:
        None.
    """
    global _PROCESS_TRACKER
    with _PROCESS_TRACKER_LOCK:
        _PROCESS_TRACKER = ProcessCostTracker()


def current_cost_run_id() -> Optional[str]:
    """
    Return the run ID from the current cost-run scope, if any.

    Returns:
        The run ID, or ``None`` outside a scope.
    """
    return _cost_run_id.get()


@contextmanager
def cost_run_scope(run_id: str) -> Iterator[str]:
    """
    Bind router records in this context to ``run_id``.

    ``asyncio.to_thread`` copies context variables, so a worker thread
    that starts after this scope is entered keeps the same run ID.

    Args:
        run_id: Pipeline run identifier.

    Yields:
        The same run ID.
    """
    token = _cost_run_id.set(run_id)
    get_cost_tracker().open_run(run_id)
    try:
        yield run_id
    finally:
        _cost_run_id.reset(token)


def _default_metrics_dir() -> Path:
    """
    Absolute ``apps/backend-py/data/metrics`` directory.

    Returns:
        The metrics directory.
    """
    return Path(__file__).resolve().parents[2] / "data" / "metrics"


def summarize_call_records(records: List[CallRecord]) -> Dict[str, Any]:
    """
    Build a cost summary from a list of call records.

    Args:
        records: Records of one run.

    Returns:
        Summary counts. ``total_cost_usd`` is ``None`` when any call
        had no price.
    """
    calls = len(records)
    prompt = sum(r.prompt_tokens for r in records)
    completion = sum(r.completion_tokens for r in records)
    total = sum(r.total_tokens for r in records)
    estimated = sum(1 for r in records if r.tokens_estimated)
    cache_hits = sum(1 for r in records if r.cache_hit)
    fallbacks = sum(1 for r in records if r.fallback)
    errors = sum(1 for r in records if r.error)
    unknown = any(r.cost_usd is None for r in records)
    cost = None if unknown else sum(float(r.cost_usd or 0.0) for r in records)
    return {
        "total_calls": calls,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "estimated_counts": estimated,
        "cache_hits": cache_hits,
        "fallbacks": fallbacks,
        "errors": errors,
        "cache_hit_rate": (cache_hits / calls) if calls else 0.0,
        "estimated_share": (estimated / calls) if calls else 0.0,
        "total_cost_usd": cost,
        "total_duration_seconds": sum(r.latency_ms for r in records) / 1000.0,
    }


def log_cost_run_to_mlflow(
    summary: Dict[str, Any],
    *,
    run_id: str,
    mode: str = "",
    tracker_factory: Optional[Callable[..., Any]] = None,
    tracking_uri: Optional[str] = None,
    timeout_s: float = 3.0,
) -> Optional[str]:
    """
    Log one pipeline cost summary to the ``pipeline-runs`` experiment.

    Fail open: an MLflow error is logged and ignored.

    Args:
        summary: Cost summary from ``summarize_call_records``.
        run_id: Pipeline run identifier.
        mode: Pipeline mode tag.
        tracker_factory: Creates the tracker; defaults to
            ``create_mlflow_tracker``.
        tracking_uri: Store to use; defaults to ``resolve_tracking_uri``.
        timeout_s: Seconds for the tracking server health check.

    Returns:
        The MLflow run ID, or ``None`` when logging was skipped.
    """
    from ..evaluation.report import (
        DEFAULT_ARTIFACT_DIR,
        DEFAULT_TRACKING_URI,
        resolve_tracking_uri,
        tracking_server_reachable,
    )
    from ..evaluation.run_metadata import BACKEND_DIR, collect_git_state

    uri = tracking_uri or resolve_tracking_uri()
    if tracker_factory is None:
        if not tracking_server_reachable(uri, timeout_s=timeout_s):
            get_logger(Components.SCRAPERS).warning(
                "MLflow at %s is not reachable; cost run not logged.", uri
            )
            return None
        from .mlflow_tracker import create_mlflow_tracker

        tracker_factory = create_mlflow_tracker
    artifact_location = None
    if uri == DEFAULT_TRACKING_URI:
        artifact_location = DEFAULT_ARTIFACT_DIR.as_uri()
    if uri.startswith("sqlite:///"):
        Path(uri[len("sqlite:///") :]).parent.mkdir(parents=True, exist_ok=True)
    try:
        import mlflow

        previous_uri = mlflow.get_tracking_uri()
    except ImportError:
        get_logger(Components.SCRAPERS).warning(
            "MLflow is not installed; cost run not logged."
        )
        return None
    git_sha, _dirty = collect_git_state(BACKEND_DIR)
    metrics = {
        "calls": summary.get("total_calls"),
        "prompt_tokens": summary.get("prompt_tokens"),
        "completion_tokens": summary.get("completion_tokens"),
        "total_tokens": summary.get("total_tokens"),
        "estimated_share": summary.get("estimated_share"),
        "cache_hit_rate": summary.get("cache_hit_rate"),
        "fallback_count": summary.get("fallbacks"),
        "error_count": summary.get("errors"),
        "cost_usd": summary.get("total_cost_usd"),
    }
    try:
        tracker = tracker_factory(
            tracking_uri=uri,
            experiment_name="pipeline-runs",
            artifact_location=artifact_location,
        )
        if tracker is None:
            get_logger(Components.SCRAPERS).warning(
                "MLflow is not installed; cost run not logged."
            )
            return None
        ml_run = tracker.start_run(
            run_name=f"pipeline-{run_id}",
            tags={"run_id": run_id, "mode": mode, "git_sha": git_sha},
        )
        try:
            tracker.log_metrics(
                {key: value for key, value in metrics.items() if value is not None}
            )
        finally:
            tracker.end_run()
        return str(ml_run)
    except Exception as exc:  # noqa: BLE001 - tracking must not fail the run
        get_logger(Components.SCRAPERS).warning(
            "MLflow logging for pipeline run %s failed: %s", run_id, exc
        )
        return None
    finally:
        mlflow.set_tracking_uri(previous_uri)


def write_cost_run_summary(
    run_id: str,
    *,
    storage_dir: Optional[Path] = None,
    mode: str = "",
    documents: int = 0,
    tracker_factory: Optional[Callable[..., Any]] = None,
    tracking_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Write ``cost_run_<run_id>.json`` and log the summary to MLflow.

    File and MLflow errors are logged. The in-memory summary is still
    returned.

    Args:
        run_id: Pipeline run identifier.
        storage_dir: Folder for the JSON file. Defaults to
            ``apps/backend-py/data/metrics``.
        mode: Pipeline mode.
        documents: Jobs that received a generated document in this run.
        tracker_factory: Optional MLflow tracker factory for tests.
        tracking_uri: Optional MLflow URI.

    Returns:
        The run summary (without the call list).
    """
    records = get_cost_tracker().run_calls(run_id)
    summary = summarize_call_records(records)
    summary["run_id"] = run_id
    summary["mode"] = mode
    summary["documents"] = documents
    if documents > 0 and summary["total_cost_usd"] is not None:
        summary["cost_per_application"] = summary["total_cost_usd"] / documents
    else:
        summary["cost_per_application"] = None
    if storage_dir is None and os.getenv("PYTEST_CURRENT_TEST"):
        return summary
    folder = Path(storage_dir) if storage_dir is not None else _default_metrics_dir()
    payload = {
        "run_id": run_id,
        "mode": mode,
        "start_time": records[0].timestamp.isoformat() if records else None,
        "end_time": datetime.now().isoformat(),
        "summary": summary,
        "calls": [
            {
                "timestamp": record.timestamp.isoformat(),
                "run_id": record.run_id,
                "task_type": record.task_type,
                "provider": record.provider,
                "model": record.model,
                "prompt_tokens": record.prompt_tokens,
                "completion_tokens": record.completion_tokens,
                "total_tokens": record.total_tokens,
                "tokens_estimated": record.tokens_estimated,
                "latency_ms": record.latency_ms,
                "cache_hit": record.cache_hit,
                "fallback": record.fallback,
                "error": record.error,
                "cost_usd": record.cost_usd,
            }
            for record in records
        ],
    }
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"cost_run_{run_id}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - file errors must not fail the run
        get_logger(Components.SCRAPERS).warning(
            "Failed to write cost run file for %s: %s", run_id, exc
        )
    in_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
    if tracker_factory is not None or not in_pytest:
        try:
            log_cost_run_to_mlflow(
                summary,
                run_id=run_id,
                mode=mode,
                tracker_factory=tracker_factory,
                tracking_uri=tracking_uri,
            )
        except Exception as exc:  # noqa: BLE001 - MLflow must not fail the run
            get_logger(Components.SCRAPERS).warning(
                "MLflow logging for pipeline run %s failed: %s", run_id, exc
            )
    return summary


class TaskType(str, Enum):
    """Types of LLM tasks."""

    EXTRACTION = "extraction"
    SCORING = "scoring"
    SELECTION = "selection"
    WRITING = "writing"
    VALIDATION = "validation"
    PARSING = "parsing"


@dataclass
class TokenUsage:
    """Token usage for a single LLM call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @property
    def total_thousands(self) -> float:
        """Total tokens in thousands."""
        return self.total_tokens / 1000.0


@dataclass
class ModelCost:
    """Cost information for a model."""

    provider: ModelProvider
    model_name: str
    input_cost_per_million: float
    output_cost_per_million: float

    def calculate_cost(self, usage: TokenUsage) -> float:
        """
        Calculate cost for given token usage.

        Args:
            usage: Token usage data

        Returns:
            Cost in USD
        """
        input_cost = (usage.prompt_tokens / 1_000_000) * self.input_cost_per_million
        output_cost = (
            usage.completion_tokens / 1_000_000
        ) * self.output_cost_per_million
        return input_cost + output_cost


@dataclass
class LLMApiCall:
    """Record of a single LLM API call."""

    timestamp: datetime
    task_type: TaskType
    model_name: str
    provider: ModelProvider
    token_usage: TokenUsage
    cost_usd: float
    duration_seconds: float
    cache_hit: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineCostSummary:
    """Cost summary for a pipeline run."""

    total_cost_usd: float
    total_calls: int
    total_tokens: int
    total_duration_seconds: float
    by_task_type: Dict[TaskType, float]
    by_model: Dict[str, float]
    by_provider: Dict[ModelProvider, float]
    cache_hit_rate: float


class CostTracker:
    """
    Track LLM API costs across pipeline execution.

    Provides detailed cost analysis, per-run summaries,
    and optimization recommendations.
    """

    def __init__(self, storage_dir: str = "data/metrics"):
        """
        Initialize the cost tracker.

        Args:
            storage_dir: Directory to store cost data
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(Components.SCRAPERS)

        # In-memory tracking
        self._calls: List[LLMApiCall] = []
        self._pipeline_start_time: Optional[datetime] = None
        self._current_run_id: Optional[str] = None

    def start_run(self, run_id: Optional[str] = None) -> str:
        """
        Start a new pipeline run tracking.

        Args:
            run_id: Optional run ID (auto-generated if None)

        Returns:
            Run ID
        """
        self._pipeline_start_time = datetime.now()
        self._current_run_id = run_id or self._generate_run_id()

        self.logger.info(f"Cost tracking started for run: {self._current_run_id}")

        return self._current_run_id

    def track_call(
        self,
        task_type: TaskType,
        model_name: str,
        token_usage: TokenUsage,
        duration_seconds: float,
        cache_hit: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track a single LLM API call.

        Args:
            task_type: Type of task performed
            model_name: Name of the model used
            token_usage: Token usage data
            duration_seconds: Call duration
            cache_hit: Whether this was a cache hit
            metadata: Additional metadata
        """
        provider_name = _catalog_provider(model_name)
        price = get_model_price(provider_name, model_name) if provider_name else None
        if price is None:
            self.logger.warning("Unknown model %s: cost is unknown", model_name)
            cost_usd = 0.0
            provider = ModelProvider.OLLAMA
        else:
            cost_usd = calculate_usage_cost(
                price, token_usage.prompt_tokens, token_usage.completion_tokens
            )
            provider = ModelProvider(provider_name)

        # Create call record
        call = LLMApiCall(
            timestamp=datetime.now(),
            task_type=task_type,
            model_name=model_name,
            provider=provider,
            token_usage=token_usage,
            cost_usd=cost_usd,
            duration_seconds=duration_seconds,
            cache_hit=cache_hit,
            metadata=metadata or {},
        )

        self._calls.append(call)

    def end_run(self) -> PipelineCostSummary:
        """
        End the current pipeline run and generate summary.

        Returns:
            PipelineCostSummary with cost breakdown
        """
        if not self._calls:
            return PipelineCostSummary(
                total_cost_usd=0.0,
                total_calls=0,
                total_tokens=0,
                total_duration_seconds=0.0,
                by_task_type={},
                by_model={},
                by_provider={},
                cache_hit_rate=0.0,
            )

        # Calculate totals
        total_cost = sum(call.cost_usd for call in self._calls)
        total_tokens = sum(call.token_usage.total_tokens for call in self._calls)
        total_duration = sum(call.duration_seconds for call in self._calls)

        # Group by task type
        by_task: Dict[TaskType, float] = {}
        for call in self._calls:
            by_task[call.task_type] = by_task.get(call.task_type, 0.0) + call.cost_usd

        # Group by model
        by_model: Dict[str, float] = {}
        for call in self._calls:
            by_model[call.model_name] = (
                by_model.get(call.model_name, 0.0) + call.cost_usd
            )

        # Group by provider
        by_provider: Dict[ModelProvider, float] = {}
        for call in self._calls:
            by_provider[call.provider] = (
                by_provider.get(call.provider, 0.0) + call.cost_usd
            )

        # Calculate cache hit rate
        cache_hits = sum(1 for call in self._calls if call.cache_hit)
        cache_hit_rate = cache_hits / len(self._calls) if self._calls else 0.0

        summary = PipelineCostSummary(
            total_cost_usd=total_cost,
            total_calls=len(self._calls),
            total_tokens=total_tokens,
            total_duration_seconds=total_duration,
            by_task_type=by_task,
            by_model=by_model,
            by_provider=by_provider,
            cache_hit_rate=cache_hit_rate,
        )

        # Save to file
        self._save_run_summary(summary)

        return summary

    def get_current_run_cost(self) -> float:
        """
        Get cost for current run so far.

        Returns:
            Cost in USD
        """
        return sum(call.cost_usd for call in self._calls)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of tracked costs.

        Returns:
            Dictionary with cost breakdown
        """
        total_cost = sum(call.cost_usd for call in self._calls)
        api_cost = sum(
            call.cost_usd
            for call in self._calls
            if call.provider == ModelProvider.ANTHROPIC
        )

        return {
            "total_cost_usd": total_cost,
            "api_cost_usd": api_cost,
            "total_calls": len(self._calls),
            "total_tokens": sum(call.token_usage.total_tokens for call in self._calls),
            "cost_per_application": 0.0,
        }

    def get_cost_per_application(self, num_applications: int) -> float:
        """
        Calculate cost per application.

        Args:
            num_applications: Number of applications processed

        Returns:
            Cost per application in USD
        """
        if num_applications == 0:
            return 0.0
        return self.get_current_run_cost() / num_applications

    def get_cost_estimate(
        self,
        num_jobs: int,
        use_local_models: bool = True,
    ) -> Dict[str, Any]:
        """
        Estimate cost for processing jobs.

        Args:
            num_jobs: Number of jobs to process
            use_local_models: Whether to use local models

        Returns:
            Cost estimate breakdown
        """
        # Average tokens per task (based on empirical data)
        avg_tokens = {
            TaskType.EXTRACTION: 1500,  # JD extraction
            TaskType.SCORING: 800,  # Relevance scoring
            TaskType.SELECTION: 1200,  # Project selection
            TaskType.WRITING: 3000,  # Resume writing
            TaskType.VALIDATION: 500,  # Validation check
            TaskType.PARSING: 2000,  # Resume parsing
        }

        # Calls per job
        calls_per_job = {
            TaskType.EXTRACTION: 1,
            TaskType.SCORING: 1,
            TaskType.SELECTION: 1,
            TaskType.WRITING: 1,
            TaskType.VALIDATION: 1,
        }

        # Model selection
        if use_local_models:
            selection_model = "qwen2.5:3b"
            writing_model = "qwen2.5:7b"
        else:
            selection_model = "claude-haiku-4-5-20251001"
            writing_model = "claude-sonnet-4-6"

        # Estimate cost
        total_cost = 0.0
        task_breakdown = {}

        for task_type, calls_per in calls_per_job.items():
            tokens = avg_tokens[task_type]
            total_calls = num_jobs * calls_per

            # Select model
            if task_type == TaskType.WRITING:
                model_name = writing_model
            elif task_type == TaskType.SELECTION:
                model_name = selection_model
            else:
                model_name = selection_model

            price = _price_for_named_model(model_name)
            if price is None:
                continue

            # Estimate 50/50 split input/output
            prompt_tokens = int(tokens * 0.5)
            completion_tokens = int(tokens * 0.5)
            task_cost = (
                calculate_usage_cost(price, prompt_tokens, completion_tokens)
                * total_calls
            )
            total_cost += task_cost

            task_breakdown[task_type.value] = {
                "calls": total_calls,
                "avg_tokens": tokens,
                "model": model_name,
                "cost": task_cost,
            }

        return {
            "total_cost_usd": total_cost,
            "cost_per_application": total_cost / num_jobs if num_jobs > 0 else 0,
            "num_applications": num_jobs,
            "use_local_models": use_local_models,
            "task_breakdown": task_breakdown,
        }

    def get_optimization_recommendations(self) -> List[str]:
        """
        Get recommendations for cost optimization.

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Check cache hit rate
        cache_hits = sum(1 for call in self._calls if call.cache_hit)
        cache_hit_rate = cache_hits / len(self._calls) if self._calls else 0

        if cache_hit_rate < 0.3:
            recommendations.append(
                f"Low cache hit rate ({cache_hit_rate:.1%}). "
                "Consider increasing cache TTL or enabling response caching."
            )

        # Check for expensive API usage
        api_cost = sum(
            call.cost_usd
            for call in self._calls
            if call.provider == ModelProvider.ANTHROPIC
        )

        if api_cost > 10.0:
            recommendations.append(
                f"High API cost (${api_cost:.2f}). "
                "Consider using local Ollama models for selection and scoring."
            )

        # Check for inefficient model usage
        for call in self._calls:
            if (
                call.task_type == TaskType.SELECTION
                and call.provider == ModelProvider.ANTHROPIC
            ):
                if call.model_name != "claude-haiku-4-5-20251001":
                    recommendations.append(
                        f"Using {call.model_name} for selection. "
                        "Consider using claude-haiku or local qwen2.5:3b for cost savings."
                    )

        # Check token efficiency
        if self._calls:
            avg_tokens = sum(
                call.token_usage.total_tokens for call in self._calls
            ) / len(self._calls)
            if avg_tokens > 5000:
                recommendations.append(
                    f"High average token count ({avg_tokens:.0f}). "
                    "Consider reducing context size or extracting only relevant sections."
                )

        return recommendations

    def _generate_run_id(self) -> str:
        """Generate a unique run ID."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _save_run_summary(self, summary: PipelineCostSummary) -> None:
        """Save run summary to file."""
        if not self._current_run_id:
            return

        filepath = self.storage_dir / f"cost_run_{self._current_run_id}.json"

        data = {
            "run_id": self._current_run_id,
            "start_time": (
                self._pipeline_start_time.isoformat()
                if self._pipeline_start_time
                else None
            ),
            "end_time": datetime.now().isoformat(),
            "summary": {
                "total_cost_usd": summary.total_cost_usd,
                "total_calls": summary.total_calls,
                "total_tokens": summary.total_tokens,
                "total_duration_seconds": summary.total_duration_seconds,
                "cache_hit_rate": summary.cache_hit_rate,
                "by_task_type": {k.value: v for k, v in summary.by_task_type.items()},
                "by_model": summary.by_model,
                "by_provider": {k.value: v for k, v in summary.by_provider.items()},
            },
            "calls": [
                {
                    "timestamp": call.timestamp.isoformat(),
                    "task_type": call.task_type.value,
                    "model_name": call.model_name,
                    "provider": call.provider.value,
                    "prompt_tokens": call.token_usage.prompt_tokens,
                    "completion_tokens": call.token_usage.completion_tokens,
                    "total_tokens": call.token_usage.total_tokens,
                    "cost_usd": call.cost_usd,
                    "duration_seconds": call.duration_seconds,
                    "cache_hit": call.cache_hit,
                    "metadata": call.metadata,
                }
                for call in self._calls
            ],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        self.logger.info(f"Cost summary saved to: {filepath}")

    def load_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Load historical cost data.

        Args:
            limit: Maximum number of runs to load

        Returns:
            List of run summaries
        """
        history = []

        for filepath in sorted(self.storage_dir.glob("cost_run_*.json"), reverse=True)[
            :limit
        ]:
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                    history.append(data)
            except Exception as e:
                self.logger.warning(f"Failed to load cost file {filepath}: {str(e)}")
                continue

        return history

    def get_aggregate_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get aggregate statistics over time period.

        Args:
            days: Number of days to look back

        Returns:
            Aggregate statistics
        """
        history = self.load_history()

        # Filter by date
        cutoff = datetime.now().timestamp() - (days * 86400)
        recent_runs = [
            run
            for run in history
            if run.get("end_time")
            and datetime.fromisoformat(run["end_time"]).timestamp() > cutoff
        ]

        if not recent_runs:
            return {
                "total_runs": 0,
                "total_cost_usd": 0.0,
                "avg_cost_per_run": 0.0,
                "total_tokens": 0,
                "total_calls": 0,
            }

        total_cost = sum(run["summary"]["total_cost_usd"] for run in recent_runs)
        total_tokens = sum(run["summary"]["total_tokens"] for run in recent_runs)
        total_calls = sum(run["summary"]["total_calls"] for run in recent_runs)

        return {
            "period_days": days,
            "total_runs": len(recent_runs),
            "total_cost_usd": total_cost,
            "avg_cost_per_run": total_cost / len(recent_runs),
            "total_tokens": total_tokens,
            "total_calls": total_calls,
            "avg_tokens_per_call": total_tokens / total_calls if total_calls > 0 else 0,
        }
