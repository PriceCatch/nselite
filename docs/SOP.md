# nselite SOP

The living plan is the "NSE Lite Library — Plan & SOP" doc. This file is the in-repo copy of the
procedures and must match the code.

## SOP-1 Set up a development environment

1. Install [uv](https://docs.astral.sh/uv/) and clone the repo.
2. `uv sync --all-extras` (creates `.venv` on Python 3.13, the version pinned in `.python-version`).
3. `uv run pytest` must pass before you change anything.
4. Optional: set `NSE_HOST` / `NSE_ARCHIVES_HOST` if NSE moves domains again.
   Defaults: `https://www.nseindia.in` and `https://nsearchives.nseindia.in`.

## SOP-2 Add a daily report

1. Open <https://www.nseindia.in/all-reports> and find the report's `fileKey` in the response of
   `/api/daily-reports?key=CM` (or `INDEX`, `SME`) in the browser's Network tab.
   Derivatives (F&O) reports are out of scope.
2. Add a member to `ReportKey` in `src/nselite/reports.py`. The value is NSE's exact `fileKey`.
3. Add its `ReportSpec` to `SPECS`: segment, archive folder, and the file name as a strftime
   pattern (`None` if the file has no date, like `bulk.csv`).
4. Add a URL case to `tests/unit/test_reports.py::test_dated_url_needs_no_metadata_call`.
   `test_every_report_key_has_a_spec` fails until step 3 is done.
5. Run `uv run pytest tests/live -m live`. `test_patterns_match_listed_files` checks the pattern
   against NSE's live listing.
6. Add the report to the inventory table in the plan doc.

## SOP-3 Add an API endpoint

1. Find the endpoint in the Network tab of the NSE page that shows the data.
2. Add an `async` method to the matching domain mixin (`corporate.py`, `market.py`, ...), and
   add the mixin to `NSE`'s bases in `client.py`. `SyncNSE` picks it up automatically.
3. Call `self._http.get_json(f"{API_BASE}/<path>", params)`. Never create another client.
4. Return `dict` / `list` or a `TypedDict` / slotted dataclass. Let `NotAvailable` propagate;
   never return an empty result for a failure.
5. Add a respx-mocked unit test with a trimmed real response in `tests/fixtures/`, plus a live test.
6. Show the method in the matching `examples/` script and run it once.

## SOP-4 Test and CI

| When | What | Where |
| --- | --- | --- |
| Every push / PR | `ruff format --check`, `ruff check`, `pyright` (strict), unit tests on 3.12–3.15 | `.github/workflows/ci.yml` |
| Weekdays 20:00 IST | Live tests against NSE; failure opens an issue | `.github/workflows/live.yml` |
| Tag `v*` | Build and publish to PyPI via trusted publishing | `.github/workflows/release.yml` |

Live failures usually mean NSE renamed a file or moved a host, not that our code broke.

## SOP-5 Release

1. Update `CHANGELOG.md`; bump `version` in `pyproject.toml` and `__version__` in
   `src/nselite/__init__.py` (SemVer; below 1.0 a public rename is a minor bump).
2. `uv run python benchmarks/backfill.py`; put the numbers in the changelog entry.
3. `git tag vX.Y.Z && git push --tags`. The release workflow builds and publishes.
   One-time setup: add a trusted publisher on PyPI for this repo and a `pypi` environment on GitHub.
4. Bump nselite in downstream projects (eod2, build_ohlc_csvs, scanners) and run their smoke scripts.

## SOP-6 Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `SessionExpired` | NSE rejected cookies twice | `nse.forget_cookies()` or delete `~/.cache/nselite/cookies.json`; check the site opens in a browser |
| `NotAvailable` on a download | Not published yet (before ~18:30 IST), a holiday, or file renamed | Retry later; check the date; compare with `await nse.daily_reports(...)` |
| 404 on every archive URL | NSE moved the archives host | Set `NSE_ARCHIVES_HOST`; update `_hosts.py` default |
| `RateLimited` / IP blocked | `rps` set too high | Go back to the default `rps=3`; wait 10–15 minutes |
| Repeated `RemoteProtocolError` | NSE dropping idle HTTP/2 connections | Already retried; if it persists use `NSE(http2=False)` |

## SOP-7 Migrate a script from the fork

1. `uv add nselite` (or `pip install -e /path/to/nselite`) in the script's environment.
2. Change `from nse import NSE` to `from nselite.compat import NSE`. Nothing else changes:
   old method names, arguments, return values and `except RuntimeError` / `ConnectionError`
   blocks all keep working.
3. Run the script once. A method outside nselite's scope (derivatives, IPO lists...) raises
   `AttributeError` naming it.
4. `nse.lookup()` still returns the old `{"symbols": [...]}` shape through compat; the native
   `NSE.lookup()` returns NSE's new flat list.
5. Later, move hot paths to `nselite.NSE` (async) to download many dates concurrently.
