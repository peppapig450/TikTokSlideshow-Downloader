from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Self

import aiohttp
import pytest

from tiktok_downloader import Config
from tiktok_downloader.downloader import DownloadManager


class DummyContent:
    def __init__(self, data: bytes) -> None:
        self.data = data

    async def iter_chunked(self, chunk_size: int) -> AsyncIterator[bytes]:
        yield self.data


class DummyResponse:
    def __init__(self, data: bytes, ct: str = "image/jpeg") -> None:
        self.data = data
        self.headers = {"Content-Length": str(len(data)), "Content-Type": ct}
        self.content = DummyContent(data)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None


@pytest.mark.asyncio
async def test_retry_and_checksum(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = Config(None)
    cfg.set("max_retries", 2)
    attempts: list[int] = []

    class FailingResponse:
        async def __aenter__(self) -> DummyResponse:
            raise aiohttp.ClientError("boom")

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    class FakeSession:
        def __init__(self, *args: object, **kwargs: object) -> None: ...

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def get(self, url: str) -> DummyResponse | FailingResponse:
            attempts.append(1)
            if len(attempts) < 3:  # noqa: PLR2004
                return FailingResponse()
            return DummyResponse(b"abc")

    monkeypatch.setattr("tiktok_downloader.downloader.aiohttp.ClientSession", FakeSession)

    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("tiktok_downloader.downloader.asyncio.sleep", fake_sleep)

    manager = DownloadManager(cfg, progress=False)
    dest = tmp_path / "file.bin"
    final, checksum = await manager.download("http://example/image", dest)

    assert final.exists()
    assert final.suffix == ".jpg"
    assert checksum == hashlib.sha256(b"abc").hexdigest()
    assert len(attempts) == 3  # noqa: PLR2004
    assert sleeps == [1.0, 2.0]


@pytest.mark.asyncio
async def test_concurrency_limit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    active = 0
    max_active = 0

    class SlowContent(DummyContent):
        async def iter_chunked(self, chunk_size: int) -> AsyncIterator[bytes]:
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.05)
            active -= 1
            yield b"x"

    class SlowResponse(DummyResponse):
        def __init__(self) -> None:
            super().__init__(b"x")
            self.content = SlowContent(b"x")

    class SlowSession:
        def __init__(self, *args: object, **kwargs: object) -> None: ...

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def get(self, url: str) -> SlowResponse:
            return SlowResponse()

    monkeypatch.setattr("tiktok_downloader.downloader.aiohttp.ClientSession", SlowSession)

    manager = DownloadManager(concurrency=2, progress=False)
    urls = ["http://a", "http://b", "http://c"]
    results = await manager.download_all(urls, tmp_path)

    assert len(results) == 3  # noqa: PLR2004
    assert max_active <= 2  # noqa: PLR2004
