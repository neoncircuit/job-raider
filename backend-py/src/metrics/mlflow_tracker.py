"""
Job Raider - MLflow Integration

This module integrates with MLflow for tracking model performance,
experiments, and pipeline metrics.

Author: Job Raider
Date: 2026-04-21
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import os

from ..utils.logger import get_logger, Components

# MLflow is optional - only required if using this feature
try:
    import mlflow
    import mlflow.sklearn
    import mlflow.pytorch
    from mlflow.entities import Metric as MLflowMetric
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


@dataclass
class ExperimentConfig:
    """Configuration for MLflow experiment."""
    tracking_uri: Optional[str] = None
    experiment_name: str = "job_raider"
    auto_log: bool = True
    disable: bool = False


class MLflowTracker:
    """
    Track experiments and metrics with MLflow.

    Provides integration for logging model performance,
    pipeline metrics, and A/B testing results.
    """

    def __init__(self, config: Optional[ExperimentConfig] = None):
        """
        Initialize MLflow tracker.

        Args:
            config: Experiment configuration

        Raises:
            ImportError: If MLflow is not installed
        """
        if not MLFLOW_AVAILABLE:
            raise ImportError(
                "MLflow is not installed. Install with: pip install mlflow"
            )

        self.config = config or ExperimentConfig()
        self.logger = get_logger(Components.SCRAPERS)
        self._current_run: Optional[str] = None

        # Setup MLflow
        if not self.config.disable:
            self._setup_mlflow()

    def _setup_mlflow(self) -> None:
        """Setup MLflow tracking."""
        if self.config.tracking_uri:
            mlflow.set_tracking_uri(self.config.tracking_uri)
            self.logger.info(f"MLflow tracking URI: {self.config.tracking_uri}")

        # Set or create experiment
        experiment = mlflow.get_experiment_by_name(self.config.experiment_name)
        if experiment is None:
            mlflow.create_experiment(self.config.experiment_name)
            self.logger.info(f"Created MLflow experiment: {self.config.experiment_name}")

        mlflow.set_experiment(self.config.experiment_name)

    def start_run(
        self,
        run_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Start a new MLflow run.

        Args:
            run_name: Optional run name
            tags: Optional tags for the run

        Returns:
            Run ID
        """
        if self.config.disable:
            return "disabled"

        run = mlflow.start_run(run_name=run_name)

        if tags:
            mlflow.set_tags(tags)

        self._current_run = run.info.run_id

        self.logger.info(f"Started MLflow run: {run.info.run_id}")

        return run.info.run_id

    def end_run(self, status: str = "FINISHED") -> None:
        """
        End the current MLflow run.

        Args:
            status: Run status (FINISHED, FAILED, KILLED)
        """
        if self.config.disable or not self._current_run:
            return

        mlflow.end_run(status=status)
        self.logger.info(f"Ended MLflow run: {self._current_run} with status: {status}")
        self._current_run = None

    def log_params(self, params: Dict[str, Any]) -> None:
        """
        Log parameters to current run.

        Args:
            params: Parameters to log
        """
        if self.config.disable or not self._current_run:
            return

        # Convert all values to strings
        str_params = {k: str(v) for k, v in params.items()}
        mlflow.log_params(str_params)

    def log_metrics(
        self,
        metrics: Dict[str, float],
        step: Optional[int] = None,
    ) -> None:
        """
        Log metrics to current run.

        Args:
            metrics: Metrics to log
            step: Optional step number
        """
        if self.config.disable or not self._current_run:
            return

        mlflow.log_metrics(metrics, step=step)

    def log_metric(
        self,
        key: str,
        value: float,
        step: Optional[int] = None,
    ) -> None:
        """
        Log a single metric.

        Args:
            key: Metric key
            value: Metric value
            step: Optional step number
        """
        if self.config.disable or not self._current_run:
            return

        mlflow.log_metric(key, value, step=step)

    def log_pipeline_summary(
        self,
        summary: Dict[str, Any],
    ) -> None:
        """
        Log pipeline execution summary.

        Args:
            summary: Pipeline summary dictionary
        """
        if self.config.disable or not self._current_run:
            return

        # Log as params
        params = {
            "keywords": ",".join(summary.get("keywords", [])),
            "locations": ",".join(summary.get("locations", [])),
            "sources": ",".join(summary.get("sources", [])),
            "dry_run": str(summary.get("dry_run", True)),
            "min_score": str(summary.get("min_score", 60)),
        }

        self.log_params(params)

        # Log metrics
        metrics = {
            "jobs_scraped": summary.get("jobs_scraped", 0),
            "jobs_scored": summary.get("jobs_scored", 0),
            "jobs_applied": summary.get("jobs_applied", 0),
            "duration_seconds": summary.get("duration_seconds", 0),
            "success_rate": summary.get("success_rate", 0.0),
        }

        self.log_metrics(metrics)

    def log_cost_summary(
        self,
        cost_summary: Dict[str, Any],
    ) -> None:
        """
        Log cost tracking summary.

        Args:
            cost_summary: Cost summary dictionary
        """
        if self.config.disable or not self._current_run:
            return

        metrics = {
            "total_cost_usd": cost_summary.get("total_cost_usd", 0.0),
            "total_calls": cost_summary.get("total_calls", 0),
            "total_tokens": cost_summary.get("total_tokens", 0),
            "cost_per_application": cost_summary.get("cost_per_application", 0.0),
            "cache_hit_rate": cost_summary.get("cache_hit_rate", 0.0),
        }

        self.log_metrics(metrics)

        # Log by model
        by_model = cost_summary.get("by_model", {})
        for model, cost in by_model.items():
            safe_name = model.replace(":", "_")
            self.log_metric(f"cost_by_model_{safe_name}", cost)

    def log_outcome_metrics(
        self,
        outcome_metrics: Dict[str, Any],
    ) -> None:
        """
        Log outcome tracking metrics.

        Args:
            outcome_metrics: Outcome metrics dictionary
        """
        if self.config.disable or not self._current_run:
            return

        # Parse conversion rates
        conversion = outcome_metrics.get("conversion_rates", {})

        metrics = {
            "total_applications": outcome_metrics.get("total_applications", 0),
            "funnel_score": outcome_metrics.get("funnel_score", 0.0),
            "screening_rate": float(conversion.get("screening", "0%").rstrip("%")) / 100,
            "technical_rate": float(conversion.get("technical", "0%").rstrip("%")) / 100,
            "onsite_rate": float(conversion.get("onsite", "0%").rstrip("%")) / 100,
            "offer_rate": float(conversion.get("offer", "0%").rstrip("%")) / 100,
        }

        self.log_metrics(metrics)

        # Log time metrics
        time_metrics = outcome_metrics.get("time_metrics", {})
        self.log_metric("avg_days_to_offer", time_metrics.get("avg_days_to_offer", 0))
        self.log_metric("avg_days_to_reject", time_metrics.get("avg_days_to_reject", 0))

    def log_scoring_experiment(
        self,
        experiment_name: str,
        weights: Dict[str, int],
        results: Dict[str, Any],
    ) -> None:
        """
        Log A/B testing experiment for scoring.

        Args:
            experiment_name: Name of the experiment
            weights: Scoring weights used
            results: Experiment results
        """
        if self.config.disable or not self._current_run:
            return

        # Log experiment name as tag
        mlflow.set_tag("experiment_name", experiment_name)

        # Log weights as params
        self.log_params({f"weight_{k}": v for k, v in weights.items()})

        # Log results as metrics
        metrics = {
            f"{experiment_name}_applications": results.get("applications", 0),
            f"{experiment_name}_interviews": results.get("interviews", 0),
            f"{experiment_name}_offers": results.get("offers", 0),
            f"{experiment_name}_offer_rate": results.get("offer_rate", 0.0),
            f"{experiment_name}_avg_score": results.get("avg_score", 0.0),
        }

        self.log_metrics(metrics)

    def log_model_performance(
        self,
        model_name: str,
        task_type: str,
        metrics: Dict[str, float],
    ) -> None:
        """
        Log model performance metrics.

        Args:
            model_name: Name of the model
            task_type: Type of task
            metrics: Performance metrics
        """
        if self.config.disable or not self._current_run:
            return

        safe_model = model_name.replace(":", "_")
        safe_task = task_type.replace(" ", "_").lower()

        for metric_name, value in metrics.items():
            key = f"{safe_model}_{safe_task}_{metric_name}"
            self.log_metric(key, value)

    def log_artifact(
        self,
        local_path: str,
        artifact_path: Optional[str] = None,
    ) -> None:
        """
        Log an artifact (file) to the run.

        Args:
            local_path: Path to local file
            artifact_path: Artifact path in MLflow
        """
        if self.config.disable or not self._current_run:
            return

        if os.path.exists(local_path):
            mlflow.log_artifact(local_path, artifact_path)
            self.logger.info(f"Logged artifact: {local_path}")
        else:
            self.logger.warning(f"Artifact not found: {local_path}")

    def log_figure(
        self,
        figure,
        artifact_file: str,
    ) -> None:
        """
        Log a matplotlib figure as an artifact.

        Args:
            figure: Matplotlib figure object
            artifact_file: Filename for the artifact
        """
        if self.config.disable or not self._current_run:
            return

        mlflow.log_figure(figure, artifact_file)
        self.logger.info(f"Logged figure: {artifact_file}")

    def create_comparison_report(
        self,
        baseline_run_id: str,
        comparison_run_id: str,
    ) -> Dict[str, Any]:
        """
        Compare two runs and generate report.

        Args:
            baseline_run_id: Baseline run ID
            comparison_run_id: Comparison run ID

        Returns:
            Comparison report
        """
        if self.config.disable:
            return {"error": "MLflow is disabled"}

        try:
            baseline = mlflow.get_run(baseline_run_id)
            comparison = mlflow.get_run(comparison_run_id)

            report = {
                "baseline": {
                    "run_id": baseline_run_id,
                    "params": baseline.data.params,
                    "metrics": baseline.data.metrics,
                },
                "comparison": {
                    "run_id": comparison_run_id,
                    "params": comparison.data.params,
                    "metrics": comparison.data.metrics,
                },
                "deltas": {},
            }

            # Calculate metric deltas
            for key, value in comparison.data.metrics.items():
                baseline_value = baseline.data.metrics.get(key, 0)
                report["deltas"][key] = value - baseline_value

            return report

        except Exception as e:
            self.logger.error(f"Failed to compare runs: {str(e)}")
            return {"error": str(e)}

    def get_best_run(
        self,
        metric_name: str,
        order: str = "DESC",
    ) -> Optional[str]:
        """
        Get the best run for a given metric.

        Args:
            metric_name: Name of the metric
            order: DESC for max, ASC for min

        Returns:
            Best run ID or None
        """
        if self.config.disable:
            return None

        try:
            experiment = mlflow.get_experiment_by_name(self.config.experiment_name)
            if not experiment:
                return None

            runs = mlflow.search_runs(
                experiment_ids=[experiment.experiment_id],
                order_by=[f"metrics.{metric_name} {order}"],
                max_results=1,
            )

            if runs.empty:
                return None

            return runs.iloc[0]["run_id"]

        except Exception as e:
            self.logger.error(f"Failed to get best run: {str(e)}")
            return None

    def get_run_history(
        self,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get recent run history.

        Args:
            limit: Maximum number of runs

        Returns:
            List of run summaries
        """
        if self.config.disable:
            return []

        try:
            experiment = mlflow.get_experiment_by_name(self.config.experiment_name)
            if not experiment:
                return []

            runs = mlflow.search_runs(
                experiment_ids=[experiment.experiment_name],
                max_results=limit,
                order_by=["start_time DESC"],
            )

            history = []
            for _, run in runs.iterrows():
                history.append({
                    "run_id": run["run_id"],
                    "start_time": run.get("start_time"),
                    "status": run.get("status"),
                    "metrics": {k: v for k, v in run.items() if k.startswith("metrics.")},
                })

            return history

        except Exception as e:
            self.logger.error(f"Failed to get run history: {str(e)}")
            return []

    def context_manager(self, run_name: Optional[str] = None):
        """
        Get a context manager for a run.

        Args:
            run_name: Optional run name

        Returns:
            Context manager for the run

        Example:
            with tracker.context_manager("my_run") as run:
                tracker.log_metric("value", 1.0)
        """
        return MLflowRunContext(self, run_name)


class MLflowRunContext:
    """Context manager for MLflow runs."""

    def __init__(self, tracker: MLflowTracker, run_name: Optional[str]):
        self.tracker = tracker
        self.run_name = run_name

    def __enter__(self):
        run_id = self.tracker.start_run(self.run_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.tracker.end_run(status="FAILED")
        else:
            self.tracker.end_run(status="FINISHED")


def create_mlflow_tracker(
    tracking_uri: Optional[str] = None,
    experiment_name: str = "job_raider",
    disable: bool = False,
) -> Optional[MLflowTracker]:
    """
    Create an MLflow tracker.

    Args:
        tracking_uri: MLflow tracking URI
        experiment_name: Name of the experiment
        disable: Disable tracking

    Returns:
        MLflowTracker or None if MLflow not available
    """
    if not MLFLOW_AVAILABLE:
        return None

    config = ExperimentConfig(
        tracking_uri=tracking_uri,
        experiment_name=experiment_name,
        disable=disable,
    )

    return MLflowTracker(config)
