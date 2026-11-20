from datetime import date
from typing import Any

import httpx
import pytest
import respx

from nselite import NSE

API = "https://www.nseindia.in/api"


def nse_day(d: date) -> str:
    return d.strftime("%d-%b-%Y").upper()


async def test_index_history_orders_across_chunks(nse: NSE, router: respx.MockRouter) -> None:
    """Chunks arrive newest first and may overlap; the result is oldest first, no duplicates."""

    def chunk(request: httpx.Request) -> httpx.Response:
        start = request.url.params["from"]
        days = (
            [date(2024, 12, 30), date(2024, 1, 1)]
            if start == "01-01-2024"
            else [date(2025, 3, 3), date(2024, 12, 30)]  # overlaps the first chunk's edge
        )
        return httpx.Response(200, json={"data": [{"EOD_TIMESTAMP": nse_day(d)} for d in days]})

    route = router.get(f"{API}/historicalOR/indicesHistory").mock(side_effect=chunk)
    rows = await nse.index_history("nifty 50", date(2024, 1, 1), date(2025, 3, 3))
    assert route.call_count == 2  # 428 days / 365-day chunks
    calls: list[Any] = list(route.calls)
    first = calls[0]
    assert first.request.url.params["indexType"] == "NIFTY 50"
    assert first.request.url.params["csv"] == "true"
    assert [r["date"] for r in rows] == [
        date(2024, 1, 1),
        date(2024, 12, 30),
        date(2025, 3, 3),
    ]


async def test_equity_history_one_request_per_year(nse: NSE, router: respx.MockRouter) -> None:
    route = router.get(f"{API}/NextApi/apiClient/GetQuoteApi").respond(
        200, json=[{"mtimestamp": "19-Nov-2026", "chClosingPrice": 1.0}]
    )
    rows = await nse.equity_history("tcs", date(2026, 1, 1), date(2026, 11, 19))
    calls: list[Any] = list(route.calls)
    assert len(calls) == 1  # 323 days fit one 365-day chunk
    assert calls[0].request.url.params["symbol"] == "TCS"
    assert calls[0].request.url.params["csv"] == "true"
    assert rows == [
        {"mtimestamp": "19-Nov-2026", "chClosingPrice": 1.0, "date": date(2026, 11, 19)}
    ]


async def test_vix_default_window_is_30_days(nse: NSE, router: respx.MockRouter) -> None:
    route = router.get(f"{API}/historicalOR/vixhistory").respond(200, json={"data": []})
    assert await nse.vix_history(to_date=date(2026, 11, 19)) == []
    params = route.calls.last.request.url.params
    assert (params["from"], params["to"]) == ("20-10-2026", "19-11-2026")


async def test_reversed_window_rejected(nse: NSE) -> None:
    with pytest.raises(ValueError):
        await nse.vix_history(date(2026, 2, 1), date(2026, 1, 1))


async def test_sampled_chunk_is_split_and_refetched(nse: NSE, router: respx.MockRouter) -> None:
    """A long chunk returning exactly NSE's 70-row sample is halved and refetched."""

    def parse(text: str) -> date:
        return date(int(text[6:]), int(text[3:5]), int(text[:2]))

    def cap(request: httpx.Request) -> httpx.Response:
        start, end = parse(request.url.params["from"]), parse(request.url.params["to"])
        n = 70 if (end - start).days > 120 else 1  # pretend NSE ignores csv=true over 120 days
        return httpx.Response(200, json={"data": [{"EOD_TIMESTAMP": nse_day(start)}] * n})

    route = router.get(f"{API}/historicalOR/vixhistory").mock(side_effect=cap)
    await nse.vix_history(date(2026, 1, 1), date(2026, 6, 30))
    assert route.call_count == 3  # 1 sampled 180-day chunk, then its two halves


async def test_short_window_of_70_rows_is_not_split(nse: NSE, router: respx.MockRouter) -> None:
    """70 rows over ~100 days is genuinely 70 sessions, not a sample."""
    route = router.get(f"{API}/historicalOR/vixhistory").respond(
        200, json={"data": [{"EOD_TIMESTAMP": "02-JAN-2026"}] * 70}
    )
    await nse.vix_history(date(2026, 1, 1), date(2026, 4, 10))
    assert route.call_count == 1
