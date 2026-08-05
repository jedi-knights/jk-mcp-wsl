"""Pure formatters that turn domain models into LLM-readable text.

Extracted from mcp_adapter.py so the adapter focuses on tool wiring while the
presentation layer stays a side-effect-free, easily testable concern.
"""

from ...domain.models import (
    AdjustedPointsPerGame,
    Match,
    MatchCompetitor,
    MatchDetails,
    MatchEvent,
    NewsArticle,
    OpponentPPG,
    Player,
    ResultsByOpponentTier,
    Standing,
    StrengthOfSchedule,
    Team,
    TierRecord,
)


def _fmt_team(team: Team) -> str:
    """Format a single Team as a labeled key-value block."""
    lines = [
        f"ID: {team.id}",
        f"Name: {team.display_name}",
        f"Abbreviation: {team.abbreviation}",
        f"Location: {team.location}",
    ]
    if team.logo_url:
        lines.append(f"Logo: {team.logo_url}")
    return "\n".join(lines)


def _fmt_teams(teams: list[Team]) -> str:
    """Format a list of teams as a numbered list."""
    if not teams:
        return "No teams found."
    entries = [f"{i}. {t.display_name} ({t.abbreviation}) — ID: {t.id}" for i, t in enumerate(teams, 1)]
    return "\n".join(entries)


def _fmt_competitor(comp: MatchCompetitor) -> str:
    """Format one side of a match: team name, score, and home/away label."""
    score_str = f" {comp.score}" if comp.score is not None else ""
    winner_str = " ✓" if comp.winner else ""
    return f"{comp.team.display_name}{score_str}{winner_str} ({comp.home_away})"


def _fmt_match(match: Match) -> str:
    """Format a single Match as a readable summary."""
    competitor_lines = "\n  ".join(_fmt_competitor(c) for c in match.competitors)
    return (
        f"Match: {match.name}\n"
        f"  ID: {match.id}\n"
        f"  Date: {match.date}\n"
        f"  Status: {match.status_detail}\n"
        f"  Competitors:\n  {competitor_lines}"
    )


def _fmt_scoreboard(matches: list[Match]) -> str:
    """Format a list of matches for the scoreboard tool."""
    if not matches:
        return "No matches found for the requested date."
    return "\n\n".join(_fmt_match(m) for m in matches)


def _fmt_team_schedule(matches: list[Match]) -> str:
    """Format a list of matches for the team-schedule tool."""
    if not matches:
        return "No scheduled matches found for this team."
    return "\n\n".join(_fmt_match(m) for m in matches)


def _fmt_player(i: int, player: Player) -> str:
    """Format a single roster row."""
    jersey = f"#{player.jersey}" if player.jersey else "  "
    pos = f" ({player.position_abbr})" if player.position_abbr else ""
    extras = []
    if player.position:
        extras.append(player.position)
    if player.citizenship:
        extras.append(player.citizenship)
    if player.age is not None:
        extras.append(f"age {player.age}")
    suffix = f" — {', '.join(extras)}" if extras else ""
    return f"{i}. {jersey} {player.full_name}{pos}{suffix}"


def _fmt_roster(players: list[Player]) -> str:
    """Format a roster as a numbered list."""
    if not players:
        return "No players found for this team."
    return "\n".join(_fmt_player(i, p) for i, p in enumerate(players, 1))


def _fmt_event(event: MatchEvent) -> str:
    """Format a single key event as a one-line summary."""
    marker = "⚽" if event.scoring else "•"
    parts = [f"  {marker} {event.clock}"]
    if event.team_name:
        parts.append(f"({event.team_name})")
    parts.append(event.text or event.type)
    return " ".join(parts)


def _fmt_venue_line(details: MatchDetails) -> str | None:
    """Build the venue line, or return None if no venue is set."""
    if not details.venue:
        return None
    if details.venue_city:
        return f"  Venue: {details.venue} ({details.venue_city})"
    return f"  Venue: {details.venue}"


def _fmt_match_details(details: MatchDetails) -> str:
    """Format a MatchDetails as a readable multi-line summary."""
    score = f"{details.home_score or '?'} - {details.away_score or '?'}"
    lines = [
        f"{details.home_team} {score} {details.away_team}",
        f"  Date: {details.date}",
        f"  Status: {details.status_detail}",
    ]
    venue_line = _fmt_venue_line(details)
    if venue_line:
        lines.append(venue_line)
    if details.attendance is not None:
        lines.append(f"  Attendance: {details.attendance:,}")
    if details.key_events:
        lines.append("  Key events:")
        lines.extend(_fmt_event(e) for e in details.key_events)
    return "\n".join(lines)


def _fmt_article(i: int, article: NewsArticle) -> str:
    """Format a single news article as a multi-line entry."""
    lines = [f"{i}. {article.headline}"]
    if article.published:
        lines.append(f"   Published: {article.published}")
    if article.description:
        lines.append(f"   {article.description}")
    if article.link:
        lines.append(f"   {article.link}")
    return "\n".join(lines)


def _fmt_news(articles: list[NewsArticle]) -> str:
    """Format a list of news articles."""
    if not articles:
        return "No news articles available."
    return "\n\n".join(_fmt_article(i, a) for i, a in enumerate(articles, 1))


def _fmt_standing(i: int, standing: Standing) -> str:
    """Format a single standings row."""
    return (
        f"{i}. {standing.team.display_name} ({standing.team.abbreviation})"
        f" — {standing.points} pts"
        f" | W:{standing.wins} L:{standing.losses} T:{standing.ties}"
        f" | GF:{standing.goals_for} GA:{standing.goals_against} GD:{standing.goal_difference:+d}"
    )


def _fmt_standings(standings: list[Standing]) -> str:
    """Format the Women's Super League standings as a single numbered list."""
    if not standings:
        return "No standings data available."
    return "\n".join(_fmt_standing(i, s) for i, s in enumerate(standings, 1))


def _fmt_opponent_row(opp: OpponentPPG, meetings: int) -> str:
    """Format one opponent row, marking repeat fixtures as 'x2', 'x3', etc."""
    suffix = f" x{meetings}" if meetings > 1 else ""
    return f"    - {opp.team.display_name}{suffix}: {opp.points_per_game:.2f} ({opp.points} pts in {opp.matches_played} GP)"


def _fmt_strength_of_schedule(sos: StrengthOfSchedule) -> str:
    """Format a StrengthOfSchedule as a labeled summary plus opponent breakdown.

    Repeat fixtures (an opponent met twice via home + away) collapse into a
    single row marked ``x2`` — the average PPG calculation already weights
    them correctly, so the output stays tidy without losing information.
    """
    if sos.matches_played == 0:
        return f"{sos.team.display_name}: no matches played yet — strength of schedule unavailable."
    counts: dict[str, int] = {}
    unique: list[OpponentPPG] = []
    for opp in sos.opponents:
        if opp.team.id in counts:
            counts[opp.team.id] += 1
        else:
            counts[opp.team.id] = 1
            unique.append(opp)
    lines = [
        f"{sos.team.display_name} — Strength of Schedule",
        f"  Matches played: {sos.matches_played}",
        f"  Average opponent PPG: {sos.average_opponent_ppg:.2f}",
        "  Opponents faced (current PPG):",
    ]
    lines.extend(_fmt_opponent_row(opp, counts[opp.team.id]) for opp in unique)
    return "\n".join(lines)


def _fmt_tier_record(t: TierRecord) -> str:
    """Format a single TierRecord row as 'Label (ranks N-M): W-L-T'."""
    return f"  {t.label} (ranks {t.rank_low}-{t.rank_high}): {t.wins}-{t.losses}-{t.ties}"


def _fmt_results_by_tier(rbt: ResultsByOpponentTier) -> str:
    """Format a ResultsByOpponentTier as a labeled W-L-T breakdown by tier."""
    lines = [f"{rbt.team.display_name} — Results by Opponent Tier (tier size: {rbt.tier_size})"]
    lines.extend(_fmt_tier_record(t) for t in rbt.tiers)
    return "\n".join(lines)


def _fmt_adjusted_ppg(a: AdjustedPointsPerGame) -> str:
    """Format an AdjustedPointsPerGame as a labeled summary."""
    return (
        f"{a.team.display_name} — Adjusted Points Per Game\n"
        f"  Record: {a.points} pts in {a.matches_played} GP\n"
        f"  Raw PPG: {a.raw_ppg:.2f}\n"
        f"  Average opponent PPG: {a.average_opponent_ppg:.2f}\n"
        f"  League average PPG: {a.league_average_ppg:.2f}\n"
        f"  Adjusted PPG: {a.adjusted_ppg:.2f}"
    )
