"""
Guard the Compose publish rules for local-first networking.

Backend port 8000 must not be published. Frontend must bind to 127.0.0.1.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"


def test_compose_does_not_publish_backend_and_binds_frontend_loopback() -> None:
    """Backend has no host ports; frontend publishes only on 127.0.0.1."""
    data = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    services = data["services"]

    backend_ports = services["backend"].get("ports") or []
    assert backend_ports == [], (
        "backend must not publish port 8000 on the host; "
        f"found ports={backend_ports!r}"
    )

    frontend_ports = services["frontend"].get("ports") or []
    assert frontend_ports, "frontend must publish a loopback port"
    for entry in frontend_ports:
        if isinstance(entry, dict):
            assert (
                entry.get("host_ip") == "127.0.0.1"
            ), f"frontend port must set host_ip 127.0.0.1; got {entry!r}"
            assert int(entry.get("target", 0)) == 3000
        else:
            raise AssertionError(
                f"frontend ports must use long syntax with host_ip; got {entry!r}"
            )
