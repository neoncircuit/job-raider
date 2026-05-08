"""
Job Raider - GPU Monitor

This module provides GPU VRAM monitoring for Ollama local models.
Monitors NVIDIA GPUs via nvidia-smi and provides fallback logic.

Author: Job Raider
Date: 2026-04-20
"""

import subprocess
import re
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class GPUInfo:
    """Information about a GPU."""
    gpu_id: int
    name: str
    memory_total_mb: int
    memory_used_mb: int
    memory_free_mb: int
    utilization_percent: float
    temperature_celsius: Optional[float] = None

    @property
    def memory_usage_percent(self) -> float:
        """Return memory usage as a percentage."""
        if self.memory_total_mb == 0:
            return 0.0
        return (self.memory_used_mb / self.memory_total_mb)


class GPUMonitor:
    """
    GPU monitoring utility for tracking VRAM usage.

    Supports NVIDIA GPUs via nvidia-smi. Falls back gracefully
    if no GPU is available.
    """

    def __init__(self, vram_threshold: float = 0.9):
        """
        Initialize the GPU monitor.

        Args:
            vram_threshold: VRAM usage threshold (0.0-1.0) for triggering warnings
        """
        self.vram_threshold = vram_threshold
        self._has_nvidia_gpu = self._check_nvidia_gpu()
        self._gpu_count = 0
        self._gpu_info: Dict[int, GPUInfo] = {}

        if self._has_nvidia_gpu:
            self._initialize_gpus()

    def _check_nvidia_gpu(self) -> bool:
        """Check if NVIDIA GPU is available."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _initialize_gpus(self) -> None:
        """Initialize GPU information."""
        if not self._has_nvidia_gpu:
            return

        try:
            # Query all GPU information
            cmd = [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return

            # Parse output
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 6:
                    continue

                gpu_id = int(parts[0])
                self._gpu_info[gpu_id] = GPUInfo(
                    gpu_id=gpu_id,
                    name=parts[1],
                    memory_total_mb=int(parts[2]),
                    memory_used_mb=int(parts[3]),
                    memory_free_mb=int(parts[4]),
                    utilization_percent=float(parts[5]),
                    temperature_celsius=float(parts[6]) if len(parts) > 6 and parts[6] != "N/A" else None,
                )

            self._gpu_count = len(self._gpu_info)

        except (subprocess.TimeoutExpired, ValueError, IndexError) as e:
            print(f"Failed to initialize GPU info: {e}")

    def get_vram_usage(self, gpu_id: int = 0) -> float:
        """
        Get current VRAM usage for a specific GPU.

        Args:
            gpu_id: GPU ID to check (default: 0)

        Returns:
            VRAM usage as a percentage (0.0-1.0), or 0.0 if no GPU available
        """
        if not self._has_nvidia_gpu:
            return 0.0

        self._update_gpu_info()

        gpu_info = self._gpu_info.get(gpu_id)
        if not gpu_info:
            return 0.0

        return gpu_info.memory_usage_percent

    def get_vram_mb(self, gpu_id: int = 0) -> Tuple[int, int, int]:
        """
        Get VRAM information in MB.

        Args:
            gpu_id: GPU ID to check (default: 0)

        Returns:
            Tuple of (total_mb, used_mb, free_mb)
        """
        if not self._has_nvidia_gpu:
            return (0, 0, 0)

        self._update_gpu_info()

        gpu_info = self._gpu_info.get(gpu_id)
        if not gpu_info:
            return (0, 0, 0)

        return (
            gpu_info.memory_total_mb,
            gpu_info.memory_used_mb,
            gpu_info.memory_free_mb,
        )

    def get_all_gpu_info(self) -> List[GPUInfo]:
        """
        Get information for all available GPUs.

        Returns:
            List of GPUInfo objects
        """
        if not self._has_nvidia_gpu:
            return []

        self._update_gpu_info()
        return list(self._gpu_info.values())

    def _update_gpu_info(self) -> None:
        """Update GPU information with current values."""
        if not self._has_nvidia_gpu:
            return

        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=index,memory.used,memory.free,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return

            # Parse and update
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 4:
                    continue

                try:
                    gpu_id = int(parts[0])
                    if gpu_id in self._gpu_info:
                        self._gpu_info[gpu_id].memory_used_mb = int(parts[1])
                        self._gpu_info[gpu_id].memory_free_mb = int(parts[2])
                        self._gpu_info[gpu_id].utilization_percent = float(parts[3])
                        self._gpu_info[gpu_id].temperature_celsius = (
                            float(parts[4]) if len(parts) > 4 and parts[4] != "N/A" else None
                        )
                except (ValueError, IndexError):
                    continue

        except (subprocess.TimeoutExpired, ValueError, IndexError):
            pass

    def has_gpu(self) -> bool:
        """Check if a GPU is available."""
        return self._has_nvidia_gpu and self._gpu_count > 0

    def get_gpu_count(self) -> int:
        """Return the number of available GPUs."""
        return self._gpu_count

    def can_fit_model(self, required_vram_gb: float, gpu_id: int = 0) -> bool:
        """
        Check if a model can fit in GPU VRAM.

        Args:
            required_vram_gb: Required VRAM in GB
            gpu_id: GPU ID to check (default: 0)

        Returns:
            True if model can fit, False otherwise
        """
        if not self._has_nvidia_gpu:
            return False

        self._update_gpu_info()

        gpu_info = self._gpu_info.get(gpu_id)
        if not gpu_info:
            return False

        required_mb = int(required_vram_gb * 1024)
        available_mb = gpu_info.memory_total_mb - gpu_info.memory_used_mb

        # Add 10% buffer
        available_mb = int(available_mb * 0.9)

        return available_mb >= required_mb

    def print_gpu_status(self) -> None:
        """Print current GPU status to console."""
        if not self._has_nvidia_gpu:
            print("No NVIDIA GPU detected")
            return

        print(f"\n{'='*60}")
        print("GPU Status")
        print(f"{'='*60}")

        for gpu_info in self.get_all_gpu_info():
            print(f"\nGPU {gpu_info.gpu_id}: {gpu_info.name}")
            print(f"  Memory: {gpu_info.memory_used_mb} MB / {gpu_info.memory_total_mb} MB "
                  f"({gpu_info.memory_usage_percent:.1%})")
            print(f"  Utilization: {gpu_info.utilization_percent:.1f}%")
            if gpu_info.temperature_celsius:
                print(f"  Temperature: {gpu_info.temperature_celsius:.0f}°C")

            # Warn if approaching threshold
            if gpu_info.memory_usage_percent >= self.vram_threshold:
                print(f"  ⚠️  WARNING: VRAM usage exceeds {self.vram_threshold:.0%} threshold")

        print(f"{'='*60}\n")

    def recommend_model_size(self) -> str:
        """
        Recommend the maximum model size that can fit in available VRAM.

        Returns:
            String description of recommended model size
        """
        if not self._has_nvidia_gpu:
            return "No GPU available - use CPU inference (slower)"

        self._update_gpu_info()

        # Check first GPU
        gpu_info = self._gpu_info.get(0)
        if not gpu_info:
            return "No GPU available"

        available_gb = (gpu_info.memory_free_mb / 1024) * 0.9  # 90% of free memory

        if available_gb >= 16:
            return f"Can run models up to ~27B parameters ({available_gb:.1f} GB available)"
        elif available_gb >= 8:
            return f"Can run models up to ~14B parameters ({available_gb:.1f} GB available)"
        elif available_gb >= 4:
            return f"Can run models up to ~7B parameters ({available_gb:.1f} GB available)"
        elif available_gb >= 2:
            return f"Can run models up to ~3B parameters ({available_gb:.1f} GB available)"
        else:
            return f"Limited VRAM available ({available_gb:.1f} GB) - use CPU or smaller models"


# Singleton instance for easy access
_default_monitor: Optional[GPUMonitor] = None


def get_gpu_monitor(vram_threshold: float = 0.9) -> GPUMonitor:
    """
    Get the default GPU monitor instance.

    Args:
        vram_threshold: VRAM threshold for warnings

    Returns:
        GPUMonitor instance
    """
    global _default_monitor
    if _default_monitor is None:
        _default_monitor = GPUMonitor(vram_threshold=vram_threshold)
    return _default_monitor
