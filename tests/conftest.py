"""Shared fixtures for the Women's Super League test suite.

These fixtures act as the composition root for testing — they wire together
real domain models and mock/stub implementations of ports, mirroring the
dependency injection pattern used in the production server.py entry point.
"""

from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from wsl.application.service import WSLService
from wsl.domain.models import (
    Match,
    MatchCompetitor,
    MatchDetails,
    MatchEvent,
    NewsArticle,
    Player,
    Standing,
    Team,
)
from wsl.ports.outbound import WSLAPIPort

# ---------------------------------------------------------------------------
# Domain model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def arsenal_wfc() -> Team:
    """Arsenal sample team."""
    return Team(
        id="19973",
        name="Arsenal",
        abbreviation="ARS",
        location="London",
        display_name="Arsenal",
        logo_url="https://a.espncdn.com/i/teamlogos/soccer/500/19973.png",
    )


@pytest.fixture
def aston_villa_wfc() -> Team:
    """Aston Villa sample team."""
    return Team(
        id="20707",
        name="Aston Villa",
        abbreviation="AVL",
        location="Birmingham",
        display_name="Aston Villa",
        logo_url="https://a.espncdn.com/i/teamlogos/soccer/500/20707.png",
    )


@pytest.fixture
def sample_match(arsenal_wfc: Team, aston_villa_wfc: Team) -> Match:
    """A completed match between Arsenal and Aston Villa."""
    return Match(
        id="701123",
        date="2026-06-01T20:00Z",
        name="Arsenal vs Aston Villa",
        short_name="ARS vs AVL",
        status_type="post",
        status_detail="FT",
        competitors=[
            MatchCompetitor(team=arsenal_wfc, home_away="home", score="2", winner=True),
            MatchCompetitor(team=aston_villa_wfc, home_away="away", score="1", winner=False),
        ],
    )


@pytest.fixture
def sample_match_details() -> MatchDetails:
    """A completed match with venue, attendance, and key events."""
    return MatchDetails(
        id="401853883",
        date="2026-04-04T22:30Z",
        status_detail="Full Time",
        home_team="Aston Villa",
        away_team="Arsenal",
        home_score="2",
        away_score="2",
        venue="Emirates Stadium",
        venue_city="London, England",
        attendance=60000,
        key_events=[
            MatchEvent(
                clock="12'",
                period=1,
                type="goal---header",
                scoring=True,
                text="Goal! AVL 0, ARS 1. Alessia Russo.",
                team_name="Arsenal",
            ),
        ],
    )


@pytest.fixture
def sample_article() -> NewsArticle:
    """A sample news article."""
    return NewsArticle(
        id="48595550",
        headline="Arsenal vs. Aston Villa - Game Highlights",
        description="Watch the Game Highlights from Arsenal vs. Aston Villa, 04/26/2026",
        published="2026-04-26T00:48:46Z",
        link="https://www.espn.com/video/clip?id=48595550",
    )


@pytest.fixture
def sample_player() -> Player:
    """A sample roster player."""
    return Player(
        id="219821",
        full_name="Alessia Russo",
        jersey="10",
        position="Forward",
        position_abbr="F",
        citizenship="England",
        age=22,
    )


@pytest.fixture
def sample_standing(arsenal_wfc: Team) -> Standing:
    """A sample standings entry for Arsenal."""
    return Standing(
        team=arsenal_wfc,
        wins=12,
        losses=4,
        ties=2,
        points=38,
        goals_for=40,
        goals_against=18,
        goal_difference=22,
    )


# ---------------------------------------------------------------------------
# Port mock and service fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo(mocker: MockerFixture) -> AsyncMock:
    """AsyncMock that satisfies the WSLAPIPort protocol."""
    return mocker.AsyncMock(spec=WSLAPIPort)


@pytest.fixture
def wsl_service(mock_repo: AsyncMock) -> WSLService:
    """WSLService wired with a mock ESPN port — the primary DI seam for service tests."""
    return WSLService(repo=mock_repo)
