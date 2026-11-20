"""Daily reports by NSE fileKey: list today's files, download the latest, backfill a range.

Run: uv run python examples/01_daily_reports.py
"""

import asyncio
from datetime import timedelta
from pathlib import Path

from nselite import NSE, ReportKey, weekdays

OUT = Path("data/reports")


async def main() -> None:
    async with NSE() as nse:
        # What NSE lists right now for the capital market segment ("CM", "SME" or "INDEX")
        listing = await nse.daily_reports("CM")
        for f in listing.current[:5]:
            print(f"{f.trading_date}  {f.key:<28} {f.name}")

        # Latest UDiFF bhavcopy, wherever NSE currently puts it
        path = await nse.download_report(ReportKey.CM_UDIFF_BHAVCOPY, OUT)
        print("latest bhavcopy:", path)

        # Backfill the last two weeks of 52-week highs/lows. Requests run concurrently,
        # throttled to 3 per second; holidays come back as None instead of raising.
        last = listing.latest(ReportKey.CM_52W_HIGH_LOW).trading_date
        days = list(weekdays(last - timedelta(days=13), last))
        got = await nse.download_reports(ReportKey.CM_52W_HIGH_LOW, days, OUT)
        for day, p in got.items():
            print(day, p.name if p else "no file (holiday)")

        # Just the URL, if you download with something else
        print(await nse.report_url(ReportKey.CM_BULK_DEAL))


asyncio.run(main())
