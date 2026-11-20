# nselite

Lean, async-first Python client for NSE India end-of-day reports and market data.
Python 3.12+, two runtime dependencies (`httpx[http2]`, `orjson`).

```python
import asyncio
from datetime import date
from pathlib import Path
from nselite import NSE, ReportKey


async def main():
    async with NSE() as nse:
        # Latest file, located via NSE's own report metadata
        await nse.download_report(ReportKey.CM_UDIFF_BHAVCOPY, Path("data"))
        # Backfill: concurrent, throttled to 3 req/s, holidays come back as None
        days = [date(2026, 11, d) for d in range(16, 20)]
        await nse.download_reports(ReportKey.CM_52W_HIGH_LOW, days, Path("data"))


asyncio.run(main())
```

Blocking scripts can use `SyncNSE`, which has the same methods without `await`.

More in a few lines:

```python
from datetime import date
from nselite import SyncNSE
from nselite.frames import to_pandas

with SyncNSE() as nse:
    nifty = nse.index_history("NIFTY 50", date(2021, 1, 1), date(2026, 1, 1))  # all 5 years
    df = to_pandas(nse.equity_history("TCS")).set_index("date")  # last 30 days
    holidays = nse.holidays()["CM"]
    movers = nse.equity_stocks_by_index("NIFTY 50")
```

## Examples

Runnable scripts for every function, in [`examples/`](https://github.com/PriceCatch/nselite/tree/main/examples):

| Script | Shows |
| --- | --- |
| [01_daily_reports.py](https://github.com/PriceCatch/nselite/blob/main/examples/01_daily_reports.py) | List NSE's daily files, download the latest, backfill a range (holidays → `None`) |
| [02_archives_and_frames.py](https://github.com/PriceCatch/nselite/blob/main/examples/02_archives_and_frames.py) | All bhavcopies for a day, `NotAvailable` on holidays, `read_report` into pandas |
| [03_history.py](https://github.com/PriceCatch/nselite/blob/main/examples/03_history.py) | Stock, index and VIX history over any range, as a DataFrame |
| [04_market.py](https://github.com/PriceCatch/nselite/blob/main/examples/04_market.py) | Market status, holidays, symbol search, index constituents, gainers/losers, volume spikes |
| [05_corporate.py](https://github.com/PriceCatch/nselite/blob/main/examples/05_corporate.py) | Corporate actions, announcements, board meetings, event calendar, circulars, annual reports |
| [06_filings.py](https://github.com/PriceCatch/nselite/blob/main/examples/06_filings.py) | Financial results, results comparison, Integrated Filings, XBRL download |
| [07_sync.py](https://github.com/PriceCatch/nselite/blob/main/examples/07_sync.py) | `SyncNSE` for plain scripts and notebooks |
| [08_compat.py](https://github.com/PriceCatch/nselite/blob/main/examples/08_compat.py) | Drop-in replacement for NseIndiaApi scripts |

Run one with `uv run python examples/03_history.py`; files go under `./data`.

## What it covers

| Module | Methods |
| --- | --- |
| reports | `daily_reports`, `download_report`, `download_reports` (17 `ReportKey`s) |
| archives | `equity_bhavcopy`, `delivery_bhavcopy`, `indices_bhavcopy`, `priceband_report`, `pr_bhavcopy`, `cm_mii_security_report` |
| corporate | `actions`, `announcements`, `board_meetings`, `event_calendar`, `annual_reports`, `circulars`, `download_document` |
| filings | `financial_results`, `results_comparison`, `integrated_filing_results`, `financial_results_xbrl`, `download_xbrl`, `fetch_xbrl_filings` |
| market | `status`, `lookup`, `holidays`, `equity_stocks_by_index`, `volume_gainers`, `traded_stocks`, `gainers`, `losers` |
| history | `equity_history`, `index_history`, `vix_history` (complete, oldest first) |
| frames | `read_report`, `to_pandas`, `to_polars` (install `nselite[pandas]` or `nselite[polars]`) |

Derivatives are out of scope.

## Migrating from NseIndiaApi

Change one import; old method names and error handling keep working:

```python
from nselite.compat import NSE  # was: from nse import NSE
```

See [docs/SOP.md](docs/SOP.md) for setup, adding reports, testing and releases.

## Credits

nselite is built on the work of **[Benny Thadikaran](https://github.com/BennyThadikaran)**, author of
[NseIndiaApi](https://github.com/BennyThadikaran/NseIndiaApi). Its session handling, endpoint
knowledge and corporate-filing code are the foundation nselite was trimmed down and rebuilt from.
Thank you, Benny.

Report URL patterns and date-chunking limits were cross-checked against
[nselib](https://github.com/RuchiTanmay/nselib) by Ruchi Tanmay and Amlan Mishra.

## License

GPL-3.0-or-later, the same license as NseIndiaApi, from which parts of this code derive.
