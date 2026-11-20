from datetime import datetime
from pathlib import Path

import pytest
import respx

from nselite._http import WARM_URL
from nselite.compat import NSE

API = "https://www.nseindia.in/api"


@pytest.fixture
def old(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NSE:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return NSE(tmp_path / "dl")


def test_old_names_and_signatures(old: NSE, tmp_path: Path) -> None:
    with respx.mock(assert_all_called=False) as r:
        r.get(WARM_URL).respond(200)
        r.get(f"{API}/corporate-board-meetings").respond(200, json=[{"symbol": "TCS"}])
        r.get(f"{API}/holiday-master").respond(200, json={"CM": []})
        r.get(
            "https://nsearchives.nseindia.in/products/content/sec_bhavdata_full_19112026.csv"
        ).respond(200, content=b"d", headers={"content-type": "text/csv"})
        with old as nse:
            assert nse.boardMeetings(symbol="TCS") == [{"symbol": "TCS"}]
            assert nse.holidays(type=nse.HOLIDAY_TRADING) == {"CM": []}
            path = nse.deliveryBhavcopy(datetime(2026, 11, 19))
            assert path == tmp_path / "dl" / "sec_bhavdata_full_19112026.csv"


def test_missing_report_is_a_runtime_error(old: NSE) -> None:
    with respx.mock(assert_all_called=False) as r:
        r.get(WARM_URL).respond(200)
        r.get(url__startswith="https://nsearchives.nseindia.in/").respond(404)
        with old as nse, pytest.raises(RuntimeError):
            nse.indicesBhavcopy(datetime(2026, 11, 22))


def test_unported_methods_say_so(old: NSE) -> None:
    with pytest.raises(AttributeError, match="optionChain"):
        old.optionChain("NIFTY")  # pyright: ignore[reportUnknownMemberType]
    old.exit()


def test_static_helpers() -> None:
    assert NSE.gainers({"data": [{"pChange": 1}, {"pChange": -1}]}) == [{"pChange": 1}]


def test_lookup_keeps_old_shape(old: NSE) -> None:
    with respx.mock(assert_all_called=False) as r:
        r.get(WARM_URL).respond(200)
        r.get(f"{API}/smart-search/equity").respond(
            200, json=[{"symbol": "HDFCBANK", "companyName": "HDFC Bank Limited"}]
        )
        with old as nse:
            res = nse.lookup("hdfcbank")
            assert res["symbols"][0]["symbol_info"] == "HDFC Bank Limited"
            assert res["symbols"][0]["symbol"] == "HDFCBANK"
