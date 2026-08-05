"""Outbound adapter — translates domain calls into ESPN API HTTP requests.

This is the only place in the codebase that knows about:
- The ESPN API host and URL structure
- How to issue HTTP requests and translate non-2xx responses into domain errors

The wire-format → domain-model mapping lives in parsers.py so this module
stays focused on transport.
"""

import asyncio
import logging
from typing import Any

import httpx

from ...domain.exceptions import UpstreamAPIError, WSLNotFoundError
from ...domain.models import Match, MatchDetails, NewsArticle, Player, Standing, Team
from .parsers import (
    _parse_article,
    _parse_match,
    _parse_match_details,
    _parse_player,
    _parse_standing,
    _parse_team,
)

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://site.api.espn.com"
_LEAGUE_PATH = "/apis/site/v2/sports/soccer/eng.w.1"
# Standings live on the /apis/v2 surface — the /apis/site/v2 path returns an empty {}.
_STANDINGS_PATH = "/apis/v2/sports/soccer/eng.w.1/standings"


def _check_response(response: httpx.Response, path: str) -> None:
    """Raise a domain exception for any non-2xx HTTP status.

    Args:
        response: The httpx response to inspect.
        path: The request path, included in exception messages for context.

    Raises:
        WSLNotFoundError: If the server returned HTTP 404.
        UpstreamAPIError: If the server returned any other 4xx or 5xx status.
    """
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise WSLNotFoundError(f"Not found: {path}") from exc
        raise UpstreamAPIError(f"Upstream error {exc.response.status_code}: {path}") from exc


class ESPNAdapter:
    """Calls the ESPN public API for Women's Super League data.

    The underlying httpx.AsyncClient is created once at construction and reused
    for all requests so the TCP connection pool is retained across calls —
    avoiding a fresh TCP+TLS handshake on every API call.
    """

    def __init__(self, base_url: str = _DEFAULT_BASE_URL, client: httpx.AsyncClient | None = None) -> None:
        """Initialize the adapter with an optional HTTP client.

        Args:
            base_url: Base URL of the ESPN API. Defaults to https://site.api.espn.com.
            client: An httpx.AsyncClient instance to reuse across all requests.
                Inject a pre-configured mock in tests.
        """
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=30.0)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GET request and return the parsed JSON body.

        Raises:
            WSLNotFoundError: If the server returns HTTP 404.
            UpstreamAPIError: If the server returns any other 4xx or 5xx response.
        """
        logger.debug("GET %s params=%s", path, params)
        response = await self._client.get(path, params=params or {})
        _check_response(response, path)
        return response.json()

    async def get_teams(self) -> list[Team]:
        """Return all active Women's Super League teams."""
        data = await self._get(f"{_LEAGUE_PATH}/teams", {"limit": 100})
        raw_teams = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
        return [_parse_team(t) for t in raw_teams]

    async def get_team(self, team_id: str) -> Team:
        """Return a single team by its ESPN team ID.

        Raises:
            WSLNotFoundError: If no team with that ID exists.
        """
        data = await self._get(f"{_LEAGUE_PATH}/teams/{team_id}")
        raw = data.get("team")
        if not raw:
            raise WSLNotFoundError(f"Team not found: {team_id}")
        return _parse_team(raw)

    async def get_scoreboard(self, date: str | None = None, end_date: str | None = None) -> list[Match]:
        """Return matches on the given date or date range, or the current week if date is None."""
        params: dict[str, Any] = {}
        if date and end_date:
            params["dates"] = f"{date}-{end_date}"
        elif date:
            params["dates"] = date
        data = await self._get(f"{_LEAGUE_PATH}/scoreboard", params)
        return [_parse_match(e) for e in data.get("events", [])]

    async def get_roster(self, team_id: str) -> list[Player]:
        """Return the active roster for a team.

        Raises:
            WSLNotFoundError: If no team with that ID exists.
        """
        data = await self._get(f"{_LEAGUE_PATH}/teams/{team_id}/roster")
        return [_parse_player(p) for p in data.get("athletes", [])]

    async def get_match_details(self, match_id: str) -> MatchDetails:
        """Return detailed information for a single match.

        Raises:
            WSLNotFoundError: If no match with that ID exists.
        """
        data = await self._get(f"{_LEAGUE_PATH}/summary", {"event": match_id})
        return _parse_match_details(data)

    async def get_team_schedule(self, team_id: str) -> list[Match]:
        """Return all scheduled, in-progress, and completed matches for a team.

        ESPN's team-schedule endpoint returns only past events by default and only
        upcoming events when called with ``fixture=true``. Both variants are fetched
        in parallel and merged, deduped by event id, and sorted chronologically so
        callers see the full season in calendar order.

        Raises:
            WSLNotFoundError: If no team with that ID exists.
        """
        path = f"{_LEAGUE_PATH}/teams/{team_id}/schedule"
        past, future = await asyncio.gather(
            self._get(path),
            self._get(path, {"fixture": "true"}),
        )
        events_by_id: dict[str, dict[str, Any]] = {}
        for event in (*past.get("events", []), *future.get("events", [])):
            event_id = str(event.get("id", ""))
            events_by_id.setdefault(event_id, event)
        ordered = sorted(events_by_id.values(), key=lambda e: e.get("date", ""))
        return [_parse_match(e) for e in ordered]

    async def get_news(self, limit: int) -> list[NewsArticle]:
        """Return recent Women's Super League news articles."""
        data = await self._get(f"{_LEAGUE_PATH}/news", {"limit": limit})
        return [_parse_article(a) for a in data.get("articles", [])]

    async def get_standings(self) -> list[Standing]:
        """Return the current Women's Super League standings ordered by points descending."""
        data = await self._get(_STANDINGS_PATH)
        entries: list[dict[str, Any]] = []
        for season in data.get("children", []):
            for division in season.get("standings", {}).get("entries", []):
                entries.append(division)
        standings = [s for e in entries if (s := _parse_standing(e)) is not None]
        return sorted(standings, key=lambda s: s.points, reverse=True)
