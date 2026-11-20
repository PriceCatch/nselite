"""Corporate data: actions, announcements, board meetings, event calendar, annual reports."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

from ._files import as_date, unpack
from ._hosts import API_BASE
from ._http import Http

type Record = dict[str, Any]
type Segment = Literal["equities", "sme", "debt", "mf"]

DATE_FMT = "%d-%m-%Y"


def date_range_params(
    params: dict[str, str | int], from_date: date | None, to_date: date | None
) -> dict[str, str | int]:
    """Add NSE's ``from_date`` / ``to_date`` (dd-mm-YYYY) when both are given."""
    if from_date and to_date:
        f, t = as_date(from_date), as_date(to_date)
        if f > t:
            raise ValueError(f"from_date {f} is after to_date {t}")
        params["from_date"] = f.strftime(DATE_FMT)
        params["to_date"] = t.strftime(DATE_FMT)
    return params


class CorporateMixin:
    """Corporate-filing methods mixed into :class:`nselite.NSE`."""

    _http: Http

    async def actions(
        self,
        segment: Segment = "equities",
        symbol: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[Record]:
        """Corporate actions (dividends, splits, bonus...). Forthcoming ones when no dates given."""
        params: dict[str, str | int] = {"index": segment}
        if symbol:
            params["symbol"] = symbol.upper()
        date_range_params(params, from_date, to_date)
        return await self._http.get_json(f"{API_BASE}/corporates-corporateActions", params)

    async def announcements(
        self,
        index: Literal["equities", "sme", "debt", "mf", "invitsreits"] = "equities",
        symbol: str | None = None,
        fno: bool = False,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[Record]:
        """Corporate announcements; today's when no dates given. ``fno`` limits to F&O stocks."""
        params: dict[str, str | int] = {"index": index}
        if symbol:
            params["symbol"] = symbol.upper()
        if fno:
            params["fo_sec"] = "true"
        date_range_params(params, from_date, to_date)
        return await self._http.get_json(f"{API_BASE}/corporate-announcements", params)

    async def board_meetings(
        self,
        index: Literal["equities", "sme"] = "equities",
        symbol: str | None = None,
        fno: bool = False,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[Record]:
        """Board meetings; forthcoming ones when no dates given."""
        params: dict[str, str | int] = {"index": index}
        if symbol:
            params["symbol"] = symbol.upper()
        if fno:
            params["fo_sec"] = "true"
        date_range_params(params, from_date, to_date)
        return await self._http.get_json(f"{API_BASE}/corporate-board-meetings", params)

    async def event_calendar(self, index: Literal["equities", "sme"] = "equities") -> list[Record]:
        """Upcoming corporate events (results, fund raising, AGMs...)."""
        return await self._http.get_json(f"{API_BASE}/event-calendar", {"index": index})

    async def annual_reports(
        self, symbol: str, segment: Literal["equities", "sme"] = "equities"
    ) -> dict[str, list[Record]]:
        """Annual report links per year (``data[i]["fileName"]`` -> :meth:`download_document`)."""
        return await self._http.get_json(
            f"{API_BASE}/annual-reports", {"index": segment, "symbol": symbol.upper()}
        )

    async def circulars(
        self,
        subject: str | None = None,
        dept_code: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> Record:
        """Exchange circulars; the last 7 days when no dates given. ``dept_code`` e.g. ``CMTR``."""
        to_date = as_date(to_date or date.today())
        from_date = as_date(from_date or to_date - timedelta(days=7))
        params = date_range_params({}, from_date, to_date)
        if subject:
            params["sub"] = subject
        if dept_code:
            params["dept"] = dept_code.upper()
        return await self._http.get_json(f"{API_BASE}/circulars", params)

    async def download_document(
        self, url: str, folder: Path, extract_files: list[str] | None = None
    ) -> Path:
        """Download any NSE document (annual report, filing). Zips are extracted and removed."""
        path = await self._http.download(url, folder / url.rsplit("/", 1)[-1])
        if path.suffix.lower() == ".zip":
            return await unpack(path, extract_files)
        return path
