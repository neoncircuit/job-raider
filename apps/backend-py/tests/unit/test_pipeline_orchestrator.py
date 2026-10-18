"""
Tests for stage order and stage dispatch in the pipeline orchestrator.

Before 2026-10-18 the orchestrator kept its own stage lists and an if/elif
dispatch that had no branch for ``linkedin_auth``. Every full-mode run
stopped there with "Unknown stage". These tests check that every stage has
a handler, that the order comes from one place, and that a full run reaches
the submit stage with each stage receiving the output of the stage before.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.api.models.requests import DISCOVER_LAST_STAGE, PIPELINE_STAGE_ORDER
from src.models.pipeline_stage import STAGE_ORDER, PipelineStage
from src.pipeline.orchestrator import PipelineConfig, PipelineOrchestrator
from src.pipeline.stages import StageResult

STAGE_METHOD_NAMES = {
    PipelineStage.SCRAPE: "stage_scrape",
    PipelineStage.DEDUPLICATE: "stage_deduplicate",
    PipelineStage.FILTER_SCAMS: "stage_filter_scams",
    PipelineStage.FILTER_PROFILE: "stage_filter_by_profile",
    PipelineStage.SCORE_RANK: "stage_score_and_rank",
    PipelineStage.RAG_RANK: "stage_rag_rank",
    PipelineStage.DETECT_AUTO_SUBMIT: "stage_detect_auto_submit",
    PipelineStage.LINKEDIN_AUTH: "stage_linkedin_auth",
    PipelineStage.PRESENT_SELECT: "stage_present_selection",
    PipelineStage.GENERATE_RESUMES: "stage_generate_resumes",
    PipelineStage.SUBMIT: "stage_submit_applications",
}
"""Orchestrator stage methods, by stage."""


def make_orchestrator(
    profile: Any, tmp_path: Path, **config: Any
) -> PipelineOrchestrator:
    """Build an orchestrator that writes only under ``tmp_path``.

    Args:
        profile: User profile.
        tmp_path: Temporary directory for data and results.
        **config: Extra ``PipelineConfig`` fields.

    Returns:
        A configured orchestrator.
    """
    return PipelineOrchestrator(
        config=PipelineConfig(
            keywords=["python"],
            locations=["Remote"],
            data_dir=str(tmp_path / "data"),
            results_dir=str(tmp_path / "results"),
            **config,
        ),
        user_profile=profile,
    )


def ok(stage: PipelineStage, data: Any) -> StageResult:
    """Build a successful stage result.

    Args:
        stage: Stage that produced the result.
        data: Stage output.

    Returns:
        A successful ``StageResult``.
    """
    return StageResult(
        stage_name=stage.value,
        success=True,
        data=data,
        metadata={},
        timestamp=datetime.now(),
    )


class TestStageOrder:
    """One stage list drives the orchestrator and the API models."""

    def test_stage_order_is_the_enum_order(self) -> None:
        """STAGE_ORDER lists every stage once, in enum definition order."""
        assert STAGE_ORDER == tuple(PipelineStage)
        assert len(set(STAGE_ORDER)) == len(STAGE_ORDER)

    def test_api_models_use_the_same_order(self) -> None:
        """The request models derive their stage list from STAGE_ORDER."""
        assert PIPELINE_STAGE_ORDER == tuple(stage.value for stage in STAGE_ORDER)
        assert DISCOVER_LAST_STAGE == PipelineStage.RAG_RANK.value

    def test_every_stage_has_a_handler(
        self, sample_user_profile: Any, tmp_path: Path
    ) -> None:
        """No stage can fall through dispatch without a handler.

        Args:
            sample_user_profile: Profile fixture.
            tmp_path: Temporary directory.
        """
        orchestrator = make_orchestrator(sample_user_profile, tmp_path)
        assert set(orchestrator._stage_handlers({})) == set(PipelineStage)

    def test_stages_to_run_slices_the_order(
        self, sample_user_profile: Any, tmp_path: Path
    ) -> None:
        """start_from and stop_at select a contiguous slice of STAGE_ORDER.

        Args:
            sample_user_profile: Profile fixture.
            tmp_path: Temporary directory.
        """
        orchestrator = make_orchestrator(sample_user_profile, tmp_path)

        assert orchestrator.plan_stages(PipelineStage.SCRAPE, None) == list(STAGE_ORDER)
        assert orchestrator.plan_stages(
            PipelineStage.DETECT_AUTO_SUBMIT, PipelineStage.PRESENT_SELECT
        ) == [
            PipelineStage.DETECT_AUTO_SUBMIT,
            PipelineStage.LINKEDIN_AUTH,
            PipelineStage.PRESENT_SELECT,
        ]

    def test_skip_submission_drops_only_the_submit_stage(
        self, sample_user_profile: Any, tmp_path: Path
    ) -> None:
        """skip_submission removes the submit stage and nothing else.

        Args:
            sample_user_profile: Profile fixture.
            tmp_path: Temporary directory.
        """
        orchestrator = make_orchestrator(
            sample_user_profile, tmp_path, skip_submission=True
        )
        stages = orchestrator.plan_stages(PipelineStage.SCRAPE, None)
        assert stages == list(STAGE_ORDER[:-1])


class TestFullRunDispatch:
    """A full-mode run calls every stage with the right input."""

    @pytest.fixture
    def recorded_run(
        self, sample_user_profile: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> Dict[str, Any]:
        """Run a full dry run with each stage method replaced by a recorder.

        Each fake returns a token that names its stage, so the test can see
        which output each stage received.

        Args:
            sample_user_profile: Profile fixture.
            tmp_path: Temporary directory.
            monkeypatch: Pytest monkeypatch fixture.

        Returns:
            The pipeline result and the recorded calls in call order.
        """
        orchestrator = make_orchestrator(
            sample_user_profile, tmp_path, mode="full", dry_run=True
        )
        calls: List[tuple] = []

        def recorder(stage: PipelineStage) -> Any:
            """Build a fake stage method for one stage.

            Args:
                stage: Stage that the fake stands in for.

            Returns:
                Fake method that records its arguments.
            """

            def fake(*args: Any, **kwargs: Any) -> StageResult:
                """Record the call and return this stage's token.

                Args:
                    *args: Positional stage arguments.
                    **kwargs: Keyword stage arguments.

                Returns:
                    A successful result whose data names the stage.
                """
                calls.append((stage, args, kwargs))
                return ok(stage, [f"out:{stage.value}"])

            return fake

        for stage, name in STAGE_METHOD_NAMES.items():
            monkeypatch.setattr(orchestrator.stages, name, recorder(stage))

        result = orchestrator.run()
        return {"result": result, "calls": calls}

    def test_full_run_succeeds_and_reaches_submit(
        self, recorded_run: Dict[str, Any]
    ) -> None:
        """All stages run, in order, and the run reports success.

        Args:
            recorded_run: Output of the recorded full run.
        """
        result = recorded_run["result"]
        assert result.success is True
        assert result.stages_completed == [stage.value for stage in STAGE_ORDER]
        assert [call[0] for call in recorded_run["calls"]] == list(STAGE_ORDER)

    def test_each_stage_receives_the_previous_output(
        self, recorded_run: Dict[str, Any]
    ) -> None:
        """Data flows from each stage to the stage that consumes it.

        Args:
            recorded_run: Output of the recorded full run.
        """
        args = {stage: call_args for stage, call_args, _ in recorded_run["calls"]}

        def out(stage: PipelineStage) -> List[str]:
            """Return the token that a stage produced.

            Args:
                stage: Producing stage.

            Returns:
                The stage's output token.
            """
            return [f"out:{stage.value}"]

        assert args[PipelineStage.DEDUPLICATE] == (out(PipelineStage.SCRAPE),)
        assert args[PipelineStage.FILTER_SCAMS] == (out(PipelineStage.DEDUPLICATE),)
        assert args[PipelineStage.RAG_RANK] == (out(PipelineStage.SCORE_RANK),)
        # Detection and selection use RAG output when RAG produced data.
        assert args[PipelineStage.DETECT_AUTO_SUBMIT] == (out(PipelineStage.RAG_RANK),)
        assert args[PipelineStage.LINKEDIN_AUTH] == (
            out(PipelineStage.DETECT_AUTO_SUBMIT),
        )
        assert args[PipelineStage.PRESENT_SELECT][:2] == (
            out(PipelineStage.RAG_RANK),
            out(PipelineStage.DETECT_AUTO_SUBMIT),
        )
        assert args[PipelineStage.GENERATE_RESUMES] == (
            out(PipelineStage.PRESENT_SELECT),
        )
        assert args[PipelineStage.SUBMIT] == (out(PipelineStage.GENERATE_RESUMES),)


class TestCooperativeCancel:
    """run(should_stop=...) stops before the next stage."""

    def test_should_stop_ends_the_run_before_the_next_stage(
        self, sample_user_profile: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When should_stop turns True, no further stage runs.

        Args:
            sample_user_profile: Profile fixture.
            tmp_path: Temporary directory.
            monkeypatch: Pytest monkeypatch fixture.
        """
        orchestrator = make_orchestrator(sample_user_profile, tmp_path, mode="full")
        ran: List[PipelineStage] = []

        def fake_for(stage: PipelineStage) -> Any:
            """Build a fake stage method that records its stage.

            Args:
                stage: Stage that the fake stands in for.

            Returns:
                Fake stage method.
            """

            def fake(*_args: Any, **_kwargs: Any) -> StageResult:
                """Record the stage and succeed.

                Args:
                    *_args: Ignored stage arguments.
                    **_kwargs: Ignored stage keyword arguments.

                Returns:
                    A successful result.
                """
                ran.append(stage)
                return ok(stage, [])

            return fake

        for stage, name in STAGE_METHOD_NAMES.items():
            monkeypatch.setattr(orchestrator.stages, name, fake_for(stage))

        result = orchestrator.run(should_stop=lambda: len(ran) >= 2)

        assert ran == [PipelineStage.SCRAPE, PipelineStage.DEDUPLICATE]
        assert result.success is False
        assert result.metadata["cancelled"] is True
        assert result.stages_completed == ["scrape", "deduplicate"]
