"""Daily reports from NSE's All Reports page, addressed by NSE's own ``fileKey``.

Two ways to fetch a report:

* **Latest** (``day=None``): ask ``/api/daily-reports`` where today's file lives. This survives
  renamed files and moved hosts, because NSE tells us the current URL.
* **Any date** (``day=...``): build the URL from the known file-name pattern. No metadata call,
  so backfills cost one request per file.
"""

import asyncio
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

from ._dates import parse_nse_date
from ._hosts import API_BASE, ARCHIVES_HOST
from ._http import Http
from .errors import NotAvailable

type Segment = Literal["CM", "SME", "INDEX"]


class ReportKey(StrEnum):
    """NSE ``fileKey`` values for the reports nselite supports. Values are NSE's exact keys."""

    # Capital market: already used by our pipelines
    CM_UDIFF_BHAVCOPY = "CM-UDIFF-BHAVCOPY-CSV"
    CM_BHAVDATA_FULL = "CM-BHAVDATA-FULL"
    CM_BHAVCOPY_PR = "CM-BHAVCOPY-PR-ZIP"
    CM_SECURITY = "NSE-CM-SECURITY-CSV"
    CM_PRICEBAND_COMPLETE = "CM-PRICEBAND-COMPLETE-LIST"
    # Capital market: additions (P1 / P2 in the plan)
    CM_52W_HIGH_LOW = "CM-52 WEEK-HIGH_LOW"
    CM_SURVEILLANCE = "CM-SURVEILLANCE-INDICATOR-NEW-CSV"
    CM_SHORT_SELLING = "CM-SHORT-SELLING"
    CM_BULK_DEAL = "CM-BULK-DEAL"
    CM_BLOCK_DEAL = "CM-BLOCK-DEAL"
    CM_PE_RATIO = "CM-PE-RATIO-CSV"
    CM_VOLATILITY = "CM-VOLATILITY"
    CM_PRICE_BAND_NEXT_DAY = "CM-PRICE-BAND-NEXT-DAY"
    CM_MARGIN_TRADING = "CM-MARGIN-TRADING-DISC"
    CM_VAR_END_DAY = "CM-VAR-END-DAY"
    SME_BHAVCOPY = "SME-BHAVCOPY-CSV"
    # Indices
    INDEX_SNAPSHOT = "INDEX-SNAPSHOT"


@dataclass(slots=True, frozen=True)
class ReportSpec:
    """Where a report lives. ``pattern`` is a strftime file name; ``None`` = latest-only file."""

    segment: Segment
    folder: str
    pattern: str | None

    def url(self, day: date) -> str:
        if self.pattern is None:
            raise ValueError("this report has no dated archive; call with day=None")
        return f"{ARCHIVES_HOST}/{self.folder}/{day.strftime(self.pattern)}"


# Patterns observed on /api/daily-reports (Nov 2026). The date in a file name is not always the
# trading date (e.g. the next-day price band file); ``day`` always means the
# date that appears in the file name.
SPECS: dict[ReportKey, ReportSpec] = {
    ReportKey.CM_UDIFF_BHAVCOPY: ReportSpec(
        "CM", "content/cm", "BhavCopy_NSE_CM_0_0_0_%Y%m%d_F_0000.csv.zip"
    ),
    ReportKey.CM_BHAVDATA_FULL: ReportSpec(
        "CM", "products/content", "sec_bhavdata_full_%d%m%Y.csv"
    ),
    ReportKey.CM_BHAVCOPY_PR: ReportSpec("CM", "archives/equities/bhavcopy/pr", "PR%d%m%y.zip"),
    ReportKey.CM_SECURITY: ReportSpec("CM", "content/cm", "NSE_CM_security_%d%m%Y.csv.gz"),
    ReportKey.CM_PRICEBAND_COMPLETE: ReportSpec("CM", "content/equities", "sec_list_%d%m%Y.csv"),
    ReportKey.CM_52W_HIGH_LOW: ReportSpec("CM", "content", "CM_52_wk_High_low_%d%m%Y.csv"),
    ReportKey.CM_SURVEILLANCE: ReportSpec("CM", "content/cm", "REG1_IND%d%m%y.csv"),
    ReportKey.CM_SHORT_SELLING: ReportSpec(
        "CM", "archives/equities/shortSelling", "shortselling_%d%m%Y.csv"
    ),
    ReportKey.CM_BULK_DEAL: ReportSpec("CM", "content/equities", None),
    ReportKey.CM_BLOCK_DEAL: ReportSpec("CM", "content/equities", None),
    ReportKey.CM_PE_RATIO: ReportSpec("CM", "content/equities/peDetail", "PE_%d%m%y.csv"),
    ReportKey.CM_VOLATILITY: ReportSpec("CM", "archives/nsccl/volt", "CMVOLT_%d%m%Y.CSV"),
    ReportKey.CM_PRICE_BAND_NEXT_DAY: ReportSpec(
        "CM", "content/equities", "eq_band_changes_%d%m%Y.csv"
    ),
    ReportKey.CM_MARGIN_TRADING: ReportSpec("CM", "content/equities", "mrg_trading_%d%m%y.zip"),
    ReportKey.CM_VAR_END_DAY: ReportSpec("CM", "archives/nsccl/var", "C_VAR1_%d%m%Y_6.DAT"),
    ReportKey.SME_BHAVCOPY: ReportSpec("SME", "archives/sme/bhavcopy", "sme%d%m%Y.csv"),
    ReportKey.INDEX_SNAPSHOT: ReportSpec("INDEX", "content/indices", "ind_close_all_%d%m%Y.csv"),
}


@dataclass(slots=True, frozen=True)
class ReportFile:
    """One file listed by ``/api/daily-reports``."""

    key: str
    name: str
    title: str
    url: str
    size: str
    trading_date: date
    segment: str

    @classmethod
    def from_api(cls, row: dict[str, Any]) -> Self:
        return cls(
            key=row["fileKey"],
            name=row["fileActlName"],
            title=row["displayName"],
            url=row["filePath"].rstrip("/") + "/" + row["fileActlName"],
            size=row.get("fileSize", ""),
            trading_date=parse_nse_date(row["tradingDate"]),
            segment=row.get("fileSegment", ""),
        )


@dataclass(slots=True, frozen=True)
class DailyReports:
    """Files NSE lists for one segment, newest group first."""

    current: list[ReportFile]
    previous: list[ReportFile]
    future: list[ReportFile]

    def latest(self, key: str) -> ReportFile:
        """Newest listed file for ``key``. Raises :class:`NotAvailable` if NSE lists none."""
        for group in (self.future, self.current, self.previous):
            for f in group:
                if f.key == key:
                    return f
        raise NotAvailable(f"report {key!r} is not listed today")


class ReportsMixin:
    """Report methods mixed into :class:`nselite.NSE`."""

    _http: Http

    async def daily_reports(self, segment: Segment = "CM") -> DailyReports:
        """List the files on the All Reports page for ``segment`` (today and the last session)."""
        data: dict[str, list[dict[str, Any]] | None] = await self._http.get_json(
            f"{API_BASE}/daily-reports", {"key": segment}
        )

        def rows(name: str) -> list[ReportFile]:
            return [ReportFile.from_api(r) for r in data.get(name) or []]

        return DailyReports(rows("CurrentDay"), rows("PreviousDay"), rows("FutureDay"))

    async def report_url(self, key: ReportKey, day: date | None = None) -> str:
        """URL of ``key`` for ``day`` (date in the file name), or the latest listed file."""
        spec = SPECS[key]
        if day is not None:
            return spec.url(day)
        return (await self.daily_reports(spec.segment)).latest(key).url

    async def download_report(
        self, key: ReportKey, folder: Path, day: date | None = None, *, overwrite: bool = False
    ) -> Path:
        """Download one report into ``folder`` and return its path.

        Skips the download when the file is already there. Raises :class:`NotAvailable` when
        NSE has no file for that day (holiday, or not published yet).
        """
        url = await self.report_url(key, day)
        return await self._http.download(url, folder / url.rsplit("/", 1)[-1], overwrite=overwrite)

    async def download_reports(
        self, key: ReportKey, days: list[date], folder: Path, *, overwrite: bool = False
    ) -> dict[date, Path | None]:
        """Download ``key`` for many dates concurrently (within the rate limit).

        Returns ``{day: path}``, with ``None`` for days NSE has no file (holidays). Any other
        error cancels the batch and is raised.
        """
        results: dict[date, Path | None] = {}

        async def one(day: date) -> None:
            try:
                results[day] = await self.download_report(key, folder, day, overwrite=overwrite)
            except NotAvailable:
                results[day] = None

        async with asyncio.TaskGroup() as tg:
            for day in days:
                tg.create_task(one(day))
        return dict(sorted(results.items()))
