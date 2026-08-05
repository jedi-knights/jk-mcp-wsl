# Changelog

## 0.1.0 (Unreleased)

Initial scaffold, adapted from `jk-mcp-usls` by retargeting the ESPN league slug
to `eng.w.1` and updating the standings table cardinality to the WSL's 14-club
shape.

### Features

- **espn:** eight ESPN-backed tools for the Women's Super League — `get_teams`, `get_team`, `get_scoreboard`, `get_roster`, `get_match_details`, `get_team_schedule`, `get_news`, `get_standings`.
- **standings:** single flat 14-team table ordered by points (top flight of English women's football, no conferences).
- **analytics:** three derived tools — `get_strength_of_schedule`, `get_results_by_opponent_tier`, `get_adjusted_points_per_game`.
- **transport:** stdio (default) and streamable-http with optional JWKS bearer-token auth.
- **infrastructure:** retry + TTL-cache outbound adapters, OpenTelemetry hook (opt-in), inbound authorization port with pass-through and policy-service adapters, `/livez` / `/readyz` / `/health` probes.

### Deferred to a later release

- SDP-tier player leaderboards, team season stats, and per-player heatmaps via `api-sdp.wslfootball.com/stats/players` — the `category` enum required to reach the endpoint has not been discovered from public traffic yet.
- FA Cup and Continental Cup fixtures.
- Playoff / relegation bracket rendering.
- UEFA Women's Champions League match-day fixtures for WSL clubs.
