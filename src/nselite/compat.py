"""Drop-in replacement for the NseIndiaApi fork's ``NSE`` class, for gradual migration.

Change only the import in an existing script::

    from nselite.compat import NSE   # was: from nse import NSE

Old method names, positional arguments and return types keep working, synchronously. Errors
subclass the same builtins the fork raised (``RuntimeError`` for a missing report,
``ConnectionError`` for network failures). Derivatives, IPO/ETF/SGB lists and other methods
outside nselite's scope raise ``AttributeError`` naming the method.

New code should use :class:`nselite.NSE` (async) or :class:`nselite.SyncNSE` instead.
"""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import date
from pathlib import Path
from typing import Any, Self

from ._hosts import API_BASE
from .client import NSE as AsyncNSE  # noqa: N811
from .filings import xbrl_filename
from .market import gainers, losers

# Old camelCase / renamed methods -> nselite method; arguments pass through unchanged.
_RENAMED = {
    "status": "status",
    "actions": "actions",
    "announcements": "announcements",
    "event_calendar": "event_calendar",
    "boardMeetings": "board_meetings",
    "annual_reports": "annual_reports",
    "circulars": "circulars",
    "financial_results": "financial_results",
    "results_comparison": "results_comparison",
    "integrated_filing_results": "integrated_filing_results",
    "financial_results_xbrl": "financial_results_xbrl",
    "holidays": "holidays",
    "listEquityStocksByIndex": "equity_stocks_by_index",
    "liveVolumeGainers": "volume_gainers",
    "volume_gainers": "volume_gainers",
    "listTradedStocks": "traded_stocks",
    "fetch_equity_historical_data": "equity_history",
    "fetch_historical_index_data": "index_history",
    "fetch_historical_vix_data": "vix_history",
}


class NSE:
    """Synchronous, fork-compatible facade over :class:`nselite.NSE`.

    :param download_folder: default folder for downloads (created if missing).
    :param server: accepted for compatibility; nselite always uses HTTP/2.
    :param timeout: network timeout in seconds.
    :param use_requests_library: accepted and ignored.
    """

    __version__ = "4.0.1"  # fork version this mirrors; eod2 checks it

    SEGMENT_EQUITY = "equities"
    SEGMENT_SME = "sme"
    SEGMENT_MF = "mf"
    SEGMENT_DEBT = "debt"
    HOLIDAY_CLEARING = "clearing"
    HOLIDAY_TRADING = "trading"
    UDIFF_SWITCH_DATE = date(2024, 7, 8)
    INTEGRATED_FINANCIALS = "Integrated Filing- Financials"
    INTEGRATED_GOVERNANCE = "Integrated Filing- Governance"

    xbrl_filename = staticmethod(xbrl_filename)
    gainers = staticmethod(gainers)
    losers = staticmethod(losers)

    def __init__(
        self,
        download_folder: str | Path,
        server: bool = False,
        timeout: int = 15,
        use_requests_library: bool = False,
    ) -> None:
        self.dir = self._folder(download_folder)
        self._runner = asyncio.Runner()
        self._nse = AsyncNSE(timeout=timeout)

    # ------------------------------------------------------------ plumbing

    @staticmethod
    def _folder(path: str | Path) -> Path:
        p = Path(path).expanduser().resolve()
        if p.is_file():
            raise ValueError(f"{p}: must be a folder")
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _dir(self, folder: str | Path | None) -> Path:
        return self._folder(folder) if folder else self.dir

    def _run[T](self, coro: Coroutine[Any, Any, T]) -> T:
        return self._runner.run(coro)

    def __getattr__(self, name: str) -> Callable[..., Any]:
        new = _RENAMED.get(name)
        if new is None:
            raise AttributeError(
                f"NSE.{name}() is not part of nselite (out of scope or not ported)."
            )
        method = getattr(self._nse, new)

        def call(*args: Any, **kwargs: Any) -> Any:
            return self._run(method(*args, **kwargs))

        call.__doc__ = method.__doc__
        return call

    def exit(self) -> None:
        """Close the session. Saved cookies are kept so the next run starts faster."""
        self._run(self._nse.aclose())
        self._runner.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> bool:
        self.exit()
        return False

    # ------------------------------------------------------------ downloads (old signatures)

    def equityBhavcopy(self, date: date, folder: str | Path | None = None) -> Path:  # noqa: N802
        return self._run(self._nse.equity_bhavcopy(date, self._dir(folder)))

    def deliveryBhavcopy(self, date: date, folder: str | Path | None = None) -> Path:  # noqa: N802
        return self._run(self._nse.delivery_bhavcopy(date, self._dir(folder)))

    def indicesBhavcopy(self, date: date, folder: str | Path | None = None) -> Path:  # noqa: N802
        return self._run(self._nse.indices_bhavcopy(date, self._dir(folder)))

    def priceband_report(self, date: date, folder: str | Path | None = None) -> Path:
        return self._run(self._nse.priceband_report(date, self._dir(folder)))

    def pr_bhavcopy(self, date: date, folder: str | Path | None = None) -> Path:
        return self._run(self._nse.pr_bhavcopy(date, self._dir(folder)))

    def cm_mii_security_report(self, date: date, folder: str | Path | None = None) -> Path:
        return self._run(self._nse.cm_mii_security_report(date, self._dir(folder)))

    def download_document(
        self,
        url: str,
        folder: str | Path | None = None,
        extract_files: list[str] | None = None,
    ) -> Path:
        return self._run(self._nse.download_document(url, self._dir(folder), extract_files))

    def download_xbrl(
        self,
        record: dict[str, Any] | str,
        folder: str | Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        return self._run(self._nse.download_xbrl(record, self._dir(folder), overwrite=overwrite))

    def fetch_xbrl_filings(
        self, symbol: str, folder: str | Path, *args: Any, **kwargs: Any
    ) -> list[dict[str, Any]]:
        return self._run(
            self._nse.fetch_xbrl_filings(symbol, self._folder(folder), *args, **kwargs)
        )

    def lookup(self, query: str) -> dict[str, list[dict[str, Any]]]:
        """Old ``{"symbols": [{"symbol", "symbol_info", ...}]}`` shape over the new search API."""
        rows = self._run(self._nse.lookup(query))
        return {"symbols": [{**r, "symbol_info": r.get("companyName", "")} for r in rows]}

    def fetch_daily_reports_file_metadata(self, segment: str = "CM") -> dict[str, Any]:
        """Raw ``/api/daily-reports`` JSON (new code: ``SyncNSE().daily_reports()``)."""
        return self._run(self._nse._http.get_json(f"{API_BASE}/daily-reports", {"key": segment}))  # pyright: ignore[reportPrivateUsage]
