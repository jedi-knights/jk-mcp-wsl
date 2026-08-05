"""Internal helpers for WSLService — validation and input normalization.

Extracted from service.py to keep that file focused on use-case orchestration.
Schedule-strength analytics helpers live in ``_analytics_helpers.py``.
"""

_DATE_PATTERN_LENGTH = 8


def _validate_yyyymmdd(value: str, label: str) -> str:
    """Return ``value`` if it is exactly 8 digits, else raise ValueError citing ``label``."""
    if not value.isdigit() or len(value) != _DATE_PATTERN_LENGTH:
        raise ValueError(f"{label} must be in YYYYMMDD format, got {value!r}")
    return value
