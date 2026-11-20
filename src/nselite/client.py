"""Public entry points: async :class:`NSE` and blocking :class:`SyncNSE`."""

import asyncio
import inspect
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import httpx

from ._http import Http
from .archives import ArchivesMixin
from .corporate import CorporateMixin
from .filings import FilingsMixin
from .history import HistoryMixin
from .market import MarketMixin


class NSE(ArchivesMixin, CorporateMixin, FilingsMixin, HistoryMixin, MarketMixin):
    """Async NSE client. Use one instance per process and share it across tasks.

    >>> async with NSE() as nse:
    ...     path = await nse.download_report(ReportKey.CM_UDIFF_BHAVCOPY, Path("data"))
    """

    def __init__(
        self,
        *,
        rps: float = 3.0,
        timeout: float = 15.0,
        retries: int = 3,
        http2: bool = True,
        cookie_path: Path | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = Http(
            rps=rps,
            timeout=timeout,
            retries=retries,
            http2=http2,
            cookie_path=cookie_path,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    def forget_cookies(self) -> None:
        """Delete saved cookies; the next call starts a fresh NSE session."""
        self._http.forget_cookies()


class SyncNSE:
    """Blocking wrapper with the same methods as :class:`NSE`, for existing scripts.

    >>> with SyncNSE() as nse:
    ...     path = nse.download_report(ReportKey.CM_UDIFF_BHAVCOPY, Path("data"))

    All calls run on one private event loop, so the HTTP/2 connection is reused between calls.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._runner = asyncio.Runner()
        self._nse = NSE(**kwargs)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._nse, name)
        if inspect.iscoroutinefunction(attr):

            def call(*args: Any, **kwargs: Any) -> Any:
                return self._runner.run(attr(*args, **kwargs))

            call.__doc__ = attr.__doc__
            return call
        return attr

    def close(self) -> None:
        self._runner.run(self._nse.aclose())
        self._runner.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
