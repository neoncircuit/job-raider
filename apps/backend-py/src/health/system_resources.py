"""
Job Raider - System resource snapshot

Lightweight CPU / RAM / GPU readings for the sidebar resource meter.
Uses psutil when available, with /proc fallbacks on Linux. GPU data comes
from nvidia-smi via GPUMonitor.

Author: Job Raider
Date: 2026-07-24
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from src.llm.gpu_monitor import get_gpu_monitor


def _cpu_percent() -> Optional[float]:
    """
    Return current CPU utilization percentage.

    Returns:
        CPU percent in ``[0, 100]``, or ``None`` if unavailable.
    """
    try:
        import psutil

        # Non-blocking after the first call; interval=None uses last cached delta.
        value = psutil.cpu_percent(interval=None)
        if value == 0.0:
            value = psutil.cpu_percent(interval=0.05)
        return round(float(value), 1)
    except Exception:
        pass

    try:
        load1, _, _ = os.getloadavg()
        cpus = os.cpu_count() or 1
        return round(min(100.0, (load1 / cpus) * 100.0), 1)
    except (AttributeError, OSError):
        return None


def _ram_stats() -> Dict[str, Optional[float]]:
    """
    Return RAM used/total/percent.

    Returns:
        Dict with ``used_mb``, ``total_mb``, and ``percent`` (nullable floats).
    """
    try:
        import psutil

        mem = psutil.virtual_memory()
        return {
            "used_mb": round(mem.used / (1024 * 1024), 1),
            "total_mb": round(mem.total / (1024 * 1024), 1),
            "percent": round(float(mem.percent), 1),
        }
    except Exception:
        pass

    try:
        info: Dict[str, int] = {}
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                key, _, raw = line.partition(":")
                info[key] = int(raw.strip().split()[0])
        total_kb = info.get("MemTotal", 0)
        available_kb = info.get("MemAvailable", info.get("MemFree", 0))
        used_kb = max(0, total_kb - available_kb)
        percent = (used_kb / total_kb) * 100.0 if total_kb else 0.0
        return {
            "used_mb": round(used_kb / 1024, 1),
            "total_mb": round(total_kb / 1024, 1),
            "percent": round(percent, 1),
        }
    except (OSError, ValueError, ZeroDivisionError):
        return {"used_mb": None, "total_mb": None, "percent": None}


def _gpu_stats() -> Optional[Dict[str, Any]]:
    """
    Return primary GPU utilization and VRAM usage when NVIDIA is available.

    Returns:
        GPU stats dict, or ``None`` when no GPU is detected.
    """
    monitor = get_gpu_monitor()
    if not monitor.has_gpu():
        return None

    gpus = monitor.get_all_gpu_info()
    if not gpus:
        return None

    primary = gpus[0]
    return {
        "name": primary.name,
        "utilization_percent": round(primary.utilization_percent, 1),
        "memory_used_mb": primary.memory_used_mb,
        "memory_total_mb": primary.memory_total_mb,
        "memory_percent": round(primary.memory_usage_percent * 100.0, 1),
        "temperature_celsius": primary.temperature_celsius,
    }


def get_system_resources() -> Dict[str, Any]:
    """
    Collect a point-in-time snapshot of local host resources.

    Returns:
        Dict with ``cpu``, ``ram``, and ``gpu`` sections suitable for JSON APIs.
    """
    ram = _ram_stats()
    return {
        "cpu": {"percent": _cpu_percent()},
        "ram": ram,
        "gpu": _gpu_stats(),
    }
