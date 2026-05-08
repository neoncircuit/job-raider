#!/usr/bin/env python3
"""
Job Raider - Check Ollama Models

This script checks which models are available in Ollama and can pull
the recommended models for the Job Raider pipeline.

Usage:
    python check_ollama_models.py
    python check_ollama_models.py --pull

Author: Job Raider
Date: 2026-04-20
"""

import argparse
import subprocess
import sys
from typing import List, Dict


# Recommended models for Job Raider (optimized for 16GB RAM + 8GB VRAM)
RECOMMENDED_MODELS = [
    {
        "name": "qwen2.5:3b",
        "description": "Small model for selection and scoring (~2 GB VRAM)",
        "required": True,
    },
    {
        "name": "qwen2.5:7b",
        "description": "Medium model for resume writing (~4 GB VRAM)",
        "required": True,
    },
    {
        "name": "gemma3:4b",
        "description": "Alternative small model (~2.5 GB VRAM)",
        "required": False,
    },
    {
        "name": "gemma3:12b",
        "description": "Alternative medium model (~7 GB VRAM)",
        "required": False,
    },
]


def is_ollama_running() -> bool:
    """Check if Ollama server is running."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_installed_models() -> List[str]:
    """Get list of installed models from Ollama."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        # Parse output (skip header line)
        lines = result.stdout.strip().split("\n")[1:]
        models = []
        for line in lines:
            if line.strip():
                # Model name is first column
                parts = line.split()
                if parts:
                    models.append(parts[0])

        return models

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def pull_model(model_name: str) -> bool:
    """
    Pull a model from Ollama library.

    Args:
        model_name: Name of model to pull

    Returns:
        True if successful, False otherwise
    """
    print(f"  Pulling {model_name}...")

    try:
        # Use ollama pull command
        result = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes timeout
        )

        if result.returncode == 0:
            print(f"  ✓ Successfully pulled {model_name}")
            return True
        else:
            print(f"  ✗ Failed to pull {model_name}")
            if result.stderr:
                print(f"    Error: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print(f"  ✗ Timed out pulling {model_name}")
        return False
    except FileNotFoundError:
        print(f"  ✗ ollama command not found. Is Ollama installed?")
        return False


def get_model_size(model_name: str) -> Dict[str, int]:
    """
    Get approximate model size information.

    Args:
        model_name: Name of the model

    Returns:
        Dictionary with vram_mb and ram_fallback_mb estimates
    """
    # Size estimates for 4-bit quantization
    size_map = {
        "qwen2.5:3b": {"vram_mb": 2048, "ram_mb": 3072},
        "qwen2.5:7b": {"vram_mb": 4096, "ram_mb": 7168},
        "gemma3:4b": {"vram_mb": 2560, "ram_mb": 4096},
        "gemma3:12b": {"vram_mb": 7168, "ram_mb": 12288},
        "qwen3:14b": {"vram_mb": 8192, "ram_mb": 14336},
        "gemma4:27b": {"vram_mb": 16384, "ram_mb": 27648},
    }

    return size_map.get(model_name, {"vram_mb": 0, "ram_mb": 0})


def print_gpu_status():
    """Print GPU status if available."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            print("\n" + "="*60)
            print("GPU Status:")
            print("="*60)
            for line in result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    print(f"  {parts[0]}")
                    print(f"    Total Memory: {parts[1]}")
                    print(f"    Free Memory:  {parts[2]}")
            print("="*60 + "\n")

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Check and manage Ollama models for Job Raider"
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Pull missing recommended models"
    )
    parser.add_argument(
        "--pull-all",
        action="store_true",
        help="Pull all recommended models (including optional ones)"
    )

    args = parser.parse_args()

    print("="*60)
    print("Job Raider - Ollama Model Checker")
    print("="*60)
    print()

    # Check if Ollama is running
    if not is_ollama_running():
        print("✗ Ollama is not running!")
        print()
        print("Please start Ollama:")
        print("  - On Linux/Mac: ollama serve")
        print("  - On Windows: ollama serve in WSL or terminal")
        print()
        print("Or install Ollama from: https://ollama.com/")
        sys.exit(1)

    print("✓ Ollama is running")
    print()

    # Get installed models
    installed_models = get_installed_models()

    if installed_models:
        print("Installed models:")
        for model in installed_models:
            size = get_model_size(model)
            vram_str = f"{size['vram_mb']} MB VRAM" if size['vram_mb'] > 0 else "Unknown size"
            print(f"  - {model} ({vram_str})")
    else:
        print("No models installed yet")
    print()

    # Check recommended models
    print("="*60)
    print("Recommended Models for Job Raider:")
    print("="*60)
    print()

    missing_required = []
    missing_optional = []

    for model_spec in RECOMMENDED_MODELS:
        model_name = model_spec["name"]
        description = model_spec["description"]
        required = model_spec["required"]

        is_installed = model_name in installed_models

        if is_installed:
            print(f"✓ {model_name}")
            print(f"  {description}")
        else:
            status = "REQUIRED" if required else "OPTIONAL"
            print(f"✗ {model_name} [{status}]")
            print(f"  {description}")

            if required:
                missing_required.append(model_name)
            else:
                missing_optional.append(model_name)

        print()

    # Print recommendations
    print("="*60)
    print("Summary:")
    print("="*60)
    print()

    if missing_required:
        print(f"Missing {len(missing_required)} required model(s):")
        for model in missing_required:
            print(f"  - {model}")
        print()

        if args.pull or args.pull_all:
            print("Pulling required models...")
            print()
            for model in missing_required:
                pull_model(model)
        else:
            print("Run with --pull to install missing required models:")
            print(f"  python {sys.argv[0]} --pull")

    if missing_optional and args.pull_all:
        print()
        print(f"Pulling {len(missing_optional)} optional model(s)...")
        print()
        for model in missing_optional:
            pull_model(model)

    print()
    if not missing_required:
        print("✓ All required models are installed!")
        print()
        print("You're ready to run Job Raider!")
    else:
        print(f"⚠ {len(missing_required)} required model(s) still missing")

    print()
    print_gpu_status()


if __name__ == "__main__":
    main()
