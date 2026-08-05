# jk-mcp-nwsl quickstart

An MCP server that exposes NWSL (National Women's Soccer League) data via the
ESPN public API. No API key required.

## Available tools

| Tool | Description |
|---|---|
| `get_teams` | List all active NWSL teams with IDs and abbreviations |
| `get_team` | Get details for a specific team by ESPN team ID |
| `get_scoreboard` | Get match scores — optionally filtered by date (YYYYMMDD) |
| `get_standings` | Get current league standings ordered by points |

## Running locally with uv

```bash
# Install dependencies
uv sync

# stdio mode (default — for use with Claude Desktop / Claude Code)
uv run python -m nwsl.server

# HTTP mode (for networked deployments)
MCP_TRANSPORT=streamable-http uv run python -m nwsl.server
```

## Running with Docker

```bash
# Build the image
docker build -t jk-mcp-nwsl:latest .

# stdio mode — pipe stdin/stdout for the MCP JSON-RPC stream
docker run -i --rm jk-mcp-nwsl:latest

# HTTP mode
docker run --rm -p 8000:8000 -e MCP_TRANSPORT=streamable-http jk-mcp-nwsl:latest
```

## Adding to Claude Desktop

Add the following to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nwsl": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "jk-mcp-nwsl:latest"]
    }
  }
}
```

Or with `uv` if you have the repo cloned locally:

```json
{
  "mcpServers": {
    "nwsl": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/jk-mcp-nwsl", "python", "-m", "nwsl.server"]
    }
  }
}
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `API_HOST` | `https://site.api.espn.com` | ESPN API base URL |
| `MCP_TRANSPORT` | `stdio` | Transport mode: `stdio` or `streamable-http` |
| `HOST` | `0.0.0.0` | Bind address (HTTP transport only) |
| `PORT` | `8000` | TCP port (HTTP transport only) |
| `LOG_LEVEL` | `INFO` | Python log level |

## Development

```bash
uv run inv test          # run tests
uv run inv coverage      # tests + coverage report
uv run inv lint          # ruff check + format check
uv run inv lint --fix    # auto-fix violations
uv run inv check-complexity  # cyclomatic complexity gate (max 7)
```
