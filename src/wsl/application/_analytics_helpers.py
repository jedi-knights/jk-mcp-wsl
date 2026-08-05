"""Pure helpers for the schedule-strength analytics use cases.

Extracted from `_helpers.py` so the general-purpose helpers stay small and
the analytics math (PPG indexing, tier classification, opponent walking) lives
in one cohesive place. All functions here are side-effect-free transformations
over domain entities — no I/O, no port calls.
"""

from dataclasses import dataclass

from ..domain.exceptions import WSLNotFoundError
from ..domain.models import Match, MatchCompetitor, Standing, Team, TierRecord


@dataclass(frozen=True)
class _PPGEntry:
    """Cached per-team standings summary used by the SoS analytics."""

    matches_played: int
    points: int
    ppg: float


def _build_ppg_index(standings: list[Standing]) -> dict[str, _PPGEntry]:
    """Build a `team_id -> _PPGEntry` map from a standings table."""
    index: dict[str, _PPGEntry] = {}
    for s in standings:
        mp = s.wins + s.losses + s.ties
        ppg = s.points / mp if mp else 0.0
        index[s.team.id] = _PPGEntry(matches_played=mp, points=s.points, ppg=ppg)
    return index


def _find_team_in_standings(standings: list[Standing], team_id: str) -> Team | None:
    """Return the Team for a given id from a standings table, or None if absent."""
    return next((s.team for s in standings if s.team.id == team_id), None)


def _team_from_schedule(schedule: list[Match], team_id: str) -> Team:
    """Recover a Team object from a schedule when standings don't contain it.

    Raises:
        WSLNotFoundError: If neither standings nor schedule reference the team.
    """
    for match in schedule:
        for comp in match.competitors:
            if comp.team.id == team_id:
                return comp.team
    raise WSLNotFoundError(f"Team not found: {team_id}")


def _resolve_team(standings: list[Standing], schedule: list[Match], team_id: str) -> Team:
    """Return the Team from standings, falling back to the schedule if absent.

    Raises:
        WSLNotFoundError: If neither standings nor schedule reference the team.
    """
    found = _find_team_in_standings(standings, team_id)
    return found if found is not None else _team_from_schedule(schedule, team_id)


def _split_competitors(match: Match, team_id: str) -> tuple[MatchCompetitor | None, MatchCompetitor | None]:
    """Return (our_side, opponent_side) for a match, or (None, None) if team not present."""
    ours = next((c for c in match.competitors if c.team.id == team_id), None)
    theirs = next((c for c in match.competitors if c.team.id != team_id), None)
    if ours is None or theirs is None:
        return None, None
    return ours, theirs


def _played_opponents(schedule: list[Match], team_id: str) -> list[Team]:
    """Return the opponent Team for each completed match in `schedule`.

    Skips unfinished matches (status_type != 'post') and any match that doesn't
    contain the requested team. Multiple meetings against the same opponent
    appear multiple times, so the caller can aggregate.
    """
    opponents: list[Team] = []
    for match in schedule:
        if match.status_type != "post":
            continue
        _ours, theirs = _split_competitors(match, team_id)
        if theirs is not None:
            opponents.append(theirs.team)
    return opponents


def _opponent_ppgs(schedule: list[Match], team_id: str, ppg_index: dict[str, _PPGEntry]) -> list[_PPGEntry]:
    """Return the PPG entry for each opponent the team has played, skipping unknowns."""
    return [ppg_index[o.id] for o in _played_opponents(schedule, team_id) if o.id in ppg_index]


def _record_result(counters: list[int], ours: MatchCompetitor, theirs: MatchCompetitor) -> None:
    """Increment win/loss/tie counters in-place from one match outcome.

    counters is mutated as `[wins, losses, ties]`. A draw is recorded when
    neither side has `winner=True`.
    """
    if ours.winner:
        counters[0] += 1
    elif theirs.winner:
        counters[1] += 1
    else:
        counters[2] += 1


def _classify_tier(rank: int, tier_specs: tuple[tuple[str, int, int], ...]) -> str:
    """Return the tier name (e.g. 'Top', 'Middle', 'Bottom') for a given rank.

    Tiers are evaluated in order; the first matching `low <= rank <= high` wins.

    Raises:
        ValueError: If rank doesn't fall within any spec — indicates a bug
            in the caller (tier_specs should cover every possible rank).
    """
    for name, low, high in tier_specs:
        if low <= rank <= high:
            return name
    raise ValueError(f"rank {rank} does not fall within any tier in {tier_specs}")


def _tally_tier_results(
    schedule: list[Match],
    team_id: str,
    rank_by_id: dict[str, int],
    tier_specs: tuple[tuple[str, int, int], ...],
) -> dict[str, list[int]]:
    """Walk completed matches and tally W-L-T per tier name."""
    tally: dict[str, list[int]] = {name: [0, 0, 0] for name, _, _ in tier_specs}
    for match in schedule:
        if match.status_type != "post":
            continue
        ours, theirs = _split_competitors(match, team_id)
        if ours is None or theirs is None:
            continue
        rank = rank_by_id.get(theirs.team.id)
        if rank is None:
            continue
        _record_result(tally[_classify_tier(rank, tier_specs)], ours, theirs)
    return tally


def _league_average_ppg(standings: list[Standing]) -> float:
    """Compute league-wide average PPG (total points / total matches played)."""
    total_points = sum(s.points for s in standings)
    total_matches = sum(s.wins + s.losses + s.ties for s in standings)
    return total_points / total_matches if total_matches else 0.0


def _self_record(ppg_index: dict[str, _PPGEntry], team_id: str) -> tuple[int, int, float]:
    """Return `(matches_played, points, raw_ppg)` for the given team, or zeros if absent.

    Returns zeros when a team has been resolved (via `_resolve_team`) but is not
    yet in the standings table — this happens for expansion teams that appear
    in fixture data before they've played a match. In practice the caller has
    already established the team exists; the zeros are a safe default for the
    "no record yet" case.
    """
    entry = ppg_index.get(team_id)
    if entry is None:
        return 0, 0, 0.0
    return entry.matches_played, entry.points, entry.ppg


def _safe_ratio(numerator: float, denominator: float) -> float:
    """Return numerator/denominator, or 0.0 if denominator is zero."""
    return numerator / denominator if denominator else 0.0


def _mean(values: list[float]) -> float:
    """Return the arithmetic mean of `values`, or 0.0 if empty."""
    return sum(values) / len(values) if values else 0.0


def _validate_team_id(team_id: str) -> str:
    """Return a stripped team_id, or raise ValueError if empty/whitespace."""
    if not team_id or not team_id.strip():
        raise ValueError("team_id must not be empty")
    return team_id.strip()


def _validate_tier_size(tier_size: int, league_size: int) -> None:
    """Raise ValueError if tier_size is outside [1, league_size // 2]."""
    if tier_size < 1 or 2 * tier_size > league_size:
        raise ValueError(f"tier_size must be between 1 and {league_size // 2} for a {league_size}-team league")


def _build_tier_specs(tier_size: int, league_size: int) -> tuple[tuple[str, int, int], ...]:
    """Return (name, rank_low, rank_high) specs for top/middle/bottom tiers."""
    return (
        ("Top", 1, tier_size),
        ("Middle", tier_size + 1, league_size - tier_size),
        ("Bottom", league_size - tier_size + 1, league_size),
    )


def _build_tier_record(name: str, low: int, high: int, tally: dict[str, list[int]]) -> TierRecord:
    """Build a TierRecord row from a tier name and its tallied counters."""
    return TierRecord(
        label=f"{name} {high - low + 1}",
        rank_low=low,
        rank_high=high,
        wins=tally[name][0],
        losses=tally[name][1],
        ties=tally[name][2],
    )
