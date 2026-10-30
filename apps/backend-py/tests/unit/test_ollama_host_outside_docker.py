"""Tests for a Docker Ollama host used outside Docker (Step 3.2, MH-H1)."""

from src.api.ollama_models import is_docker_gateway_host, resolve_effective_ollama_host


def test_docker_gateway_settings_use_localhost_outside_docker() -> None:
    """Outside Docker, host.docker.internal does not resolve; localhost is used."""
    assert (
        resolve_effective_ollama_host(
            "http://host.docker.internal:11434", env_host="", in_docker=False
        )
        == "localhost:11434"
    )


def test_docker_gateway_settings_use_the_env_host_outside_docker() -> None:
    """Outside Docker, OLLAMA_HOST is used when it is set."""
    assert (
        resolve_effective_ollama_host(
            "host.docker.internal:11434", env_host="127.0.0.1:11500", in_docker=False
        )
        == "127.0.0.1:11500"
    )


def test_a_docker_gateway_env_host_is_not_used_outside_docker() -> None:
    """An OLLAMA_HOST of host.docker.internal does not resolve either."""
    assert (
        resolve_effective_ollama_host(
            "host.docker.internal:11434",
            env_host="host.docker.internal:11434",
            in_docker=False,
        )
        == "localhost:11434"
    )


def test_docker_gateway_settings_are_kept_inside_docker() -> None:
    """Inside Docker, host.docker.internal is the right host and is kept."""
    assert (
        resolve_effective_ollama_host(
            "host.docker.internal:11434", env_host="", in_docker=True
        )
        == "host.docker.internal:11434"
    )


def test_is_docker_gateway_host() -> None:
    """The check reads the host name with any scheme, letter case, or port."""
    assert is_docker_gateway_host("http://HOST.docker.internal:11434")
    assert is_docker_gateway_host("host.docker.internal")
    assert not is_docker_gateway_host("localhost:11434")
    assert not is_docker_gateway_host("ollama:11434")
