"""Tests for domain model construction and field access."""

from wsl.domain.models import Match, Standing, Team


def test_team_fields(arsenal_wfc: Team) -> None:
    # Arrange / Act / Assert
    assert arsenal_wfc.id == "19973"
    assert arsenal_wfc.abbreviation == "ARS"
    assert arsenal_wfc.display_name == "Arsenal"


def test_match_competitor_fields(sample_match: Match) -> None:
    # Arrange
    home = next(c for c in sample_match.competitors if c.home_away == "home")
    # Assert
    assert home.score == "2"
    assert home.winner is True


def test_standing_goal_difference(sample_standing: Standing) -> None:
    # Arrange / Act / Assert
    assert sample_standing.goal_difference == 22
    assert sample_standing.points == 38
