"""Daily history for equities, indices and India VIX, fetched in concurrent chunks.

Without ``csv=true`` NSE returns only a 70-row sample of the range, silently (the page shows
a sample; the full data is the "download" variant). With it, each request returns the whole
range, up to 365 days. Rows come back in inconsistent order (equity and index newest first,
VIX oldest first). Benny Thadikaran found the ``csv`` fix (NseIndiaApi #32, v5.1.1).

So every method sends ``csv=true``, fetches 365-day chunks concurrently, and returns rows
**oldest first**, de-duplicated, each with a parsed ``date`` key added. As a guard, a long
chunk that still returns exactly the 70-row sample is split and refetched.
"""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import date, timedelta
from typing import Any, Literal

from ._dates import parse_nse_date, split_range
from ._files import as_date
from ._hosts import API_BASE
from ._http import Http

type Record = dict[str, Any]
type Series = Literal["EQ", "BE", "BL", "SM", "ST", "GB", "GS", "AE", "AF", "IL", "RL", "W3"]

CHUNK_DAYS = 365  # NSE rejects longer ranges
SAMPLE_ROWS = 70  # size of NSE's sample when csv=true is ignored
SAMPLE_MIN_DAYS = 105  # a range this long holds more than 70 sessions, so 70 rows = a sample
DATE_FMT = "%d-%m-%Y"


def _window(from_date: date | None, to_date: date | None) -> tuple[date, date]:
    end = as_date(to_date or date.today())
    start = as_date(from_date or end - timedelta(days=30))
    if start > end:
        raise ValueError(f"from_date {start} is after to_date {end}")
    return start, end


def _finish(rows: list[Record], date_key: str) -> list[Record]:
    """Add ``date``, drop duplicate days (chunk edges), sort oldest first."""
    by_day: dict[date, Record] = {}
    for row in rows:
        day = parse_nse_date(row[date_key])
        by_day[day] = {**row, "date": day}
    return [by_day[d] for d in sorted(by_day)]


class HistoryMixin:
    """History methods mixed into :class:`nselite.NSE`."""

    _http: Http

    async def _chunked(
        self,
        start: date,
        end: date,
        fetch: Callable[[date, date], Coroutine[Any, Any, list[Record]]],
    ) -> list[Record]:
        """Fetch ``start..end`` in concurrent chunks; halve any chunk that looks sampled."""

        async def chunk(s: date, e: date) -> list[Record]:
            rows = await fetch(s, e)
            if len(rows) != SAMPLE_ROWS or (e - s).days < SAMPLE_MIN_DAYS:
                return rows
            mid = s + (e - s) // 2
            async with asyncio.TaskGroup() as tg:
                left = tg.create_task(chunk(s, mid))
                right = tg.create_task(chunk(mid + timedelta(days=1), e))
            return left.result() + right.result()

        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(chunk(s, e)) for s, e in split_range(start, end, CHUNK_DAYS)]
        return [row for t in tasks for row in t.result()]

    async def equity_history(
        self,
        symbol: str,
        from_date: date | None = None,
        to_date: date | None = None,
        series: Series = "EQ",
    ) -> list[Record]:
        """Daily OHLCV, VWAP and trade counts for ``symbol`` (last 30 days by default).

        Row keys are NSE's (``chOpeningPrice``, ``chClosingPrice``, ``chTotTradedQty``,
        ``vwap``...) plus ``date``.
        """
        start, end = _window(from_date, to_date)

        async def fetch(s: date, e: date) -> list[Record]:
            return await self._http.get_json(
                f"{API_BASE}/NextApi/apiClient/GetQuoteApi",
                {
                    "functionName": "getHistoricalTradeData",
                    "symbol": symbol.upper(),
                    "series": series,
                    "fromDate": s.strftime(DATE_FMT),
                    "toDate": e.strftime(DATE_FMT),
                    "csv": "true",
                },
            )

        rows = await self._chunked(start, end, fetch)
        return _finish(rows, "mtimestamp")

    async def index_history(
        self, index: str, from_date: date | None = None, to_date: date | None = None
    ) -> list[Record]:
        """Daily OHLC, turnover and volume for an index such as ``NIFTY 50``."""
        start, end = _window(from_date, to_date)

        async def fetch(s: date, e: date) -> list[Record]:
            data = await self._http.get_json(
                f"{API_BASE}/historicalOR/indicesHistory",
                {
                    "indexType": index.upper(),
                    "from": s.strftime(DATE_FMT),
                    "to": e.strftime(DATE_FMT),
                    "csv": "true",
                },
            )
            return data["data"]

        rows = await self._chunked(start, end, fetch)
        return _finish(rows, "EOD_TIMESTAMP")

    async def vix_history(
        self, from_date: date | None = None, to_date: date | None = None
    ) -> list[Record]:
        """Daily India VIX open, high, low, close and change."""
        start, end = _window(from_date, to_date)

        async def fetch(s: date, e: date) -> list[Record]:
            data = await self._http.get_json(
                f"{API_BASE}/historicalOR/vixhistory",
                {"from": s.strftime(DATE_FMT), "to": e.strftime(DATE_FMT), "csv": "true"},
            )
            return data["data"]

        rows = await self._chunked(start, end, fetch)
        return _finish(rows, "EOD_TIMESTAMP")
