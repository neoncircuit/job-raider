"""
Evaluation reports: a JSON file per run, and an MLflow run (Step 3.1).

The JSON report is always written. MLflow logging is best effort: when the
tracking server cannot be reached, the run is skipped with a warning and
the report file stays. Without ``MLFLOW_TRACKING_URI`` the store is a local
SQLite file at an absolute path under ``apps/backend-py/data`` (decision 5,
2026-10-22; MLflow 3.14 refuses the plain file store).
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

from ..utils.logger import Components, get_logger
from .run_metadata import BACKEND_DIR, RunMetadata

logger = get_logger(Components.SCRAPERS)

DATA_DIR = BACKEND_DIR / "data"
DEFAULT_REPORT_DIR = DATA_DIR / "eval"
DEFAULT_DB_PATH = DATA_DIR / "mlflow.db"
DEFAULT_ARTIFACT_DIR = DATA_DIR / "mlartifacts"
DEFAULT_TRACKING_URI = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
EVAL_EXPERIMENT = "job_raider_eval"


class EvalReport(BaseModel):
    """Result of one evaluation run."""

    suite: str
    metadata: RunMetadata
    metrics: Dict[str, Optional[float]]
    details: Dict[str, Any] = Field(default_factory=dict)


def write_report(report: EvalReport, out_dir: Optional[Path] = None) -> Path:
    """
    Write the report as JSON to ``<out_dir>/<suite>/<UTC timestamp>.json``.

    Args:
        report: Report to write.
        out_dir: Base folder; defaults to ``apps/backend-py/data/eval``.

    Returns:
        Path of the written file.
    """
    folder = (out_dir or DEFAULT_REPORT_DIR) / report.suite
    folder.mkdir(parents=True, exist_ok=True)
    stamp = report.metadata.started_at.strftime("%Y%m%dT%H%M%S%fZ")
    path = folder / f"{stamp}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def resolve_tracking_uri() -> str:
    """
    MLflow tracking URI for evaluation runs.

    Returns:
        ``MLFLOW_TRACKING_URI`` when set, otherwise a SQLite URI with an
        absolute path to ``apps/backend-py/data/mlflow.db``.
    """
    configured = os.getenv("MLFLOW_TRACKING_URI", "").strip()
    return configured or DEFAULT_TRACKING_URI


def tracking_server_reachable(uri: str, timeout_s: float = 3.0) -> bool:
    """
    Check that an HTTP tracking server answers its health endpoint.

    MLflow retries a dead server with back-off for minutes, so the harness
    checks first. Non-HTTP stores (SQLite, files) count as reachable.

    Args:
        uri: Tracking URI.
        timeout_s: Seconds to wait for the health check.

    Returns:
        True when the store can be used.
    """
    if not uri.startswith(("http://", "https://")):
        return True
    try:
        with urllib.request.urlopen(
            f"{uri.rstrip('/')}/health", timeout=timeout_s
        ) as response:
            return bool(200 <= response.status < 300)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _metadata_params(metadata: RunMetadata) -> Dict[str, Any]:
    """
    Run metadata as MLflow params, without empty values.

    Args:
        metadata: Run metadata.

    Returns:
        Params dict.
    """
    params = metadata.model_dump(mode="json")
    return {key: value for key, value in params.items() if value is not None}


def log_report_to_mlflow(
    report: EvalReport,
    report_path: Path,
    *,
    tracking_uri: Optional[str] = None,
    artifact_location: Optional[str] = None,
    experiment_name: str = EVAL_EXPERIMENT,
    timeout_s: float = 3.0,
    tracker_factory: Optional[Callable[..., Any]] = None,
) -> Optional[str]:
    """
    Log one report as an MLflow run: tags, params, metrics, and the JSON file.

    Undefined metrics (None) are not logged. The process-wide MLflow
    tracking URI is restored afterwards. Any MLflow error is logged and
    swallowed, so a finished evaluation is never lost.

    Args:
        report: Report to log.
        report_path: Written JSON report, attached as an artifact.
        tracking_uri: Store to use; defaults to ``resolve_tracking_uri()``.
        artifact_location: Artifact root for a new experiment. Defaults to
            ``apps/backend-py/data/mlartifacts`` for the default SQLite store;
            a tracking server chooses its own.
        experiment_name: MLflow experiment.
        timeout_s: Seconds for the tracking server health check.
        tracker_factory: Creates the tracker; defaults to
            ``create_mlflow_tracker``.

    Returns:
        The MLflow run ID, or None when the run was not logged.
    """
    uri = tracking_uri or resolve_tracking_uri()
    if not tracking_server_reachable(uri, timeout_s=timeout_s):
        logger.warning("MLflow at %s is not reachable; run not logged.", uri)
        return None
    if artifact_location is None and uri == DEFAULT_TRACKING_URI:
        artifact_location = DEFAULT_ARTIFACT_DIR.as_uri()
    if uri.startswith("sqlite:///"):
        Path(uri[len("sqlite:///") :]).parent.mkdir(parents=True, exist_ok=True)

    if tracker_factory is None:
        from ..metrics.mlflow_tracker import create_mlflow_tracker

        tracker_factory = create_mlflow_tracker

    try:
        import mlflow

        previous_uri = mlflow.get_tracking_uri()
    except ImportError:
        logger.warning("MLflow is not installed; run not logged.")
        return None

    metadata = report.metadata
    try:
        tracker = tracker_factory(
            tracking_uri=uri,
            experiment_name=experiment_name,
            artifact_location=artifact_location,
        )
        if tracker is None:
            logger.warning("MLflow is not installed; run not logged.")
            return None
        run_id = tracker.start_run(
            run_name=f"{report.suite}-{report_path.stem}",
            tags={
                "suite": report.suite,
                "git_sha": metadata.git_sha,
                "git_dirty": str(metadata.git_dirty),
                "dataset_sha256": metadata.dataset_sha256,
            },
        )
        try:
            tracker.log_params(_metadata_params(metadata))
            tracker.log_metrics(
                {
                    key: value
                    for key, value in report.metrics.items()
                    if value is not None
                }
            )
            tracker.log_artifact(str(report_path))
        finally:
            tracker.end_run()
        return str(run_id)
    except Exception as exc:  # noqa: BLE001 - tracking must not fail the eval
        logger.warning("MLflow logging for %s failed: %s", report.suite, exc)
        return None
    finally:
        mlflow.set_tracking_uri(previous_uri)
