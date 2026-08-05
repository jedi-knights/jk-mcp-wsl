"""Security primitives for the Women's Super League MCP server.

The package exposes a single entry point — :func:`build_token_verifier`
— that wires the JWKS-backed RS256 verifier used by the streamable-http
transport when bearer-token authentication is enabled.

The stdio transport runs as a subprocess of its client; the trust
boundary is the process boundary itself, so the verifier is never wired
in that mode (see :mod:`wsl.server`).
"""

from .token_verifier import JWKSTokenVerifier, build_token_verifier

__all__ = ["JWKSTokenVerifier", "build_token_verifier"]
