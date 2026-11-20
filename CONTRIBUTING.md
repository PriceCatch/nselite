# Contributing to nselite

Bug reports and pull requests are welcome. NSE changes its site often, so a failing live test or a
renamed report is the most useful thing to report.

## Set up

1. Install [uv](https://docs.astral.sh/uv/) and clone the repo.
2. `uv sync --all-extras` creates `.venv` with the dev tools and the pandas/polars extras.
3. `uv run pytest` must pass before you change anything.
4. If NSE moves domains, set `NSE_HOST` / `NSE_ARCHIVES_HOST`.
   Defaults: `https://www.nseindia.in` and `https://nsearchives.nseindia.in`.

nselite supports Python 3.12+. Don't use syntax newer than 3.12; ruff and pyright target 3.12 and
will flag it.

## Add a daily report

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

## Add an API endpoint

1. Find the endpoint in the Network tab of the NSE page that shows the data.
2. Add an `async` method to the matching domain mixin (`corporate.py`, `market.py`, ...), and
   add the mixin to `NSE`'s bases in `client.py`. `SyncNSE` picks it up automatically.
3. Call `self._http.get_json(f"{API_BASE}/<path>", params)`. Never create another client.
4. Return `dict` / `list` or a `TypedDict` / slotted dataclass. Let `NotAvailable` propagate;
   never return an empty result for a failure.
5. Add a respx-mocked unit test with a trimmed real response in `tests/fixtures/`, plus a live test.
6. Show the method in the matching `examples/` script and run it once.

## Checks

Run these before opening a pull request. CI runs the same on every push.

```bash
uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest
```

| When | What | Where |
| --- | --- | --- |
| Every push / PR | Format, lint, `pyright` (strict), unit tests on 3.12–3.15 | `.github/workflows/ci.yml` |
| Weekdays 20:00 IST | Live tests against NSE; failure opens an issue | `.github/workflows/live.yml` |
| Tag `v*` | Build and publish to PyPI via trusted publishing | `.github/workflows/release.yml` |

A live failure usually means NSE renamed a file or moved a host, not that the code broke.

## Release (maintainers)

1. Update `CHANGELOG.md`; bump `version` in `pyproject.toml` and `__version__` in
   `src/nselite/__init__.py` (SemVer; below 1.0 a public rename is a minor bump).
2. `uv run python benchmarks/backfill.py`; put the numbers in the changelog entry.
3. Push to `main`, wait for CI, then `git tag -a vX.Y.Z -m "nselite X.Y.Z" && git push origin vX.Y.Z`.
   The release workflow publishes to PyPI.
4. PyPI rejects project-URL labels longer than 32 characters; `uv build && uvx twine check dist/*`
   catches most metadata problems before tagging.
