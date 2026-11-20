"""Real NSE calls. Run with: uv run pytest tests/live -m live"""

from pathlib import Path

import pytest

from nselite import NSE, ReportKey

pytestmark = pytest.mark.live


async def test_metadata_lists_bhavcopy() -> None:
    async with NSE() as nse:
        reports = await nse.daily_reports("CM")
        assert reports.previous, "NSE listed no previous-day reports"
        assert reports.latest(ReportKey.CM_UDIFF_BHAVCOPY).name.endswith(".csv.zip")


async def test_latest_and_dated_downloads_agree(tmp_path: Path) -> None:
    async with NSE() as nse:
        latest = (await nse.daily_reports("CM")).latest(ReportKey.CM_52W_HIGH_LOW)
        by_date = await nse.download_report(
            ReportKey.CM_52W_HIGH_LOW, tmp_path, latest.trading_date
        )
        assert by_date.name == latest.name, "file-name pattern drifted from NSE's metadata"
        assert by_date.stat().st_size > 1000


@pytest.mark.parametrize("segment", ["CM", "INDEX"])
async def test_patterns_match_listed_files(segment: str) -> None:
    """Every spec's pattern must reproduce the file name NSE lists for its trading date."""
    from nselite.reports import SPECS

    async with NSE() as nse:
        reports = await nse.daily_reports(segment)  # type: ignore[arg-type]
        listed = {f.key: f for f in reports.previous}
        checked = 0
        for key, spec in SPECS.items():
            f = listed.get(key)
            if spec.segment != segment or spec.pattern is None or f is None:
                continue
            if f.trading_date.strftime(spec.pattern) == f.name:
                checked += 1
        assert checked, f"no {segment} pattern matched NSE's listing"


async def test_archives_for_last_session(tmp_path: Path) -> None:
    async with NSE() as nse:
        day = (await nse.daily_reports("CM")).latest(ReportKey.CM_UDIFF_BHAVCOPY).trading_date
        bhav = await nse.equity_bhavcopy(day, tmp_path)
        assert bhav.suffix == ".csv" and bhav.stat().st_size > 10_000
        mii = await nse.cm_mii_security_report(day, tmp_path)
        assert mii.suffix == ".csv" and mii.stat().st_size > 10_000
        for p in (
            await nse.delivery_bhavcopy(day, tmp_path),
            await nse.indices_bhavcopy(day, tmp_path),
            await nse.priceband_report(day, tmp_path),
            await nse.pr_bhavcopy(day, tmp_path),
        ):
            assert p.stat().st_size > 1000, p.name


async def test_market_and_corporate_endpoints() -> None:
    async with NSE() as nse:
        assert await nse.status()
        assert "CM" in await nse.holidays()
        assert (await nse.lookup("hdfcbank"))[0]["symbol"] == "HDFCBANK"
        assert (await nse.equity_stocks_by_index("NIFTY 50"))["data"]
        assert isinstance(await nse.actions(), list)
        assert isinstance(await nse.event_calendar(), list)
        assert (await nse.annual_reports("HDFCBANK"))["data"]


async def test_xbrl_both_sources(tmp_path: Path) -> None:
    from datetime import date

    async with NSE() as nse:
        recs = await nse.fetch_xbrl_filings(
            "TCS", tmp_path, date(2024, 10, 1), date(2025, 9, 30), basis="consolidated"
        )
        assert {r["source"] for r in recs} == {"results", "integrated"}
        assert all(r["error"] is None for r in recs), [r["error"] for r in recs]
