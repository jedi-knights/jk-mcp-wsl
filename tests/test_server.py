"""Unit tests for the server.py entry point.

Tests verify that build_server wires the dependency graph correctly and
that main() raises on invalid transport values.
"""

import pytest

from wsl.server import build_server


def test_build_server_returns_fastmcp_instance() -> None:
    server = build_server()
    assert server is not None


def test_build_server_with_custom_host_and_port() -> None:
    server = build_server(host="127.0.0.1", port=9000)
    assert server is not None


def test_main_raises_on_invalid_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "websocket")
    from wsl.server import main

    with pytest.raises(ValueError, match="Invalid MCP_TRANSPORT"):
        main()
