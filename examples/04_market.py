"""Market status, holidays, symbol search, index constituents and today's movers.

Run: uv run python examples/04_market.py
"""

import asyncio

from nselite import NSE
from nselite.market import gainers, losers


async def main() -> None:
    async with NSE() as nse:
        for m in await nse.status():
            if "market" in m:  # one row is the NIFTY 50 in USD, not a market
                print(f"{m['market']:<22} {m['marketStatus']}")

        holidays = await nse.holidays()  # or holidays("clearing")
        print("trading holidays:", [h["tradingDate"] for h in holidays["CM"]][:5], "...")

        for hit in (await nse.lookup("tata motors"))[:3]:
            print("lookup:", hit["symbol"], "-", hit["companyName"])

        # Constituents with live prices; row 0 is the index itself
        nifty = await nse.equity_stocks_by_index("NIFTY 50")
        stocks = {"data": nifty["data"][1:]}
        print("top gainers:", [(r["symbol"], r["pChange"]) for r in gainers(stocks, 3)])
        print("top losers: ", [(r["symbol"], r["pChange"]) for r in losers(stocks, 3)])

        vol = await nse.volume_gainers()
        print("volume spikes:", [(r["symbol"], r["week1volChange"]) for r in vol["data"][:3]])

        traded = await nse.traded_stocks()  # every stock traded today, plus breadth
        print(len(traded["data"]), "stocks traded;", traded["count"])


asyncio.run(main())
