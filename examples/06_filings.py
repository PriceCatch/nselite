"""Financial results and their XBRL files, including Integrated Filings.

Run: uv run python examples/06_filings.py
"""

import asyncio
from datetime import date, timedelta
from pathlib import Path

from nselite import NSE


async def main() -> None:
    async with NSE() as nse:
        # Result filings in the old format (quarterly by default; period="annual" also works).
        # Most companies switched to Integrated Filings in 2025, so these stop around then.
        results = await nse.financial_results(symbol="TCS")
        r = results[0]
        print("latest old-format result:", r["toDate"], r["consolidated"])

        # NSE's own last-5-quarters comparison table
        cmp = await nse.results_comparison("TCS")
        for q in cmp["resCmpData"][:5]:
            print("quarter to", q["re_to_dt"], "net profit", q["re_net_profit"])

        # Integrated Filing (Financials), the format NSE moved to in 2025
        integrated = await nse.integrated_filing_results(symbol="TCS")
        print(len(integrated), "integrated filings; latest quarter", integrated[0]["qe_Date"])

        # XBRL records from both sources, newest per period and basis
        today = date.today()
        two_years = today - timedelta(days=730)  # dates are optional, but pass both or neither
        xbrl = await nse.financial_results_xbrl("TCS", from_date=two_years, to_date=today)
        print(len(xbrl), "XBRL records")
        print("saved:", await nse.download_xbrl(xbrl[0], Path("data/xbrl")))

        # Or find and download them all in one call
        files = await nse.fetch_xbrl_filings("INFY", Path("data/xbrl"), two_years, today)
        print(len(files), "INFY XBRL files")


asyncio.run(main())
