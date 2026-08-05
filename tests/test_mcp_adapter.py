"""Unit tests for the MCP inbound adapter formatters and tool handlers.

Tests the formatting functions and safe_call error handling directly,
without spinning up a full MCP server.
"""

from __future__ import annotations

from pytest_mock import MockerFixture

from wsl.adapters.inbound.formatters import (
    _fmt_adjusted_ppg,
    _fmt_match_details,
    _fmt_news,
    _fmt_results_by_tier,
    _fmt_roster,
    _fmt_scoreboard,
    _fmt_standings,
    _fmt_strength_of_schedule,
    _fmt_team,
    _fmt_team_schedule,
    _fmt_teams,
)
from wsl.adapters.inbound.mcp_adapter import _safe_call, create_mcp_server
from wsl.application.service import WSLService
from wsl.domain.exceptions import UpstreamAPIError, WSLNotFoundError
from wsl.domain.models import (
    AdjustedPointsPerGame,
    Match,
    MatchDetails,
    NewsArticle,
    OpponentPPG,
    Player,
    ResultsByOpponentTier,
    Standing,
    StrengthOfSchedule,
    Team,
    TierRecord,
)


async def test_safe_call_returns_formatted_result(arsenal_wfc: Team) -> None:
    # Arrange
    async def _coro() -> Team:
        return arsenal_wfc

    # Act
    result = await _safe_call(_coro(), _fmt_team)
    # Assert
    assert "Arsenal" in result
    assert "ARS" in result


async def test_safe_call_handles_not_found() -> None:
    # Arrange
    async def _coro() -> list[Team]:
        raise WSLNotFoundError("Team not found: 9999")

    # Act
    result = await _safe_call(_coro(), _fmt_teams)
    # Assert
    assert "Not found" in result


async def test_safe_call_handles_upstream_error() -> None:
    # Arrange
    async def _coro() -> list[Team]:
        raise UpstreamAPIError("503")

    # Act
    result = await _safe_call(_coro(), _fmt_teams)
    # Assert
    assert "Upstream error" in result


async def test_safe_call_handles_value_error() -> None:
    # Arrange
    async def _coro() -> list[Match]:
        raise ValueError("date must be YYYYMMDD")

    # Act
    result = await _safe_call(_coro(), _fmt_scoreboard)
    # Assert
    assert "Invalid request" in result


def test_fmt_teams_empty() -> None:
    # Arrange / Act / Assert
    assert _fmt_teams([]) == "No teams found."


def test_fmt_teams_lists_all(arsenal_wfc: Team, aston_villa_wfc: Team) -> None:
    # Act
    result = _fmt_teams([arsenal_wfc, aston_villa_wfc])
    # Assert
    assert "Arsenal" in result
    assert "Aston Villa" in result
    assert "1." in result
    assert "2." in result


def test_fmt_scoreboard_empty() -> None:
    # Arrange / Act / Assert
    assert "No matches found" in _fmt_scoreboard([])


def test_fmt_scoreboard_shows_score(sample_match: Match) -> None:
    # Act
    result = _fmt_scoreboard([sample_match])
    # Assert
    assert "Arsenal" in result
    assert "2" in result
    assert "FT" in result


def test_fmt_scoreboard_shows_match_id(sample_match: Match) -> None:
    """get_match_details requires the match ID, so the listing must surface it."""
    # Act
    result = _fmt_scoreboard([sample_match])
    # Assert
    assert sample_match.id in result


def test_fmt_team_schedule_shows_match_id(sample_match: Match) -> None:
    """get_match_details requires the match ID, so the listing must surface it."""
    # Act
    result = _fmt_team_schedule([sample_match])
    # Assert
    assert sample_match.id in result


def test_fmt_news_empty() -> None:
    # Arrange / Act / Assert
    assert "No news" in _fmt_news([])


def test_fmt_news_lists_articles(sample_article: NewsArticle) -> None:
    # Act
    result = _fmt_news([sample_article])
    # Assert
    assert "2026-04-26" in result
    assert "espn.com" in result


def test_fmt_roster_empty() -> None:
    # Arrange / Act / Assert
    assert "No players" in _fmt_roster([])


def test_fmt_roster_lists_players(sample_player: Player) -> None:
    # Act
    result = _fmt_roster([sample_player])
    # Assert
    assert "Alessia Russo" in result
    assert "#10" in result
    assert "Forward" in result
    assert "England" in result


def test_fmt_match_details_includes_teams_score_venue(sample_match_details: MatchDetails) -> None:
    # Act
    result = _fmt_match_details(sample_match_details)
    # Assert
    assert "Aston Villa" in result
    assert "Arsenal" in result
    assert "2 - 2" in result
    assert "Emirates Stadium" in result
    assert "60,000" in result or "60000" in result


def test_fmt_match_details_lists_key_events(sample_match_details: MatchDetails) -> None:
    # Act
    result = _fmt_match_details(sample_match_details)
    # Assert
    assert "12'" in result
    assert "Alessia Russo" in result


def test_fmt_team_schedule_empty() -> None:
    # Arrange / Act / Assert
    assert "No scheduled matches" in _fmt_team_schedule([])


def test_fmt_team_schedule_lists_matches(sample_match: Match) -> None:
    # Act
    result = _fmt_team_schedule([sample_match])
    # Assert
    assert "Arsenal" in result
    assert "FT" in result


def test_fmt_standings_empty() -> None:
    # Arrange / Act / Assert
    assert "No standings data" in _fmt_standings([])


def test_fmt_standings_shows_points(sample_standing: Standing) -> None:
    # Act
    result = _fmt_standings([sample_standing])
    # Assert
    assert "38 pts" in result
    assert "Arsenal" in result
    assert "+22" in result


def test_fmt_standings_renders_flat_table(arsenal_wfc: Team, aston_villa_wfc: Team) -> None:
    """USL SL is a single-table league — both rows should appear in one numbered list."""
    # Arrange
    top = Standing(
        team=arsenal_wfc,
        wins=10,
        losses=3,
        ties=2,
        points=32,
        goals_for=30,
        goals_against=15,
        goal_difference=15,
    )
    second = Standing(
        team=aston_villa_wfc,
        wins=8,
        losses=5,
        ties=2,
        points=26,
        goals_for=25,
        goals_against=20,
        goal_difference=5,
    )
    # Act
    result = _fmt_standings([top, second])
    # Assert
    assert "1." in result
    assert "2." in result
    assert "Arsenal" in result
    assert "Aston Villa" in result


def test_create_mcp_server_returns_fastmcp(mocker: MockerFixture) -> None:
    # Arrange
    mock_service = mocker.MagicMock(spec=WSLService)
    # Act
    server = create_mcp_server(mock_service)
    # Assert
    assert server is not None


# ---------------------------------------------------------------------------
# Schedule-strength analytics formatters
# ---------------------------------------------------------------------------


def test_fmt_strength_of_schedule_empty(arsenal_wfc: Team) -> None:
    # Arrange
    sos = StrengthOfSchedule(team=arsenal_wfc, matches_played=0, opponents=[], average_opponent_ppg=0.0)
    # Act
    result = _fmt_strength_of_schedule(sos)
    # Assert
    assert "Arsenal" in result
    assert "no matches played" in result.lower()


def test_fmt_strength_of_schedule_lists_opponents(arsenal_wfc: Team, aston_villa_wfc: Team) -> None:
    # Arrange
    sos = StrengthOfSchedule(
        team=arsenal_wfc,
        matches_played=1,
        opponents=[OpponentPPG(team=aston_villa_wfc, matches_played=5, points=10, points_per_game=2.0)],
        average_opponent_ppg=2.0,
    )
    # Act
    result = _fmt_strength_of_schedule(sos)
    # Assert
    assert "Arsenal" in result
    assert "Aston Villa" in result
    assert "2.00" in result


def test_fmt_strength_of_schedule_collapses_repeat_opponents(arsenal_wfc: Team, aston_villa_wfc: Team) -> None:
    """When the same opponent appears twice, the formatter collapses to one row with x2."""
    # Arrange
    opp = OpponentPPG(team=aston_villa_wfc, matches_played=5, points=10, points_per_game=2.0)
    sos = StrengthOfSchedule(
        team=arsenal_wfc,
        matches_played=2,
        opponents=[opp, opp],
        average_opponent_ppg=2.0,
    )
    # Act
    result = _fmt_strength_of_schedule(sos)
    # Assert
    assert result.count("Aston Villa") == 1
    assert "x2" in result


def test_fmt_results_by_tier(arsenal_wfc: Team) -> None:
    # Arrange
    rbt = ResultsByOpponentTier(
        team=arsenal_wfc,
        tier_size=2,
        tiers=[
            TierRecord(label="Top 2", rank_low=1, rank_high=2, wins=0, losses=1, ties=0),
            TierRecord(label="Middle 2", rank_low=3, rank_high=4, wins=0, losses=0, ties=1),
            TierRecord(label="Bottom 2", rank_low=5, rank_high=6, wins=1, losses=0, ties=0),
        ],
    )
    # Act
    result = _fmt_results_by_tier(rbt)
    # Assert
    assert "Arsenal" in result
    assert "Top 2" in result
    assert "Middle 2" in result
    assert "Bottom 2" in result
    assert "0-1-0" in result
    assert "1-0-0" in result


def test_fmt_adjusted_ppg(arsenal_wfc: Team) -> None:
    # Arrange
    a = AdjustedPointsPerGame(
        team=arsenal_wfc,
        matches_played=5,
        points=10,
        raw_ppg=2.0,
        average_opponent_ppg=1.667,
        league_average_ppg=1.75,
        adjusted_ppg=1.905,
    )
    # Act
    result = _fmt_adjusted_ppg(a)
    # Assert
    assert "Arsenal" in result
    assert "2.00" in result
    assert "1.90" in result or "1.91" in result
