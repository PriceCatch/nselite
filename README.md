# nselite

Lean, async-first Python client for NSE India end-of-day reports and market data.
Python 3.13+, two runtime dependencies (`httpx[http2]`, `orjson`).

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

## What it covers

| Module | Methods |
| --- | --- |
| reports | `daily_reports`, `download_report`, `download_reports` (17 `ReportKey`s) |
| archives | `equity_bhavcopy`, `delivery_bhavcopy`, `indices_bhavcopy`, `priceband_report`, `pr_bhavcopy`, `cm_mii_security_report` |
| corporate | `actions`, `announcements`, `board_meetings`, `event_calendar`, `annual_reports`, `circulars`, `download_document` |
| filings | `financial_results`, `results_comparison`, `integrated_filing_results`, `financial_results_xbrl`, `download_xbrl`, `fetch_xbrl_filings` |
| market | `status`, `lookup`, `holidays`, `equity_stocks_by_index`, `volume_gainers`, `traded_stocks`, `gainers`, `losers` |

Derivatives are out of scope.

## Migrating from NseIndiaApi

Change one import; old method names and error handling keep working:

```python
from nselite.compat import NSE  # was: from nse import NSE
```

See [docs/SOP.md](docs/SOP.md) for setup, adding reports, testing and releases.

Licensed GPL-3.0-or-later (parts derive from NseIndiaApi by Benny Thadikaran).
