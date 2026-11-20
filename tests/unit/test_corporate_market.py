from datetime import date, datetime
from pathlib import Path

import pytest
import respx

from nselite import NSE
from nselite.market import gainers, losers

API = "https://www.nseindia.in/api"


async def test_actions_sends_nse_date_format(nse: NSE, router: respx.MockRouter) -> None:
    route = router.get(f"{API}/corporates-corporateActions").respond(200, json=[{"symbol": "TCS"}])
    out = await nse.actions(symbol="TCS", from_date=datetime(2026, 1, 1), to_date=date(2026, 3, 31))
    assert out == [{"symbol": "TCS"}]
    assert dict(route.calls.last.request.url.params) == {
        "index": "equities",
        "symbol": "TCS",
        "from_date": "01-01-2026",
        "to_date": "31-03-2026",
    }


async def test_reversed_range_is_rejected(nse: NSE) -> None:
    with pytest.raises(ValueError):
        await nse.board_meetings(from_date=date(2026, 2, 1), to_date=date(2026, 1, 1))


async def test_announcements_fno_flag(nse: NSE, router: respx.MockRouter) -> None:
    route = router.get(f"{API}/corporate-announcements").respond(200, json=[])
    await nse.announcements(fno=True)
    assert route.calls.last.request.url.params["fo_sec"] == "true"


async def test_circulars_default_to_last_week(nse: NSE, router: respx.MockRouter) -> None:
    route = router.get(f"{API}/circulars").respond(200, json={"data": []})
    await nse.circulars(dept_code="cmtr", to_date=date(2026, 11, 20))
    params = route.calls.last.request.url.params
    assert (params["from_date"], params["to_date"], params["dept"]) == (
        "13-11-2026",
        "20-11-2026",
        "CMTR",
    )


async def test_event_calendar_uses_plain_index(nse: NSE, router: respx.MockRouter) -> None:
    route = router.get(f"{API}/event-calendar").respond(200, json=[])
    await nse.event_calendar()
    assert route.calls.last.request.url.params["index"] == "equities"


async def test_download_document_extracts_zip(
    nse: NSE, router: respx.MockRouter, tmp_path: Path
) -> None:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("AR_2026.pdf", b"%PDF")
    url = "https://nsearchives.nseindia.in/annual_reports/AR_X.zip"
    router.get(url).respond(
        200, content=buf.getvalue(), headers={"content-type": "application/zip"}
    )
    path = await nse.download_document(url, tmp_path)
    assert path == tmp_path / "AR_2026.pdf"


async def test_status_and_traded_stocks_unwrap(nse: NSE, router: respx.MockRouter) -> None:
    router.get(f"{API}/marketStatus").respond(200, json={"marketState": [{"market": "CM"}]})
    router.get(f"{API}/live-analysis-stocksTraded").respond(200, json={"total": {"count": 1}})
    assert await nse.status() == [{"market": "CM"}]
    assert await nse.traded_stocks() == {"count": 1}


@pytest.mark.parametrize(
    ("index", "endpoint"),
    [("nifty 50", "equity-stock-indices"), ("PERMITTED TO TRADE", "equity-stockIndex")],
)
async def test_index_constituents_endpoint(
    nse: NSE, router: respx.MockRouter, index: str, endpoint: str
) -> None:
    route = router.get(f"{API}/{endpoint}").respond(200, json={"data": []})
    await nse.equity_stocks_by_index(index)
    assert route.calls.last.request.url.params["index"] == index.upper()


def test_gainers_and_losers() -> None:
    data = {"data": [{"pChange": 2.0}, {"pChange": -1.0}, {"pChange": 5.0}, {"pChange": -3.0}]}
    assert [r["pChange"] for r in gainers(data)] == [5.0, 2.0]
    assert [r["pChange"] for r in losers(data, 1)] == [-3.0]
