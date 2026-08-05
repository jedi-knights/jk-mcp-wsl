"""Unit tests for CachingAdapter.

Uses a synthetic clock so tests can simulate TTL expiry without sleeping.
"""

from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from wsl.adapters.outbound.caching_adapter import CachingAdapter
from wsl.domain.models import Team
from wsl.ports.outbound import WSLAPIPort


@pytest.fixture
def mock_inner(mocker: MockerFixture) -> AsyncMock:
    return mocker.AsyncMock(spec=WSLAPIPort)


@pytest.fixture
def clock() -> list[float]:
    return [0.0]


def make_clock(state: list[float]):
    def _now() -> float:
        return state[0]

    return _now


async def test_cache_hit_skips_inner_call(
    mock_inner: AsyncMock,
    arsenal_wfc: Team,
    clock: list[float],
) -> None:
    adapter = CachingAdapter(mock_inner, ttl_seconds=60.0, now=make_clock(clock))
    mock_inner.get_teams.return_value = [arsenal_wfc]

    result1 = await adapter.get_teams()
    result2 = await adapter.get_teams()

    assert result1 == [arsenal_wfc]
    assert result2 == [arsenal_wfc]
    mock_inner.get_teams.assert_called_once()


async def test_cache_miss_after_ttl_expiry(
    mock_inner: AsyncMock,
    arsenal_wfc: Team,
    clock: list[float],
) -> None:
    adapter = CachingAdapter(mock_inner, ttl_seconds=30.0, now=make_clock(clock))
    mock_inner.get_teams.return_value = [arsenal_wfc]

    await adapter.get_teams()
    clock[0] = 31.0
    await adapter.get_teams()

    assert mock_inner.get_teams.call_count == 2


async def test_get_news_is_cached(
    mock_inner: AsyncMock,
    sample_article,
    clock: list[float],
) -> None:
    adapter = CachingAdapter(mock_inner, ttl_seconds=60.0, now=make_clock(clock))
    mock_inner.get_news.return_value = [sample_article]

    await adapter.get_news(5)
    await adapter.get_news(5)

    mock_inner.get_news.assert_called_once_with(limit=5)


async def test_get_roster_is_cached(
    mock_inner: AsyncMock,
    sample_player,
    clock: list[float],
) -> None:
    adapter = CachingAdapter(mock_inner, ttl_seconds=60.0, now=make_clock(clock))
    mock_inner.get_roster.return_value = [sample_player]

    await adapter.get_roster("15362")
    await adapter.get_roster("15362")

    mock_inner.get_roster.assert_called_once_with(team_id="15362")


async def test_get_match_details_is_cached(
    mock_inner: AsyncMock,
    sample_match_details,
    clock: list[float],
) -> None:
    adapter = CachingAdapter(mock_inner, ttl_seconds=60.0, now=make_clock(clock))
    mock_inner.get_match_details.return_value = sample_match_details

    await adapter.get_match_details("401853883")
    await adapter.get_match_details("401853883")

    mock_inner.get_match_details.assert_called_once_with(match_id="401853883")


async def test_get_team_schedule_is_cached(
    mock_inner: AsyncMock,
    sample_match,
    clock: list[float],
) -> None:
    adapter = CachingAdapter(mock_inner, ttl_seconds=60.0, now=make_clock(clock))
    mock_inner.get_team_schedule.return_value = [sample_match]

    await adapter.get_team_schedule("1899")
    await adapter.get_team_schedule("1899")

    mock_inner.get_team_schedule.assert_called_once_with(team_id="1899")


async def test_scoreboard_uses_shorter_ttl(
    mock_inner: AsyncMock,
    sample_match,
    clock: list[float],
) -> None:
    adapter = CachingAdapter(mock_inner, ttl_seconds=300.0, scoreboard_ttl_seconds=60.0, now=make_clock(clock))
    mock_inner.get_scoreboard.return_value = [sample_match]

    await adapter.get_scoreboard("20250601")
    clock[0] = 61.0
    await adapter.get_scoreboard("20250601")

    assert mock_inner.get_scoreboard.call_count == 2
