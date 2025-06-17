from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import aiohttp
from tqdm import tqdm

from .config import Config
from .logger import get_logger
from .utils import build_dest_path, guess_extension, unique_path

logger = get_logger(__name__)


class DownloadManager:
    """Asynchronous manager for HTTP downloads."""

    def __init__(
        self,
        config: Config | None = None,
        *,
        concurrency: int = 3,
        progress: bool = True,
        progress_callback: Callable[[Path, int, int], None] | None = None,
    ) -> None:
        self.config = config if isinstance(config, Config) else Config(config)
        self.concurrency = concurrency
        self.progress = progress
        self.progress_callback = progress_callback

    async def download(self, url: str, dest_path: Path) -> tuple[Path, str]:
        """Download ``url`` to ``dest_path`` with retries.

        Returns the final destination path and SHA256 checksum.
        """
        max_retries = self.config.get("max_retries")
        backoff = 1.0
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                async with (
                    aiohttp.ClientSession(
                        headers={"User-Agent": self.config.get("user_agent")}
                    ) as session,
                    session.get(url) as response,
                ):
                    response.raise_for_status()
                    ext = guess_extension(url, response.headers.get("Content-Type"))
                    final = unique_path(dest_path.with_suffix(ext))
                    checksum = await self._save_response(response, final)
                    return final, checksum
            except Exception as exc:  # pragma: no cover - network error path
                last_exc = exc
                logger.warning("Attempt %d for %s failed: %s", attempt + 1, url, exc)
                if attempt >= max_retries:
                    break
                await asyncio.sleep(backoff)
                backoff *= 2
        raise RuntimeError(f"Failed to download {url}") from last_exc

    async def _save_response(self, response: aiohttp.ClientResponse, dest: Path) -> str:
        chunk_size = self.config.get("chunk_size")
        total = int(response.headers.get("content-length", 0))
        checksum = hashlib.sha256()
        progress: tqdm | None = None
        downloaded = 0
        if self.progress and not self.progress_callback:
            size_desc = tqdm.format_sizeof(total) if total else "unknown"
            progress = tqdm(
                total=total or None,
                unit="B",
                unit_scale=True,
                desc=f"{dest.name} ({size_desc})",
                leave=False,
            )
        with dest.open("wb") as file:
            async for chunk in response.content.iter_chunked(chunk_size):
                if not chunk:
                    continue
                file.write(chunk)
                checksum.update(chunk)
                downloaded += len(chunk)
                if progress is not None:
                    progress.update(len(chunk))
                if self.progress_callback:
                    self.progress_callback(dest, downloaded, total)
        if progress is not None:
            progress.close()
        return checksum.hexdigest()

    async def download_all(
        self, urls: Sequence[str], dest_dir: Path | str
    ) -> list[tuple[str, Path, str]]:
        directory = Path(dest_dir)
        semaphore = asyncio.Semaphore(self.concurrency)
        results: list[tuple[str, Path, str]] = []

        async def worker(url: str) -> None:
            dest = build_dest_path(directory, Path(url).stem)
            async with semaphore:
                final, checksum = await self.download(url, dest)
            results.append((url, final, checksum))

        await asyncio.gather(*(worker(u) for u in urls))
        return results


def run_download(
    urls: Sequence[str], dest_dir: Path | str, **kwargs: Any
) -> list[tuple[str, Path, str]]:
    """Synchronously download ``urls`` to ``dest_dir`` using :class:`DownloadManager`."""
    return asyncio.run(DownloadManager(**kwargs).download_all(urls, dest_dir))
