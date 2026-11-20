"""End-of-day archive files our pipelines read every day (bhavcopies, MII file, price bands)."""

from datetime import date
from pathlib import Path

from ._files import as_date, unpack, unpacked_name
from ._hosts import ARCHIVES_HOST
from .reports import SPECS, ReportKey, ReportsMixin

# NSE switched the CM bhavcopy to the UDiFF format on this date.
UDIFF_SWITCH_DATE = date(2024, 7, 8)


class ArchivesMixin(ReportsMixin):
    """Archive downloads mixed into :class:`nselite.NSE`. All take the trading date."""

    async def _download_unpacked(self, url: str, folder: Path, overwrite: bool) -> Path:
        name = url.rsplit("/", 1)[-1]
        target = folder / unpacked_name(name)
        if target.exists() and not overwrite:
            return target
        archive = await self._http.download(url, folder / name, overwrite=True)
        return await unpack(archive)

    async def equity_bhavcopy(self, day: date, folder: Path, *, overwrite: bool = False) -> Path:
        """CM bhavcopy CSV (extracted); pre-UDiFF ``cmDDMONYYYYbhav.csv`` before 2024-07-08."""
        day = as_date(day)
        if day < UDIFF_SWITCH_DATE:
            stamp = day.strftime("%d%b%Y").upper()
            url = (
                f"{ARCHIVES_HOST}/content/historical/EQUITIES/{day.year}/{stamp[2:5]}"
                f"/cm{stamp}bhav.csv.zip"
            )
        else:
            url = SPECS[ReportKey.CM_UDIFF_BHAVCOPY].url(day)
        return await self._download_unpacked(url, folder, overwrite)

    async def delivery_bhavcopy(self, day: date, folder: Path, *, overwrite: bool = False) -> Path:
        """Full bhavcopy with delivery quantities (``sec_bhavdata_full_DDMMYYYY.csv``)."""
        return await self.download_report(
            ReportKey.CM_BHAVDATA_FULL, folder, day, overwrite=overwrite
        )

    async def indices_bhavcopy(self, day: date, folder: Path, *, overwrite: bool = False) -> Path:
        """Closing values of all indices (``ind_close_all_DDMMYYYY.csv``)."""
        return await self.download_report(
            ReportKey.INDEX_SNAPSHOT, folder, day, overwrite=overwrite
        )

    async def priceband_report(self, day: date, folder: Path, *, overwrite: bool = False) -> Path:
        """Price band of every security (``sec_list_DDMMYYYY.csv``)."""
        return await self.download_report(
            ReportKey.CM_PRICEBAND_COMPLETE, folder, day, overwrite=overwrite
        )

    async def pr_bhavcopy(self, day: date, folder: Path, *, overwrite: bool = False) -> Path:
        """PR bhavcopy zip (kept zipped: it bundles many reports plus a Readme)."""
        return await self.download_report(
            ReportKey.CM_BHAVCOPY_PR, folder, day, overwrite=overwrite
        )

    async def cm_mii_security_report(
        self, day: date, folder: Path, *, overwrite: bool = False
    ) -> Path:
        """CM MII security master CSV (extracted from ``.csv.gz``)."""
        url = SPECS[ReportKey.CM_SECURITY].url(day)
        return await self._download_unpacked(url, folder, overwrite)
