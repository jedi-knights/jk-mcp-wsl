"""Outbound ports — interfaces the application layer depends on.

These are the contracts that secondary/driven adapters must satisfy. The
application layer only imports these protocols; it never references concrete
implementations. This is what makes the hexagonal boundary testable and
swap-able (e.g. real HTTP adapter vs. an in-memory stub).
"""

from typing import Protocol

from ..domain.models import Match, MatchDetails, NewsArticle, Player, Standing, Team


class WSLAPIPort(Protocol):
    """Contract for the upstream Women's Super League data source (ESPN API)."""

    async def get_teams(self) -> list[Team]:
        """Return all active Women's Super League teams."""
        ...

    async def get_team(self, team_id: str) -> Team:
        """Return a single team by its ESPN team ID.

        Raises:
            WSLNotFoundError: If no team with that ID exists.
        """
        ...

    async def get_scoreboard(self, date: str | None = None, end_date: str | None = None) -> list[Match]:
        """Return matches on the given date or date range, or today if date is None.

        When ``end_date`` is provided, ``date`` is the start of the range and the
        upstream is queried with ``dates=START-END``.
        """
        ...

    async def get_news(self, limit: int) -> list[NewsArticle]:
        """Return up to ``limit`` recent Women's Super League news articles."""
        ...

    async def get_roster(self, team_id: str) -> list[Player]:
        """Return the active roster for a team.

        Raises:
            WSLNotFoundError: If no team with that ID exists.
        """
        ...

    async def get_match_details(self, match_id: str) -> MatchDetails:
        """Return detailed information for a single match.

        Raises:
            WSLNotFoundError: If no match with that ID exists.
        """
        ...

    async def get_team_schedule(self, team_id: str) -> list[Match]:
        """Return all scheduled and completed matches for a team in the current season.

        Raises:
            WSLNotFoundError: If no team with that ID exists.
        """
        ...

    async def get_standings(self) -> list[Standing]:
        """Return the current Women's Super League standings ordered by points descending.

        Each Standing carries its ``conference`` label ("Eastern Conference" /
        "Western Conference") so callers can group when needed. The list is
        flat across both conferences.
        """
        ...
