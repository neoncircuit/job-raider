"""
Job Raider - Cost Tracker

This module tracks API costs for LLM usage across the pipeline,
providing detailed cost analysis and optimization insights.

Author: Job Raider
Date: 2026-04-21
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.logger import Components, get_logger

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
        self._calls = []

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
