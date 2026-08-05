# jk-mcp-wsl

MCP server that gives Claude live access to Women's Super League (England) data — teams, matches, standings, rosters, and schedule-strength analytics — via the ESPN public API.

[![CI](https://github.com/jedi-knights/jk-mcp-wsl/actions/workflows/ci.yml/badge.svg)](https://github.com/jedi-knights/jk-mcp-wsl/actions/workflows/ci.yml)
[![Badge](https://github.com/jedi-knights/jk-mcp-wsl/actions/workflows/badge.yml/badge.svg)](https://github.com/jedi-knights/jk-mcp-wsl/actions/workflows/badge.yml)
[![Evals](https://github.com/jedi-knights/jk-mcp-wsl/actions/workflows/evals.yml/badge.svg)](https://github.com/jedi-knights/jk-mcp-wsl/actions/workflows/evals.yml)
[![Release](https://github.com/jedi-knights/jk-mcp-wsl/actions/workflows/release.yml/badge.svg)](https://github.com/jedi-knights/jk-mcp-wsl/actions/workflows/release.yml)
[![Python](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Claude Code](#claude-code)
- [Claude Desktop](#claude-desktop)
- [Docker](#docker)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

AI assistants like Claude are knowledgeable, but they have a hard cutoff date — they cannot tell you today's Women's Super League standings, last night's scores, or which teams are currently on top. This project fixes that.

It is an **MCP server** — a plugin that gives Claude direct access to live Women's Super League data: scores, standings, rosters, and derived schedule-strength analytics. Once installed, you can ask Claude natural-language questions about the WSL and get accurate, up-to-date answers. No subscription, no API key, and no programming required to use it.

The Women's Super League is the top flight of English women's football. In 2024 it was spun out of The FA into its own independent operating company (WSL Football Ltd), running the WSL and WSL 2 as a fully professional 14-team pyramid. This server wraps the ESPN public JSON feed, which is the cleanest freely-accessible source for the league. Rich per-player and team-season stats — historically served via `api-sdp.wslfootball.com` — are deferred to v2 pending discovery of the correct `stats/players` `category` enum.

---

## Features

The v1 surface is eleven read-only, idempotent tools split across two tiers.

### ESPN-backed (8)

| Tool | Description |
|---|---|
| `get_teams` | List all 14 clubs with IDs and abbreviations |
| `get_team` | Details for a specific team |
| `get_roster` | Team's active roster — jersey, position, age, citizenship |
| `get_scoreboard` | Match scores for a single day, a date range, or the current matchweek |
| `get_team_schedule` | Every match for a team in the current season — past + upcoming |
| `get_match_details` | One match's full details — score, venue, attendance, goals, cards, subs |
| `get_standings` | Current standings — single 14-team table ordered by points |
| `get_news` | Recent Women's Super League news articles |

### Derived analytics (3)

Pure functions over live standings + team schedules, exposing schedule-strength context the raw table does not.

| Tool | Description |
|---|---|
| `get_strength_of_schedule` | Team's average opponent points-per-game across matches already played |
| `get_results_by_opponent_tier` | Team's W-L-T split across current top / middle / bottom standings tiers |
| `get_adjusted_points_per_game` | Team's raw PPG alongside an opponent-quality-adjusted PPG |

### Roadmap

Deferred to v2+:

- Player leaderboards, team season stats, and per-player heatmaps via the league's own SDP tier (`api-sdp.wslfootball.com/stats/players`) — the `category` enum required to hit the endpoint has not been discovered from public traffic yet
- FA Cup and Continental Cup fixtures
- Playoff / relegation bracket rendering
- Related competitions (UEFA Women's Champions League match-day fixtures for WSL clubs)

---

## Requirements

- [Python 3.13+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

---

## Installation

```bash
git clone https://github.com/jedi-knights/jk-mcp-wsl.git
cd jk-mcp-wsl
uv sync
```

---

## Usage

Run the server in stdio mode (the default — used by Claude Code and Claude Desktop):

```bash
uv run python -m wsl.server
```

Run in HTTP mode (for networked or deployed access):

```bash
MCP_TRANSPORT=streamable-http uv run python -m wsl.server
```

### Example prompts

**Standings, scores, rosters:**
- Who is leading the WSL right now?
- Show me every WSL result from this past weekend.
- Who is on Arsenal's roster?
- When does Aston Villa play next?

**Schedule strength:**
- Which WSL side has played the toughest schedule so far?
- Show me Manchester United's record against the current top 3 clubs.
- Compare Chelsea and Manchester City on adjusted points-per-game.

---

## Configuration

All configuration is via environment variables. None are required for local use.

| Variable | Default | Description |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | Transport mode: `stdio` or `streamable-http` |
| `HOST` | `0.0.0.0` | Bind address (HTTP transport only) |
| `PORT` | `8000` | TCP port (HTTP transport only) |
| `MCP_PATH` | `/mcp/wsl` | URL path (HTTP transport only) |
| `API_HOST` | `https://site.api.espn.com` | ESPN API base URL |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `MCP_TRACING_ENABLED` | unset | Bootstrap the OpenTelemetry SDK |
| `MCP_AUTH_ENABLED` | unset | Require RS256 bearer tokens on streamable-http |
| `MCP_AUTH_ISSUER_URL` | unset | Auth-server origin (required when auth is on) |
| `MCP_AUTH_RESOURCE_URL` | unset | This server's public URL for the `aud` claim |

---

## Claude Code

Install from your local clone globally so the server is available in every project:

```bash
claude mcp add --scope user wsl -- uv run --directory /path/to/jk-mcp-wsl python -m wsl.server
```

Replace `/path/to/jk-mcp-wsl` with the absolute path to your clone. Verify with `claude mcp list`.

Drop `--scope user` to register only for the current project, or commit a `.mcp.json` to the repo root for collaborators:

```json
{
  "mcpServers": {
    "wsl": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/jk-mcp-wsl", "python", "-m", "wsl.server"]
    }
  }
}
```

---

## Claude Desktop

Add the following to your Claude Desktop configuration file.

**Location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "wsl": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/path/to/jk-mcp-wsl",
        "python", "-m", "wsl.server"
      ]
    }
  }
}
```

If `uv` is not on Claude Desktop's `PATH`, use the absolute path (`which uv` will show it). Fully quit and relaunch Claude Desktop after saving — a window close is not enough.

---

## Docker

Build the image:

```bash
docker build -t jk-mcp-wsl:latest .
```

Run in stdio mode (for MCP clients that spawn a subprocess):

```bash
docker run -i --rm jk-mcp-wsl:latest
```

Run in HTTP mode:

```bash
docker run --rm -p 8000:8000 \
  -e MCP_TRANSPORT=streamable-http \
  jk-mcp-wsl:latest
```

---

## Development

### Install

```bash
uv sync
```

### Invoke tasks

All common workflows are `invoke` tasks. Run `uv run inv --list` to see everything.

| Task | Alias | Description |
|---|---|---|
| `uv run inv lint` | `inv l` | Run ruff linter and format check |
| `uv run inv lint --fix` | `inv l --fix` | Auto-fix lint violations and reformat |
| `uv run inv test` | `inv t` | Run the full test suite |
| `uv run inv coverage` | `inv v` | Run tests with coverage report (threshold: 90%) |
| `uv run inv check-complexity` | `inv cc` | Check cyclomatic complexity (max 7) |
| `uv run inv build` | `inv b` | Build wheel and sdist into `dist/` |
| `uv run inv build-image` | `inv bi` | Build the Docker image |
| `uv run inv clean` | `inv c` | Remove build and coverage artifacts |

### Project structure

```
src/wsl/
├── server.py                     # entry point, transport selection, logging setup
├── adapters/
│   ├── inbound/
│   │   ├── mcp_adapter.py        # FastMCP server, health endpoints, tool registration
│   │   ├── formatters.py         # domain → LLM-readable text
│   │   ├── authorization.py      # inbound authz port implementations
│   │   └── tools/
│   │       ├── espn.py           # 8 ESPN-backed tools
│   │       └── analytics.py      # 3 schedule-strength analytics tools
│   └── outbound/
│       ├── espn_adapter.py       # ESPN HTTP client
│       ├── parsers.py            # ESPN JSON → domain models
│       ├── retry_adapter.py      # transient-failure retry decorator
│       └── caching_adapter.py    # in-process TTL cache
├── application/
│   ├── service.py                # WSLService — use cases, orchestration
│   ├── _helpers.py               # input validation
│   └── _analytics_helpers.py     # pure math for schedule-strength tools
├── domain/
│   ├── models.py                 # Team, Match, Standing, etc.
│   └── exceptions.py             # WSLNotFoundError, UpstreamAPIError
├── ports/
│   ├── inbound.py                # Authorizer protocol
│   └── outbound.py               # WSLAPIPort protocol
├── observability/                # OpenTelemetry bootstrap (opt-in)
└── security/                     # JWKS token verifier
```

The dependency direction flows inward: adapters → ports → domain. Nothing in `domain/` imports from adapters or a framework.

---

## Contributing

1. Fork the repository and clone your fork
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes following the existing patterns (hexagonal architecture, TDD, conventional commits)
4. Verify the full check suite passes: `uv run inv lint && uv run inv check-complexity && uv run inv coverage`
5. Open a pull request against `main`

All CI checks (lint, complexity, tests, coverage ≥ 90%) must pass before merge.

---

## License

MIT — see [LICENSE](LICENSE).
