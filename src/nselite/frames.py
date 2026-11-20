"""Optional DataFrame helpers. Needs ``pip install nselite[pandas]`` or ``nselite[polars]``.

pandas and polars are imported only when these functions are called, so ``import nselite``
stays light.
"""

import io
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl

type Engine = Literal["pandas", "polars"]


def _need(module: str) -> Any:
    try:
        return __import__(module)
    except ImportError as e:
        raise ImportError(f"{module} is not installed: pip install 'nselite[{module}]'") from e


def to_pandas(rows: Sequence[dict[str, Any]]) -> "pd.DataFrame":
    """List of records (any nselite JSON result) to a pandas DataFrame."""
    return _need("pandas").DataFrame.from_records(list(rows))


def to_polars(rows: Sequence[dict[str, Any]]) -> "pl.DataFrame":
    """List of records (any nselite JSON result) to a polars DataFrame."""
    return _need("polars").from_dicts(list(rows), infer_schema_length=None)


def _csv_bytes(path: Path) -> bytes:
    """Raw CSV bytes from ``.csv``, ``.zip`` (first member) or ``.gz``."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            return zf.read(zf.namelist()[0])
    if path.suffix.lower() == ".gz":
        import gzip

        return gzip.decompress(path.read_bytes())
    return path.read_bytes()


def read_report(path: Path, engine: Engine = "pandas", **kwargs: Any) -> Any:
    """Read a downloaded NSE CSV report (plain, zipped or gzipped) into a DataFrame.

    NSE pads many headers and values with spaces (``" SERIES"``, ``" EQ"``); both are
    stripped. Extra ``kwargs`` go to ``pandas.read_csv`` / ``polars.read_csv``.
    """
    data = _csv_bytes(Path(path))
    if engine == "pandas":
        pd = _need("pandas")
        df = pd.read_csv(io.BytesIO(data), skipinitialspace=True, **kwargs)
        df.columns = [str(c).strip() for c in df.columns]
        for col in df.select_dtypes(include=["object", "string"]).columns:
            df[col] = df[col].str.strip()
        return df
    pl = _need("polars")
    df = pl.read_csv(io.BytesIO(data), infer_schema_length=10_000, **kwargs)
    df = df.rename({c: c.strip() for c in df.columns})
    return df.with_columns(pl.col(pl.String).str.strip_chars())
