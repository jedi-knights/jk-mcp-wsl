"""Schedule-strength analytics MCP tools.

Derived metrics computed on top of the ESPN standings + team-schedule feeds:
strength of schedule, results-by-opponent-tier, and opponent-quality-adjusted
points-per-game. These complement the raw league table by exposing
schedule-strength context the standings alone don't reveal.
"""

import logging

from mcp.server.fastmcp import FastMCP

from ....application.service import WSLService
from ....ports.inbound import Authorizer
from ..formatters import (
    _fmt_adjusted_ppg,
    _fmt_results_by_tier,
    _fmt_strength_of_schedule,
)
from ._base import _READ_ANNOTATIONS, _safe_call_authorized

logger = logging.getLogger(__name__)


def register_analytics_tools(mcp: FastMCP, service: WSLService, authorizer: Authorizer) -> None:
    """Register the three schedule-strength analytics tools on `mcp`."""

    @mcp.tool(annotations=_READ_ANNOTATIONS)
    async def get_strength_of_schedule(team_id: str) -> str:
        """Get a team's strength of schedule based on opponents already faced.

        Returns the average current points-per-game of every opponent the team
        has played in completed matches, plus a per-opponent breakdown. Useful
        early in the season for "who has played the tougher schedule so far?"
        questions.

        Args:
            team_id: ESPN numeric team ID (e.g. "18418" for Atlanta United FC).
        """
        logger.info("tool=get_strength_of_schedule team_id=%r", team_id)
        return await _safe_call_authorized(
            authorizer, "get_strength_of_schedule", service.get_strength_of_schedule(team_id), _fmt_strength_of_schedule
        )

    @mcp.tool(annotations=_READ_ANNOTATIONS)
    async def get_results_by_opponent_tier(team_id: str, tier_size: int = 5) -> str:
        """Get a team's W-L-T splits against current top-tier, middle, and bottom-tier teams.

        Tiers are derived from the live league standings: top `tier_size`,
        bottom `tier_size`, and everyone in between. Lets you ask "how does
        this team do against the top of the table?" without scanning every
        result manually.

        Args:
            team_id: ESPN numeric team ID.
            tier_size: Number of teams in each of the top and bottom tiers.
                Defaults to 5. Must be at least 1, and 2*tier_size must not
                exceed the league size.
        """
        logger.info("tool=get_results_by_opponent_tier team_id=%r tier_size=%r", team_id, tier_size)
        return await _safe_call_authorized(
            authorizer,
            "get_results_by_opponent_tier",
            service.get_results_by_opponent_tier(team_id, tier_size),
            _fmt_results_by_tier,
        )

    @mcp.tool(annotations=_READ_ANNOTATIONS)
    async def get_adjusted_points_per_game(team_id: str) -> str:
        """Get a team's raw points-per-game alongside an opponent-quality-adjusted PPG.

        Adjusted PPG scales raw PPG by `avg_opponent_ppg / league_average_ppg`,
        so values above raw PPG indicate the team has earned points against a
        tougher schedule than league average.

        Args:
            team_id: ESPN numeric team ID.
        """
        logger.info("tool=get_adjusted_points_per_game team_id=%r", team_id)
        return await _safe_call_authorized(
            authorizer, "get_adjusted_points_per_game", service.get_adjusted_points_per_game(team_id), _fmt_adjusted_ppg
        )
