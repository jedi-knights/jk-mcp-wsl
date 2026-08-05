"""Domain exceptions for the Women's Super League application.

All exceptions raised by the application layer or adapters are rooted here.
Callers can catch WSLError to handle any domain-level failure, or catch
subclasses for finer-grained handling.
"""


class WSLError(Exception):
    """Base class for all Women's Super League domain exceptions."""


class WSLNotFoundError(WSLError):
    """Raised when the requested resource does not exist (HTTP 404)."""


class UpstreamAPIError(WSLError):
    """Raised when the upstream ESPN API returns an unexpected error (non-2xx HTTP response)."""
