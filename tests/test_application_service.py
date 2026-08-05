"""Unit tests for the WSLService application layer.

Tests verify that the service delegates correctly to the outbound port and
enforces input validation before any port call is made.
"""

from unittest.mock import AsyncMock

import pytest

from wsl.application.service import WSLService
from wsl.domain.models import (
    AdjustedPointsPerGame,
    Match,
    MatchCompetitor,
    MatchDetails,
    NewsArticle,
    Player,
    ResultsByOpponentTier,
    Standing,
    StrengthOfSchedule,
    Team,
)


async def test_get_teams_delegates_to_repo(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    arsenal_wfc: Team,
) -> None:
    mock_repo.get_teams.return_value = [arsenal_wfc]
    result = await wsl_service.get_teams()
    mock_repo.get_teams.assert_called_once()
    assert result == [arsenal_wfc]


async def test_get_team_delegates_to_repo(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    arsenal_wfc: Team,
) -> None:
    mock_repo.get_team.return_value = arsenal_wfc
    result = await wsl_service.get_team("19973")
    mock_repo.get_team.assert_called_once_with("19973")
    assert result == arsenal_wfc


async def test_get_team_strips_whitespace(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    arsenal_wfc: Team,
) -> None:
    mock_repo.get_team.return_value = arsenal_wfc
    await wsl_service.get_team("  19973  ")
    mock_repo.get_team.assert_called_once_with("19973")


@pytest.mark.parametrize("bad_id", ["", "   "])
async def test_get_team_rejects_empty_id(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    bad_id: str,
) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await wsl_service.get_team(bad_id)
    mock_repo.get_team.assert_not_called()


async def test_get_scoreboard_delegates_to_repo(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    sample_match: Match,
) -> None:
    mock_repo.get_scoreboard.return_value = [sample_match]
    result = await wsl_service.get_scoreboard("20250601")
    mock_repo.get_scoreboard.assert_called_once_with("20250601", None)
    assert result == [sample_match]


async def test_get_scoreboard_with_date_range(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    sample_match: Match,
) -> None:
    mock_repo.get_scoreboard.return_value = [sample_match]
    result = await wsl_service.get_scoreboard("20260404", end_date="20260405")
    mock_repo.get_scoreboard.assert_called_once_with("20260404", "20260405")
    assert result == [sample_match]


async def test_get_scoreboard_rejects_end_date_without_start(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    with pytest.raises(ValueError, match="end_date requires"):
        await wsl_service.get_scoreboard(None, end_date="20260405")
    mock_repo.get_scoreboard.assert_not_called()


@pytest.mark.parametrize("bad_end", ["2026-04-05", "2026040", "ABCDEFGH"])
async def test_get_scoreboard_rejects_invalid_end_date(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    bad_end: str,
) -> None:
    with pytest.raises(ValueError, match="YYYYMMDD"):
        await wsl_service.get_scoreboard("20260404", end_date=bad_end)
    mock_repo.get_scoreboard.assert_not_called()


async def test_get_scoreboard_accepts_none_date(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    mock_repo.get_scoreboard.return_value = []
    await wsl_service.get_scoreboard(None)
    mock_repo.get_scoreboard.assert_called_once_with(None, None)


@pytest.mark.parametrize("bad_date", ["2025-06-01", "20250", "ABCDEFGH", "2025060"])
async def test_get_scoreboard_rejects_invalid_date(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    bad_date: str,
) -> None:
    with pytest.raises(ValueError, match="YYYYMMDD"):
        await wsl_service.get_scoreboard(bad_date)
    mock_repo.get_scoreboard.assert_not_called()


async def test_get_news_delegates_to_repo(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    sample_article: NewsArticle,
) -> None:
    mock_repo.get_news.return_value = [sample_article]
    result = await wsl_service.get_news(5)
    mock_repo.get_news.assert_called_once_with(5)
    assert result == [sample_article]


async def test_get_news_defaults_to_ten(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    mock_repo.get_news.return_value = []
    await wsl_service.get_news()
    mock_repo.get_news.assert_called_once_with(10)


@pytest.mark.parametrize("bad_limit", [0, -1, -100])
async def test_get_news_rejects_non_positive_limit(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    bad_limit: int,
) -> None:
    with pytest.raises(ValueError, match="positive"):
        await wsl_service.get_news(bad_limit)
    mock_repo.get_news.assert_not_called()


async def test_get_roster_delegates_to_repo(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    sample_player: Player,
) -> None:
    mock_repo.get_roster.return_value = [sample_player]
    result = await wsl_service.get_roster("19973")
    mock_repo.get_roster.assert_called_once_with("19973")
    assert result == [sample_player]


async def test_get_roster_strips_whitespace(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    mock_repo.get_roster.return_value = []
    await wsl_service.get_roster("  19973  ")
    mock_repo.get_roster.assert_called_once_with("19973")


@pytest.mark.parametrize("bad_id", ["", "   "])
async def test_get_roster_rejects_empty_id(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    bad_id: str,
) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await wsl_service.get_roster(bad_id)
    mock_repo.get_roster.assert_not_called()


async def test_get_match_details_delegates_to_repo(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    sample_match_details: MatchDetails,
) -> None:
    mock_repo.get_match_details.return_value = sample_match_details
    result = await wsl_service.get_match_details("401853883")
    mock_repo.get_match_details.assert_called_once_with("401853883")
    assert result == sample_match_details


async def test_get_match_details_strips_whitespace(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    sample_match_details: MatchDetails,
) -> None:
    mock_repo.get_match_details.return_value = sample_match_details
    await wsl_service.get_match_details("  401853883  ")
    mock_repo.get_match_details.assert_called_once_with("401853883")


@pytest.mark.parametrize("bad_id", ["", "   "])
async def test_get_match_details_rejects_empty_id(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    bad_id: str,
) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await wsl_service.get_match_details(bad_id)
    mock_repo.get_match_details.assert_not_called()


async def test_get_team_schedule_delegates_to_repo(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    sample_match: Match,
) -> None:
    mock_repo.get_team_schedule.return_value = [sample_match]
    result = await wsl_service.get_team_schedule("19973")
    mock_repo.get_team_schedule.assert_called_once_with("19973")
    assert result == [sample_match]


async def test_get_team_schedule_strips_whitespace(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    mock_repo.get_team_schedule.return_value = []
    await wsl_service.get_team_schedule("  19973  ")
    mock_repo.get_team_schedule.assert_called_once_with("19973")


@pytest.mark.parametrize("bad_id", ["", "   "])
async def test_get_team_schedule_rejects_empty_id(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    bad_id: str,
) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await wsl_service.get_team_schedule(bad_id)
    mock_repo.get_team_schedule.assert_not_called()


async def test_get_standings_delegates_to_repo(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    sample_standing: Standing,
) -> None:
    mock_repo.get_standings.return_value = [sample_standing]
    result = await wsl_service.get_standings()
    mock_repo.get_standings.assert_called_once()
    assert result == [sample_standing]


# ---------------------------------------------------------------------------
# Schedule-strength analytics — shared scaffolding
# ---------------------------------------------------------------------------


def _team(team_id: str, name: str, abbr: str) -> Team:
    """Build a minimal Team for analytics fixtures."""
    return Team(id=team_id, name=name, abbreviation=abbr, location=name, display_name=name)


def _standing(team: Team, w: int, l_: int, t: int, gf: int = 0, ga: int = 0) -> Standing:
    """Build a Standing row from W-L-T (points and GD derived)."""
    return Standing(
        team=team,
        wins=w,
        losses=l_,
        ties=t,
        points=3 * w + t,
        goals_for=gf,
        goals_against=ga,
        goal_difference=gf - ga,
    )


def _played(match_id: str, home: Team, away: Team, home_score: str, away_score: str) -> Match:
    """Build a completed Match (status_type='post') with declared winner."""
    home_won = int(home_score) > int(away_score)
    away_won = int(away_score) > int(home_score)
    return Match(
        id=match_id,
        date="2026-04-01T20:00Z",
        name=f"{away.display_name} at {home.display_name}",
        short_name=f"{away.abbreviation} @ {home.abbreviation}",
        status_type="post",
        status_detail="FT",
        competitors=[
            MatchCompetitor(team=home, home_away="home", score=home_score, winner=home_won),
            MatchCompetitor(team=away, home_away="away", score=away_score, winner=away_won),
        ],
    )


def _scheduled(match_id: str, home: Team, away: Team) -> Match:
    """Build an unplayed Match (status_type='pre') with no scores."""
    return Match(
        id=match_id,
        date="2026-05-01T20:00Z",
        name=f"{away.display_name} at {home.display_name}",
        short_name=f"{away.abbreviation} @ {home.abbreviation}",
        status_type="pre",
        status_detail="Scheduled",
        competitors=[
            MatchCompetitor(team=home, home_away="home"),
            MatchCompetitor(team=away, home_away="away"),
        ],
    )


# ---------------------------------------------------------------------------
# get_strength_of_schedule
# ---------------------------------------------------------------------------


async def test_get_strength_of_schedule_averages_played_opponents_ppg(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    mia = _team("mia", "Aston Villa", "AVL")
    atl = _team("19973", "Arsenal", "ARS")
    nyc = _team("nyc", "Chelsea Reserves", "NYC")
    chi = _team("chi", "Manchester City", "MCI")
    # 5 matches each — PPG: AVL 12/5=2.4, ARS 10/5=2.0, NYC 10/5=2.0, CHI 3/5=0.6
    mock_repo.get_standings.return_value = [
        _standing(mia, w=4, l_=1, t=0),
        _standing(atl, w=3, l_=1, t=1),
        _standing(nyc, w=3, l_=1, t=1),
        _standing(chi, w=1, l_=4, t=0),
    ]
    # Arsenal has played 3 of 4 opponents
    mock_repo.get_team_schedule.return_value = [
        _played("m1", home=mia, away=atl, home_score="3", away_score="1"),
        _played("m2", home=atl, away=nyc, home_score="2", away_score="0"),
        _played("m3", home=atl, away=chi, home_score="2", away_score="0"),
        _scheduled("m4", home=atl, away=mia),
    ]

    result = await wsl_service.get_strength_of_schedule("19973")

    assert isinstance(result, StrengthOfSchedule)
    assert result.team == atl
    assert result.matches_played == 3
    assert {o.team.id for o in result.opponents} == {"mia", "nyc", "chi"}
    assert result.average_opponent_ppg == pytest.approx((2.4 + 2.0 + 0.6) / 3)


async def test_get_strength_of_schedule_returns_zero_when_no_matches_played(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    atl = _team("19973", "Arsenal", "ARS")
    mia = _team("mia", "Aston Villa", "AVL")
    mock_repo.get_standings.return_value = [_standing(atl, 0, 0, 0), _standing(mia, 0, 0, 0)]
    mock_repo.get_team_schedule.return_value = [_scheduled("m1", home=atl, away=mia)]

    result = await wsl_service.get_strength_of_schedule("19973")

    assert result.matches_played == 0
    assert result.opponents == []
    assert result.average_opponent_ppg == 0.0


async def test_get_strength_of_schedule_rejects_empty_team_id(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await wsl_service.get_strength_of_schedule("  ")
    mock_repo.get_standings.assert_not_called()


async def test_get_strength_of_schedule_skips_opponents_missing_from_standings(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    """An opponent that's in the schedule but absent from the live standings is skipped.

    Happens during expansion-team weeks or if the standings response lags the
    fixture data. The played match against the unranked team should not be
    included in the SoS aggregate.
    """
    mia = _team("mia", "Aston Villa", "AVL")
    atl = _team("19973", "Arsenal", "ARS")
    ghost = _team("ghost", "New Expansion", "NEW")
    # `ghost` is absent from standings entirely.
    mock_repo.get_standings.return_value = [
        _standing(mia, w=4, l_=1, t=0),
        _standing(atl, w=3, l_=1, t=1),
    ]
    mock_repo.get_team_schedule.return_value = [
        _played("m1", home=mia, away=atl, home_score="3", away_score="1"),
        _played("m2", home=atl, away=ghost, home_score="2", away_score="0"),
    ]

    result = await wsl_service.get_strength_of_schedule("19973")

    # Only AVL counts toward the average; ghost is silently skipped.
    assert {o.team.id for o in result.opponents} == {"mia"}
    assert result.matches_played == 1
    assert result.average_opponent_ppg == pytest.approx(12 / 5)


# ---------------------------------------------------------------------------
# get_results_by_opponent_tier
# ---------------------------------------------------------------------------


async def test_get_results_by_opponent_tier_splits_by_current_standings(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    # 6-team league. Atl sits in the middle and has played one team in each tier.
    mia = _team("mia", "Aston Villa", "AVL")
    nyc = _team("nyc", "Chelsea Reserves", "NYC")
    atl = _team("19973", "Arsenal", "ARS")
    nc = _team("nc", "Chelsea FC", "CHE")
    chi = _team("chi", "Manchester City", "MCI")
    bos = _team("bos", "Tottenham", "TOT")
    # Standings order: AVL, NYC, ARS, NC, CHI, BOS  (rank 1..6)
    mock_repo.get_standings.return_value = [
        _standing(mia, w=4, l_=0, t=0),
        _standing(nyc, w=3, l_=1, t=0),
        _standing(atl, w=2, l_=2, t=0),
        _standing(nc, w=2, l_=2, t=0),
        _standing(chi, w=1, l_=3, t=0),
        _standing(bos, w=0, l_=4, t=0),
    ]
    # ARS: lost to AVL (top tier), tied NC (middle), beat BOS (bottom)
    mock_repo.get_team_schedule.return_value = [
        _played("m1", home=mia, away=atl, home_score="2", away_score="0"),
        _played("m2", home=atl, away=nc, home_score="1", away_score="1"),
        _played("m3", home=atl, away=bos, home_score="3", away_score="0"),
        _scheduled("m4", home=atl, away=chi),
    ]

    result = await wsl_service.get_results_by_opponent_tier("19973", tier_size=2)

    assert isinstance(result, ResultsByOpponentTier)
    assert result.tier_size == 2
    by_label = {t.label: t for t in result.tiers}
    assert by_label["Top 2"].wins == 0
    assert by_label["Top 2"].losses == 1
    assert by_label["Top 2"].ties == 0
    assert by_label["Middle 2"].wins == 0
    assert by_label["Middle 2"].losses == 0
    assert by_label["Middle 2"].ties == 1  # Drew NC, who is rank 4 (middle)
    assert by_label["Bottom 2"].wins == 1
    assert by_label["Bottom 2"].losses == 0
    assert by_label["Bottom 2"].ties == 0


@pytest.mark.parametrize("bad_size", [0, -1, 4])
async def test_get_results_by_opponent_tier_rejects_invalid_tier_size(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
    bad_size: int,
) -> None:
    # 6-team league means valid tier_size is 1..3 (2*tier_size <= league_size).
    teams = [_team(f"t{i}", f"Team {i}", f"T{i}") for i in range(6)]
    mock_repo.get_standings.return_value = [_standing(t, w=0, l_=0, t=0) for t in teams]
    mock_repo.get_team_schedule.return_value = []

    with pytest.raises(ValueError, match="tier_size"):
        await wsl_service.get_results_by_opponent_tier("t0", tier_size=bad_size)


async def test_get_results_by_opponent_tier_rejects_empty_team_id(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await wsl_service.get_results_by_opponent_tier("", tier_size=2)
    mock_repo.get_standings.assert_not_called()


async def test_get_results_by_opponent_tier_accepts_max_tier_size(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    """At tier_size = league_size // 2, the middle tier is empty and gets filtered out."""
    teams = [_team(f"t{i}", f"Team {i}", f"T{i}") for i in range(6)]
    mock_repo.get_standings.return_value = [_standing(t, w=0, l_=0, t=0) for t in teams]
    mock_repo.get_team_schedule.return_value = []

    result = await wsl_service.get_results_by_opponent_tier("t0", tier_size=3)

    # 6-team league, tier_size 3 -> Top 3 (1-3) + Bottom 3 (4-6); no middle.
    labels = [tier.label for tier in result.tiers]
    assert labels == ["Top 3", "Bottom 3"]


# ---------------------------------------------------------------------------
# get_adjusted_points_per_game
# ---------------------------------------------------------------------------


async def test_get_adjusted_points_per_game_scales_by_opponent_quality(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    mia = _team("mia", "Aston Villa", "AVL")
    atl = _team("19973", "Arsenal", "ARS")
    nyc = _team("nyc", "Chelsea Reserves", "NYC")
    chi = _team("chi", "Manchester City", "MCI")
    # 5 matches each — total = 35 pts / 20 matches = 1.75 league avg PPG
    mock_repo.get_standings.return_value = [
        _standing(mia, w=4, l_=1, t=0),  # 12 pts → 2.4 PPG
        _standing(atl, w=3, l_=1, t=1),  # 10 pts → 2.0 PPG
        _standing(nyc, w=3, l_=1, t=1),  # 10 pts → 2.0 PPG
        _standing(chi, w=1, l_=4, t=0),  # 3 pts → 0.6 PPG
    ]
    # Arsenal's played opponents: AVL, NYC, CHI → avg opp PPG = (2.4+2.0+0.6)/3 ≈ 1.667
    mock_repo.get_team_schedule.return_value = [
        _played("m1", home=mia, away=atl, home_score="3", away_score="1"),
        _played("m2", home=atl, away=nyc, home_score="2", away_score="0"),
        _played("m3", home=atl, away=chi, home_score="2", away_score="0"),
    ]

    result = await wsl_service.get_adjusted_points_per_game("19973")

    assert isinstance(result, AdjustedPointsPerGame)
    assert result.team == atl
    assert result.matches_played == 5
    assert result.points == 10
    assert result.raw_ppg == pytest.approx(2.0)
    expected_avg_opp = (2.4 + 2.0 + 0.6) / 3
    assert result.average_opponent_ppg == pytest.approx(expected_avg_opp)
    assert result.league_average_ppg == pytest.approx(35 / 20)
    assert result.adjusted_ppg == pytest.approx(2.0 * (expected_avg_opp / (35 / 20)))


async def test_get_adjusted_points_per_game_handles_zero_league_average(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    atl = _team("19973", "Arsenal", "ARS")
    mia = _team("mia", "Aston Villa", "AVL")
    mock_repo.get_standings.return_value = [_standing(atl, 0, 0, 0), _standing(mia, 0, 0, 0)]
    mock_repo.get_team_schedule.return_value = []

    result = await wsl_service.get_adjusted_points_per_game("19973")

    assert result.raw_ppg == 0.0
    assert result.adjusted_ppg == 0.0
    assert result.league_average_ppg == 0.0


async def test_get_adjusted_points_per_game_rejects_empty_team_id(
    wsl_service: WSLService,
    mock_repo: AsyncMock,
) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await wsl_service.get_adjusted_points_per_game("")
    mock_repo.get_standings.assert_not_called()
