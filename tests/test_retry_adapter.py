"""Unit tests for RetryingAdapter.

Uses a no-op sleep callable so tests run at full speed.
"""

from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from wsl.adapters.outbound.retry_adapter import RetryingAdapter
from wsl.domain.exceptions import WSLNotFoundError, UpstreamAPIError
from wsl.domain.models import Team
from wsl.ports.outbound import WSLAPIPort


@pytest.fixture
def mock_inner(mocker: MockerFixture) -> AsyncMock:
    return mocker.AsyncMock(spec=WSLAPIPort)


async def _no_sleep(_: float) -> None:
    pass


async def test_success_on_first_attempt(mock_inner: AsyncMock, arsenal_wfc: Team) -> None:
    adapter = RetryingAdapter(mock_inner, sleep=_no_sleep)
    mock_inner.get_teams.return_value = [arsenal_wfc]
    result = await adapter.get_teams()
    assert result == [arsenal_wfc]
    mock_inner.get_teams.assert_called_once()


async def test_retries_on_upstream_error(mock_inner: AsyncMock, arsenal_wfc: Team) -> None:
    adapter = RetryingAdapter(mock_inner, max_attempts=3, sleep=_no_sleep)
    mock_inner.get_teams.side_effect = [UpstreamAPIError("503"), [arsenal_wfc]]
    result = await adapter.get_teams()
    assert result == [arsenal_wfc]
    assert mock_inner.get_teams.call_count == 2


async def test_raises_after_max_attempts(mock_inner: AsyncMock) -> None:
    adapter = RetryingAdapter(mock_inner, max_attempts=2, sleep=_no_sleep)
    mock_inner.get_teams.side_effect = UpstreamAPIError("503")
    with pytest.raises(UpstreamAPIError):
        await adapter.get_teams()
    assert mock_inner.get_teams.call_count == 2


async def test_get_news_retries_on_upstream_error(mock_inner: AsyncMock, sample_article) -> None:
    adapter = RetryingAdapter(mock_inner, max_attempts=3, sleep=_no_sleep)
    mock_inner.get_news.side_effect = [UpstreamAPIError("503"), [sample_article]]
    result = await adapter.get_news(5)
    assert result == [sample_article]
    assert mock_inner.get_news.call_count == 2


async def test_get_roster_retries_on_upstream_error(mock_inner: AsyncMock, sample_player) -> None:
    adapter = RetryingAdapter(mock_inner, max_attempts=3, sleep=_no_sleep)
    mock_inner.get_roster.side_effect = [UpstreamAPIError("503"), [sample_player]]
    result = await adapter.get_roster("15362")
    assert result == [sample_player]
    assert mock_inner.get_roster.call_count == 2


async def test_get_match_details_retries_on_upstream_error(mock_inner: AsyncMock, sample_match_details) -> None:
    adapter = RetryingAdapter(mock_inner, max_attempts=3, sleep=_no_sleep)
    mock_inner.get_match_details.side_effect = [UpstreamAPIError("503"), sample_match_details]
    result = await adapter.get_match_details("401853883")
    assert result == sample_match_details
    assert mock_inner.get_match_details.call_count == 2


async def test_get_team_schedule_retries_on_upstream_error(mock_inner: AsyncMock, sample_match) -> None:
    adapter = RetryingAdapter(mock_inner, max_attempts=3, sleep=_no_sleep)
    mock_inner.get_team_schedule.side_effect = [UpstreamAPIError("503"), [sample_match]]
    result = await adapter.get_team_schedule("1899")
    assert result == [sample_match]
    assert mock_inner.get_team_schedule.call_count == 2


async def test_not_found_is_not_retried(mock_inner: AsyncMock) -> None:
    adapter = RetryingAdapter(mock_inner, max_attempts=3, sleep=_no_sleep)
    mock_inner.get_team.side_effect = WSLNotFoundError("Team not found: 9999")
    with pytest.raises(WSLNotFoundError):
        await adapter.get_team("9999")
    mock_inner.get_team.assert_called_once()
