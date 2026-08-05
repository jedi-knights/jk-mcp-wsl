"""CachingAdapter — transparent TTL-cache decorator for WSLAPIPort.

Wraps any WSLAPIPort implementation and caches successful results in a
plain dict. Cache keys are derived from the method name plus the sorted
keyword arguments, making the cache transparent to callers.

The clock function is injectable so tests can control TTL expiry without
actually sleeping.

Women's Super League data changes infrequently (lineups, scores update during matches), so
a default TTL of 5 minutes is appropriate for most tools. The scoreboard
uses a shorter TTL of 60 seconds to stay reasonably live during matches.
"""

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from ...domain.models import Match, MatchDetails, NewsArticle, Player, Standing, Team
from ...ports.outbound import WSLAPIPort

logger = logging.getLogger(__name__)


def _cache_key(method: str, kwargs: dict[str, Any]) -> str:
    """Build a deterministic cache key from a method name and its kwargs.

    Args:
        method: The name of the port method being called.
        kwargs: The keyword arguments passed to that method.

    Returns:
        A JSON string that uniquely identifies this (method, params) pair.
    """
    return json.dumps({"method": method, "params": kwargs}, sort_keys=True, default=str)


class CachingAdapter:
    """Decorates a WSLAPIPort with a TTL-based in-memory cache."""

    def __init__(
        self,
        inner: WSLAPIPort,
        ttl_seconds: float = 300.0,
        scoreboard_ttl_seconds: float = 60.0,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize the caching adapter.

        Args:
            inner: The WSLAPIPort implementation to wrap.
            ttl_seconds: Default time-to-live for cached entries in seconds.
            scoreboard_ttl_seconds: TTL for scoreboard data (shorter for live match updates).
            now: Callable that returns the current monotonic time. Injectable for testing.
        """
        self._inner = inner
        self._ttl = ttl_seconds
        self._scoreboard_ttl = scoreboard_ttl_seconds
        self._now = now
        self._cache: dict[str, tuple[float, Any]] = {}

    async def _get_or_fetch(self, method_name: str, ttl: float, **kwargs: Any) -> Any:
        """Return a cached result or fetch from the inner adapter.

        Args:
            method_name: Name of the method on the inner adapter to call.
            ttl: TTL in seconds to use for this cache entry.
            **kwargs: Keyword arguments forwarded to the method.

        Returns:
            The cached or freshly-fetched result.
        """
        key = _cache_key(method_name, kwargs)
        entry = self._cache.get(key)
        if entry is not None:
            expiry, result = entry
            if self._now() < expiry:
                logger.debug("Cache hit for %s", method_name)
                return result
            del self._cache[key]

        logger.debug("Cache miss for %s, fetching from inner adapter", method_name)
        method = getattr(self._inner, method_name)
        result = await method(**kwargs)
        self._cache[key] = (self._now() + ttl, result)
        return result

    async def get_teams(self) -> list[Team]:
        return await self._get_or_fetch("get_teams", self._ttl)

    async def get_team(self, team_id: str) -> Team:
        return await self._get_or_fetch("get_team", self._ttl, team_id=team_id)

    async def get_scoreboard(self, date: str | None = None, end_date: str | None = None) -> list[Match]:
        return await self._get_or_fetch("get_scoreboard", self._scoreboard_ttl, date=date, end_date=end_date)

    async def get_team_schedule(self, team_id: str) -> list[Match]:
        return await self._get_or_fetch("get_team_schedule", self._ttl, team_id=team_id)

    async def get_match_details(self, match_id: str) -> MatchDetails:
        return await self._get_or_fetch("get_match_details", self._scoreboard_ttl, match_id=match_id)

    async def get_roster(self, team_id: str) -> list[Player]:
        return await self._get_or_fetch("get_roster", self._ttl, team_id=team_id)

    async def get_news(self, limit: int) -> list[NewsArticle]:
        return await self._get_or_fetch("get_news", self._ttl, limit=limit)

    async def get_standings(self) -> list[Standing]:
        return await self._get_or_fetch("get_standings", self._ttl)
