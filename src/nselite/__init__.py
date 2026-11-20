"""nselite: lean, async-first client for NSE India reports and market data."""

from ._dates import split_range, weekdays
from .client import NSE, SyncNSE
from .errors import NotAvailable, NSEError, RateLimited, SessionExpired
from .reports import DailyReports, ReportFile, ReportKey

__all__ = [
    "NSE",
    "DailyReports",
    "NSEError",
    "NotAvailable",
    "RateLimited",
    "ReportFile",
    "ReportKey",
    "SessionExpired",
    "SyncNSE",
    "split_range",
    "weekdays",
]
__version__ = "0.2.0"
