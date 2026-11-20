"""Corporate actions, announcements, board meetings, events, circulars and annual reports.

Run: uv run python examples/05_corporate.py
"""

import asyncio
from datetime import date, timedelta
from pathlib import Path

from nselite import NSE


async def main() -> None:
    today = date.today()
    month_ago = today - timedelta(days=30)
    async with NSE() as nse:
        # Splits, bonuses, dividends... for all stocks, or pass symbol="TCS"
        for a in (await nse.actions(from_date=month_ago, to_date=today))[:5]:
            print("action:", a["exDate"], a["symbol"], a["subject"])

        ann = await nse.announcements(symbol="TCS", from_date=month_ago, to_date=today)
        for a in ann[:3]:
            print("announcement:", a["an_dt"], a["desc"])

        for m in await nse.board_meetings(from_date=today, to_date=today + timedelta(days=7)):
            print("board meeting:", m["bm_date"], m["bm_symbol"], m["bm_purpose"])

        for e in (await nse.event_calendar())[:5]:
            print("event:", e["date"], e["symbol"], e["purpose"])

        circ = await nse.circulars(from_date=today - timedelta(days=7), to_date=today)
        for c in circ["data"][:3]:
            print("circular:", c["cirDisplayDate"], c["sub"])

        # Annual report PDFs/zips; download_document saves (and unzips) any NSE attachment
        reports = await nse.annual_reports("TCS")
        latest = reports["data"][0]
        print("annual report", latest["fromYr"], "-", latest["toYr"])
        path = await nse.download_document(latest["fileName"], Path("data/annual_reports"))
        print("saved:", path)


asyncio.run(main())
