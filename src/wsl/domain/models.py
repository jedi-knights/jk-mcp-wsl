"""Domain models for the Women's Super League MCP server.

Pure Python dataclasses with zero framework dependencies. Adapters are
responsible for translating to/from these types from the ESPN API wire format.
"""

from dataclasses import dataclass, field


@dataclass
class Team:
    """An Women's Super League franchise.

    id and abbreviation are the stable identifiers used by the ESPN API.
    """

    id: str
    name: str
    abbreviation: str
    location: str
    display_name: str
    logo_url: str | None = None


@dataclass
class MatchCompetitor:
    """One side of a match — home or away team with its score."""

    team: Team
    home_away: str
    score: str | None = None
    winner: bool | None = None


@dataclass
class Match:
    """A single Women's Super League match (scheduled, in-progress, or completed).

    status_type values from the ESPN API:
      "pre"  — scheduled, not yet started
      "in"   — in progress
      "post" — final
    """

    id: str
    date: str
    name: str
    short_name: str
    status_type: str
    status_detail: str
    competitors: list[MatchCompetitor] = field(default_factory=list)


@dataclass
class NewsArticle:
    """A single Women's Super League news article from the ESPN news feed."""

    id: str
    headline: str
    description: str
    published: str
    link: str | None = None


@dataclass
class Player:
    """An Women's Super League player on a team's roster.

    Optional fields (jersey, position, citizenship, age) may be missing for
    unsigned, recently traded, or international players whose data ESPN has
    not fully populated.
    """

    id: str
    full_name: str
    jersey: str | None = None
    position: str | None = None
    position_abbr: str | None = None
    citizenship: str | None = None
    age: int | None = None


@dataclass
class MatchEvent:
    """A single key event within a match (goal, substitution, card, etc.).

    Mirrors ESPN's keyEvents entries: type is the raw event tag
    (e.g. "goal", "goal---header", "yellow-card", "substitution"); scoring
    is a convenience flag for goal events.
    """

    clock: str
    period: int
    type: str
    scoring: bool
    text: str | None = None
    team_name: str | None = None


@dataclass
class MatchDetails:
    """Detailed information about a single Women's Super League match.

    Combines header data (teams, score, status) with venue, attendance, and
    a chronological list of key in-game events.
    """

    id: str
    date: str
    status_detail: str
    home_team: str
    away_team: str
    home_score: str | None = None
    away_score: str | None = None
    venue: str | None = None
    venue_city: str | None = None
    attendance: int | None = None
    key_events: list[MatchEvent] = field(default_factory=list)


@dataclass
class Standing:
    """A team's position in the Women's Super League table."""

    team: Team
    wins: int
    losses: int
    ties: int
    points: int
    goals_for: int
    goals_against: int
    goal_difference: int


@dataclass
class OpponentPPG:
    """One opponent a team has played, paired with that opponent's current PPG.

    ``points_per_game`` is computed from the opponent's full league record (no
    self-exclusion), so it reflects current standings position rather than a
    strict RPI-style adjustment.
    """

    team: Team
    matches_played: int
    points: int
    points_per_game: float


@dataclass
class StrengthOfSchedule:
    """Opponent-quality summary for a single team.

    Aggregates the current points-per-game of every opponent the team has
    actually faced (completed matches only). Useful for "who has played the
    tougher schedule so far?" questions early in the season.
    """

    team: Team
    matches_played: int
    opponents: list[OpponentPPG]
    average_opponent_ppg: float


@dataclass
class TierRecord:
    """A team's W-L-T record against opponents in one current-standings tier."""

    label: str
    rank_low: int
    rank_high: int
    wins: int
    losses: int
    ties: int


@dataclass
class ResultsByOpponentTier:
    """A team's results split by the current-standings tier of each opponent.

    Tiers are derived from the live league table at call time, not the table
    at the time each match was played — interpret as "how have you done
    against teams that are currently strong/middle/weak?"
    """

    team: Team
    tier_size: int
    tiers: list[TierRecord]


@dataclass
class AdjustedPointsPerGame:
    """Raw vs. opponent-quality-adjusted PPG for a single team.

    ``adjusted_ppg`` scales raw PPG by ``average_opponent_ppg / league_average_ppg``,
    so values above raw PPG mean the team has earned points against a tougher
    schedule than league average.
    """

    team: Team
    matches_played: int
    points: int
    raw_ppg: float
    average_opponent_ppg: float
    league_average_ppg: float
    adjusted_ppg: float
