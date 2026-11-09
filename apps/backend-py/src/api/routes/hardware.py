"""
Job Raider - Hardware Fit Routes

``GET /api/hardware/fit`` tells which installed Ollama models fit the user's
safety budget of GPU memory, and suggests models to pull. llmfit is optional:
without it, the report says so and gives an install hint.
"""

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from ...hardware import service as hardware_service
from ...hardware.service import HardwareFitReport
from .. import ollama_admin
from ..ollama_models import resolve_effective_ollama_host
from ..settings import get_storage

router = APIRouter()


@router.get("/fit", response_model=HardwareFitReport)
async def hardware_fit(refresh: bool = False) -> HardwareFitReport:
    """
    Get the hardware fit report.

    The first call runs llmfit and can take several seconds. Later calls use
    the cache for 10 minutes, unless ``refresh`` is true.

    Args:
        refresh: True to run llmfit again instead of using the cache.

    Returns:
        The hardware, the safety budget, a label for each installed model,
        and suggestions.
    """
    settings = get_storage().load_settings()
    host = resolve_effective_ollama_host(settings.api_config.ollama_host)
    listing = await run_in_threadpool(ollama_admin.list_models, host, set())
    return await run_in_threadpool(
        hardware_service.get_fit_service().report,
        settings.hardware.vram_headroom_percent,
        listing["models"],
        bool(listing["reachable"]),
        refresh,
    )
