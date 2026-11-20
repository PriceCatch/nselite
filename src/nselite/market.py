"""Market-wide data: status, symbol lookup, holidays, index constituents, movers."""

from typing import Any, Literal

from ._hosts import API_BASE
from ._http import Http

type Record = dict[str, Any]


def gainers(data: Record, count: int | None = None) -> list[Record]:
    """Rows of ``data["data"]`` with ``pChange > 0``, biggest first."""
    rows: list[Record] = [r for r in data["data"] if r["pChange"] > 0]
    return sorted(rows, key=lambda r: r["pChange"], reverse=True)[:count]


def losers(data: Record, count: int | None = None) -> list[Record]:
    """Rows of ``data["data"]`` with ``pChange < 0``, biggest fall first."""
    rows: list[Record] = [r for r in data["data"] if r["pChange"] < 0]
    return sorted(rows, key=lambda r: r["pChange"])[:count]


class MarketMixin:
    """Market methods mixed into :class:`nselite.NSE`."""

    _http: Http

    async def status(self) -> list[Record]:
        """Open/closed state of every NSE market segment."""
        data = await self._http.get_json(f"{API_BASE}/marketStatus")
        return data["marketState"]

    async def lookup(self, query: str) -> list[Record]:
        """Search equities by company name or symbol; best match first.

        Each row has ``symbol``, ``companyName``, ``series`` and ``segment``.
        (NSE retired the old ``/api/search/autocomplete`` endpoint in 2026.)
        """
        return await self._http.get_json(f"{API_BASE}/smart-search/equity", {"q": query})

    async def holidays(
        self, type: Literal["trading", "clearing"] = "trading"
    ) -> dict[str, list[Record]]:
        """Holiday list per segment; ``CM`` is the equity market."""
        return await self._http.get_json(f"{API_BASE}/holiday-master", {"type": type})

    async def equity_stocks_by_index(self, index: str = "NIFTY 50") -> Record:
        """Live constituents of an index, e.g. ``NIFTY 50`` or ``PERMITTED TO TRADE``."""
        index = index.upper()
        endpoint = "equity-stockIndex" if index == "PERMITTED TO TRADE" else "equity-stock-indices"
        return await self._http.get_json(f"{API_BASE}/{endpoint}", {"index": index})

    async def volume_gainers(self) -> Record:
        """Live volume spurts: stocks trading far above their average volume."""
        return await self._http.get_json(f"{API_BASE}/live-analysis-volume-gainers")

    async def traded_stocks(self) -> Record:
        """Every stock traded today (~3,500, all series), with price change, volume and value."""
        data = await self._http.get_json(f"{API_BASE}/live-analysis-stocksTraded")
        return data.get("total", data)

    gainers = staticmethod(gainers)
    losers = staticmethod(losers)
