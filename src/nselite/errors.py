"""Exceptions raised by nselite. Every failure is loud; nothing returns an empty result silently.

Each error also subclasses the builtin the NseIndiaApi fork raised for the same situation, so
existing ``except RuntimeError`` / ``except ConnectionError`` blocks keep working.
"""


class NSEError(Exception):
    """Base class for all nselite errors."""


class NotAvailable(NSEError, RuntimeError):
    """The resource does not exist (404), or NSE served an HTML page instead of data.

    Usually the report is not published yet, or the date was a holiday.
    """


class NetworkError(NSEError, ConnectionError):
    """Timeouts, dropped connections or unexpected HTTP status after all retries."""


class RateLimited(NetworkError):
    """NSE kept answering 429 after all retries."""


class SessionExpired(NetworkError):
    """NSE rejected the session (401/403) even after the cookies were refreshed."""
