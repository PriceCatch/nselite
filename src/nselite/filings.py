"""Financial results and their XBRL files, including SEBI Integrated Filings (Mar 2025 on).

NSE serves results from two endpoints: ``corporates-financial-results`` (filings up to the
December 2024 quarter) and ``integrated-filing-results`` (from the March 2025 quarter).
:meth:`FilingsMixin.financial_results_xbrl` queries both and merges them into one record shape.
"""

import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from ._dates import split_range
from ._files import as_date
from ._hosts import API_BASE
from ._http import Http
from .corporate import date_range_params
from .errors import NotAvailable, NSEError

type Record = dict[str, Any]
type Period = Literal["quarterly", "annual", "half-yearly"]
type Basis = Literal["consolidated", "standalone", "both"]
type Source = Literal["both", "results", "integrated"]

INTEGRATED_FINANCIALS = "Integrated Filing- Financials"
INTEGRATED_GOVERNANCE = "Integrated Filing- Governance"
_DT_FORMATS = ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y")


def parse_nse_dt(value: str | None) -> datetime | None:
    """Parse ``16-Jan-2025 20:20:21`` / ``01-Oct-2024``; ``None`` for blank, ``-`` or junk."""
    if not value or value.strip() in ("", "-"):
        return None
    value = value.strip()
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _xml_link(row: Record) -> str | None:
    xbrl = (row.get("xbrl") or "").strip()
    return xbrl if xbrl and xbrl != "-" and xbrl.lower().endswith(".xml") else None


def normalise_result_filing(row: Record) -> Record | None:
    """Add ``basis`` (C/S), ``period_from``/``period_to`` (date), ``broadcast_dt``, ``source``.

    ``broadcast_dt`` is when NSE disseminated the filing: use it, not ``period_to``, as the
    point-in-time availability stamp to avoid look-ahead bias. ``None`` if unusable.
    """
    xbrl = _xml_link(row)
    period_from = parse_nse_dt(row.get("fromDate"))
    period_to = parse_nse_dt(row.get("toDate"))
    if xbrl is None or period_from is None or period_to is None:
        return None
    broadcast_dt = (
        parse_nse_dt(row.get("exchdisstime"))
        or parse_nse_dt(row.get("broadCastDate"))
        or parse_nse_dt(row.get("filingDate"))
    )
    consolidated = (row.get("consolidated") or "").strip().lower()
    return {
        **row,
        "xbrl": xbrl,
        "basis": "C" if consolidated == "consolidated" else "S",
        "period_from": period_from.date(),
        "period_to": period_to.date(),
        "broadcast_dt": broadcast_dt,
        "source": "results",
    }


def normalise_integrated_filing(row: Record) -> Record | None:
    """Map an Integrated Filing row to the :func:`normalise_result_filing` shape.

    ``period_from`` is the first day of the quarter ending ``qe_Date``. ``broadcast_dt`` is
    ``revised_Date`` for revisions, else ``broadcast_Date``. Governance filings are dropped.
    """
    if (row.get("type") or INTEGRATED_FINANCIALS) != INTEGRATED_FINANCIALS:
        return None
    xbrl = _xml_link(row)
    qe = parse_nse_dt(row.get("qe_Date"))
    if xbrl is None or qe is None:
        return None
    period_to = qe.date()
    start_month = (period_to.month - 3) % 12 + 1
    start_year = period_to.year - (1 if start_month > period_to.month else 0)
    revision = (row.get("type_Sub") or "").strip().lower() == "revision"
    stamps = (
        ("revised_Date", "broadcast_Date", "creation_Date")
        if revision
        else ("broadcast_Date", "creation_Date", "revised_Date")
    )
    broadcast_dt = next((dt for k in stamps if (dt := parse_nse_dt(row.get(k)))), None)
    consolidated = (row.get("consolidated") or "").strip().lower()
    return {
        **row,
        "xbrl": xbrl,
        "basis": "C" if consolidated == "consolidated" else "S",
        "period_from": date(start_year, start_month, 1),
        "period_to": period_to,
        "broadcast_dt": broadcast_dt,
        "cumulative": "Non-cumulative",
        "seqNumber": row.get("seq_Id"),
        "source": "integrated",
    }


def select_xbrl_records(candidates: list[Record], basis: Basis, latest_only: bool) -> list[Record]:
    """De-duplicate by URL, filter by basis, collapse revisions, sort by period then broadcast."""
    wanted = {"consolidated": {"C"}, "standalone": {"S"}, "both": {"C", "S"}}[basis]
    seen: set[str] = set()
    records: list[Record] = []
    for rec in candidates:
        if rec["xbrl"] in seen or rec["basis"] not in wanted:
            continue
        seen.add(rec["xbrl"])
        records.append(rec)

    def order(r: Record) -> tuple[datetime, int]:
        return (r["broadcast_dt"] or datetime.min, int(r.get("seqNumber") or 0))

    if latest_only:
        groups: dict[tuple[Any, ...], list[Record]] = {}
        for rec in records:
            cum = (rec.get("cumulative") or "").strip().lower()
            groups.setdefault((rec["period_from"], rec["period_to"], rec["basis"], cum), []).append(
                rec
            )
        records = []
        for versions in groups.values():
            latest = max(versions, key=order)
            latest["revision_count"] = len(versions)
            records.append(latest)

    records.sort(key=lambda r: (r["period_to"], r["broadcast_dt"] or datetime.min, r["basis"]))
    return records


def xbrl_filename(record: Record) -> str:
    """``{SYMBOL}_{period_to:YYYYMMDD}_{C|S}_{N|Y}_{broadcast:YYYYMMDDHHMMSS}.xml``.

    ``Y`` marks cumulative figures. The broadcast stamp keeps each revision a separate file.
    """
    symbol = (record.get("symbol") or "UNKNOWN").upper()
    cumulative = (record.get("cumulative") or "").strip().lower()
    cum_flag = "N" if cumulative in ("", "non-cumulative") else "Y"
    bdt: datetime | None = record.get("broadcast_dt")
    stamp = bdt.strftime("%Y%m%d%H%M%S") if bdt else "00000000000000"
    return f"{symbol}_{record['period_to']:%Y%m%d}_{record['basis']}_{cum_flag}_{stamp}.xml"


class FilingsMixin:
    """Financial-results methods mixed into :class:`nselite.NSE`."""

    _http: Http

    async def financial_results(
        self,
        segment: Literal["equities", "sme", "debt", "mf"] = "equities",
        period: Period = "quarterly",
        symbol: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[Record]:
        """Results filing metadata (to the Dec 2024 quarter); year to date if no dates."""
        params: dict[str, str | int] = {"index": segment, "period": period}
        if symbol:
            params["symbol"] = symbol.upper()
        date_range_params(params, from_date, to_date)
        data = await self._http.get_json(f"{API_BASE}/corporates-financial-results", params)
        return data.get("data", []) if isinstance(data, dict) else data  # type: ignore[union-attr]

    async def results_comparison(self, symbol: str) -> Record:
        """Last ~5 quarters of revenue / profit / EPS (``resCmpData``), amounts in Rs lakhs."""
        # NSE's own path is misspelled "comparision".
        return await self._http.get_json(
            f"{API_BASE}/results-comparision", {"symbol": symbol.upper()}
        )

    async def integrated_filing_results(
        self,
        symbol: str | None = None,
        segment: Literal["equities", "sme"] = "equities",
        filing_type: str | None = INTEGRATED_FINANCIALS,
        from_date: date | None = None,
        to_date: date | None = None,
        page_size: int = 500,
    ) -> list[Record]:
        """SEBI Integrated Filing rows (Mar 2025 quarter on). All pages, fetched concurrently."""
        url = f"{API_BASE}/integrated-filing-results"
        params: dict[str, str | int] = {"index": segment, "size": page_size}
        if symbol:
            params["symbol"] = symbol.upper()
        if filing_type:
            params["type"] = filing_type
        date_range_params(params, from_date, to_date)

        first = await self._http.get_json(url, {**params, "page": 1})
        if isinstance(first, list):  # unpaged response
            return first  # type: ignore[return-value]
        rows: list[Record] = first.get("data") or []
        total = int(first.get("totalCount") or 0)
        pages = -(-total // page_size)  # ceil
        if pages <= 1 or len(rows) < page_size:
            return rows
        async with asyncio.TaskGroup() as tg:  # NSE pages are 1-based
            tasks = [
                tg.create_task(self._http.get_json(url, {**params, "page": p}))
                for p in range(2, pages + 1)
            ]
        for t in tasks:
            rows.extend(t.result().get("data") or [])
        return rows

    async def financial_results_xbrl(
        self,
        symbol: str,
        from_date: date | None = None,
        to_date: date | None = None,
        period: Period = "quarterly",
        basis: Basis = "both",
        latest_only: bool = True,
        segment: Literal["equities", "sme"] = "equities",
        source: Source = "both",
    ) -> list[Record]:
        """Filings with an XBRL file for ``symbol``, from both endpoints, normalised and merged.

        Dates filter on the broadcast date. Long ranges are split into 1-year chunks fetched
        concurrently. With ``latest_only`` only the newest revision per period is kept, with
        ``revision_count`` recording how many existed. Integrated filings are quarterly only.
        """
        if (from_date is None) != (to_date is None):
            raise ValueError("pass both from_date and to_date, or neither")
        if from_date and to_date and as_date(from_date) > as_date(to_date):
            raise ValueError("from_date is after to_date")

        chunks: list[tuple[date | None, date | None]] = (
            list(split_range(as_date(from_date), as_date(to_date), 365))
            if from_date and to_date
            else [(None, None)]
        )
        async with asyncio.TaskGroup() as tg:
            results = (
                [
                    tg.create_task(self.financial_results(segment, period, symbol, s, e))
                    for s, e in chunks
                ]
                if source in ("both", "results")
                else []
            )
            integrated = (
                tg.create_task(
                    self.integrated_filing_results(
                        symbol, segment, from_date=from_date, to_date=to_date
                    )
                )
                if source in ("both", "integrated") and period == "quarterly"
                else None
            )

        records = [
            rec for t in results for row in t.result() if (rec := normalise_result_filing(row))
        ]
        if integrated is not None:
            records += [
                rec for row in integrated.result() if (rec := normalise_integrated_filing(row))
            ]
        return select_xbrl_records(records, basis, latest_only)

    async def download_xbrl(
        self, record: Record | str, folder: Path, *, overwrite: bool = False
    ) -> Path:
        """Download one XBRL file and check it is XML. Skips files already on disk.

        ``record`` is a :meth:`financial_results_xbrl` record (saved as :func:`xbrl_filename`)
        or a raw URL (saved under its own name).
        """
        if isinstance(record, str):
            url, target = record, folder / record.rsplit("/", 1)[-1]
        else:
            url, target = record["xbrl"], folder / xbrl_filename(record)
        if target.exists() and target.stat().st_size > 0 and not overwrite:
            return target
        path = await self._http.download(url, target, overwrite=True)
        with path.open("rb") as f:
            head = f.read(2048).lstrip()
        if not (head.startswith(b"<?xml") or b"<xbrl" in head.lower()):
            path.unlink(missing_ok=True)
            raise NotAvailable(f"downloaded file is not XBRL/XML: {url}")
        return path

    async def fetch_xbrl_filings(
        self,
        symbol: str,
        folder: Path,
        from_date: date | None = None,
        to_date: date | None = None,
        period: Period = "quarterly",
        basis: Basis = "both",
        latest_only: bool = True,
        overwrite: bool = False,
        source: Source = "both",
    ) -> list[Record]:
        """List and download every XBRL filing for ``symbol`` into ``folder/SYMBOL/``.

        Downloads run concurrently. A failed file does not stop the batch: each record gets
        ``local_path`` (``Path`` or ``None``) and ``error`` (message or ``None``).
        """
        dest = folder / symbol.upper()
        records = await self.financial_results_xbrl(
            symbol, from_date, to_date, period, basis, latest_only, source=source
        )

        async def one(rec: Record) -> None:
            try:
                rec["local_path"] = await self.download_xbrl(rec, dest, overwrite=overwrite)
                rec["error"] = None
            except NSEError as e:
                rec["local_path"] = None
                rec["error"] = str(e)

        async with asyncio.TaskGroup() as tg:
            for rec in records:
                tg.create_task(one(rec))
        return records
