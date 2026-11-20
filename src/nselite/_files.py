"""Archive unpacking. Runs in a worker thread so large files never block the event loop."""

import asyncio
import gzip
import shutil
from datetime import date, datetime
from pathlib import Path
from zipfile import ZipFile


def as_date(d: date) -> date:
    """Accept ``date`` or ``datetime`` (the fork took datetimes) and return a plain ``date``."""
    return d.date() if isinstance(d, datetime) else d


def unpacked_name(archive_name: str) -> str:
    """``x.csv.zip`` -> ``x.csv``; ``x.csv.gz`` -> ``x.csv``."""
    return archive_name.removesuffix(".zip").removesuffix(".gz")


def _unpack(archive: Path, members: list[str] | None) -> Path:
    folder = archive.parent
    if archive.suffix.lower() == ".zip":
        with ZipFile(archive) as zf:
            if members:
                zf.extractall(folder, members=members)
                out = folder / members[-1]
            else:
                out = Path(zf.extract(zf.namelist()[0], folder))
    elif archive.suffix.lower() == ".gz":
        out = folder / archive.stem
        with gzip.open(archive, "rb") as src, out.open("wb") as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
    else:
        raise ValueError(f"not a .zip or .gz file: {archive.name}")
    archive.unlink()
    return out


async def unpack(archive: Path, members: list[str] | None = None) -> Path:
    """Extract ``archive`` next to itself, delete it, and return the extracted file.

    For zips, extracts ``members`` (returning the last) or else the first member.
    """
    return await asyncio.to_thread(_unpack, archive, members)
