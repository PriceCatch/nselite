"""Daily history for a stock, an index and India VIX, as lists and DataFrames.

Any range length works: nselite splits it into year-long requests and fetches them together.
Run: uv run python examples/03_history.py
"""

import asyncio
from datetime import date, timedelta

from nselite import NSE
from nselite.frames import to_pandas


async def main() -> None:
    today = date.today()
    async with NSE() as nse:
        tcs, nifty, vix = await asyncio.gather(
            nse.equity_history("TCS", today - timedelta(days=730), today),
            nse.index_history("NIFTY 50", today - timedelta(days=5 * 365), today),
            nse.vix_history(),  # no dates: the last 30 days
        )

    # Rows are oldest first and carry a parsed `date`; the other keys are NSE's own
    print(len(tcs), "TCS sessions; last close", tcs[-1]["chClosingPrice"], "on", tcs[-1]["date"])
    print(len(nifty), "NIFTY 50 sessions since", nifty[0]["date"])
    print("VIX now", vix[-1]["EOD_CLOSE_INDEX_VAL"])

    # Needs pip install 'nselite[pandas]' (or use to_polars with nselite[polars])
    df = to_pandas(tcs).set_index("date")
    ohlcv = df[["chOpeningPrice", "chTradeHighPrice", "chTradeLowPrice", "chClosingPrice"]]
    print(ohlcv.tail())

    # Other series: equity_history("SYMBOL", series="BE"); SME stocks use series="SM"


asyncio.run(main())
