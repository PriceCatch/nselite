import gzip
import io
import zipfile
from datetime import date, datetime
from pathlib import Path

import respx

from nselite import NSE

A = "https://nsearchives.nseindia.in"


def zipped(name: str, data: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, data)
    return buf.getvalue()


async def test_equity_bhavcopy_unzips_and_skips_rerun(
    nse: NSE, router: respx.MockRouter, tmp_path: Path
) -> None:
    name = "BhavCopy_NSE_CM_0_0_0_20261119_F_0000.csv"
    route = router.get(f"{A}/content/cm/{name}.zip").respond(
        200, content=zipped(name, b"SYMBOL\nTCS\n"), headers={"content-type": "application/zip"}
    )
    path = await nse.equity_bhavcopy(datetime(2026, 11, 19, 18, 0), tmp_path)  # datetime OK
    assert path == tmp_path / name
    assert path.read_bytes() == b"SYMBOL\nTCS\n"
    assert not (tmp_path / f"{name}.zip").exists()
    await nse.equity_bhavcopy(date(2026, 11, 19), tmp_path)
    assert route.call_count == 1


async def test_equity_bhavcopy_before_udiff_uses_old_archive(
    nse: NSE, router: respx.MockRouter, tmp_path: Path
) -> None:
    route = router.get(f"{A}/content/historical/EQUITIES/2023/JAN/cm02JAN2023bhav.csv.zip").respond(
        200,
        content=zipped("cm02JAN2023bhav.csv", b"x"),
        headers={"content-type": "application/zip"},
    )
    path = await nse.equity_bhavcopy(date(2023, 1, 2), tmp_path)
    assert route.called
    assert path.name == "cm02JAN2023bhav.csv"


async def test_mii_security_file_is_gunzipped(
    nse: NSE, router: respx.MockRouter, tmp_path: Path
) -> None:
    router.get(f"{A}/content/cm/NSE_CM_security_19112026.csv.gz").respond(
        200, content=gzip.compress(b"a|b\n"), headers={"content-type": "application/gzip"}
    )
    path = await nse.cm_mii_security_report(date(2026, 11, 19), tmp_path)
    assert path == tmp_path / "NSE_CM_security_19112026.csv"
    assert path.read_bytes() == b"a|b\n"


async def test_plain_csv_reports(nse: NSE, router: respx.MockRouter, tmp_path: Path) -> None:
    csv = {"content-type": "text/csv"}
    router.get(f"{A}/products/content/sec_bhavdata_full_19112026.csv").respond(
        200, content=b"d", headers=csv
    )
    router.get(f"{A}/content/indices/ind_close_all_19112026.csv").respond(
        200, content=b"i", headers=csv
    )
    router.get(f"{A}/content/equities/sec_list_19112026.csv").respond(
        200, content=b"p", headers=csv
    )
    router.get(f"{A}/archives/equities/bhavcopy/pr/PR191126.zip").respond(
        200, content=b"z", headers=csv
    )
    d = date(2026, 11, 19)
    assert (await nse.delivery_bhavcopy(d, tmp_path)).read_bytes() == b"d"
    assert (await nse.indices_bhavcopy(d, tmp_path)).read_bytes() == b"i"
    assert (await nse.priceband_report(d, tmp_path)).read_bytes() == b"p"
    assert (await nse.pr_bhavcopy(d, tmp_path)).name == "PR191126.zip"  # stays zipped
