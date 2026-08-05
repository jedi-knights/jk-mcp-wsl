"""Application service — the core of the hexagonal architecture.

This layer orchestrates work by delegating to outbound ports. It knows nothing
about MCP, HTTP, or JSON — those are adapter concerns.
"""

from ..domain.models import (
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
)
from ..ports.outbound import WSLAPIPort
from ._analytics_helpers import (
    _build_ppg_index,
    _build_tier_record,
    _build_tier_specs,
    _league_average_ppg,
    _mean,
    _opponent_ppgs,
    _played_opponents,
    _resolve_team,
    _safe_ratio,
    _self_record,
    _tally_tier_results,
    _validate_team_id,
    _validate_tier_size,
)
from ._helpers import _validate_yyyymmdd


class WSLService:
    """Coordinates Women's Super League data lookups through the outbound ports.

    One driven port is injected: the ESPN-backed ``repo`` (read-only league
    feeds). Additional data sources (SDP/Opta, CMS) can be added as separate
    ports as they come online.
    """

    def __init__(self, repo: WSLAPIPort) -> None:
        self._repo = repo

    async def get_teams(self) -> list[Team]:
        """Return all active Women's Super League teams."""
        return await self._repo.get_teams()

    async def get_team(self, team_id: str) -> Team:
        """Return a single team by its ESPN team ID.

        Args:
            team_id: ESPN numeric team ID or team abbreviation.

        Raises:
            ValueError: If team_id is empty.
            WSLNotFoundError: If no team with that ID exists.
        """
        if not team_id or not team_id.strip():
            raise ValueError("team_id must not be empty")
        return await self._repo.get_team(team_id.strip())

    async def get_scoreboard(self, date: str | None = None, end_date: str | None = None) -> list[Match]:
        """Return matches for a date, a date range, or today if date is None.

        Args:
            date: Optional date string in YYYYMMDD format (e.g. "20260601").
            end_date: Optional end of a range in YYYYMMDD format. Requires ``date``
                to be provided as the start of the range.

        Raises:
            ValueError: If either argument is malformed, or if end_date is given
                without a starting date.
        """
        if end_date is not None and date is None:
            raise ValueError("end_date requires a starting date")
        if date is not None:
            date = _validate_yyyymmdd(date.strip(), "date")
        if end_date is not None:
            end_date = _validate_yyyymmdd(end_date.strip(), "end_date")
        return await self._repo.get_scoreboard(date, end_date)

    async def get_news(self, limit: int = 10) -> list[NewsArticle]:
        """Return up to ``limit`` recent Women's Super League news articles.

        Args:
            limit: Maximum number of articles to return (must be positive).

        Raises:
            ValueError: If limit is not a positive integer.
        """
        if limit <= 0:
            raise ValueError("limit must be positive")
        return await self._repo.get_news(limit)

    async def get_roster(self, team_id: str) -> list[Player]:
        """Return the active roster for a team.

        Args:
            team_id: ESPN numeric team ID.

        Raises:
            ValueError: If team_id is empty.
            WSLNotFoundError: If no team with that ID exists.
        """
        if not team_id or not team_id.strip():
            raise ValueError("team_id must not be empty")
        return await self._repo.get_roster(team_id.strip())

    async def get_match_details(self, match_id: str) -> MatchDetails:
        """Return detailed information for a single match.

        Args:
            match_id: ESPN numeric event ID.

        Raises:
            ValueError: If match_id is empty.
            WSLNotFoundError: If no match with that ID exists.
        """
        if not match_id or not match_id.strip():
            raise ValueError("match_id must not be empty")
        return await self._repo.get_match_details(match_id.strip())

    async def get_team_schedule(self, team_id: str) -> list[Match]:
        """Return all scheduled and completed matches for a team in the current season.

        Args:
            team_id: ESPN numeric team ID.

        Raises:
            ValueError: If team_id is empty.
            WSLNotFoundError: If no team with that ID exists.
        """
        if not team_id or not team_id.strip():
            raise ValueError("team_id must not be empty")
        return await self._repo.get_team_schedule(team_id.strip())

    async def get_standings(self) -> list[Standing]:
        """Return the current Women's Super League standings ordered by points descending."""
        return await self._repo.get_standings()

    async def get_strength_of_schedule(self, team_id: str) -> StrengthOfSchedule:
        """Return the average current PPG of opponents this team has faced.

        Walks the team's completed matches and aggregates each opponent's
        league-table points-per-game (no self-exclusion). Useful for "who has
        played the tougher schedule so far?" questions.

        Args:
            team_id: ESPN numeric team ID.

        Raises:
            ValueError: If team_id is empty.
            WSLNotFoundError: If no team with that ID exists.
        """
        team_id = _validate_team_id(team_id)
        standings = await self._repo.get_standings()
        schedule = await self._repo.get_team_schedule(team_id)
        ppg_index = _build_ppg_index(standings)
        team = _resolve_team(standings, schedule, team_id)
        opponents = [
            OpponentPPG(
                team=opp,
                matches_played=ppg_index[opp.id].matches_played,
                points=ppg_index[opp.id].points,
                points_per_game=ppg_index[opp.id].ppg,
            )
            for opp in _played_opponents(schedule, team_id)
            if opp.id in ppg_index
        ]
        return StrengthOfSchedule(
            team=team,
            matches_played=len(opponents),
            opponents=opponents,
            average_opponent_ppg=_mean([o.points_per_game for o in opponents]),
        )

    async def get_results_by_opponent_tier(self, team_id: str, tier_size: int = 5) -> ResultsByOpponentTier:
        """Return W-L-T splits against current top-tier, middle, and bottom-tier teams.

        Tiers are derived from the current league standings: the top ``tier_size``,
        the bottom ``tier_size``, and everyone in between. Draws (no declared winner)
        count as ties; matches against teams not in the current standings are
        skipped.

        Args:
            team_id: ESPN numeric team ID.
            tier_size: Number of teams in each of the top and bottom tiers.
                Defaults to 5. Must be at least 1, and 2*tier_size must not
                exceed the league size.

        Raises:
            ValueError: If team_id is empty or tier_size is invalid.
            WSLNotFoundError: If no team with that ID exists.
        """
        team_id = _validate_team_id(team_id)
        standings = await self._repo.get_standings()
        _validate_tier_size(tier_size, len(standings))
        schedule = await self._repo.get_team_schedule(team_id)
        rank_by_id = {s.team.id: i + 1 for i, s in enumerate(standings)}
        team = _resolve_team(standings, schedule, team_id)
        tier_specs = _build_tier_specs(tier_size, len(standings))
        tally = _tally_tier_results(schedule, team_id, rank_by_id, tier_specs)
        tiers = [_build_tier_record(name, low, high, tally) for name, low, high in tier_specs if high >= low]
        return ResultsByOpponentTier(team=team, tier_size=tier_size, tiers=tiers)

    async def get_adjusted_points_per_game(self, team_id: str) -> AdjustedPointsPerGame:
        """Return raw PPG plus a schedule-strength-adjusted PPG.

        Adjusted PPG = raw_ppg * (avg_opponent_ppg / league_average_ppg). Values
        above raw_ppg mean the team has earned points against a tougher
        schedule than league average.

        Args:
            team_id: ESPN numeric team ID.

        Raises:
            ValueError: If team_id is empty.
            WSLNotFoundError: If no team with that ID exists.
        """
        team_id = _validate_team_id(team_id)
        standings = await self._repo.get_standings()
        schedule = await self._repo.get_team_schedule(team_id)
        ppg_index = _build_ppg_index(standings)
        team = _resolve_team(standings, schedule, team_id)
        matches_played, points, raw_ppg = _self_record(ppg_index, team_id)
        opp_entries = _opponent_ppgs(schedule, team_id, ppg_index)
        avg_opp_ppg = _mean([e.ppg for e in opp_entries])
        league_avg = _league_average_ppg(standings)
        return AdjustedPointsPerGame(
            team=team,
            matches_played=matches_played,
            points=points,
            raw_ppg=raw_ppg,
            average_opponent_ppg=avg_opp_ppg,
            league_average_ppg=league_avg,
            adjusted_ppg=raw_ppg * _safe_ratio(avg_opp_ppg, league_avg),
        )
