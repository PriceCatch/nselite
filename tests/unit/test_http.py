import time
from pathlib import Path

import httpx
import orjson
import pytest
import respx

from nselite import NotAvailable, SessionExpired
from nselite._http import Http, TokenBucket

URL = "https://www.nseindia.in/api/marketStatus"
FILE = "https://nsearchives.nseindia.in/content/x.csv"


def make(tmp_path: Path, **kw: object) -> Http:
    return Http(rps=1000, cookie_path=tmp_path / "c.json", http2=False, **kw)  # type: ignore[arg-type]


async def test_token_bucket_limits_rate() -> None:
    bucket = TokenBucket(rate=20, burst=1)
    t0 = time.monotonic()
    for _ in range(5):
        await bucket.acquire()
    assert time.monotonic() - t0 >= 0.19  # 4 waits of 50 ms after the first token


async def test_warms_once_and_persists_cookies(tmp_path: Path, router: respx.MockRouter) -> None:
    router.get(URL).respond(200, json={"ok": 1})
    http = make(tmp_path)
    assert await http.get_json(URL) == {"ok": 1}
    assert await http.get_json(URL) == {"ok": 1}
    assert router.routes[0].call_count == 1  # warm route
    saved = orjson.loads((tmp_path / "c.json").read_bytes())
    assert saved["cookies"] == {"nsit": "abc"}
    await http.aclose()


async def test_reuses_saved_cookies_without_warming(
    tmp_path: Path, router: respx.MockRouter
) -> None:
    (tmp_path / "c.json").write_bytes(
        orjson.dumps({"saved_at": time.time(), "cookies": {"nsit": "old"}})
    )
    route = router.get(URL).respond(200, json=[])
    http = make(tmp_path)
    await http.get_json(URL)
    assert router.routes[0].call_count == 0
    assert route.calls.last.request.headers["cookie"] == "nsit=old"
    await http.aclose()


async def test_refreshes_cookies_once_on_401(tmp_path: Path, router: respx.MockRouter) -> None:
    router.get(URL).mock(side_effect=[httpx.Response(401), httpx.Response(200, json={"ok": 1})])
    http = make(tmp_path)
    assert await http.get_json(URL) == {"ok": 1}
    assert router.routes[0].call_count == 2  # initial warm + forced refresh
    await http.aclose()


async def test_raises_session_expired_after_second_403(
    tmp_path: Path, router: respx.MockRouter
) -> None:
    router.get(URL).respond(403)
    http = make(tmp_path)
    with pytest.raises(SessionExpired):
        await http.get(URL)
    await http.aclose()


async def test_retries_5xx_then_succeeds(tmp_path: Path, router: respx.MockRouter) -> None:
    route = router.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(502), httpx.Response(200, json=1)]
    )
    http = make(tmp_path)
    assert await http.get_json(URL) == 1
    assert route.call_count == 3
    await http.aclose()


async def test_retries_dropped_connection(tmp_path: Path, router: respx.MockRouter) -> None:
    route = router.get(URL).mock(
        side_effect=[httpx.RemoteProtocolError("closed"), httpx.Response(200, json=1)]
    )
    http = make(tmp_path)
    assert await http.get_json(URL) == 1
    assert route.call_count == 2
    await http.aclose()


async def test_404_is_not_available(tmp_path: Path, router: respx.MockRouter) -> None:
    router.get(URL).respond(404)
    http = make(tmp_path)
    with pytest.raises(NotAvailable):
        await http.get(URL)
    await http.aclose()


async def test_html_instead_of_json_is_not_available(
    tmp_path: Path, router: respx.MockRouter
) -> None:
    router.get(URL).respond(200, html="<html>maintenance</html>")
    http = make(tmp_path)
    with pytest.raises(NotAvailable):
        await http.get_json(URL)
    await http.aclose()


async def test_download_streams_and_skips_existing(
    tmp_path: Path, router: respx.MockRouter
) -> None:
    route = router.get(FILE).respond(
        200, content=b"a,b\n1,2\n", headers={"content-type": "text/csv"}
    )
    http = make(tmp_path)
    dest = tmp_path / "out" / "x.csv"
    assert await http.download(FILE, dest) == dest
    assert dest.read_bytes() == b"a,b\n1,2\n"
    await http.download(FILE, dest)
    assert route.call_count == 1
    await http.aclose()


async def test_download_html_leaves_no_file(tmp_path: Path, router: respx.MockRouter) -> None:
    router.get(FILE).respond(200, html="<html>not yet</html>")
    http = make(tmp_path)
    dest = tmp_path / "x.csv"
    with pytest.raises(NotAvailable):
        await http.download(FILE, dest)
    assert not dest.exists()
    assert not (tmp_path / "x.csv.part").exists()
    await http.aclose()
