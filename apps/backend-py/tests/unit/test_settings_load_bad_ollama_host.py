"""
Step 2 review R3: a stored ollama_host outside the allowlist must not drop settings.
"""

from __future__ import annotations

import json
import logging

from src.api.settings import get_storage


def test_load_replaces_bad_ollama_host_and_keeps_other_fields(caplog) -> None:
    """
    Load a file with a disallowed host; keep keys and routing; default the host.

    Uses the R6-isolated ``get_storage()`` temporary directory.

    Args:
        caplog: Pytest log capture.

    Returns:
        None.
    """
    storage = get_storage()
    payload = {
        "routing": {
            "selection": {
                "task_type": "selection",
                "primary_provider": "ollama",
                "primary_model": "custom-kept:1b",
                "fallback_provider": None,
                "fallback_model": None,
            }
        },
        "api_config": {
            "anthropic_api_key": "test-key",
            "gemini_api_key": None,
            "cloud_fallback_provider": "none",
            "ollama_host": "192.168.1.5:11434",
        },
        "model_params": {
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 0.9,
            "top_k": 40,
        },
        "cost_limits": {
            "max_api_cost_per_run": 5.0,
            "enable_cache": True,
            "cache_ttl": 3600,
            "max_concurrent_requests": 2,
            "enable_jd_llm_extract": False,
            "enable_company_mission": False,
            "enable_prompt_cache": False,
            "ollama_keep_alive": None,
        },
        "version": "1.0",
    }
    storage.settings_file.write_text(json.dumps(payload), encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        loaded = storage.load_settings()

    assert loaded.api_config.ollama_host == "host.docker.internal:11434"
    assert loaded.api_config.anthropic_api_key == "test-key"
    assert loaded.routing["selection"].primary_model == "custom-kept:1b"
    assert any(
        "ollama_host" in record.getMessage() and "192.168.1.5" in record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.WARNING
    )
