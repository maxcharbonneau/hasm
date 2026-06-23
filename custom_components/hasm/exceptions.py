"""Exceptions for the HASM API client (independent of Home Assistant)."""

from __future__ import annotations


class HasmError(Exception):
    """Base error for any interaction with a Home Assistant instance."""


class HasmConnectionError(HasmError):
    """Instance unreachable: timeout, connection refused, DNS, etc."""


class HasmAuthError(HasmError):
    """Invalid or rejected token (HTTP 401/403)."""


class HasmResponseError(HasmError):
    """Unexpected HTTP response (unhandled status or unreadable body)."""
