"""Time a 30-weekday bhavcopy backfill. Run: uv run python benchmarks/backfill.py"""

import asyncio
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

from nselite import NSE, ReportKey, weekdays


async def main() -> None:
    end = date.today() - timedelta(days=1)
    days = list(weekdays(end - timedelta(days=45), end))[-30:]
    with tempfile.TemporaryDirectory() as tmp:
        async with NSE() as nse:
            t0 = time.perf_counter()
            got = await nse.download_reports(ReportKey.CM_UDIFF_BHAVCOPY, days, Path(tmp))
            dt = time.perf_counter() - t0
    ok = sum(p is not None for p in got.values())
    print(f"{ok}/{len(days)} files in {dt:.1f}s ({len(days) / dt:.2f} files/s)")


if __name__ == "__main__":
    asyncio.run(main())
