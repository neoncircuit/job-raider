"""Tests for the writer suite's real writer and its ``eval writer`` command (Step 3.8, MH-2)."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

import src.evaluation.suites.writer as writer_suite
from src.evaluation.report import EvalReport
from src.evaluation.run_metadata import build_run_metadata
from src.evaluation.suites import SUITE_NAMES, get_suite
from src.llm.base import LLMResponse
from src.llm.router import TaskType
from tests.unit.test_cli import parse
from tests.unit.test_writer_suite import MODEL, FakeValidator, small_dataset, writer_for


def fake_router(provider: str = "ollama", resolved: str = MODEL) -> MagicMock:
    """
    A router whose cover-letter route resolves to the given provider and model.

    Args:
        provider: The provider that the route resolves to.
        resolved: The model that the route resolves to.

    Returns:
        A mock router with ``resolve_primary_model``, ``routes``, and ``generate``.
    """
    router = MagicMock()
    router.resolve_primary_model.return_value = (provider, resolved)
    router.routes = {
        TaskType.COVER_LETTER_WRITING: SimpleNamespace(
            primary_model=resolved,
            fallback_provider="anthropic",
            fallback_model="claude-x",
        )
    }
    router.generate.return_value = LLMResponse(
        content="Dear team, I built a data pipeline in Python.",
        model=resolved,
        provider=provider,
    )
    return router


def fake_report(tmp_path: Path) -> EvalReport:
    """
    A small writer report for the command tests.

    Args:
        tmp_path: The test folder, which holds the dataset file.

    Returns:
        The report with one metric.
    """
    path = tmp_path / "cases.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    return EvalReport(
        suite="writer",
        metadata=build_run_metadata("writer", [path], 1, repo_dir=tmp_path),
        metrics={"written": 1.0},
        details={},
    )


def test_writer_is_a_registered_suite() -> None:
    """``eval writer`` is in the registry and runs the writer suite."""
    runner, dataset_dir = get_suite("writer")

    assert "writer" in SUITE_NAMES
    assert runner is writer_suite.run_writer_suite
    assert dataset_dir == writer_suite.DEFAULT_DATASET_DIR


def test_writer_allow_list_has_the_four_approved_models() -> None:
    """The allow-list holds the four approved local models."""
    assert writer_suite.WRITER_MODELS == (
        "qwen2.5:7b",
        "qwen3.5:4b",
        "qwen2.5:3b",
        "gemma3:4b",
    )


@pytest.mark.parametrize("model", ["gemma4:e4b", "qwen3.5:9b", "qwen2.5:14b"])
def test_a_model_outside_the_allow_list_is_refused(tmp_path: Path, model: str) -> None:
    """A model that is not on the allow-list stops the run."""
    with pytest.raises(ValueError, match="allow-list"):
        writer_suite.run_writer_suite(
            small_dataset(tmp_path, count=1), model=model, write=writer_for()
        )


def test_a_cloud_route_stops_the_run_before_any_call(tmp_path: Path) -> None:
    """A cover-letter route that is not Ollama stops the run with no call."""
    router = fake_router(provider="anthropic", resolved="claude-x")

    with pytest.raises(ValueError, match="anthropic/claude-x"):
        writer_suite.run_writer_suite(
            small_dataset(tmp_path, count=1),
            model=MODEL,
            router=router,
            unload=lambda name: None,
            vram_probe=lambda: None,
        )

    router.generate.assert_not_called()


def test_a_route_that_ignores_the_model_stops_the_run(tmp_path: Path) -> None:
    """A route that resolves to another Ollama model stops the run with no call."""
    router = fake_router(resolved="qwen2.5:3b")

    with pytest.raises(ValueError, match="ollama/qwen2.5:3b"):
        writer_suite.run_writer_suite(
            small_dataset(tmp_path, count=1),
            model=MODEL,
            router=router,
            unload=lambda name: None,
            vram_probe=lambda: None,
        )

    router.generate.assert_not_called()


def test_the_real_writer_writes_with_the_model_and_no_fallback(tmp_path: Path) -> None:
    """The real writer calls the router with the model and the route has no fallback."""
    router = fake_router()

    report = writer_suite.run_writer_suite(
        small_dataset(tmp_path, count=1),
        model=MODEL,
        samples=2,
        router=router,
        unload=lambda name: None,
        vram_probe=lambda: None,
        validator=FakeValidator({}),
    )

    route = router.routes[TaskType.COVER_LETTER_WRITING]
    assert route.fallback_provider == "none"
    assert router.generate.call_count == 2
    for call in router.generate.call_args_list:
        assert call.kwargs["model"] == MODEL
        assert call.kwargs["task_type"] == TaskType.COVER_LETTER_WRITING
    assert report.metrics["written"] == 2


def test_the_model_is_unloaded_once_after_the_letters(tmp_path: Path) -> None:
    """The model is unloaded one time when the letters are done."""
    unloaded: List[str] = []

    writer_suite.run_writer_suite(
        small_dataset(tmp_path, count=3),
        model=MODEL,
        write=writer_for(),
        samples=2,
        validator=FakeValidator({}),
        unload=unloaded.append,
    )

    assert unloaded == [MODEL]


def test_the_model_is_unloaded_when_the_run_stops(tmp_path: Path) -> None:
    """A run that raises still unloads the model."""
    unloaded: List[str] = []
    validator = MagicMock()
    validator.validate.side_effect = RuntimeError("validator failed")

    with pytest.raises(RuntimeError):
        writer_suite.run_writer_suite(
            small_dataset(tmp_path, count=1),
            model=MODEL,
            write=writer_for(),
            samples=1,
            validator=validator,
            unload=unloaded.append,
        )

    assert unloaded == [MODEL]


def test_peak_vram_is_the_highest_reading(tmp_path: Path) -> None:
    """The peak VRAM is the highest reading, taken after each letter."""
    readings = iter([5000, 6400, 6100])

    report = writer_suite.run_writer_suite(
        small_dataset(tmp_path, count=3),
        model=MODEL,
        write=writer_for(),
        samples=1,
        validator=FakeValidator({}),
        unload=lambda name: None,
        vram_probe=lambda: next(readings),
    )

    assert report.metrics["peak_vram_mib"] == 6400.0


def test_a_given_writer_reads_no_vram(tmp_path: Path) -> None:
    """With a given writer and no probe, there is no VRAM reading."""
    report = writer_suite.run_writer_suite(
        small_dataset(tmp_path, count=1),
        model=MODEL,
        write=writer_for(),
        samples=1,
        validator=FakeValidator({}),
    )

    assert report.metrics["peak_vram_mib"] is None


def test_the_default_writer_uses_the_app_router_unload_and_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a writer, the suite uses the app router, unloads, and reads VRAM."""
    router = fake_router()
    routers_made: List[Any] = []
    unloaded: List[Any] = []

    def make_router() -> MagicMock:
        """Record the call and return the fake router."""
        routers_made.append(router)
        return router

    monkeypatch.setattr(writer_suite, "default_router", make_router)
    monkeypatch.setattr(
        writer_suite,
        "unload_ollama_model",
        lambda app_router, name: unloaded.append((app_router, name)),
    )
    monkeypatch.setattr(writer_suite, "gpu_memory_used_mib", lambda: 4000)

    report = writer_suite.run_writer_suite(
        small_dataset(tmp_path, count=1),
        model=MODEL,
        samples=1,
        validator=FakeValidator({}),
    )

    assert len(routers_made) == 1
    assert unloaded == [(router, MODEL)]
    assert report.metrics["peak_vram_mib"] == 4000.0


def test_eval_writer_passes_model_and_samples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``eval writer --model --samples`` passes both to the suite."""
    import main as cli

    seen: Dict[str, Any] = {}

    def fake_writer(dataset: Path, **kwargs: Any) -> EvalReport:
        """Record the keyword arguments and return a report."""
        seen["kwargs"] = kwargs
        return fake_report(tmp_path)

    monkeypatch.setattr(
        "src.evaluation.suites.get_suite",
        lambda name: (fake_writer, tmp_path),
    )
    routed = parse(
        [
            "eval",
            "writer",
            "--model",
            "gemma3:4b",
            "--samples",
            "2",
            "--out",
            str(tmp_path / "out"),
            "--no-mlflow",
        ]
    )

    assert cli.run_eval_command(routed) == 0
    assert seen["kwargs"] == {"model": "gemma3:4b", "samples": 2}


def test_eval_writer_needs_a_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """``eval writer`` without ``--model`` stops before the suite runs."""
    import main as cli

    called: List[Any] = []

    def fake_writer(dataset: Path, **kwargs: Any) -> EvalReport:
        """Record that the suite ran."""
        called.append(kwargs)
        return fake_report(tmp_path)

    monkeypatch.setattr(
        "src.evaluation.suites.get_suite",
        lambda name: (fake_writer, tmp_path),
    )
    routed = parse(["eval", "writer", "--out", str(tmp_path / "out"), "--no-mlflow"])

    assert cli.run_eval_command(routed) == 1
    assert called == []
    assert "--model" in capsys.readouterr().out


def test_other_suites_get_no_writer_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Other suites do not receive the writer options."""
    import main as cli

    seen: Dict[str, Any] = {}

    def fake_grounding(dataset: Path, **kwargs: Any) -> EvalReport:
        """Record the keyword arguments and return a report."""
        seen["kwargs"] = kwargs
        return fake_report(tmp_path)

    monkeypatch.setattr(
        "src.evaluation.suites.get_suite",
        lambda name: (fake_grounding, tmp_path),
    )
    routed = parse(
        [
            "eval",
            "grounding",
            "--model",
            "gemma3:4b",
            "--samples",
            "5",
            "--out",
            str(tmp_path / "out"),
            "--no-mlflow",
        ]
    )

    assert cli.run_eval_command(routed) == 0
    assert seen["kwargs"] == {}
