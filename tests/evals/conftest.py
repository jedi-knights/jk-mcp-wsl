"""pytest fixtures for the eval harness.

Provides ``mcp_client`` — an async ``ClientSession`` connected to an
in-process FastMCP instance whose outbound HTTP adapter is a stub
returning deterministic domain objects. Scenarios run hermetically in
unit-test CI without contacting the live ESPN API.

The stubs cover only the small slice of upstream calls the registered
scenarios exercise. Adding a scenario that calls a new tool means
adding the matching stub method here — there is no automatic
discovery. The trade-off is deliberate: scenarios act as both
documentation and contract tests, so explicitly listing the supported
shape keeps the test surface honest.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest_asyncio
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from wsl.adapters.inbound.mcp_adapter import create_mcp_server
from wsl.application.service import WSLService
from wsl.domain.models import Standing, Team


@dataclass
class _StubRepo:
    """Application-port stub returning deterministic domain objects.

    Only the methods the registered scenarios call are implemented.
    Adding a scenario that hits an unimplemented tool will surface an
    AttributeError — the explicit failure mode is the right one for
    a contract-test harness.
    """

    async def get_teams(self) -> list[Team]:
        return [_arsenal_wfc()]

    async def get_team(self, team_id: str) -> Team:
        _ = team_id
        return _arsenal_wfc()

    async def get_standings(self) -> list[Standing]:
        return [
            Standing(
                team=_arsenal_wfc(),
                wins=14,
                losses=3,
                ties=3,
                points=45,
                goals_for=42,
                goals_against=18,
                goal_difference=24,
            ),
        ]


def _arsenal_wfc() -> Team:
    return Team(
        id="19973",
        name="Arsenal",
        abbreviation="ARS",
        location="London",
        display_name="Arsenal",
    )


@pytest_asyncio.fixture
async def mcp_client() -> AsyncIterator[ClientSession]:
    """Yield a ClientSession bound to an in-process Women's Super League MCP server.

    The service receives the stub above; tools that are out of scope
    for the current scenario suite are still reachable through the
    ESPN port stub. Extend ``_StubRepo`` when a new scenario needs a
    new tool.
    """
    service = WSLService(repo=_StubRepo())
    server = create_mcp_server(service)
    async with _server_session(server) as client:
        yield client


@asynccontextmanager
async def _server_session(server) -> AsyncIterator[ClientSession]:
    """Wrap ``create_connected_server_and_client_session`` so the fixture stays one-line."""
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        yield session
