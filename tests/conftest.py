from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import respx

from nselite import NSE
from nselite._http import WARM_URL, Http

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    async def instant(attempt: int) -> None:
        return None

    monkeypatch.setattr(Http, "_backoff", staticmethod(instant))


@pytest.fixture
def router() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as r:
        r.get(WARM_URL).respond(200, headers={"set-cookie": "nsit=abc; Path=/"})
        yield r


@pytest.fixture
async def nse(tmp_path: Path, router: respx.MockRouter) -> AsyncIterator[NSE]:
    async with NSE(rps=1000, cookie_path=tmp_path / "cookies.json", http2=False) as client:
        yield client
