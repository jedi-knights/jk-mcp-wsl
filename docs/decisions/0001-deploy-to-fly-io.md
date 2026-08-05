# ADR-0001: Deploy MCP server to Fly.io

## Status

Accepted

## Date

2026-04-25

## Context

The NWSL MCP server supports two transports: `stdio` (default, for local subprocess use) and `streamable-http` (for networked deployments). To make the server accessible to remote MCP clients without requiring local installation, it needs to run as a persistent HTTP service on managed infrastructure.

The options considered were:

- **Fly.io** — container-native PaaS with per-second billing, a generous free tier, and a first-class CLI (`flyctl`). Deploys directly from a `Dockerfile` with no registry setup required.
- **Railway** — similar PaaS with a simple deploy model, but less control over networking and no free tier.
- **AWS ECS / Fargate** — more flexible, but significantly more operational overhead for a single lightweight server.
- **Self-hosted VPS** — full control, but requires manual TLS, process supervision, and maintenance.

## Decision

Deploy using Fly.io with the `streamable-http` transport. The existing `Dockerfile` already supports this transport via the `MCP_TRANSPORT` environment variable, so no application changes are required — only infrastructure configuration.

Deployment is triggered automatically from the release workflow on every new semantic version.

## Setup

### One-time local setup

**1. Install flyctl and authenticate**

```sh
brew install flyctl
fly auth login
```

**2. Create the app and generate `fly.toml`**

Run from the repository root. Accept the defaults and decline a Postgres database.

```sh
fly launch --no-deploy
```

**3. Configure the transport in `fly.toml`**

Add an `[env]` section so the container starts in HTTP mode instead of stdio:

```toml
[env]
  MCP_TRANSPORT = "streamable-http"
  PORT = "8000"
```

Ensure `internal_port` in `[[services]]` matches `PORT` (8000).

**4. Generate a deploy token and add it to GitHub**

```sh
fly tokens create deploy -x 999999h
```

Add the output as a repository secret named `FLY_API_TOKEN` under
`Settings → Secrets and variables → Actions`.

### Release workflow changes

Add the `flyctl` installer before the semantic release step in `.github/workflows/release.yml`:

```yaml
      - name: Install flyctl
        uses: superfly/flyctl-actions/setup-flyctl@master
```

Add the deploy step after the "Update floating major-version tag" step:

```yaml
      - name: Deploy to Fly.io
        run: |
          if [ ! -f VERSION ]; then
            echo "No new version released — skipping deployment."
            exit 0
          fi
          flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

`--remote-only` instructs Fly.io to build the Docker image on their infrastructure rather than in the GitHub Actions runner, avoiding Docker-in-Docker setup and reducing build time.

## Consequences

- The server is reachable at a stable `*.fly.dev` URL without any local installation.
- Deployments are automatic on every released version — no manual deploy step needed.
- `fly.toml` must be committed to the repository so `flyctl deploy` has its configuration.
- The `FLY_API_TOKEN` secret must be rotated if it is ever exposed.
- Running continuously on Fly.io incurs cost beyond the free tier if traffic is sustained; the per-second billing model keeps idle costs low.
