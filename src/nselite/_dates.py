"""Date helpers shared by all modules."""

from collections.abc import Iterator
from datetime import date, datetime, timedelta

NSE_DATE_FORMATS = ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y")


def split_range(start: date, end: date, max_days: int = 365) -> list[tuple[date, date]]:
    """Split ``start``..``end`` (inclusive) into consecutive chunks of at most ``max_days``.

    NSE's historical endpoints reject long ranges, so callers fetch each chunk concurrently.
    """
    if start > end:
        raise ValueError(f"start {start} is after end {end}")
    if max_days < 1:
        raise ValueError("max_days must be at least 1")

    chunks: list[tuple[date, date]] = []
    step = timedelta(days=max_days - 1)
    cur = start
    while cur <= end:
        chunk_end = min(cur + step, end)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return chunks


def weekdays(start: date, end: date) -> Iterator[date]:
    """Yield Monday-Friday dates in ``start``..``end``. Holidays are not excluded."""
    cur = start
    one = timedelta(days=1)
    while cur <= end:
        if cur.weekday() < 5:
            yield cur
        cur += one


def parse_nse_date(text: str) -> date:
    """Parse NSE's ``19-Nov-2026`` style dates (with or without a time part)."""
    text = text.strip()
    for fmt in NSE_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised NSE date: {text!r}")
