from datetime import date
from pathlib import Path

import pytest
import respx

from nselite import NSE, NotAvailable, ReportKey, SyncNSE
from nselite._http import WARM_URL
from nselite.reports import SPECS

FIXTURES = Path(__file__).parent.parent / "fixtures"
META = "https://www.nseindia.in/api/daily-reports"


def test_every_report_key_has_a_spec() -> None:
    assert set(SPECS) == set(ReportKey)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (
            ReportKey.CM_UDIFF_BHAVCOPY,
            "https://nsearchives.nseindia.in/content/cm/BhavCopy_NSE_CM_0_0_0_20261119_F_0000.csv.zip",
        ),
        (
            ReportKey.CM_BHAVCOPY_PR,
            "https://nsearchives.nseindia.in/archives/equities/bhavcopy/pr/PR191126.zip",
        ),
        (
            ReportKey.CM_SURVEILLANCE,
            "https://nsearchives.nseindia.in/content/cm/REG1_IND191126.csv",
        ),
        (
            ReportKey.INDEX_SNAPSHOT,
            "https://nsearchives.nseindia.in/content/indices/ind_close_all_19112026.csv",
        ),
    ],
)
async def test_dated_url_needs_no_metadata_call(
    nse: NSE, router: respx.MockRouter, key: ReportKey, expected: str
) -> None:
    assert await nse.report_url(key, date(2026, 11, 19)) == expected
    assert not router.calls


async def test_latest_only_report_rejects_a_date(nse: NSE) -> None:
    with pytest.raises(ValueError):
        await nse.report_url(ReportKey.CM_BULK_DEAL, date(2026, 11, 19))


async def test_daily_reports_parses_metadata(nse: NSE, router: respx.MockRouter) -> None:
    router.get(META, params={"key": "CM"}).respond(
        200,
        content=(FIXTURES / "daily_reports_cm.json").read_bytes(),
        headers={"content-type": "application/json"},
    )
    reports = await nse.daily_reports("CM")
    assert len(reports.previous) == 3
    latest = reports.latest(ReportKey.CM_52W_HIGH_LOW)
    assert latest.trading_date == date(2026, 11, 20)
    assert latest.url == "https://nsearchives.nseindia.in/content/CM_52_wk_High_low_20112026.csv"
    with pytest.raises(NotAvailable):
        reports.latest(ReportKey.CM_PE_RATIO)


async def test_download_latest_uses_metadata_url(
    nse: NSE, router: respx.MockRouter, tmp_path: Path
) -> None:
    router.get(META).respond(
        200,
        content=(FIXTURES / "daily_reports_cm.json").read_bytes(),
        headers={"content-type": "application/json"},
    )
    router.get("https://nsearchives.nseindia.in/content/equities/bulk.csv").respond(
        200, content=b"x", headers={"content-type": "text/csv"}
    )
    path = await nse.download_report(ReportKey.CM_BULK_DEAL, tmp_path)
    assert path == tmp_path / "bulk.csv"


async def test_download_many_maps_holidays_to_none(
    nse: NSE, router: respx.MockRouter, tmp_path: Path
) -> None:
    base = "https://nsearchives.nseindia.in/content/CM_52_wk_High_low_{}.csv"
    router.get(base.format("18112026")).respond(
        200, content=b"a", headers={"content-type": "text/csv"}
    )
    router.get(base.format("19112026")).respond(404)
    days = [date(2026, 11, 19), date(2026, 11, 18)]
    result = await nse.download_reports(ReportKey.CM_52W_HIGH_LOW, days, tmp_path)
    assert list(result) == [date(2026, 11, 18), date(2026, 11, 19)]
    assert result[date(2026, 11, 18)] == tmp_path / "CM_52_wk_High_low_18112026.csv"
    assert result[date(2026, 11, 19)] is None


def test_sync_wrapper_runs_coroutines(tmp_path: Path) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get(WARM_URL).respond(200)
        with SyncNSE(cookie_path=tmp_path / "c.json", http2=False) as nse:
            url = nse.report_url(ReportKey.CM_PE_RATIO, date(2026, 11, 19))
    assert url.endswith("/content/equities/peDetail/PE_191126.csv")
