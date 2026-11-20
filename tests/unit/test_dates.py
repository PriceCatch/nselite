from datetime import date

import pytest

from nselite._dates import parse_nse_date, split_range, weekdays


def test_split_range_chunks_inclusive() -> None:
    chunks = split_range(date(2024, 1, 1), date(2024, 1, 10), max_days=4)
    assert chunks == [
        (date(2024, 1, 1), date(2024, 1, 4)),
        (date(2024, 1, 5), date(2024, 1, 8)),
        (date(2024, 1, 9), date(2024, 1, 10)),
    ]


def test_split_range_single_day() -> None:
    assert split_range(date(2024, 1, 1), date(2024, 1, 1)) == [(date(2024, 1, 1), date(2024, 1, 1))]


def test_split_range_rejects_reversed() -> None:
    with pytest.raises(ValueError):
        split_range(date(2024, 1, 2), date(2024, 1, 1))


def test_weekdays_skips_weekend() -> None:
    days = list(weekdays(date(2026, 11, 20), date(2026, 11, 24)))  # Fri..Tue
    assert days == [date(2026, 11, 20), date(2026, 11, 23), date(2026, 11, 24)]


@pytest.mark.parametrize("text", ["19-Nov-2026", "19-Nov-2026 18:30", "19-Nov-2026 18:30:05"])
def test_parse_nse_date(text: str) -> None:
    assert parse_nse_date(text) == date(2026, 11, 19)
