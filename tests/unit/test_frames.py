import gzip
import io
import zipfile
from pathlib import Path

import pytest

from nselite.frames import read_report, to_pandas, to_polars

# Shape of sec_bhavdata_full: NSE pads headers and values with a leading space.
CSV = b"SYMBOL, SERIES, CLOSE_PRICE\nTCS, EQ, 3500.5\nINFY, BE, 1500\n"


@pytest.fixture(params=["csv", "zip", "gz"])
def report(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    kind: str = request.param
    if kind == "csv":
        path = tmp_path / "r.csv"
        path.write_bytes(CSV)
    elif kind == "zip":
        path = tmp_path / "r.csv.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("r.csv", CSV)
        path.write_bytes(buf.getvalue())
    else:
        path = tmp_path / "r.csv.gz"
        path.write_bytes(gzip.compress(CSV))
    return path


def test_pandas_strips_padding(report: Path) -> None:
    df = read_report(report)
    assert list(df.columns) == ["SYMBOL", "SERIES", "CLOSE_PRICE"]
    assert df["SERIES"].tolist() == ["EQ", "BE"]
    assert df["CLOSE_PRICE"].tolist() == [3500.5, 1500.0]


def test_polars_strips_padding(report: Path) -> None:
    df = read_report(report, engine="polars")
    assert df.columns == ["SYMBOL", "SERIES", "CLOSE_PRICE"]
    assert df["SERIES"].to_list() == ["EQ", "BE"]


def test_records_to_frames() -> None:
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": None}]
    assert to_pandas(rows).shape == (2, 2)
    assert to_polars(rows).shape == (2, 2)
