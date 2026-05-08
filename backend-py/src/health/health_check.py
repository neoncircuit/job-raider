"""
Job Raider - Health Check Module

This module provides health check functionality for monitoring
the status of services, dependencies, and system resources.

Author: Job Raider
Date: 2026-04-21
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import subprocess
import json
import os
from pathlib import Path

from ..utils.logger import get_logger, Components


class HealthStatus(str, Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    metadata: Dict[str, Any]
    timestamp: datetime


class HealthCheck:
    """Base class for health checks."""

    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(Components.SCRAPERS)

    def check(self) -> HealthCheckResult:
        """
        Perform the health check.

        Returns:
            HealthCheckResult with check outcome
        """
        raise NotImplementedError


class DiskSpaceCheck(HealthCheck):
    """Check available disk space."""

    def __init__(self, path: str = ".", warning_threshold_gb: int = 10, critical_threshold_gb: int = 5):
        super().__init__("disk_space")
        self.path = path
        self.warning_threshold_gb = warning_threshold_gb
        self.critical_threshold_gb = critical_threshold_gb

    def check(self) -> HealthCheckResult:
        start = datetime.now()

        try:
            import shutil
            total, used, free = shutil.disk_usage(self.path)

            free_gb = free / (1024 ** 3)
            used_percent = (used / total) * 100

            if free_gb < self.critical_threshold_gb:
                status = HealthStatus.UNHEALTHY
                message = f"Critical: Only {free_gb:.1f}GB free ({used_percent:.1f}% used)"
            elif free_gb < self.warning_threshold_gb:
                status = HealthStatus.DEGRADED
                message = f"Warning: {free_gb:.1f}GB free ({used_percent:.1f}% used)"
            else:
                status = HealthStatus.HEALTHY
                message = f"{free_gb:.1f}GB free ({used_percent:.1f}% used)"

            duration = (datetime.now() - start).total_seconds() * 1000

            return HealthCheckResult(
                name=self.name,
                status=status,
                message=message,
                duration_ms=duration,
                metadata={
                    "path": self.path,
                    "free_gb": round(free_gb, 2),
                    "used_percent": round(used_percent, 2),
                    "total_gb": round(total / (1024 ** 3), 2),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check disk space: {str(e)}",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={},
                timestamp=datetime.now(),
            )


class GPUMemoryCheck(HealthCheck):
    """Check GPU memory usage."""

    def __init__(self, warning_threshold_mb: int = 1000, critical_threshold_mb: int = 500):
        super().__init__("gpu_memory")
        self.warning_threshold_mb = warning_threshold_mb
        self.critical_threshold_mb = critical_threshold_mb

    def check(self) -> HealthCheckResult:
        start = datetime.now()

        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.free,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNKNOWN,
                    message="nvidia-smi not available or GPU not detected",
                    duration_ms=(datetime.now() - start).total_seconds() * 1000,
                    metadata={"error": "GPU not available"},
                    timestamp=datetime.now(),
                )

            # Parse output
            lines = result.stdout.strip().split("\n")
            if not lines:
                raise ValueError("No GPU data returned")

            parts = lines[0].split(",")
            if len(parts) < 2:
                raise ValueError("Unexpected GPU data format")

            free_mb = int(parts[0].strip())
            total_mb = int(parts[1].strip())
            used_mb = total_mb - free_mb
            used_percent = (used_mb / total_mb) * 100

            if free_mb < self.critical_threshold_mb:
                status = HealthStatus.UNHEALTHY
                message = f"Critical: Only {free_mb}MB free ({used_percent:.1f}% used)"
            elif free_mb < self.warning_threshold_mb:
                status = HealthStatus.DEGRADED
                message = f"Warning: {free_mb}MB free ({used_percent:.1f}% used)"
            else:
                status = HealthStatus.HEALTHY
                message = f"{free_mb}MB free ({used_percent:.1f}% used)"

            duration = (datetime.now() - start).total_seconds() * 1000

            return HealthCheckResult(
                name=self.name,
                status=status,
                message=message,
                duration_ms=duration,
                metadata={
                    "free_mb": free_mb,
                    "used_mb": used_mb,
                    "total_mb": total_mb,
                    "used_percent": round(used_percent, 2),
                },
                timestamp=datetime.now(),
            )

        except FileNotFoundError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="nvidia-smi not found (GPU monitoring unavailable)",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"gpu_available": False},
                timestamp=datetime.now(),
            )
        except subprocess.TimeoutExpired:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="nvidia-smi timeout",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"error": "timeout"},
                timestamp=datetime.now(),
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check GPU: {str(e)}",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"error": str(e)},
                timestamp=datetime.now(),
            )


class OllamaHealthCheck(HealthCheck):
    """Check Ollama service availability."""

    def __init__(self, base_url: str | None = None):
        super().__init__("ollama")
        import os
        self.base_url = base_url or f"http://{os.getenv('OLLAMA_HOST', 'localhost:11434')}"

    def check(self) -> HealthCheckResult:
        start = datetime.now()

        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)

            if response.status_code == 200:
                models = response.json().get("models", [])
                status = HealthStatus.HEALTHY
                message = f"Ollama running, {len(models)} models available"

                return HealthCheckResult(
                    name=self.name,
                    status=status,
                    message=message,
                    duration_ms=(datetime.now() - start).total_seconds() * 1000,
                    metadata={
                        "base_url": self.base_url,
                        "models": [m.get("name", "unknown") for m in models[:5]],
                        "total_models": len(models),
                    },
                    timestamp=datetime.now(),
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Ollama returned status {response.status_code}",
                    duration_ms=(datetime.now() - start).total_seconds() * 1000,
                    metadata={"status_code": response.status_code},
                    timestamp=datetime.now(),
                )

        except requests.exceptions.ConnectionError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="Ollama not running or not accessible",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"base_url": self.base_url, "error": "connection refused"},
                timestamp=datetime.now(),
            )
        except requests.exceptions.Timeout:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="Ollama request timeout",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"error": "timeout"},
                timestamp=datetime.now(),
            )
        except ImportError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="requests library not available",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"error": "missing dependency"},
                timestamp=datetime.now(),
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check Ollama: {str(e)}",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"error": str(e)},
                timestamp=datetime.now(),
            )


class DataDirectoryCheck(HealthCheck):
    """Check data directories exist and are writable."""

    def __init__(self, base_dir: str = "data"):
        super().__init__("data_directories")
        self.base_dir = Path(base_dir)

        # Expected subdirectories
        self.expected_dirs = [
            "listings",
            "cache",
            "results",
            "applications",
            "metrics",
        ]

    def check(self) -> HealthCheckResult:
        start = datetime.now()

        try:
            issues = []
            existing_dirs = []

            # Check base directory
            if not self.base_dir.exists():
                issues.append(f"Base directory {self.base_dir} does not exist")
            else:
                # Check subdirectories
                for dir_name in self.expected_dirs:
                    dir_path = self.base_dir / dir_name
                    if dir_path.exists():
                        existing_dirs.append(dir_name)
                        # Check if writable
                        if not os.access(dir_path, os.W_OK):
                            issues.append(f"{dir_name} is not writable")
                    else:
                        issues.append(f"{dir_name} does not exist")

            if issues:
                status = HealthStatus.DEGRADED if len(existing_dirs) > 0 else HealthStatus.UNHEALTHY
                message = f"Issues found: {', '.join(issues[:3])}"
            else:
                status = HealthStatus.HEALTHY
                message = f"All {len(self.expected_dirs)} directories exist and are writable"

            duration = (datetime.now() - start).total_seconds() * 1000

            return HealthCheckResult(
                name=self.name,
                status=status,
                message=message,
                duration_ms=duration,
                metadata={
                    "base_dir": str(self.base_dir),
                    "existing_dirs": existing_dirs,
                    "issues": issues,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check directories: {str(e)}",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"error": str(e)},
                timestamp=datetime.now(),
            )


class ConfigurationCheck(HealthCheck):
    """Check configuration files exist and are valid."""

    def __init__(self, config_dir: str = "config"):
        super().__init__("configuration")
        self.config_dir = Path(config_dir)

        self.required_configs = [
            "model_config.yaml",
            "prompt_templates.yaml",
            "scoring_config.yaml",
            "logging_config.yaml",
        ]

    def check(self) -> HealthCheckResult:
        start = datetime.now()

        try:
            missing = []
            valid = []

            for config_file in self.required_configs:
                config_path = self.config_dir / config_file
                if config_path.exists():
                    # Try to parse YAML
                    try:
                        import yaml
                        with open(config_path, "r") as f:
                            yaml.safe_load(f)
                        valid.append(config_file)
                    except Exception as e:
                        missing.append(f"{config_file} (invalid: {str(e)[:30]})")
                else:
                    missing.append(config_file)

            if missing:
                status = HealthStatus.DEGRADED if valid else HealthStatus.UNHEALTHY
                message = f"Missing/invalid configs: {', '.join(missing[:3])}"
            else:
                status = HealthStatus.HEALTHY
                message = f"All {len(self.required_configs)} configs valid"

            duration = (datetime.now() - start).total_seconds() * 1000

            return HealthCheckResult(
                name=self.name,
                status=status,
                message=message,
                duration_ms=duration,
                metadata={
                    "valid_configs": valid,
                    "missing_configs": missing,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message=f"Failed to check configs: {str(e)}",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"error": str(e)},
                timestamp=datetime.now(),
            )


class ChromaDBHealthCheck(HealthCheck):
    """Check ChromaDB vector store health."""

    def __init__(self, persist_directory: str = "data/chroma"):
        super().__init__("chromadb")
        self.persist_directory = persist_directory

    def check(self) -> HealthCheckResult:
        start = datetime.now()

        try:
            from ..rag.vector_store import ChromaStore
            from ..rag.config import VectorStoreConfig

            config = VectorStoreConfig(persist_directory=self.persist_directory)
            store = ChromaStore(config)
            store.initialize()

            health = store.health_check()
            status = HealthStatus.HEALTHY if health["status"] == "healthy" else HealthStatus.DEGRADED
            message = f"ChromaDB {health['status']}, collections: {list(health.get('collections', {}).keys())}"

            return HealthCheckResult(
                name=self.name,
                status=status,
                message=message,
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata=health,
                timestamp=datetime.now(),
            )

        except ImportError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                message="chromadb package not installed",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"error": "import failed"},
                timestamp=datetime.now(),
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                message=f"ChromaDB check failed: {str(e)[:80]}",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"error": str(e)},
                timestamp=datetime.now(),
            )


class EmbeddingModelHealthCheck(HealthCheck):
    """Check if the embedding model is loaded in Ollama."""

    def __init__(self, model: str = "nomic-embed-text", base_url: str | None = None):
        super().__init__("embedding_model")
        self.model = model
        import os
        self.base_url = base_url or f"http://{os.getenv('OLLAMA_HOST', 'localhost:11434')}"

    def check(self) -> HealthCheckResult:
        start = datetime.now()

        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]

            available = self.model in models or f"{self.model}:latest" in models

            if available:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message=f"Embedding model '{self.model}' loaded",
                    duration_ms=(datetime.now() - start).total_seconds() * 1000,
                    metadata={"model": self.model},
                    timestamp=datetime.now(),
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=f"Embedding model '{self.model}' not loaded. Pull with: ollama pull {self.model}",
                    duration_ms=(datetime.now() - start).total_seconds() * 1000,
                    metadata={"model": self.model, "available_models": models[:5]},
                    timestamp=datetime.now(),
                )

        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message=f"Cannot check embedding model: {str(e)[:80]}",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"error": str(e)},
                timestamp=datetime.now(),
            )


class MLflowHealthCheck(HealthCheck):
    """Check MLflow tracking server availability."""

    def __init__(self, tracking_uri: str | None = None):
        """
        Initialize MLflow health check.

        Args:
            tracking_uri: MLflow tracking server URI. Defaults to config or localhost.
        """
        super().__init__("mlflow")
        import os
        self.tracking_uri = tracking_uri or os.getenv(
            "MLFLOW_TRACKING_URI", "http://localhost:5000"
        )

    def check(self) -> HealthCheckResult:
        """
        Check if MLflow tracking server is reachable.

        Returns:
            HealthCheckResult indicating server status
        """
        start = datetime.now()

        try:
            import requests
            response = requests.get(f"{self.tracking_uri}/health", timeout=5)

            if response.status_code == 200:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="MLflow tracking server is reachable",
                    duration_ms=(datetime.now() - start).total_seconds() * 1000,
                    metadata={"tracking_uri": self.tracking_uri},
                    timestamp=datetime.now(),
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=f"MLflow returned status {response.status_code}",
                    duration_ms=(datetime.now() - start).total_seconds() * 1000,
                    metadata={"tracking_uri": self.tracking_uri, "status_code": response.status_code},
                    timestamp=datetime.now(),
                )

        except ImportError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="MLflow package not installed",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={},
                timestamp=datetime.now(),
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.DEGRADED,
                message=f"MLflow server unreachable: {str(e)[:80]}",
                duration_ms=(datetime.now() - start).total_seconds() * 1000,
                metadata={"tracking_uri": self.tracking_uri, "error": str(e)},
                timestamp=datetime.now(),
            )


class HealthMonitor:
    """
    Monitor health of the Job Raider system.

    Runs multiple health checks and aggregates results.
    """

    def __init__(self):
        """Initialize the health monitor."""
        self.logger = get_logger(Components.SCRAPERS)
        self.checks: List[HealthCheck] = []
        self.register_default_checks()

    def register_default_checks(self) -> None:
        """Register default health checks."""
        import shutil

        self.checks = [
            DiskSpaceCheck(),
            OllamaHealthCheck(),
            DataDirectoryCheck(),
            ConfigurationCheck(),
        ]

        if shutil.which("nvidia-smi"):
            self.checks.append(GPUMemoryCheck())

        # RAG health checks (graceful if chromadb not installed)
        try:
            import chromadb  # noqa: F401
            self.checks.append(ChromaDBHealthCheck())
            self.checks.append(EmbeddingModelHealthCheck())
        except ImportError:
            pass

        # MLflow health check (graceful if mlflow not installed)
        try:
            import mlflow  # noqa: F401
            self.checks.append(MLflowHealthCheck())
        except ImportError:
            pass

    def register_check(self, check: HealthCheck) -> None:
        """Register a custom health check."""
        self.checks.append(check)

    def run_checks(self) -> List[HealthCheckResult]:
        """Run all health checks."""
        results = []

        for check in self.checks:
            try:
                result = check.check()
                results.append(result)
            except Exception as e:
                self.logger.error(f"Health check {check.name} failed: {str(e)}")
                results.append(HealthCheckResult(
                    name=check.name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(e)}",
                    duration_ms=0,
                    metadata={"error": str(e)},
                    timestamp=datetime.now(),
                ))

        return results

    def get_overall_status(self, results: List[HealthCheckResult]) -> HealthStatus:
        """Determine overall health status from results."""
        if not results:
            return HealthStatus.UNKNOWN

        # If any are unhealthy, overall is unhealthy
        if any(r.status == HealthStatus.UNHEALTHY for r in results):
            return HealthStatus.UNHEALTHY

        # If any are degraded, overall is degraded
        if any(r.status == HealthStatus.DEGRADED for r in results):
            return HealthStatus.DEGRADED

        # If any are unknown, overall is degraded (not fully healthy)
        if any(r.status == HealthStatus.UNKNOWN for r in results):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report."""
        results = self.run_checks()
        overall_status = self.get_overall_status(results)

        return {
            "status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "checks": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "duration_ms": r.duration_ms,
                    "metadata": r.metadata,
                }
                for r in results
            ],
            "summary": {
                "total": len(results),
                "healthy": sum(1 for r in results if r.status == HealthStatus.HEALTHY),
                "degraded": sum(1 for r in results if r.status == HealthStatus.DEGRADED),
                "unhealthy": sum(1 for r in results if r.status == HealthStatus.UNHEALTHY),
                "unknown": sum(1 for r in results if r.status == HealthStatus.UNKNOWN),
            },
        }

    def print_report(self) -> None:
        """Print health report to console."""
        report = self.get_health_report()

        status_symbol = {
            HealthStatus.HEALTHY: "✓",
            HealthStatus.DEGRADED: "⚠",
            HealthStatus.UNHEALTHY: "✗",
            HealthStatus.UNKNOWN: "?",
        }

        print("\n" + "="*60)
        print("Job Raider - Health Check")
        print("="*60)
        print(f"\nOverall Status: {report['status'].upper()}")
        print(f"Timestamp: {report['timestamp']}")

        print("\nChecks:")
        for check in report["checks"]:
            symbol = status_symbol.get(check["status"], "?")
            print(f"  [{symbol}] {check['name']}: {check['message']}")
            if check["metadata"]:
                for key, value in check["metadata"].items():
                    if key not in ["error", "base_url"]:
                        print(f"      {key}: {value}")

        print(f"\nSummary: {report['summary']['healthy']}/{report['summary']['total']} healthy")
        print("="*60 + "\n")

    def save_report(self, filepath: str) -> None:
        """Save health report to file."""
        report = self.get_health_report()

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)

        self.logger.info(f"Health report saved to: {filepath}")


# Convenience function
def check_health() -> Dict[str, Any]:
    """Quick health check function."""
    monitor = HealthMonitor()
    return monitor.get_health_report()
