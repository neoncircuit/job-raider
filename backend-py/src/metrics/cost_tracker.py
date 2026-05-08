"""
Job Raider - Cost Tracker

This module tracks API costs for LLM usage across the pipeline,
providing detailed cost analysis and optimization insights.

Author: Job Raider
Date: 2026-04-21
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path

from ..utils.logger import get_logger, Components


class ModelProvider(str, Enum):
    """LLM model providers."""
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    OPENAI = "openai"


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
        output_cost = (usage.completion_tokens / 1_000_000) * self.output_cost_per_million
        return input_cost + output_cost


# Model pricing (as of 2026)
MODEL_PRICING = {
    # Anthropic models
    "claude-haiku-4-5-20251001": ModelCost(
        provider=ModelProvider.ANTHROPIC,
        model_name="claude-haiku-4-5-20251001",
        input_cost_per_million=1.0,
        output_cost_per_million=5.0,
    ),
    "claude-sonnet-4-6": ModelCost(
        provider=ModelProvider.ANTHROPIC,
        model_name="claude-sonnet-4-6",
        input_cost_per_million=3.0,
        output_cost_per_million=15.0,
    ),
    "claude-opus-4-7": ModelCost(
        provider=ModelProvider.ANTHROPIC,
        model_name="claude-opus-4-7",
        input_cost_per_million=15.0,
        output_cost_per_million=75.0,
    ),

    # Ollama models (free, local)
    "qwen2.5:3b": ModelCost(
        provider=ModelProvider.OLLAMA,
        model_name="qwen2.5:3b",
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
    ),
    "qwen2.5:7b": ModelCost(
        provider=ModelProvider.OLLAMA,
        model_name="qwen2.5:7b",
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
    ),
    "gemma3:4b": ModelCost(
        provider=ModelProvider.OLLAMA,
        model_name="gemma3:4b",
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
    ),
    "gemma3:12b": ModelCost(
        provider=ModelProvider.OLLAMA,
        model_name="gemma3:12b",
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
    ),
}


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
        # Get model pricing
        model_cost = MODEL_PRICING.get(model_name)
        if not model_cost:
            self.logger.warning(f"Unknown model: {model_name}, assuming zero cost")
            model_cost = ModelCost(
                provider=ModelProvider.OLLAMA,
                model_name=model_name,
                input_cost_per_million=0.0,
                output_cost_per_million=0.0,
            )

        # Calculate cost
        cost_usd = model_cost.calculate_cost(token_usage)

        # Create call record
        call = LLMApiCall(
            timestamp=datetime.now(),
            task_type=task_type,
            model_name=model_name,
            provider=model_cost.provider,
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
            by_model[call.model_name] = by_model.get(call.model_name, 0.0) + call.cost_usd

        # Group by provider
        by_provider: Dict[ModelProvider, float] = {}
        for call in self._calls:
            by_provider[call.provider] = by_provider.get(call.provider, 0.0) + call.cost_usd

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
            call.cost_usd for call in self._calls
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

            model_cost = MODEL_PRICING.get(model_name)
            if not model_cost:
                continue

            # Estimate 50/50 split input/output
            prompt_tokens = int(tokens * 0.5)
            completion_tokens = int(tokens * 0.5)

            usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=tokens,
            )

            task_cost = model_cost.calculate_cost(usage) * total_calls
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
            call.cost_usd for call in self._calls
            if call.provider == ModelProvider.ANTHROPIC
        )

        if api_cost > 10.0:
            recommendations.append(
                f"High API cost (${api_cost:.2f}). "
                "Consider using local Ollama models for selection and scoring."
            )

        # Check for inefficient model usage
        for call in self._calls:
            if call.task_type == TaskType.SELECTION and call.provider == ModelProvider.ANTHROPIC:
                if call.model_name != "claude-haiku-4-5-20251001":
                    recommendations.append(
                        f"Using {call.model_name} for selection. "
                        "Consider using claude-haiku or local qwen2.5:3b for cost savings."
                    )

        # Check token efficiency
        if self._calls:
            avg_tokens = sum(call.token_usage.total_tokens for call in self._calls) / len(self._calls)
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
            "start_time": self._pipeline_start_time.isoformat() if self._pipeline_start_time else None,
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

        for filepath in sorted(self.storage_dir.glob("cost_run_*.json"), reverse=True)[:limit]:
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
            run for run in history
            if run.get("end_time") and datetime.fromisoformat(run["end_time"]).timestamp() > cutoff
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
