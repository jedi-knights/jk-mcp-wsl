"""Pure functions that map ESPN JSON wire format into domain models.

Extracted from espn_adapter.py so the adapter focuses on HTTP/transport concerns
while parsing stays a side-effect-free, easily testable concern.
"""

from typing import Any

from ...domain.exceptions import WSLNotFoundError
from ...domain.models import Match, MatchCompetitor, MatchDetails, MatchEvent, NewsArticle, Player, Standing, Team


def _parse_team(raw: dict[str, Any]) -> Team:
    """Map a raw ESPN team object to a domain Team.

    Args:
        raw: The team dict from the ESPN API (may be nested under "team" key).
    """
    team = raw.get("team", raw)
    logos = team.get("logos", [])
    logo_url = logos[0].get("href") if logos else None
    return Team(
        id=str(team.get("id", "")),
        name=team.get("name", ""),
        abbreviation=team.get("abbreviation", ""),
        location=team.get("location", ""),
        display_name=team.get("displayName", ""),
        logo_url=logo_url,
    )


def _extract_score(raw_score: object) -> str | None:
    """Pull a clean score string out of either ESPN serialization shape.

    The scoreboard endpoint returns ``score`` as a primitive (e.g. ``2``), but the
    team-schedule endpoint returns it as a $ref dict like
    ``{'$ref': '...', 'value': 2.0, 'displayValue': '2', 'winner': False, ...}``.
    We prefer ``displayValue``, fall back to ``value``, and stringify primitives.
    """
    if raw_score is None:
        return None
    if isinstance(raw_score, dict):
        display = raw_score.get("displayValue")
        if display is not None:
            return str(display)
        value = raw_score.get("value")
        return str(int(value)) if isinstance(value, int | float) else None
    return str(raw_score)


def _extract_winner(raw_score: object, raw_winner: object) -> bool | None:
    """Pull ``winner`` from the competitor, falling back to the embedded score dict."""
    if raw_winner is not None:
        return bool(raw_winner)
    if isinstance(raw_score, dict) and raw_score.get("winner") is not None:
        return bool(raw_score.get("winner"))
    return None


def _parse_competitor(raw: dict[str, Any]) -> MatchCompetitor:
    """Map a raw ESPN competitor object to a domain MatchCompetitor."""
    score = raw.get("score")
    return MatchCompetitor(
        team=_parse_team(raw),
        home_away=raw.get("homeAway", ""),
        score=_extract_score(score),
        winner=_extract_winner(score, raw.get("winner")),
    )


def _parse_match(event: dict[str, Any]) -> Match:
    """Map a raw ESPN scoreboard event to a domain Match."""
    competition = event.get("competitions", [{}])[0]
    status = competition.get("status", {})
    status_type = status.get("type", {})
    competitors = [_parse_competitor(c) for c in competition.get("competitors", [])]
    return Match(
        id=str(event.get("id", "")),
        date=event.get("date", ""),
        name=event.get("name", ""),
        short_name=event.get("shortName", ""),
        status_type=status_type.get("state", ""),
        status_detail=status.get("displayClock", status_type.get("description", "")),
        competitors=competitors,
    )


def _parse_key_event(raw: dict[str, Any]) -> MatchEvent:
    """Map a raw ESPN keyEvents entry to a domain MatchEvent."""
    team = raw.get("team") or {}
    return MatchEvent(
        clock=raw.get("clock", {}).get("displayValue", ""),
        period=int(raw.get("period", {}).get("number", 0)),
        type=raw.get("type", {}).get("type", ""),
        scoring=bool(raw.get("scoringPlay", False)),
        text=raw.get("text"),
        team_name=team.get("displayName"),
    )


def _competitor_by_side(competitors: list[dict[str, Any]], side: str) -> dict[str, Any]:
    """Find the home or away competitor in a competitors list."""
    return next((c for c in competitors if c.get("homeAway") == side), {})


def _competitor_team_name(competitor: dict[str, Any]) -> str:
    """Pull the displayName off a competitor's nested team dict."""
    return (competitor.get("team") or {}).get("displayName", "")


def _extract_status_detail(status: dict[str, Any]) -> str:
    """Pick a human-readable status string, preferring description over clock."""
    return status.get("type", {}).get("description", status.get("displayClock", ""))


def _extract_venue(game_info: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return ``(venue_full_name, venue_city)`` from a gameInfo block."""
    venue = game_info.get("venue") or {}
    return venue.get("fullName"), (venue.get("address") or {}).get("city")


def _parse_match_details(data: dict[str, Any]) -> MatchDetails:
    """Map a raw ESPN summary response to a domain MatchDetails.

    Raises:
        WSLNotFoundError: If the response lacks a ``header.competitions[0]`` block.
    """
    header = data.get("header") or {}
    competitions = header.get("competitions") or []
    if not competitions:
        raise WSLNotFoundError(f"Match not found: {header.get('id', '?')}")

    competition = competitions[0]
    competitors = competition.get("competitors", [])
    home = _competitor_by_side(competitors, "home")
    away = _competitor_by_side(competitors, "away")
    game_info = data.get("gameInfo") or {}
    venue_name, venue_city = _extract_venue(game_info)

    return MatchDetails(
        id=str(header.get("id", "")),
        date=competition.get("date", ""),
        status_detail=_extract_status_detail(competition.get("status", {})),
        home_team=_competitor_team_name(home),
        away_team=_competitor_team_name(away),
        home_score=home.get("score"),
        away_score=away.get("score"),
        venue=venue_name,
        venue_city=venue_city,
        attendance=game_info.get("attendance"),
        key_events=[_parse_key_event(e) for e in data.get("keyEvents", [])],
    )


def _parse_player(raw: dict[str, Any]) -> Player:
    """Map a raw ESPN roster athlete entry to a domain Player."""
    position = raw.get("position") or {}
    return Player(
        id=str(raw.get("id", "")),
        full_name=raw.get("fullName", ""),
        jersey=raw.get("jersey"),
        position=position.get("displayName"),
        position_abbr=position.get("abbreviation"),
        citizenship=raw.get("citizenship"),
        age=raw.get("age"),
    )


def _parse_article(raw: dict[str, Any]) -> NewsArticle:
    """Map a raw ESPN news article entry to a domain NewsArticle."""
    web_link = (raw.get("links") or {}).get("web") or {}
    return NewsArticle(
        id=str(raw.get("id", "")),
        headline=raw.get("headline", ""),
        description=raw.get("description", ""),
        published=raw.get("published", ""),
        link=web_link.get("href"),
    )


def _parse_standing(entry: dict[str, Any]) -> Standing | None:
    """Map a raw ESPN standings entry to a domain Standing.

    Returns None for entries that lack the required team data.
    """
    team_raw = entry.get("team")
    if not team_raw:
        return None

    stats: dict[str, Any] = {s["name"]: s.get("value", 0) for s in entry.get("stats", [])}
    return Standing(
        team=_parse_team(team_raw),
        wins=int(stats.get("wins", 0)),
        losses=int(stats.get("losses", 0)),
        ties=int(stats.get("ties", 0)),
        points=int(stats.get("points", 0)),
        goals_for=int(stats.get("pointsFor", 0)),
        goals_against=int(stats.get("pointsAgainst", 0)),
        goal_difference=int(stats.get("pointDifferential", 0)),
    )
