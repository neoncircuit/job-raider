"""
Tests for the hardware fit service, its route, and the pull warning
(Step 6, MH-3).

A stub client stands in for llmfit, with made-up hardware (8 GB of VRAM, so
the default budget is 6 GB).
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api import ollama_admin
from src.hardware import service as hardware_service
from src.hardware.fit import FitLabel, FitSource
from src.hardware.llmfit_client import (
    CatalogModel,
    HardwareProfile,
    LlmfitUnavailable,
    QuantPlan,
)
from src.hardware.service import (
    INSTALL_HINT,
    HardwareFitService,
    quant_from_tag,
)

PLAN_NEEDS = {
    ("example/Chat-7B", "Q4_K_M"): 5.35,
    ("example/Reason-8B", "Q4_K_M"): 6.2,
    ("example/Big-14B", "Q4_K_M"): 10.6,
}

CATALOG = [
    CatalogModel(
        name="example/Chat-7B",
        ollama_name="examplechat:7b",
        runtime="llama.cpp",
        best_quant="Q4_K_M",
        memory_required_gb=5.3,
        score=80.0,
        params_b=7.0,
    ),
    CatalogModel(
        name="example/Reason-8B",
        ollama_name="examplereason:8b",
        runtime="llama.cpp",
        best_quant="Q4_K_M",
        memory_required_gb=5.9,
        score=85.0,
        params_b=8.0,
    ),
    CatalogModel(
        name="example/Big-14B",
        ollama_name="examplebig:14b",
        runtime="llama.cpp",
        best_quant="Q2_K",
        memory_required_gb=5.8,
        score=70.0,
        params_b=14.0,
    ),
    CatalogModel(
        name="example/Small-3B",
        ollama_name="examplesmall:3b",
        runtime="llama.cpp",
        best_quant="Q8_0",
        memory_required_gb=4.0,
        score=75.0,
        params_b=3.0,
    ),
]

INSTALLED: List[Dict[str, Any]] = [
    {"name": "examplechat:7b", "size": 4_680_000_000, "quantization": "Q4_K_M"},
    {"name": "examplereason:8b", "size": 5_230_000_000, "quantization": "Q4_K_M"},
    {"name": "mine-16k:latest", "size": 6_590_000_000, "quantization": "Q4_K_M"},
]


class StubClient:
    """Answers like LlmfitClient and counts the calls."""

    def __init__(self, unavailable: Optional[str] = None) -> None:
        """
        Initialize the stub.

        Args:
            unavailable: When set, every call raises LlmfitUnavailable.
        """
        self.unavailable = unavailable
        self.calls: List[Tuple[str, Any]] = []

    def _check(self) -> None:
        """Raise when the stub plays a missing llmfit."""
        if self.unavailable:
            raise LlmfitUnavailable(self.unavailable)

    def version(self) -> Tuple[int, int, int]:
        """Return the minimum version."""
        self._check()
        self.calls.append(("version", None))
        return (1, 1, 20)

    def system(self) -> HardwareProfile:
        """Return made-up hardware with 8 GB of VRAM."""
        self._check()
        self.calls.append(("system", None))
        return HardwareProfile(
            has_gpu=True, gpu_name="Example GPU", gpu_vram_gb=8.0, total_ram_gb=32.0
        )

    def catalog(self, memory_gb: Optional[float] = None) -> List[CatalogModel]:
        """Return the stub catalog and record the budget."""
        self._check()
        self.calls.append(("catalog", memory_gb))
        return list(CATALOG)

    def plan(self, model_name: str, quantization: str, context: int) -> QuantPlan:
        """Return a plan from PLAN_NEEDS, or raise for an unknown pair."""
        self._check()
        self.calls.append(("plan", (model_name, quantization)))
        need = PLAN_NEEDS.get((model_name, quantization))
        if need is None:
            raise LlmfitUnavailable("no plan")
        return QuantPlan(
            model_name=model_name,
            quantization=quantization,
            context=context,
            min_vram_gb=need,
        )

    def count(self, kind: str) -> int:
        """
        Count the calls of one kind.

        Args:
            kind: version, system, catalog, or plan.

        Returns:
            The number of calls.
        """
        return sum(1 for name, _ in self.calls if name == kind)


class FakeClock:
    """A clock that tests move by hand."""

    def __init__(self) -> None:
        """Start at zero."""
        self.now = 0.0

    def __call__(self) -> float:
        """Return the current time."""
        return self.now


def make_service(
    stub: StubClient, clock: Optional[FakeClock] = None
) -> HardwareFitService:
    """
    Build a service that uses the stub client.

    Args:
        stub: Stub llmfit client.
        clock: Fake clock, or None for a new one.

    Returns:
        The service.
    """
    return HardwareFitService(
        client_factory=lambda: stub,
        max_params_billion=9.0,
        clock=clock or FakeClock(),
    )


class TestReport:
    """The report for the Settings page."""

    def test_labels_and_suggestions(self) -> None:
        """Plans label mapped models; the file size labels the others."""
        stub = StubClient()
        report = make_service(stub).report(75, INSTALLED, True)
        assert report.available is True
        assert report.llmfit_version == "1.1.20"
        assert report.budget_gb == 6.0
        assert ("catalog", 6.0) in stub.calls
        by_name = {fit.name: fit for fit in report.installed}
        assert by_name["examplechat:7b"].label == FitLabel.FITS
        assert by_name["examplechat:7b"].source == FitSource.LLMFIT_PLAN
        assert by_name["examplereason:8b"].label == FitLabel.OVER_BUDGET
        assert by_name["examplereason:8b"].need_gb == 6.2
        assert by_name["mine-16k:latest"].source == FitSource.ROUGH_ESTIMATE
        assert by_name["mine-16k:latest"].label == FitLabel.OVER_BUDGET
        # examplebig is 14B at Q2_K; examplesmall fits and is not installed.
        assert [s.ollama_name for s in report.suggestions] == ["examplesmall:3b"]

    def test_unavailable_gives_a_reason_and_a_hint(self) -> None:
        """Without llmfit the report says why and how to install it."""
        report = make_service(StubClient(unavailable="llmfit is not installed")).report(
            75, INSTALLED, True
        )
        assert report.available is False
        assert report.reason == "llmfit is not installed"
        assert report.install_hint == INSTALL_HINT
        assert "llmfit==1.1.20" in INSTALL_HINT
        assert report.installed == []

    def test_a_failed_plan_falls_back_to_the_file_size(self) -> None:
        """A model that llmfit cannot plan still gets a rough label."""
        installed = [{"name": "examplechat:7b", "size": 4_680_000_000}]
        installed[0]["quantization"] = "Q5_K_M"
        report = make_service(StubClient()).report(75, installed, True)
        assert report.installed[0].source == FitSource.ROUGH_ESTIMATE
        assert report.installed[0].need_gb == 5.36


class TestCache:
    """The cache keeps llmfit calls rare."""

    def test_second_report_uses_the_cache(self) -> None:
        """Hardware, catalog, and plans run once within the cache period."""
        stub = StubClient()
        service = make_service(stub)
        service.report(75, INSTALLED, True)
        service.report(75, INSTALLED, True)
        assert stub.count("system") == 1
        assert stub.count("catalog") == 1
        assert stub.count("plan") == 2

    def test_refresh_and_expiry_run_llmfit_again(self) -> None:
        """refresh=True and an old cache both run llmfit again."""
        stub = StubClient()
        clock = FakeClock()
        service = make_service(stub, clock)
        service.report(75, INSTALLED, True)
        service.report(75, INSTALLED, True, refresh=True)
        assert stub.count("catalog") == 2
        assert stub.count("plan") == 4
        clock.now = hardware_service.CACHE_SECONDS + 1
        service.report(75, INSTALLED, True)
        assert stub.count("catalog") == 3

    def test_a_new_headroom_scores_a_new_budget(self) -> None:
        """Each headroom value has its own catalog run."""
        stub = StubClient()
        service = make_service(stub)
        service.report(75, INSTALLED, True)
        report = service.report(90, INSTALLED, True)
        assert ("catalog", 7.2) in stub.calls
        by_name = {fit.name: fit for fit in report.installed}
        assert by_name["examplereason:8b"].label == FitLabel.FITS


class TestPullCheck:
    """The check before a pull."""

    @pytest.mark.parametrize(
        ("tag", "quant"),
        [
            ("qwen2.5:7b", "Q4_K_M"),
            ("llama3.1:8b-instruct-q8_0", "Q8_0"),
            ("phi3:mini-fp16", "F16"),
            ("model:3b-iq3_xs", "IQ3_XS"),
        ],
    )
    def test_quant_from_tag(self, tag: str, quant: str) -> None:
        """A quant in the tag wins; otherwise the default Q4_K_M."""
        assert quant_from_tag(tag) == quant

    def test_over_budget(self) -> None:
        """A mapped model above the budget is over_budget, with the numbers."""
        check = make_service(StubClient()).check_pull("examplereason:8b", 75)
        assert check is not None
        assert check.label == FitLabel.OVER_BUDGET
        assert check.need_gb == 6.2
        assert check.budget_gb == 6.0
        assert check.total_vram_gb == 8.0

    def test_too_large(self) -> None:
        """A model above the total VRAM is too_large."""
        check = make_service(StubClient()).check_pull("examplebig:14b", 75)
        assert check is not None
        assert check.label == FitLabel.TOO_LARGE

    def test_unknown_tag_or_no_llmfit_gives_no_check(self) -> None:
        """No data means no warning."""
        assert make_service(StubClient()).check_pull("other:7b", 75) is None
        missing = make_service(StubClient(unavailable="llmfit is not installed"))
        assert missing.check_pull("examplereason:8b", 75) is None


def _stream_response(events: List[dict]) -> MagicMock:
    """
    Build a mock streaming response for ``requests.post``.

    Args:
        events: NDJSON events that Ollama would send.

    Returns:
        Context-manager mock whose ``iter_lines`` yields the events.
    """
    response = MagicMock()
    response.iter_lines.return_value = [json.dumps(e).encode() for e in events]
    response.__enter__.return_value = response
    return response


@pytest.fixture
def stub_service(monkeypatch: pytest.MonkeyPatch) -> HardwareFitService:
    """
    Make the routes use a service with the stub client.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        The service.
    """
    service = make_service(StubClient())
    monkeypatch.setattr(hardware_service, "get_fit_service", lambda: service)
    return service


@pytest.fixture(autouse=True)
def reset_pull_state():
    """
    Free the pull slot and clear state around each test.

    Yields:
        None.
    """
    yield
    if ollama_admin._pull_lock.locked():
        ollama_admin._pull_lock.release()
    ollama_admin._pull_state.clear()
    ollama_admin._pull_state["status"] = "idle"


class TestRoutes:
    """GET /api/hardware/fit and the pull warning."""

    def test_fit_route_without_llmfit(self, client: TestClient) -> None:
        """No llmfit (the conftest hides any real binary): available is false."""
        listing = {"host": "h", "reachable": False, "models": [], "in_use": []}
        with patch.object(ollama_admin, "list_models", return_value=listing):
            body = client.get("/api/hardware/fit").json()
        assert body["available"] is False
        assert body["reason"] == "llmfit is not installed"
        assert "llmfit==1.1.20" in body["install_hint"]
        assert body["headroom_percent"] == 75
        assert body["ollama_reachable"] is False

    def test_fit_route_with_llmfit(
        self, client: TestClient, stub_service: HardwareFitService
    ) -> None:
        """The route passes the installed models and the headroom setting."""
        listing = {"host": "h", "reachable": True, "models": INSTALLED, "in_use": []}
        with patch.object(ollama_admin, "list_models", return_value=listing):
            body = client.get("/api/hardware/fit").json()
        assert body["available"] is True
        assert body["budget_gb"] == 6.0
        assert body["hardware"]["gpu_name"] == "Example GPU"
        labels = {fit["name"]: fit["label"] for fit in body["installed"]}
        assert labels["examplereason:8b"] == "over_budget"
        assert body["suggestions"][0]["ollama_name"] == "examplesmall:3b"

    def test_list_models_reports_the_quantization(self) -> None:
        """ollama_admin passes the quantization of each installed model."""
        tags = {
            "models": [
                {
                    "name": "x:7b",
                    "size": 1,
                    "details": {"parameter_size": "7B", "quantization_level": "Q4_0"},
                }
            ]
        }
        response = MagicMock()
        response.json.return_value = tags
        with patch.object(ollama_admin.requests, "get", return_value=response):
            listing = ollama_admin.list_models("localhost:11434", set())
        assert listing["models"][0]["quantization"] == "Q4_0"

    def test_over_budget_pull_asks_to_confirm(
        self, client: TestClient, stub_service: HardwareFitService
    ) -> None:
        """A model over the budget gets 409 and no pull starts."""
        response = client.post(
            "/api/settings/ollama/pull", json={"model": "examplereason:8b"}
        )
        assert response.status_code == 409
        body = response.json()
        assert body["details"]["code"] == "over_budget"
        assert body["details"]["need_gb"] == 6.2
        assert body["details"]["budget_gb"] == 6.0
        assert "safety budget of 6.0 GB (75% of 8.0 GB)" in body["message"]
        assert ollama_admin.get_pull_state()["status"] == "idle"

    def test_too_large_pull_names_the_total(
        self, client: TestClient, stub_service: HardwareFitService
    ) -> None:
        """Above the total VRAM, the message names the total."""
        with patch.object(ollama_admin, "check_pull_allowed", return_value=None):
            response = client.post(
                "/api/settings/ollama/pull", json={"model": "examplebig:14b"}
            )
        assert response.status_code == 409
        assert "total GPU memory of 8.0 GB" in response.json()["message"]

    def test_confirmed_pull_starts(
        self, client: TestClient, stub_service: HardwareFitService
    ) -> None:
        """confirm_over_budget lets the pull start."""
        with patch.object(
            ollama_admin.requests,
            "post",
            return_value=_stream_response([{"status": "success"}]),
        ):
            response = client.post(
                "/api/settings/ollama/pull",
                json={"model": "examplereason:8b", "confirm_over_budget": True},
            )
        assert response.status_code == 202
        assert response.json()["model"] == "examplereason:8b"

    def test_a_pull_that_fits_starts(
        self, client: TestClient, stub_service: HardwareFitService
    ) -> None:
        """A model within the budget needs no confirmation."""
        with patch.object(
            ollama_admin.requests,
            "post",
            return_value=_stream_response([{"status": "success"}]),
        ):
            response = client.post(
                "/api/settings/ollama/pull", json={"model": "examplechat:7b"}
            )
        assert response.status_code == 202
