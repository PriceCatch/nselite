"""Bhavcopies and other archive files for one day, read into a DataFrame.

Needs pandas for the last step: pip install 'nselite[pandas]'
Run: uv run python examples/02_archives_and_frames.py
"""

import asyncio
from pathlib import Path

from nselite import NSE, NotAvailable, ReportKey
from nselite.frames import read_report

OUT = Path("data/archives")


async def main() -> None:
    async with NSE() as nse:
        # Last trading day NSE has published
        day = (await nse.daily_reports()).latest(ReportKey.CM_UDIFF_BHAVCOPY).trading_date
        print("trading day:", day)

        # Each returns the path of the (unzipped) file
        bhav = await nse.equity_bhavcopy(day, OUT)  # UDiFF CSV (old format before 2024-07-08)
        delivery = await nse.delivery_bhavcopy(day, OUT)  # sec_bhavdata_full: delivery qty and %
        await nse.indices_bhavcopy(day, OUT)  # closing values of all indices
        await nse.priceband_report(day, OUT)  # circuit limits per symbol
        await nse.pr_bhavcopy(day, OUT)  # PR zip: 52w highs/lows, top gainers, ETFs...
        await nse.cm_mii_security_report(day, OUT)  # security master, ~11 MB
        print(bhav.name, delivery.name)

        # A holiday or a not-yet-published day raises NotAvailable
        try:
            await nse.equity_bhavcopy(day.replace(month=1, day=26), OUT)  # Republic Day
        except NotAvailable as e:
            print("not available:", e)

    # NSE pads headers and values with spaces; read_report strips them (csv, zip or gz).
    # Extra arguments go to pandas.read_csv: here "-" (no delivery data) becomes NaN.
    df = read_report(delivery, na_values="-")
    eq = df[df["SERIES"] == "EQ"]
    print(eq.nlargest(5, "DELIV_PER")[["SYMBOL", "CLOSE_PRICE", "DELIV_PER"]])


asyncio.run(main())
