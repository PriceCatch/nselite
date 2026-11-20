# Changelog

All notable changes to nselite. Versions follow SemVer; below 1.0 a public rename is a minor bump.

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
