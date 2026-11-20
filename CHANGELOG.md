# Changelog

All notable changes to nselite. Versions follow SemVer; below 1.0 a public rename is a minor bump.

## 0.2.0 — 2026-11-20

Phase 3 of the plan.

### Added
- History: `equity_history`, `index_history`, `vix_history`. Sends `csv=true` (without it NSE
  returns only a 70-row sample) and fetches 365-day chunks concurrently. Rows are returned
  oldest first, de-duplicated, with a parsed `date` key. The `csv=true` fix is Benny
  Thadikaran's (NseIndiaApi #32, v5.1.1).
- `nselite.frames`: `read_report` (plain, zipped or gzipped CSV, padding stripped) and
  `to_pandas` / `to_polars`. pandas and polars load only when used.
- Compat names `fetch_equity_historical_data`, `fetch_historical_index_data`,
  `fetch_historical_vix_data`.
- Credits to Benny Thadikaran (NseIndiaApi) in README and package metadata.
- `examples/`: eight runnable scripts covering every public function; README examples section.

### Fixed (vs the NseIndiaApi 4.0.1 fork)
- The fork predates upstream's `csv=true` fix, so its index/VIX history got NSE's 70-row
  sample: 351 of 1,240 NIFTY 50 rows for 5 years, 70 of ~250 VIX rows for 1 year. nselite
  returns all rows, oldest first.
- Equity history date key is now `mtimestamp` (NSE renamed it from `mTIMESTAMP`).

### Benchmarks (2026-11-20, single runs)
- 30-day CM bhavcopy backfill: 28 files + 2 holidays in 9.1 s (3.3 files/s, at the rate limit).
- TCS 2-year, NIFTY 50 5-year and VIX 1-year history together: 508 + 1,240 + 249 rows in
  2.8 s (8 requests).
- Live tests pass from GitHub Actions runners (NSE does not block them).

## 0.1.0 — 2026-11-20

First release: Phases 1 and 2 of the plan.

### Added
- Async `NSE` client and blocking `SyncNSE`, sharing one throttled (3 req/s), retrying HTTP/2
  session with cookies persisted to `~/.cache/nselite/cookies.json`.
- Reports by NSE `fileKey` (17 capital-market and index reports): latest file via
  `/api/daily-reports`, or any date via the file-name pattern; `download_reports` backfills
  many dates concurrently, with holidays returned as `None`.
- Archives: CM bhavcopy (UDiFF and pre-July-2024), delivery, index close, price bands, PR zip,
  MII security file.
- Corporate: actions, announcements, board meetings, event calendar, annual reports, circulars,
  document download.
- Filings: financial results, Integrated Filings and XBRL, with year chunks, result pages and
  XBRL downloads fetched concurrently.
- Market: status, lookup, holidays, index constituents, volume gainers, stocks traded,
  gainers/losers.
- `nselite.compat.NSE`: drop-in for the NseIndiaApi fork (old names, sync, same exception types).

### Changed (vs the NseIndiaApi fork)
- Archive host defaults to `nsearchives.nseindia.in` (the fork still used `.com`).
- `lookup()` uses NSE's new `/api/smart-search/equity`; the old autocomplete endpoint returns 404.

### Removed
- Derivatives (F&O bhavcopy, option chain, expiries, lots), IPO/ETF/SGB lists, debt.

### Benchmarks
- eod2 replay (metadata, holidays, actions, circulars, 4 bhavcopies): 3.2 s vs 4.4 s with the fork
  (single run, 2026-11-20).
