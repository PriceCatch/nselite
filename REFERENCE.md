# nselite reference

Every option nselite accepts: report keys, parameter values, index names, series codes, client
settings and errors. For worked code, see [`examples/`](examples).

## Scope: equities first

nselite covers NSE's **capital market (equities, including SME)**, **indices** and **India VIX**:
end-of-day reports and archives, price history, corporate actions and filings, and live market
lists (status, index constituents, movers).

**Not available:** futures and options (F&O) data of any kind, including option chains, open
interest, max pain, F&O bhavcopies and participant-wise OI. Currency, commodity and
interest-rate derivatives are out of scope too. A per-symbol live quote isn't included. Use a
broker API for live prices.

## Daily reports: `ReportKey`

Use with `download_report`, `download_reports` and `report_url`. Each value is NSE's own `fileKey`
from its [All Reports](https://www.nseindia.in/all-reports) page.

```python
await nse.download_report(ReportKey.CM_PE_RATIO, Path("data"))  # latest file
await nse.download_report(ReportKey.CM_PE_RATIO, Path("data"), date(2026, 11, 19))  # one date
await nse.download_reports(ReportKey.CM_PE_RATIO, days, Path("data"))  # many dates, concurrently
```

| `ReportKey` | NSE `fileKey` | Segment | Report | File for 19 Nov 2026 |
| --- | --- | --- | --- | --- |
| `CM_UDIFF_BHAVCOPY` | `CM-UDIFF-BHAVCOPY-CSV` | CM | CM-UDiFF Common Bhavcopy Final (zip) | `BhavCopy_NSE_CM_0_0_0_20261119_F_0000.csv.zip` |
| `CM_BHAVDATA_FULL` | `CM-BHAVDATA-FULL` | CM | Full Bhavcopy and Security Deliverable data | `sec_bhavdata_full_19112026.csv` |
| `CM_BHAVCOPY_PR` | `CM-BHAVCOPY-PR-ZIP` | CM | Bhavcopy (PR) (zip) | `PR191126.zip` |
| `CM_SECURITY` | `NSE-CM-SECURITY-CSV` | CM | CM - MII - Security File (NSE listed securities) | `NSE_CM_security_19112026.csv.gz` |
| `CM_PRICEBAND_COMPLETE` | `CM-PRICEBAND-COMPLETE-LIST` | CM | CM - Price Band complete list | `sec_list_19112026.csv` |
| `CM_52W_HIGH_LOW` | `CM-52 WEEK-HIGH_LOW` | CM | 52 Week High Low Report | `CM_52_wk_High_low_19112026.csv` |
| `CM_SURVEILLANCE` | `CM-SURVEILLANCE-INDICATOR-NEW-CSV` | CM | Surveillance Indicator | `REG1_IND191126.csv` |
| `CM_SHORT_SELLING` | `CM-SHORT-SELLING` | CM | Short Selling | `shortselling_19112026.csv` |
| `CM_BULK_DEAL` | `CM-BULK-DEAL` | CM | Bulk Deals | latest only |
| `CM_BLOCK_DEAL` | `CM-BLOCK-DEAL` | CM | Block Deals | latest only |
| `CM_PE_RATIO` | `CM-PE-RATIO-CSV` | CM | PE Ratio | `PE_191126.csv` |
| `CM_VOLATILITY` | `CM-VOLATILITY` | CM | Daily Volatility | `CMVOLT_19112026.CSV` |
| `CM_PRICE_BAND_NEXT_DAY` | `CM-PRICE-BAND-NEXT-DAY` | CM | Price Band changes from next trade date | `eq_band_changes_19112026.csv` |
| `CM_MARGIN_TRADING` | `CM-MARGIN-TRADING-DISC` | CM | Margin Trading Disclosure | `mrg_trading_191126.zip` |
| `CM_VAR_END_DAY` | `CM-VAR-END-DAY` | CM | VaR End of Day File | `C_VAR1_19112026_6.DAT` |
| `SME_BHAVCOPY` | `SME-BHAVCOPY-CSV` | SME | SME - Bhavcopy file | `sme19112026.csv` |
| `INDEX_SNAPSHOT` | `INDEX-SNAPSHOT` | INDEX | Daily Snapshot (all indices' closing values) | `ind_close_all_19112026.csv` |

- **latest only:** NSE keeps one undated file, so pass no date.
- The date in a file name is not always the trading date. The next-day price band file, for
  example, is named for the day it takes effect. `day` always means the date in the file name.
- `await nse.daily_reports("CM")` (or `"SME"`, `"INDEX"`) lists everything NSE publishes today,
  including reports that have no `ReportKey` yet. Each `ReportFile` has a `url` you can download
  with `download_document`.

## Archive downloads

Each takes `(day, folder)`, returns the path of the unzipped file, and raises `NotAvailable` on a
holiday or before NSE publishes (around 18:30 IST).

| Method | File |
| --- | --- |
| `equity_bhavcopy` | UDiFF bhavcopy (old-format bhavcopy for dates before 8 Jul 2024) |
| `delivery_bhavcopy` | `sec_bhavdata_full`: prices plus delivery quantity and percentage |
| `indices_bhavcopy` | Closing values of all indices |
| `priceband_report` | Circuit limits per symbol |
| `pr_bhavcopy` | PR zip: 52-week highs/lows, top movers, ETFs and more |
| `cm_mii_security_report` | Security master (~11 MB) |

## Parameter values

| Method | Parameter | Values (default first) |
| --- | --- | --- |
| `daily_reports` | `segment` | `"CM"`, `"SME"`, `"INDEX"` |
| `equity_history` | `series` | `"EQ"`, `"BE"`, `"BL"`, `"SM"`, `"ST"`, `"GB"`, `"GS"`, `"AE"`, `"AF"`, `"IL"`, `"RL"`, `"W3"` ([series codes](#series-codes)) |
| `equity_history`, `index_history`, `vix_history` | `from_date`, `to_date` | `date`; both optional, default the last 30 days, any length |
| `holidays` | `type` | `"trading"`, `"clearing"` |
| `actions` | `segment` | `"equities"`, `"sme"`, `"debt"`, `"mf"` |
| `announcements` | `index` | `"equities"`, `"sme"`, `"debt"`, `"mf"`, `"invitsreits"` |
| `board_meetings`, `event_calendar`, `annual_reports` | `index` / `segment` | `"equities"`, `"sme"` |
| `financial_results` | `segment` | `"equities"`, `"sme"`, `"debt"`, `"mf"` |
| `financial_results`, `financial_results_xbrl`, `fetch_xbrl_filings` | `period` | `"quarterly"`, `"annual"`, `"half-yearly"` |
| `financial_results_xbrl`, `fetch_xbrl_filings` | `basis` | `"both"`, `"consolidated"`, `"standalone"` |
| `financial_results_xbrl`, `fetch_xbrl_filings` | `source` | `"both"`, `"results"` (old format), `"integrated"` (Integrated Filings, 2025 on) |
| `financial_results_xbrl`, `fetch_xbrl_filings` | `from_date`, `to_date` | pass both or neither |
| `integrated_filing_results` | `filing_type` | `"Integrated Filing- Financials"`, `"Integrated Filing- Governance"`, `None` (all) |
| `read_report` | `engine` | `"pandas"`, `"polars"` |

Symbols and index names are upper-cased for you, so `"tcs"` works.

## Index names

NSE spells each index two ways, and each endpoint accepts only one of them. A name in the wrong form
returns **no rows rather than an error**.

| Use | Pass | Example |
| --- | --- | --- |
| `index_history` | Full name: `index` | `"NIFTY FINANCIAL SERVICES"` |
| `equity_stocks_by_index` | Short name: `indexSymbol` | `"NIFTY FIN SERVICE"` |

`await nse.indices()` returns all ~140 indices with both names and a category. Common ones:

| Full name (`index_history`) | Short name (`equity_stocks_by_index`) |
| --- | --- |
| `NIFTY 50` | `NIFTY 50` |
| `NIFTY NEXT 50` | `NIFTY NEXT 50` |
| `NIFTY 100` / `NIFTY 200` / `NIFTY 500` | same |
| `NIFTY MIDCAP 100` / `NIFTY MIDCAP 150` | same |
| `NIFTY SMALLCAP 100` | `NIFTY SMLCAP 100` |
| `NIFTY SMALLCAP 250` | `NIFTY SMLCAP 250` |
| `NIFTY MIDSMALLCAP 400` | `NIFTY MIDSML 400` |
| `NIFTY MIDCAP SELECT` | `NIFTY MID SELECT` |
| `NIFTY TOTAL MARKET` | `NIFTY TOTAL MKT` |
| `NIFTY BANK` | `NIFTY BANK` |
| `NIFTY FINANCIAL SERVICES` | `NIFTY FIN SERVICE` |
| `NIFTY PRIVATE BANK` | `NIFTY PVT BANK` |
| `NIFTY IT`, `NIFTY AUTO`, `NIFTY FMCG`, `NIFTY METAL`, `NIFTY PHARMA`, `NIFTY REALTY` | same |

`equity_stocks_by_index("PERMITTED TO TRADE")` lists every stock permitted to trade. India VIX has
its own method, `vix_history`.

## Series codes

`series` in `equity_history` and the bhavcopies is NSE's trading series. The common ones:

| Code | Meaning |
| --- | --- |
| `EQ` | Normal equity (rolling settlement) |
| `BE` | Trade-for-trade: every trade settles by delivery, no intraday squaring off |
| `BL` | Block deal window |
| `SM` | SME platform |
| `ST` | SME trade-for-trade |
| `GB` | Sovereign Gold Bonds |
| `GS` | Government securities |

The rest are NSE's own codes, so see the series column in a bhavcopy for what trades today.

## Client settings

```python
NSE(rps=3.0, timeout=15.0, retries=3, http2=True, cookie_path=None)
```

| Setting | Meaning |
| --- | --- |
| `rps` | Requests per second across all calls. Keep the default; NSE blocks heavy clients. |
| `timeout` | Seconds per request |
| `retries` | Retries with backoff on timeouts, dropped connections, 429 and 5xx |
| `http2` | Set `False` if a network drops HTTP/2 connections |
| `cookie_path` | Where the NSE session cookie is saved; default `~/.cache/nselite/cookies.json` |

`SyncNSE` takes the same settings. The environment variables `NSE_HOST` (default
`https://www.nseindia.in`) and `NSE_ARCHIVES_HOST` (default `https://nsearchives.nseindia.in`)
override NSE's hosts if it moves domains again.

## Errors

| Exception | Raised when | Also a |
| --- | --- | --- |
| `NSEError` | Base class of all nselite errors | `Exception` |
| `NotAvailable` | File or data doesn't exist (404, holiday, not published yet) | `RuntimeError` |
| `nselite.errors.NetworkError` | Timeouts or bad HTTP status after all retries | `ConnectionError` |
| `RateLimited` | NSE kept answering 429 | `NetworkError` |
| `SessionExpired` | NSE rejected the session even after fresh cookies | `NetworkError` |

## NseIndiaApi compatibility constants

`nselite.compat.NSE` keeps the fork's class constants: `SEGMENT_EQUITY`, `SEGMENT_SME`,
`SEGMENT_MF`, `SEGMENT_DEBT`, `HOLIDAY_TRADING`, `HOLIDAY_CLEARING`, `UDIFF_SWITCH_DATE`,
`INTEGRATED_FINANCIALS`, `INTEGRATED_GOVERNANCE` and `__version__` (`"4.0.1"`, the fork version
it mirrors).
