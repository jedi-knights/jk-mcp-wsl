"""RetryingAdapter — transparent retry decorator for WSLAPIPort.

Wraps any WSLAPIPort implementation and retries on UpstreamAPIError using
exponential backoff. WSLNotFoundError is not retried because a 404 is a
definitive answer, not a transient failure.

The sleep callable is injectable so tests can assert on backoff timing without
actually sleeping.
"""

import asyncio
import logging
from collections.abc import Callable

from ...domain.exceptions import WSLNotFoundError, UpstreamAPIError
from ...domain.models import Match, MatchDetails, NewsArticle, Player, Standing, Team
from ...ports.outbound import WSLAPIPort

logger = logging.getLogger(__name__)


class RetryingAdapter:
    """Decorates an WSLAPIPort with exponential-backoff retry on UpstreamAPIError.

    WSLNotFoundError propagates immediately — a 404 will not become a 200 on retry.
    """

    def __init__(
        self,
        inner: WSLAPIPort,
        max_attempts: int = 3,
        delay_seconds: float = 1.0,
        sleep: Callable[[float], object] = asyncio.sleep,
    ) -> None:
        """Initialize the retrying adapter.

        Args:
            inner: The WSLAPIPort implementation to wrap.
            max_attempts: Total number of attempts before giving up (minimum 1).
            delay_seconds: Base delay in seconds; doubled on each retry (exponential backoff).
            sleep: Async callable used to wait between retries. Injectable for testing.
        """
        self._inner = inner
        self._max_attempts = max(1, max_attempts)
        self._delay_seconds = delay_seconds
        self._sleep = sleep

    async def _retry(self, method_name: str, **kwargs: object) -> object:
        """Execute a port method with retry on UpstreamAPIError.

        Raises:
            WSLNotFoundError: Immediately, without retrying.
            UpstreamAPIError: After all attempts are exhausted.
        """
        method = getattr(self._inner, method_name)
        last_error: UpstreamAPIError | None = None
        for attempt in range(self._max_attempts):
            try:
                return await method(**kwargs)
            except WSLNotFoundError:
                raise
            except UpstreamAPIError as exc:
                last_error = exc
                if attempt < self._max_attempts - 1:
                    delay = self._delay_seconds * (2**attempt)
                    logger.warning(
                        "Attempt %d/%d failed for %s, retrying in %.1fs: %s",
                        attempt + 1,
                        self._max_attempts,
                        method_name,
                        delay,
                        exc,
                    )
                    await self._sleep(delay)
        raise last_error  # type: ignore[misc]

    async def get_teams(self) -> list[Team]:
        return await self._retry("get_teams")  # type: ignore[return-value]

    async def get_team(self, team_id: str) -> Team:
        return await self._retry("get_team", team_id=team_id)  # type: ignore[return-value]

    async def get_scoreboard(self, date: str | None = None, end_date: str | None = None) -> list[Match]:
        return await self._retry("get_scoreboard", date=date, end_date=end_date)  # type: ignore[return-value]

    async def get_team_schedule(self, team_id: str) -> list[Match]:
        return await self._retry("get_team_schedule", team_id=team_id)  # type: ignore[return-value]

    async def get_match_details(self, match_id: str) -> MatchDetails:
        return await self._retry("get_match_details", match_id=match_id)  # type: ignore[return-value]

    async def get_roster(self, team_id: str) -> list[Player]:
        return await self._retry("get_roster", team_id=team_id)  # type: ignore[return-value]

    async def get_news(self, limit: int) -> list[NewsArticle]:
        return await self._retry("get_news", limit=limit)  # type: ignore[return-value]

    async def get_standings(self) -> list[Standing]:
        return await self._retry("get_standings")  # type: ignore[return-value]
