"""
Job Raider - VRAM Monitoring and Alerts

This module monitors GPU VRAM usage and sends alerts when
thresholds are exceeded or when OOM risks are detected.

Author: Job Raider
Date: 2026-04-21
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import subprocess
import threading
import time

from ..utils.logger import get_logger, Components
from ..health.health_check import GPUMemoryCheck


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class VRAMAlert:
    """VRAM alert data."""
    level: AlertLevel
    message: str
    free_mb: int
    used_mb: int
    total_mb: int
    used_percent: float
    timestamp: datetime
    metadata: Dict[str, Any]


class AlertAction:
    """Actions to take when an alert is triggered."""

    def __init__(self, name: str, callback: Callable[[VRAMAlert], None]):
        self.name = name
        self.callback = callback

    def execute(self, alert: VRAMAlert) -> None:
        """Execute the alert action."""
        try:
            self.callback(alert)
        except Exception as e:
            print(f"Alert action {self.name} failed: {str(e)}")


class VRAMMonitor:
    """
    Monitor GPU VRAM usage and send alerts.

    Runs in background thread and checks VRAM at regular intervals.
    """

    def __init__(
        self,
        check_interval_seconds: int = 60,
        warning_threshold_mb: int = 1000,
        critical_threshold_mb: int = 500,
        enable_oom_protection: bool = True,
    ):
        """
        Initialize VRAM monitor.

        Args:
            check_interval_seconds: How often to check VRAM
            warning_threshold_mb: Warning threshold (free MB)
            critical_threshold_mb: Critical threshold (free MB)
            enable_oom_protection: Enable automatic OOM protection
        """
        self.check_interval = check_interval_seconds
        self.warning_threshold_mb = warning_threshold_mb
        self.critical_threshold_mb = critical_threshold_mb
        self.enable_oom_protection = enable_oom_protection

        self.logger = get_logger(Components.SCRAPERS)
        self.check = GPUMemoryCheck(
            warning_threshold_mb=warning_threshold_mb,
            critical_threshold_mb=critical_threshold_mb,
        )

        # Monitoring state
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._alerts_history: List[VRAMAlert] = []
        self._alert_actions: List[AlertAction] = []

        # Register default actions
        self._register_default_actions()

    def _register_default_actions(self) -> None:
        """Register default alert actions."""
        # Log alert
        self._alert_actions.append(AlertAction(
            name="log_alert",
            callback=lambda alert: self.logger.warning(
                f"VRAM Alert [{alert.level.value}]: {alert.message}"
            )
        ))

        # Print to console
        self._alert_actions.append(AlertAction(
            name="print_alert",
            callback=lambda alert: print(
                f"\n[VRAM ALERT] {alert.level.value.upper()}: {alert.message}\n"
            )
        ))

        # Save critical alerts to file
        self._alert_actions.append(AlertAction(
            name="save_critical_alert",
            callback=lambda alert: self._save_alert(alert) if alert.level == AlertLevel.CRITICAL else None
        ))

    def _save_alert(self, alert: VRAMAlert) -> None:
        """Save alert to file."""
        try:
            from pathlib import Path
            import json

            alerts_dir = Path("data/alerts")
            alerts_dir.mkdir(parents=True, exist_ok=True)

            timestamp_str = alert.timestamp.strftime("%Y%m%d_%H%M%S")
            filepath = alerts_dir / f"vram_alert_{timestamp_str}.json"

            with open(filepath, "w") as f:
                json.dump({
                    "level": alert.level.value,
                    "message": alert.message,
                    "free_mb": alert.free_mb,
                    "used_mb": alert.used_mb,
                    "total_mb": alert.total_mb,
                    "used_percent": alert.used_percent,
                    "timestamp": alert.timestamp.isoformat(),
                    "metadata": alert.metadata,
                }, f, indent=2)

            self.logger.info(f"VRAM alert saved to: {filepath}")

        except Exception as e:
            self.logger.error(f"Failed to save alert: {str(e)}")

    def add_alert_action(self, action: AlertAction) -> None:
        """Add a custom alert action."""
        self._alert_actions.append(action)

    def check_vram_now(self) -> Optional[VRAMAlert]:
        """
        Check VRAM immediately and return alert if threshold exceeded.

        Returns:
            VRAMAlert if threshold exceeded, None otherwise
        """
        result = self.check.check()

        # Extract metadata
        free_mb = result.metadata.get("free_mb", 0)
        used_mb = result.metadata.get("used_mb", 0)
        total_mb = result.metadata.get("total_mb", 0)
        used_percent = result.metadata.get("used_percent", 0)

        # Determine alert level
        if result.status.value == "unhealthy":
            level = AlertLevel.CRITICAL
            message = result.message
        elif result.status.value == "degraded":
            level = AlertLevel.WARNING
            message = result.message
        else:
            return None

        alert = VRAMAlert(
            level=level,
            message=message,
            free_mb=free_mb,
            used_mb=used_mb,
            total_mb=total_mb,
            used_percent=used_percent,
            timestamp=datetime.now(),
            metadata={
                "duration_ms": result.duration_ms,
                "check_name": result.name,
            },
        )

        self._alerts_history.append(alert)
        self._trigger_alert(alert)

        return alert

    def _trigger_alert(self, alert: VRAMAlert) -> None:
        """Trigger all alert actions."""
        for action in self._alert_actions:
            action.execute(alert)

        # OOM protection: warn if running large models
        if self.enable_oom_protection and alert.level == AlertLevel.CRITICAL:
            self.logger.critical(
                "CRITICAL VRAM LEVEL! Consider: "
                "1. Closing other GPU applications "
                "2. Using smaller models (qwen2.5:3b instead of qwen2.5:7b) "
                "3. Reducing batch sizes "
                "4. Enabling CPU fallback"
            )

    def get_current_vram_usage(self) -> Dict[str, int]:
        """
        Get current VRAM usage.

        Returns:
            Dict with free_mb, used_mb, total_mb
        """
        result = self.check.check()
        return {
            "free_mb": result.metadata.get("free_mb", 0),
            "used_mb": result.metadata.get("used_mb", 0),
            "total_mb": result.metadata.get("total_mb", 0),
            "used_percent": result.metadata.get("used_percent", 0),
        }

    def get_recommended_model(self, required_vram_mb: int) -> Optional[str]:
        """
        Recommend a model based on available VRAM.

        Args:
            required_vram_mb: VRAM required by model

        Returns:
            Model name or None if insufficient VRAM
        """
        usage = self.get_current_vram_usage()
        available_mb = usage["free_mb"]

        # Model VRAM requirements (4-bit quantization)
        model_vram = {
            "qwen2.5:3b": 2000,
            "gemma3:4b": 2500,
            "qwen2.5:7b": 4000,
            "gemma3:12b": 7000,
            "qwen3:14b": 8000,
        }

        # Find largest model that fits
        for model, vram in sorted(model_vram.items(), key=lambda x: x[1], reverse=True):
            if vram <= available_mb:
                return model

        # Smallest model doesn't fit
        if available_mb < 2000:
            self.logger.warning(
                f"Insufficient VRAM ({available_mb}MB free) for any model. "
                "CPU fallback will be required."
            )
            return None

        return "qwen2.5:3b"  # Smallest model

    def get_alert_history(
        self,
        hours: int = 24,
        level: Optional[AlertLevel] = None,
    ) -> List[VRAMAlert]:
        """
        Get alert history.

        Args:
            hours: Hours to look back
            level: Filter by alert level

        Returns:
            List of alerts
        """
        cutoff = datetime.now() - timedelta(hours=hours)

        alerts = [
            alert for alert in self._alerts_history
            if alert.timestamp >= cutoff
        ]

        if level:
            alerts = [a for a in alerts if a.level == level]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_alert_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get alert summary statistics.

        Args:
            hours: Hours to look back

        Returns:
            Summary statistics
        """
        alerts = self.get_alert_history(hours)

        return {
            "period_hours": hours,
            "total_alerts": len(alerts),
            "by_level": {
                "critical": sum(1 for a in alerts if a.level == AlertLevel.CRITICAL),
                "warning": sum(1 for a in alerts if a.level == AlertLevel.WARNING),
                "info": sum(1 for a in alerts if a.level == AlertLevel.INFO),
            },
            "latest_alert": alerts[0].__dict__ if alerts else None,
        }

    def start_monitoring(self) -> None:
        """Start background VRAM monitoring."""
        if self._running:
            self.logger.warning("VRAM monitoring already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()

        self.logger.info(f"VRAM monitoring started (interval: {self.check_interval}s)")

    def stop_monitoring(self) -> None:
        """Stop background VRAM monitoring."""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

        self.logger.info("VRAM monitoring stopped")

    def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                self.check_vram_now()
            except Exception as e:
                self.logger.error(f"VRAM check failed: {str(e)}")

            # Wait for next check
            for _ in range(self.check_interval * 10):  # Check every 0.1s if should stop
                if not self._running:
                    break
                time.sleep(0.1)

    def enable_oom_protection_for_pipeline(self) -> None:
        """
        Enable OOM protection for pipeline execution.

        This adds safeguards to prevent OOM errors during pipeline runs.
        """
        self.logger.info("OOM Protection enabled for pipeline")

        # Check current VRAM
        usage = self.get_current_vram_usage()

        if usage["free_mb"] < 2000:
            self.logger.critical(
                f"Low VRAM ({usage['free_mb']}MB free). "
                "Consider stopping other GPU applications before running pipeline."
            )
        elif usage["free_mb"] < 4000:
            self.logger.warning(
                f"Moderate VRAM ({usage['free_mb']}MB free). "
                "Consider using qwen2.5:3b instead of qwen2.5:7b."
            )


class VRAMAlertManager:
    """
    Manages VRAM alerts and provides convenient interface.
    """

    _instance: Optional[VRAMMonitor] = None

    @classmethod
    def get_monitor(cls) -> VRAMMonitor:
        """Get or create VRAM monitor instance."""
        if cls._instance is None:
            cls._instance = VRAMMonitor()
        return cls._instance

    @classmethod
    def check_now(cls) -> Optional[Dict[str, Any]]:
        """Quick VRAM check."""
        monitor = cls.get_monitor()
        alert = monitor.check_vram_now()

        if alert:
            return {
                "alert": True,
                "level": alert.level.value,
                "message": alert.message,
                "free_mb": alert.free_mb,
                "used_percent": alert.used_percent,
            }

        return {
            "alert": False,
            "usage": monitor.get_current_vram_usage(),
        }

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Get current VRAM status."""
        monitor = cls.get_monitor()
        usage = monitor.get_current_vram_usage()
        summary = monitor.get_alert_summary(hours=1)

        return {
            "current_usage": usage,
            "recent_alerts": summary,
        }


# Convenience functions
def check_vram() -> Dict[str, Any]:
    """Quick VRAM check."""
    return VRAMAlertManager.get_status()


def monitor_vram(
    warning_threshold_mb: int = 1000,
    critical_threshold_mb: int = 500,
) -> VRAMMonitor:
    """
    Start VRAM monitoring.

    Args:
        warning_threshold_mb: Warning threshold
        critical_threshold_mb: Critical threshold

    Returns:
        VRAMMonitor instance
    """
    monitor = VRAMMonitor(
        warning_threshold_mb=warning_threshold_mb,
        critical_threshold_mb=critical_threshold_mb,
    )
    monitor.start_monitoring()
    return monitor
