"""Unit tests for the ESPNAdapter outbound adapter.

Uses a mock httpx.AsyncClient to avoid real network calls, keeping tests
fast and deterministic.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from wsl.adapters.outbound.espn_adapter import ESPNAdapter
from wsl.adapters.outbound.parsers import _parse_match, _parse_standing, _parse_team
from wsl.domain.exceptions import WSLNotFoundError, UpstreamAPIError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_RAW_TEAM = {
    "id": "1899",
    "name": "Thorns",
    "abbreviation": "POR",
    "location": "Portland",
    "displayName": "Portland Thorns FC",
    "logos": [{"href": "https://a.espncdn.com/i/teamlogos/soccer/500/1899.png"}],
}

_RAW_EVENT = {
    "id": "701123",
    "date": "2025-06-01T20:00Z",
    "name": "Portland Thorns FC vs North Carolina Courage",
    "shortName": "POR vs NCC",
    "competitions": [
        {
            "status": {
                "displayClock": "FT",
                "type": {"name": "STATUS_FULL_TIME", "state": "post", "description": "Final"},
            },
            "competitors": [
                {
                    "homeAway": "home",
                    "score": "2",
                    "winner": True,
                    "team": _RAW_TEAM,
                    "id": "1899",
                    "name": "Thorns",
                    "abbreviation": "POR",
                    "location": "Portland",
                    "displayName": "Portland Thorns FC",
                    "logos": [{"href": "https://a.espncdn.com/i/teamlogos/soccer/500/1899.png"}],
                },
            ],
        }
    ],
}

_RAW_STANDING_ENTRY = {
    "team": _RAW_TEAM,
    "stats": [
        {"name": "wins", "value": 12},
        {"name": "losses", "value": 4},
        {"name": "ties", "value": 2},
        {"name": "points", "value": 38},
        {"name": "pointsFor", "value": 40},
        {"name": "pointsAgainst", "value": 18},
        {"name": "pointDifferential", "value": 22},
    ],
}


_RAW_SUMMARY = {
    "header": {
        "id": "401853883",
        "competitions": [
            {
                "date": "2026-04-04T22:30Z",
                "status": {
                    "displayClock": "FT",
                    "type": {"name": "STATUS_FULL_TIME", "description": "Full Time"},
                },
                "competitors": [
                    {
                        "homeAway": "home",
                        "score": "2",
                        "winner": False,
                        "team": {**_RAW_TEAM, "id": "2695", "displayName": "North Carolina Courage"},
                    },
                    {
                        "homeAway": "away",
                        "score": "2",
                        "winner": False,
                        "team": _RAW_TEAM,
                    },
                ],
            }
        ],
    },
    "gameInfo": {
        "venue": {"fullName": "WakeMed Soccer Park", "address": {"city": "Cary, North Carolina"}},
        "attendance": 7018,
    },
    "keyEvents": [
        {
            "type": {"type": "goal---header"},
            "scoringPlay": True,
            "period": {"number": 1},
            "clock": {"displayValue": "12'"},
            "text": "Goal! NC 0, POR 1. Reilyn Turner.",
            "team": {"displayName": "Portland Thorns FC"},
        },
        {
            "type": {"type": "yellow-card"},
            "scoringPlay": False,
            "period": {"number": 2},
            "clock": {"displayValue": "84'"},
            "text": "Castellanos shown the yellow card.",
            "team": {"displayName": "Portland Thorns FC"},
        },
    ],
}


_RAW_ARTICLE = {
    "id": 48595550,
    "type": "Story",
    "headline": "Chicago Stars vs. Boston Legacy FC - Game Highlights",
    "description": "Watch the Game Highlights from Chicago Stars vs. Boston Legacy FC, 04/26/2026",
    "published": "2026-04-26T00:48:46Z",
    "links": {"web": {"href": "https://www.espn.com/video/clip?id=48595550"}},
}


_RAW_PLAYER = {
    "id": "219821",
    "fullName": "Mackenzie Arnold",
    "jersey": "18",
    "position": {"displayName": "Goalkeeper", "abbreviation": "G"},
    "citizenship": "Australia",
    "age": 32,
}


@pytest.fixture
def mock_client() -> AsyncMock:
    """A mock httpx.AsyncClient that returns 200 by default."""
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    client.get.return_value = response
    return client


@pytest.fixture
def adapter(mock_client: AsyncMock) -> ESPNAdapter:
    return ESPNAdapter(client=mock_client)


# ---------------------------------------------------------------------------
# Helper parser tests (pure unit — no network)
# ---------------------------------------------------------------------------


def test_parse_team_maps_fields() -> None:
    team = _parse_team(_RAW_TEAM)
    assert team.id == "1899"
    assert team.abbreviation == "POR"
    assert team.logo_url == "https://a.espncdn.com/i/teamlogos/soccer/500/1899.png"


def test_parse_team_no_logos() -> None:
    raw = {**_RAW_TEAM, "logos": []}
    team = _parse_team(raw)
    assert team.logo_url is None


def test_parse_match_maps_fields() -> None:
    match = _parse_match(_RAW_EVENT)
    assert match.id == "701123"
    assert match.status_type == "post"
    assert match.status_detail == "FT"
    assert len(match.competitors) == 1
    assert match.competitors[0].score == "2"
    assert match.competitors[0].winner is True


def test_parse_match_status_type_uses_state_not_name() -> None:
    """status_type must come from ESPN's `state` field ("pre"/"in"/"post"), not `name`.

    The `name` field is a verbose label like "STATUS_FULL_TIME"; the analytics
    helpers (and Match docstring) require the short state value. Reading `name`
    silently broke every schedule-strength tool because matches never matched
    the "post" filter.
    """
    event = {
        "id": "401853883",
        "date": "2026-04-04T22:30Z",
        "name": "POR at NC",
        "shortName": "POR @ NC",
        "competitions": [
            {
                "status": {
                    "displayClock": "90'+5'",
                    "type": {
                        "name": "STATUS_FULL_TIME",
                        "state": "post",
                        "completed": True,
                        "description": "Full Time",
                        "shortDetail": "FT",
                    },
                },
                "competitors": [],
            }
        ],
    }
    match = _parse_match(event)
    assert match.status_type == "post"


def test_parse_match_extracts_score_from_ref_dict() -> None:
    """The team-schedule endpoint returns scores as $ref dicts; we must extract displayValue.

    Reproduces a bug where get_team_schedule output contained the full score dict
    (e.g. `{'$ref': '...', 'value': 2.0, 'displayValue': '2', ...}`) instead of
    a clean string like '2'. Same Match model and formatter as get_scoreboard;
    the difference is purely in how ESPN serializes the competitor score field.
    """
    event_with_ref_score = {
        "id": "401853883",
        "date": "2026-04-04T22:30Z",
        "name": "POR at NC",
        "shortName": "POR @ NC",
        "competitions": [
            {
                "status": {
                    "displayClock": "FT",
                    "type": {"name": "STATUS_FULL_TIME", "state": "post", "description": "Full Time"},
                },
                "competitors": [
                    {
                        "homeAway": "home",
                        "score": {
                            "$ref": "http://sports.core.api.espn.pvt/...",
                            "value": 2.0,
                            "displayValue": "2",
                            "winner": False,
                            "source": {"id": "38", "description": "SA.ENVOY"},
                        },
                        "winner": False,
                        "team": _RAW_TEAM,
                    },
                ],
            }
        ],
    }
    match = _parse_match(event_with_ref_score)
    assert match.competitors[0].score == "2"
    assert match.competitors[0].winner is False


def test_parse_standing_maps_stats() -> None:
    standing = _parse_standing(_RAW_STANDING_ENTRY)
    assert standing is not None
    assert standing.wins == 12
    assert standing.points == 38
    assert standing.goal_difference == 22


def test_parse_standing_returns_none_without_team() -> None:
    result = _parse_standing({"stats": []})
    assert result is None


# ---------------------------------------------------------------------------
# Adapter method tests (mock httpx client)
# ---------------------------------------------------------------------------


async def test_get_teams_returns_team_list(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"sports": [{"leagues": [{"teams": [{"team": _RAW_TEAM}]}]}]}
    teams = await adapter.get_teams()
    assert len(teams) == 1
    assert teams[0].id == "1899"


async def test_get_team_returns_single_team(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"team": _RAW_TEAM}
    team = await adapter.get_team("1899")
    assert team.display_name == "Portland Thorns FC"


async def test_get_team_raises_not_found_when_missing(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {}
    with pytest.raises(WSLNotFoundError):
        await adapter.get_team("9999")


async def test_get_scoreboard_returns_matches(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"events": [_RAW_EVENT]}
    matches = await adapter.get_scoreboard("20250601")
    assert len(matches) == 1
    assert matches[0].id == "701123"


async def test_get_scoreboard_without_date(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"events": []}
    matches = await adapter.get_scoreboard(None)
    assert matches == []


async def test_get_scoreboard_with_date_range(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"events": [_RAW_EVENT]}
    matches = await adapter.get_scoreboard("20260404", end_date="20260405")
    assert len(matches) == 1
    sent_params = mock_client.get.call_args.kwargs.get("params", {})
    assert sent_params.get("dates") == "20260404-20260405"


async def test_get_news_returns_articles(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"articles": [_RAW_ARTICLE]}
    articles = await adapter.get_news(limit=5)
    assert len(articles) == 1
    a = articles[0]
    assert a.id == "48595550"
    assert a.headline.startswith("Chicago Stars")
    assert a.published == "2026-04-26T00:48:46Z"
    assert a.link == "https://www.espn.com/video/clip?id=48595550"


async def test_get_news_passes_limit(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"articles": []}
    await adapter.get_news(limit=10)
    call = mock_client.get.call_args
    assert "/news" in call.args[0]
    assert call.kwargs.get("params", {}).get("limit") == 10


async def test_get_news_handles_missing_link(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    article = {**_RAW_ARTICLE, "links": {}}
    mock_client.get.return_value.json.return_value = {"articles": [article]}
    articles = await adapter.get_news(limit=5)
    assert articles[0].link is None


async def test_get_roster_returns_players(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"athletes": [_RAW_PLAYER]}
    players = await adapter.get_roster("15362")
    assert len(players) == 1
    p = players[0]
    assert p.id == "219821"
    assert p.full_name == "Mackenzie Arnold"
    assert p.jersey == "18"
    assert p.position == "Goalkeeper"
    assert p.position_abbr == "G"
    assert p.citizenship == "Australia"
    assert p.age == 32


async def test_get_roster_uses_team_specific_path(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"athletes": []}
    await adapter.get_roster("15362")
    assert "/teams/15362/roster" in mock_client.get.call_args.args[0]


async def test_get_roster_handles_missing_optional_fields(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    minimal_player = {"id": "1", "fullName": "Jane Doe"}
    mock_client.get.return_value.json.return_value = {"athletes": [minimal_player]}
    players = await adapter.get_roster("15362")
    assert players[0].jersey is None
    assert players[0].position is None
    assert players[0].citizenship is None
    assert players[0].age is None


async def test_get_match_details_parses_summary(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = _RAW_SUMMARY
    details = await adapter.get_match_details("401853883")
    assert details.id == "401853883"
    assert details.date == "2026-04-04T22:30Z"
    assert details.status_detail == "Full Time"
    assert details.home_team == "North Carolina Courage"
    assert details.away_team == "Portland Thorns FC"
    assert details.home_score == "2"
    assert details.away_score == "2"
    assert details.venue == "WakeMed Soccer Park"
    assert details.venue_city == "Cary, North Carolina"
    assert details.attendance == 7018
    assert len(details.key_events) == 2
    goal = details.key_events[0]
    assert goal.type == "goal---header"
    assert goal.scoring is True
    assert goal.clock == "12'"
    assert goal.team_name == "Portland Thorns FC"


async def test_get_match_details_passes_event_param(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = _RAW_SUMMARY
    await adapter.get_match_details("401853883")
    call = mock_client.get.call_args
    assert "/summary" in call.args[0]
    assert call.kwargs.get("params", {}).get("event") == "401853883"


async def test_get_match_details_raises_not_found_when_no_header(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {}
    with pytest.raises(WSLNotFoundError):
        await adapter.get_match_details("9999999")


async def test_get_team_schedule_returns_matches(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"events": [_RAW_EVENT]}
    matches = await adapter.get_team_schedule("1899")
    assert len(matches) == 1
    assert matches[0].id == "701123"


async def test_get_team_schedule_uses_team_specific_path(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"events": []}
    await adapter.get_team_schedule("1899")
    requested_path = mock_client.get.call_args.args[0]
    assert "/teams/1899/schedule" in requested_path


def _schedule_response(events: list[dict[str, Any]]) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {"events": events}
    return response


async def test_get_team_schedule_merges_past_results_and_future_fixtures(
    adapter: ESPNAdapter, mock_client: AsyncMock
) -> None:
    """ESPN's /teams/{id}/schedule returns only past events by default; passing
    `fixture=true` returns only upcoming. The adapter must call both and merge
    so users see the full season schedule."""
    past = {**_RAW_EVENT, "id": "PAST", "date": "2026-03-14T16:00Z"}
    future = {**_RAW_EVENT, "id": "FUTURE", "date": "2026-05-03T19:00Z"}

    async def fake_get(_path: str, params: dict[str, Any] | None = None) -> MagicMock:
        if params and params.get("fixture"):
            return _schedule_response([future])
        return _schedule_response([past])

    mock_client.get = AsyncMock(side_effect=fake_get)

    matches = await adapter.get_team_schedule("131562")

    assert {m.id for m in matches} == {"PAST", "FUTURE"}


async def test_get_team_schedule_requests_fixture_variant(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    """Adapter must make a second call with `fixture=true` to retrieve upcoming events."""
    mock_client.get.return_value.json.return_value = {"events": []}
    await adapter.get_team_schedule("131562")
    fixture_calls = [c for c in mock_client.get.call_args_list if (c.kwargs.get("params") or {}).get("fixture")]
    assert len(fixture_calls) == 1


async def test_get_team_schedule_returns_chronological_order(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    """Merged schedule should be sorted ascending by date so callers see the season
    in calendar order rather than the past-descending / future-ascending split ESPN returns."""
    past_old = {**_RAW_EVENT, "id": "P1", "date": "2026-03-14T16:00Z"}
    past_new = {**_RAW_EVENT, "id": "P2", "date": "2026-04-25T22:30Z"}
    future_first = {**_RAW_EVENT, "id": "F1", "date": "2026-05-03T19:00Z"}
    future_later = {**_RAW_EVENT, "id": "F2", "date": "2026-05-09T22:30Z"}

    async def fake_get(_path: str, params: dict[str, Any] | None = None) -> MagicMock:
        if params and params.get("fixture"):
            return _schedule_response([future_first, future_later])
        return _schedule_response([past_new, past_old])

    mock_client.get = AsyncMock(side_effect=fake_get)

    matches = await adapter.get_team_schedule("131562")

    assert [m.id for m in matches] == ["P1", "P2", "F1", "F2"]


async def test_get_team_schedule_dedupes_events_present_in_both_responses(
    adapter: ESPNAdapter, mock_client: AsyncMock
) -> None:
    """If ESPN returns the same event from both default and fixture variants, the
    merged result must contain it only once."""
    shared = {**_RAW_EVENT, "id": "SHARED", "date": "2026-04-25T22:30Z"}

    async def fake_get(_path: str, params: dict[str, Any] | None = None) -> MagicMock:
        return _schedule_response([shared])

    mock_client.get = AsyncMock(side_effect=fake_get)

    matches = await adapter.get_team_schedule("131562")

    assert [m.id for m in matches] == ["SHARED"]


async def test_get_standings_returns_sorted_list(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"children": [{"standings": {"entries": [_RAW_STANDING_ENTRY]}}]}
    standings = await adapter.get_standings()
    assert len(standings) == 1
    assert standings[0].points == 38


async def test_get_standings_uses_v2_path_without_site_segment(adapter: ESPNAdapter, mock_client: AsyncMock) -> None:
    mock_client.get.return_value.json.return_value = {"children": []}
    await adapter.get_standings()
    requested_path = mock_client.get.call_args.args[0]
    assert requested_path == "/apis/v2/sports/soccer/eng.w.1/standings"


async def test_get_teams_raises_upstream_error_on_500(
    adapter: ESPNAdapter, mock_client: AsyncMock, mocker: MockerFixture
) -> None:
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 500
    http_error = httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)
    mock_client.get.return_value.raise_for_status.side_effect = http_error
    with pytest.raises(UpstreamAPIError):
        await adapter.get_teams()


async def test_get_team_raises_not_found_on_404(
    adapter: ESPNAdapter, mock_client: AsyncMock, mocker: MockerFixture
) -> None:
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 404
    http_error = httpx.HTTPStatusError("404", request=MagicMock(), response=mock_response)
    mock_client.get.return_value.raise_for_status.side_effect = http_error
    with pytest.raises(WSLNotFoundError):
        await adapter.get_team("9999")
