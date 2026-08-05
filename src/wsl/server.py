"""Entry point for the Women's Super League MCP server.

Wires together the outbound adapter (ESPN HTTP), the application service, and
the inbound MCP adapter. The dependency graph flows inward — adapters depend on
ports, ports depend on domain models. Nothing here is circular.

Transport: controlled by the MCP_TRANSPORT environment variable.
- "stdio" (default): JSON-RPC over stdin/stdout — client spawns the server as
  a subprocess. Never write to stdout in this mode; it corrupts the message stream.
- "streamable-http": HTTP server on HOST:PORT. The MCP client connects over HTTP.
  Use this for deployed / networked deployments. HOST defaults to "0.0.0.0" and
  PORT defaults to 8000.

ESPN API host: controlled by the API_HOST environment variable.
- Default: https://site.api.espn.com

Structured logging: all log records are emitted as JSON objects to stderr.
Docker captures stderr as container logs, so JSON output is parseable by
log aggregators without additional parsing rules. The log level can be
overridden at runtime with the LOG_LEVEL environment variable (default: INFO).
"""

import json
import logging
import os
import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .adapters.inbound.authorization import build_authorizer
from .adapters.inbound.mcp_adapter import create_mcp_server
from .adapters.outbound.caching_adapter import CachingAdapter
from .adapters.outbound.espn_adapter import ESPNAdapter
from .adapters.outbound.retry_adapter import RetryingAdapter
from .application.service import WSLService
from .observability import setup_tracing
from .security import build_token_verifier


class _JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Using a custom formatter rather than a third-party library keeps the
    dependency surface minimal. Each record becomes one JSON line, which is
    the format expected by most container log drivers and aggregators.
    """

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def _configure_logging() -> None:
    """Configure the root logger to emit JSON records to stderr.

    Reads the LOG_LEVEL environment variable (default: INFO). Invalid values
    fall back to INFO.
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    logging.root.setLevel(level)
    logging.root.addHandler(handler)


load_dotenv()
_configure_logging()

logger = logging.getLogger(__name__)

_VALID_TRANSPORTS = ("stdio", "streamable-http")


def build_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    api_host: str = "https://site.api.espn.com",
    path: str = "/mcp",
    auth_settings=None,
    token_verifier=None,
    authorizer=None,
) -> FastMCP:
    """Wire ESPNAdapter → WSLService → FastMCP and return the server.

    Extracted from main() so the composition graph can be constructed and
    tested without starting any transport.

    Args:
        host: Bind address for HTTP transport (ignored for stdio). Defaults to 0.0.0.0.
        port: TCP port for HTTP transport (ignored for stdio). Defaults to 8000.
        api_host: Base URL of the upstream ESPN API.
        path: URL path for the streamable-http transport (ignored for stdio).
        auth_settings: Optional AuthSettings to enable bearer-token enforcement.
        token_verifier: Optional TokenVerifier consulted on every request.
    """
    adapter = ESPNAdapter(base_url=api_host)
    # Compose cross-cutting adapters: HTTP → retry on transient errors → cache results.
    retrying = RetryingAdapter(adapter)
    caching = CachingAdapter(retrying)

    service = WSLService(repo=caching)
    return create_mcp_server(
        service,
        host=host,
        port=port,
        path=path,
        auth_settings=auth_settings,
        token_verifier=token_verifier,
        authorizer=authorizer,
    )


def main() -> None:
    """Start the Women's Super League MCP server.

    Reads configuration from the environment:
      API_HOST              — base URL of the upstream ESPN API (default: https://site.api.espn.com)
      MCP_TRANSPORT         — "stdio" (default) or "streamable-http"
      HOST                  — bind address for HTTP transport (default: 0.0.0.0)
      PORT                  — TCP port for HTTP transport (default: 8000)
      MCP_PATH              — URL path for streamable-http transport (default: /mcp/wsl)
      MCP_TRACING_ENABLED   — bootstrap the OpenTelemetry SDK (default false)
      MCP_AUTH_ENABLED      — require RS256 bearer tokens on streamable-http (default false)
      MCP_AUTH_ISSUER_URL   — auth-server origin (required when MCP_AUTH_ENABLED=true)
      MCP_AUTH_RESOURCE_URL — this server's public URL for the aud claim (optional)
    """
    api_host = os.environ.get("API_HOST", "https://site.api.espn.com")
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    path = os.environ.get("MCP_PATH", "/mcp/wsl")

    if transport not in _VALID_TRANSPORTS:
        raise ValueError(f"Invalid MCP_TRANSPORT={transport!r}. Must be one of: {', '.join(_VALID_TRANSPORTS)}")

    auth_settings, token_verifier = _build_auth(transport)
    # Build the inbound authorizer once at startup. Defaults to
    # PassThroughAuthorizer when MCP_AUTHZ_URL is unset, matching the
    # local-dev and stdio posture; production deployments set the URL
    # so every tool dispatch consults authorization-policy-service.
    authorizer = build_authorizer()

    # Wire OpenTelemetry before constructing the server so the
    # HTTPXClientInstrumentor patches httpx before any outbound
    # adapters are instantiated. A no-op when MCP_TRACING_ENABLED is
    # unset; the returned shutdown is invoked on normal exit via
    # try/finally so buffered spans flush.
    shutdown_tracing = setup_tracing("jk-mcp-wsl")
    try:
        if transport == "streamable-http":
            logger.info(
                "Starting Women's Super League MCP server (streamable-http transport, %s:%s, path=%s, auth=%s)",
                host,
                port,
                path,
                "on" if token_verifier else "off",
            )
            build_server(
                host=host,
                port=port,
                api_host=api_host,
                path=path,
                auth_settings=auth_settings,
                token_verifier=token_verifier,
                authorizer=authorizer,
            ).run(transport="streamable-http")
        else:
            logger.info("Starting Women's Super League MCP server (stdio transport)")
            build_server(api_host=api_host, authorizer=authorizer).run(transport="stdio")
    finally:
        shutdown_tracing()


def _build_auth(transport: str):
    """Build the AuthSettings + TokenVerifier pair for the streamable-http
    transport.

    The stdio transport relies on the subprocess boundary as its trust
    anchor; injecting bearer-token auth there would only confuse
    operators. The function returns ``(None, None)`` for stdio
    regardless of the env-var state.
    """
    if transport != "streamable-http":
        return None, None
    verifier = build_token_verifier()
    if verifier is None:
        return None, None
    # AuthSettings is imported lazily — when MCP_AUTH_ENABLED is unset
    # the import cost is skipped, matching the same lazy posture the
    # observability bootstrap uses.
    from mcp.server.auth.settings import AuthSettings

    settings = AuthSettings(
        issuer_url=verifier.issuer,
        resource_server_url=verifier.audience or verifier.issuer,
    )
    return settings, verifier


if __name__ == "__main__":
    main()
