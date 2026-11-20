"""Shared HTTP layer: one AsyncClient per NSE instance, persisted cookies, throttle and retries.

Every request in nselite goes through :class:`Http`. Never create another client.
"""

import asyncio
import random
import time
from pathlib import Path
from typing import Any

import httpx
import orjson

from ._hosts import NSE_HOST
from .errors import NetworkError, NotAvailable, RateLimited, SessionExpired

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/118.0"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Referer": f"{NSE_HOST}/get-quotes/equity?symbol=HDFCBANK",
}
# Page that reliably sets the session cookies NSE's API expects.
WARM_URL = f"{NSE_HOST}/option-chain"
CHUNK = 1 << 20  # 1 MiB
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
RETRY_EXC = (httpx.TimeoutException, httpx.RemoteProtocolError, httpx.ConnectError)

type Params = dict[str, str | int] | None


def default_cookie_path() -> Path:
    """``$XDG_CACHE_HOME/nselite/cookies.json`` (``~/.cache`` when unset)."""
    import os

    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "nselite" / "cookies.json"


class TokenBucket:
    """Async token bucket: at most ``rate`` requests per second, bursts up to ``burst``."""

    def __init__(self, rate: float, burst: int | None = None) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        self.rate = rate
        self.capacity = float(burst if burst is not None else max(1, int(rate)))
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
                self._last = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                await asyncio.sleep((1 - self._tokens) / self.rate)


class Http:
    """Throttled, retrying HTTP/2 client with NSE session cookies.

    :param rps: requests per second across all concurrent tasks (NSE blocks aggressive clients).
    :param timeout: per-request timeout in seconds.
    :param retries: extra attempts on timeouts, dropped connections, 429 and 5xx.
    :param http2: use HTTP/2 multiplexing (falls back to HTTP/1.1 if the server refuses).
    :param cookie_path: where session cookies persist between runs; ``None`` for the default.
    :param cookie_ttl: seconds before saved cookies are re-warmed proactively.
    """

    def __init__(
        self,
        *,
        rps: float = 3.0,
        timeout: float = 15.0,
        retries: int = 3,
        http2: bool = True,
        cookie_path: Path | None = None,
        cookie_ttl: float = 3600.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.retries = retries
        self.cookie_path = cookie_path or default_cookie_path()
        self.cookie_ttl = cookie_ttl
        self._bucket = TokenBucket(rps)
        self._client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            http2=http2,
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )
        self._warm_lock = asyncio.Lock()
        self._warmed = False

    # ---------------------------------------------------------------- lifecycle

    async def aclose(self) -> None:
        await self._client.aclose()

    # ---------------------------------------------------------------- cookies

    def _load_cookies(self) -> bool:
        try:
            saved = orjson.loads(self.cookie_path.read_bytes())
        except (FileNotFoundError, orjson.JSONDecodeError):
            return False
        if time.time() - saved.get("saved_at", 0) > self.cookie_ttl or not saved.get("cookies"):
            return False
        self._client.cookies.update(saved["cookies"])
        return True

    def _save_cookies(self) -> None:
        cookies = {c.name: c.value for c in self._client.cookies.jar if c.value is not None}
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cookie_path.with_suffix(".tmp")
        tmp.write_bytes(orjson.dumps({"saved_at": time.time(), "cookies": cookies}))
        tmp.replace(self.cookie_path)

    async def _warm(self, *, force: bool = False) -> None:
        """Make sure the client holds valid NSE cookies. Safe to call from many tasks at once."""
        async with self._warm_lock:
            if self._warmed and not force:
                return
            if not force and self._load_cookies():
                self._warmed = True
                return
            self._client.cookies.clear()
            await self._bucket.acquire()
            try:
                r = await self._client.get(WARM_URL)
            except RETRY_EXC as e:
                raise NetworkError(f"could not reach {WARM_URL}: {e!r}") from e
            if r.status_code >= 400:
                raise SessionExpired(f"could not warm NSE session: {r.status_code} on {WARM_URL}")
            self._save_cookies()
            self._warmed = True

    def forget_cookies(self) -> None:
        """Delete the saved cookies; the next request warms a fresh session."""
        self.cookie_path.unlink(missing_ok=True)
        self._client.cookies.clear()
        self._warmed = False

    # ---------------------------------------------------------------- requests

    @staticmethod
    async def _backoff(attempt: int) -> None:
        await asyncio.sleep(0.5 * 2**attempt + random.uniform(0, 0.25))

    async def _request(self, url: str, params: Params, *, stream: bool) -> httpx.Response:
        """Send a GET with throttle, retries and one cookie refresh. Raises on any non-2xx."""
        await self._warm()
        attempt = 0
        refreshed = False
        while True:
            await self._bucket.acquire()
            req = self._client.build_request("GET", url, params=params)
            try:
                r = await self._client.send(req, stream=stream)
            except RETRY_EXC as e:
                if attempt >= self.retries:
                    raise NetworkError(
                        f"GET {url} failed after {attempt + 1} attempts: {e!r}"
                    ) from e
                await self._backoff(attempt)
                attempt += 1
                continue

            status = r.status_code
            if 200 <= status < 300:
                return r
            if stream:
                await r.aclose()

            if status in (401, 403):
                if refreshed:
                    raise SessionExpired(f"GET {url}: {status} even after refreshing cookies")
                refreshed = True
                await self._warm(force=True)
                continue
            if status == 404:
                raise NotAvailable(f"GET {url}: 404 Not Found")
            if status in RETRY_STATUS and attempt < self.retries:
                await self._backoff(attempt)
                attempt += 1
                continue
            if status == 429:
                raise RateLimited(f"GET {url}: still 429 after {attempt + 1} attempts")
            raise NetworkError(f"GET {url}: {status} {r.reason_phrase}")

    async def get(self, url: str, params: Params = None) -> httpx.Response:
        """GET ``url`` and return the fully read response."""
        return await self._request(url, params, stream=False)

    async def get_json(self, url: str, params: Params = None) -> Any:
        """GET ``url`` and parse JSON with orjson. Raises :class:`NotAvailable` on empty/HTML."""
        r = await self.get(url, params)
        if not r.content or "text/html" in r.headers.get("content-type", ""):
            raise NotAvailable(f"GET {url}: no JSON in response")
        return orjson.loads(r.content)

    async def download(self, url: str, dest: Path, *, overwrite: bool = False) -> Path:
        """Stream ``url`` to ``dest`` in 1 MiB chunks; skip if ``dest`` already exists.

        Writes to ``dest.part`` first and renames on success, so a crash never leaves a
        truncated file under the final name. Local file I/O stays synchronous on purpose:
        a stat or a 1 MiB write is far cheaper than a thread hop, and the network dominates.
        """
        if dest.exists() and not overwrite:  # noqa: ASYNC240
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        r = await self._request(url, None, stream=True)
        try:
            if "text/html" in r.headers.get("content-type", ""):
                raise NotAvailable(f"GET {url}: HTML page instead of a file (not published yet?)")
            with part.open("wb") as f:
                async for chunk in r.aiter_bytes(CHUNK):
                    f.write(chunk)
        except BaseException:
            part.unlink(missing_ok=True)
            raise
        finally:
            await r.aclose()
        part.replace(dest)
        return dest
