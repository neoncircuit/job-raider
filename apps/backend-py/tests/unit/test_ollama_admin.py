"""
Job Raider - Ollama model management tests.

Unit tests for the guards and pull streaming in ``src.api.ollama_admin``, and
route tests for ``/api/settings/ollama/*`` with the Ollama HTTP API mocked.
"""

import json
from typing import Iterator, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api import ollama_admin
from src.api.settings import ModelRouting, Provider, UserSettings


@pytest.fixture(autouse=True)
def reset_pull_state() -> Iterator[None]:
    """Free the pull slot and clear state around each test.

    Yields:
        None.
    """
    yield
    if ollama_admin._pull_lock.locked():
        ollama_admin._pull_lock.release()
    ollama_admin._pull_state.clear()
    ollama_admin._pull_state["status"] = "idle"


def _stream_response(events: List[dict]) -> MagicMock:
    """Build a mock streaming response for ``requests.post``.

    Args:
        events: NDJSON events that Ollama would send.

    Returns:
        Context-manager mock whose ``iter_lines`` yields the events.
    """
    response = MagicMock()
    response.iter_lines.return_value = [json.dumps(e).encode() for e in events]
    response.__enter__.return_value = response
    return response


class TestGuards:
    """Name validation, size limit, and in-use detection."""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("qwen2.5:3b", 3.0),
            ("deepseek-r1:1.5b", 1.5),
            ("gemma3:12b", 12.0),
            ("mixtral:8x7b", 56.0),
            ("qwen3:30b-a3b", 30.0),
            ("llama3.1:8b-instruct-q4_0", 8.0),
            ("nomic-embed-text", None),
            ("phi3:mini", None),
        ],
    )
    def test_parameter_billions(self, name: str, expected: float) -> None:
        """Parameter counts are read from the tag."""
        assert ollama_admin.parameter_billions(name) == expected

    @pytest.mark.parametrize(
        "name", ["qwen3.5:9b", "gemma3:12b", "qwen2.5:14b", "qwen:32b", "llama3:70b"]
    )
    def test_large_models_blocked(self, name: str) -> None:
        """Tags of 9B or more are refused."""
        with pytest.raises(ollama_admin.OllamaAdminError, match="blocked"):
            ollama_admin.check_pull_allowed(name)

    @pytest.mark.parametrize("name", ["qwen2.5:7b", "llama3.1:8b", "nomic-embed-text"])
    def test_small_models_allowed(self, name: str) -> None:
        """Tags under 9B, or without a size, are allowed."""
        ollama_admin.check_pull_allowed(name)

    @pytest.mark.parametrize("name", ["", " ", "-bad", "a b", "x;rm", "../etc"])
    def test_invalid_names_rejected(self, name: str) -> None:
        """Malformed tags are refused."""
        with pytest.raises(ollama_admin.OllamaAdminError):
            ollama_admin.validate_model_name(name)

    def test_models_in_use_collects_routing_and_embedding(self) -> None:
        """Ollama primaries and fallbacks plus the embedding model are in use."""
        settings = UserSettings(
            routing={
                "selection": ModelRouting(
                    task_type="selection",
                    primary_provider=Provider.OLLAMA,
                    primary_model="qwen2.5:3b",
                    fallback_provider=Provider.OLLAMA,
                    fallback_model="gemma3:4b",
                ),
                "resume_writing": ModelRouting(
                    task_type="resume_writing",
                    primary_provider=Provider.ANTHROPIC,
                    primary_model="claude-sonnet-4-6",
                    fallback_provider=None,
                ),
            }
        )
        used = ollama_admin.models_in_use(settings, "nomic-embed-text")
        assert used == {"qwen2.5:3b", "gemma3:4b", "nomic-embed-text"}

    def test_is_in_use_treats_missing_tag_as_latest(self) -> None:
        """``nomic-embed-text`` matches ``nomic-embed-text:latest``."""
        assert ollama_admin.is_in_use("nomic-embed-text:latest", {"nomic-embed-text"})
        assert not ollama_admin.is_in_use("qwen2.5:7b", {"qwen2.5:3b"})


class TestPull:
    """Single-slot pull and progress streaming."""

    def test_second_pull_refused_while_running(self) -> None:
        """Only one pull can hold the slot."""
        ollama_admin.begin_pull("qwen2.5:3b")
        with pytest.raises(ollama_admin.OllamaAdminError) as exc:
            ollama_admin.begin_pull("gemma3:4b")
        assert exc.value.status_code == 409

    def test_run_pull_records_progress_and_frees_slot(self) -> None:
        """Progress events update state; success frees the slot."""
        ollama_admin.begin_pull("qwen2.5:3b")
        events = [
            {"status": "pulling manifest"},
            {"status": "downloading", "total": 100, "completed": 40},
            {"status": "downloading", "total": 100, "completed": 100},
            {"status": "success"},
        ]
        with patch.object(
            ollama_admin.requests, "post", return_value=_stream_response(events)
        ):
            ollama_admin.run_pull("localhost:11434", "qwen2.5:3b")

        state = ollama_admin.get_pull_state()
        assert state["status"] == "success"
        assert state["completed"] == 100 and state["total"] == 100
        assert not ollama_admin._pull_lock.locked()

    def test_run_pull_reports_ollama_error(self) -> None:
        """An error event marks the pull failed and frees the slot."""
        ollama_admin.begin_pull("nope:1b")
        with patch.object(
            ollama_admin.requests,
            "post",
            return_value=_stream_response([{"error": "file does not exist"}]),
        ):
            ollama_admin.run_pull("localhost:11434", "nope:1b")

        state = ollama_admin.get_pull_state()
        assert state["status"] == "error"
        assert "file does not exist" in state["error"]
        assert not ollama_admin._pull_lock.locked()


class TestListAndDelete:
    """Listing and delete guards against the Ollama API."""

    def test_list_marks_in_use(self) -> None:
        """Installed models carry size and in-use flags."""
        response = MagicMock()
        response.json.return_value = {
            "models": [
                {
                    "name": "qwen2.5:3b",
                    "size": 1900000000,
                    "details": {"parameter_size": "3.1B"},
                },
                {"name": "phi3:mini", "size": 2200000000},
            ]
        }
        with patch.object(ollama_admin.requests, "get", return_value=response):
            result = ollama_admin.list_models("localhost:11434", {"qwen2.5:3b"})

        assert result["reachable"] is True
        by_name = {m["name"]: m for m in result["models"]}
        assert by_name["qwen2.5:3b"]["in_use"] is True
        assert by_name["qwen2.5:3b"]["parameter_size"] == "3.1B"
        assert by_name["phi3:mini"]["in_use"] is False

    def test_list_unreachable(self) -> None:
        """A transport error returns reachable False, not an exception."""
        with patch.object(
            ollama_admin.requests, "get", side_effect=ConnectionError("refused")
        ):
            result = ollama_admin.list_models("localhost:11434", set())
        assert result["reachable"] is False
        assert result["models"] == []

    def test_delete_in_use_refused_without_calling_ollama(self) -> None:
        """In-use models are never sent to Ollama for deletion."""
        with patch.object(ollama_admin.requests, "delete") as delete:
            with pytest.raises(ollama_admin.OllamaAdminError) as exc:
                ollama_admin.delete_model(
                    "localhost:11434", "qwen2.5:3b", {"qwen2.5:3b"}
                )
        assert exc.value.status_code == 409
        delete.assert_not_called()

    def test_delete_missing_model_is_404(self) -> None:
        """Ollama 404 maps to a 404 error."""
        with patch.object(
            ollama_admin.requests, "delete", return_value=MagicMock(status_code=404)
        ):
            with pytest.raises(ollama_admin.OllamaAdminError) as exc:
                ollama_admin.delete_model("localhost:11434", "phi3:mini", set())
        assert exc.value.status_code == 404


class TestOllamaRoutes:
    """Route wiring for ``/api/settings/ollama/*``."""

    def test_pull_blocked_model_is_400(self, client: TestClient) -> None:
        """A 9B+ tag is refused before any pull starts."""
        response = client.post(
            "/api/settings/ollama/pull", json={"model": "gemma3:12b"}
        )
        assert response.status_code == 400
        assert "blocked" in response.json()["message"]
        assert ollama_admin.get_pull_state()["status"] == "idle"

    def test_pull_conflict_is_409(self, client: TestClient) -> None:
        """A second pull while one runs is refused."""
        ollama_admin.begin_pull("qwen2.5:3b")
        response = client.post("/api/settings/ollama/pull", json={"model": "phi3:mini"})
        assert response.status_code == 409

    def test_pull_runs_and_status_reports_success(self, client: TestClient) -> None:
        """A pull starts with 202 and the status endpoint reports the result."""
        with patch.object(
            ollama_admin.requests,
            "post",
            return_value=_stream_response([{"status": "success"}]),
        ):
            response = client.post(
                "/api/settings/ollama/pull", json={"model": "qwen2.5:3b"}
            )
        assert response.status_code == 202
        assert response.json()["model"] == "qwen2.5:3b"

        status = client.get("/api/settings/ollama/pull/status").json()
        assert status["status"] == "success"

    def test_delete_in_use_is_409(self, client: TestClient) -> None:
        """The embedding model cannot be deleted."""
        response = client.delete("/api/settings/ollama/models/nomic-embed-text")
        assert response.status_code == 409

    def test_delete_unused_model(self, client: TestClient) -> None:
        """An unused model is deleted through Ollama."""
        with patch.object(
            ollama_admin.requests, "delete", return_value=MagicMock(status_code=200)
        ) as delete:
            response = client.delete("/api/settings/ollama/models/phi3:mini")
        assert response.status_code == 200
        assert response.json() == {"deleted": "phi3:mini"}
        assert delete.call_args.kwargs["json"] == {"model": "phi3:mini"}

    def test_list_route(self, client: TestClient) -> None:
        """The list route returns the in-use set alongside models."""
        response = MagicMock()
        response.json.return_value = {"models": [{"name": "phi3:mini", "size": 1}]}
        with patch.object(ollama_admin.requests, "get", return_value=response):
            data = client.get("/api/settings/ollama/models").json()
        assert data["reachable"] is True
        assert "nomic-embed-text" in data["in_use"]
        assert data["models"][0]["name"] == "phi3:mini"
