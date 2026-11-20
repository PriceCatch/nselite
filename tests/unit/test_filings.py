from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
import respx

from nselite import NSE
from nselite.filings import (
    normalise_integrated_filing,
    normalise_result_filing,
    select_xbrl_records,
    xbrl_filename,
)

API = "https://www.nseindia.in/api"
XML = b'<?xml version="1.0"?><xbrl/>'


def result_row(**kw: str) -> dict[str, str]:
    row = {
        "symbol": "LINDEINDIA",
        "xbrl": "https://nsearchives.nseindia.in/corporate/xbrl/A.xml",
        "fromDate": "01-Oct-2024",
        "toDate": "31-Dec-2024",
        "broadCastDate": "16-Jan-2025 20:20:21",
        "consolidated": "Consolidated",
        "cumulative": "Non-cumulative",
    }
    return {**row, **kw}


def integrated_row(**kw: str) -> dict[str, str]:
    row = {
        "symbol": "LINDEINDIA",
        "xbrl": "https://nsearchives.nseindia.in/corporate/xbrl/B.xml",
        "qe_Date": "31-Mar-2025",
        "broadcast_Date": "20-May-2025 18:01:02",
        "consolidated": "Standalone",
        "type_Sub": "Original",
        "seq_Id": "7",
    }
    return {**row, **kw}


def test_normalise_result_filing() -> None:
    rec = normalise_result_filing(result_row())
    assert rec is not None
    assert (rec["basis"], rec["period_from"], rec["period_to"]) == (
        "C",
        date(2024, 10, 1),
        date(2024, 12, 31),
    )
    assert rec["broadcast_dt"] == datetime(2025, 1, 16, 20, 20, 21)
    assert normalise_result_filing(result_row(xbrl="-")) is None


def test_normalise_integrated_filing_quarter_start_and_revision_stamp() -> None:
    rec = normalise_integrated_filing(integrated_row())
    assert rec is not None
    assert (rec["period_from"], rec["basis"], rec["source"]) == (
        date(2025, 1, 1),
        "S",
        "integrated",
    )
    rev = normalise_integrated_filing(
        integrated_row(type_Sub="Revision", revised_Date="02-Jun-2025 10:00:00")
    )
    assert rev is not None and rev["broadcast_dt"] == datetime(2025, 6, 2, 10, 0)
    assert normalise_integrated_filing(integrated_row(type="Integrated Filing- Governance")) is None


def test_select_keeps_latest_revision_and_filters_basis() -> None:
    a = normalise_result_filing(result_row())
    b = normalise_result_filing(
        result_row(xbrl="https://x/A2.xml", broadCastDate="20-Jan-2025 09:00:00")
    )
    s = normalise_result_filing(result_row(xbrl="https://x/S.xml", consolidated="Standalone"))
    assert a and b and s
    out = select_xbrl_records([a, b, s, a], "consolidated", latest_only=True)
    assert [r["xbrl"] for r in out] == ["https://x/A2.xml"]
    assert out[0]["revision_count"] == 2


def test_xbrl_filename() -> None:
    rec = normalise_result_filing(result_row())
    assert rec is not None
    assert xbrl_filename(rec) == "LINDEINDIA_20241231_C_N_20250116202021.xml"


async def test_fetch_xbrl_filings_merges_sources_and_records_errors(
    nse: NSE, router: respx.MockRouter, tmp_path: Path
) -> None:
    router.get(f"{API}/corporates-financial-results").respond(200, json=[result_row()])
    router.get(f"{API}/integrated-filing-results").respond(
        200, json={"data": [integrated_row()], "totalCount": 1}
    )
    router.get("https://nsearchives.nseindia.in/corporate/xbrl/A.xml").respond(
        200, content=XML, headers={"content-type": "application/xml"}
    )
    router.get("https://nsearchives.nseindia.in/corporate/xbrl/B.xml").respond(
        200, html="<html>oops</html>"
    )
    recs = await nse.fetch_xbrl_filings("lindeindia", tmp_path)
    assert [r["source"] for r in recs] == ["results", "integrated"]
    ok, bad = recs
    assert ok["local_path"] == tmp_path / "LINDEINDIA" / xbrl_filename(ok)
    assert ok["local_path"].read_bytes() == XML
    assert bad["local_path"] is None and "HTML" in bad["error"]


async def test_long_range_is_chunked_by_year(nse: NSE, router: respx.MockRouter) -> None:
    route = router.get(f"{API}/corporates-financial-results").respond(200, json=[])
    await nse.financial_results_xbrl("TCS", date(2023, 1, 1), date(2025, 6, 30), source="results")
    calls: list[Any] = list(route.calls)
    froms = sorted(c.request.url.params["from_date"] for c in calls)
    assert froms == ["01-01-2023", "01-01-2024", "31-12-2024"]


async def test_integrated_pages_fetched(nse: NSE, router: respx.MockRouter) -> None:
    def page(request: httpx.Request) -> httpx.Response:
        p = int(request.url.params["page"])
        return httpx.Response(200, json={"data": [{"p": p}] * 2, "totalCount": 5})

    router.get(f"{API}/integrated-filing-results").mock(side_effect=page)
    rows = await nse.integrated_filing_results("TCS", page_size=2)
    assert sorted({r["p"] for r in rows}) == [1, 2, 3]
    assert len(rows) == 6
