from __future__ import annotations

import io
import tempfile
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO, cast

import yt_dlp
from yt_dlp.utils import DownloadError

from ..config import Config, PartialConfigDict
from ..cookies import CookieManager, _write_netscape
from ..logger import get_logger
from .base import BaseExtractor

logger = get_logger(__name__)


@dataclass(slots=True)
class VideoResult:
    """Result of a video extraction."""

    video_id: str
    title: str
    author: str
    duration: int
    video_url: str
    thumbnail_url: str
    description: str
    tags: list[str]
    filepath: Path | None = None


class VideoExtractor(BaseExtractor[VideoResult]):
    """Extractor for TikTok videos using ``yt-dlp``."""

    def __init__(
        self,
        config: Config | PartialConfigDict | None = None,
        *,
        cookie_profile: str | None = None,
        user_agents: list[str] | None = None,
        quality: str | None = None,
    ) -> None:
        super().__init__(
            config,
            cookie_profile=cookie_profile,
            user_agents=user_agents,
        )
        self.quality = quality or "best"
        self.cookie_file: Path | None = None
        if cookie_profile:
            cookies = CookieManager().load(cookie_profile)
            with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
                _write_netscape(cookies, cast(TextIO, tmp))
                tmp.flush()
                self.cookie_file = Path(tmp.name)

    # ------------------------------------------------------------------
    def extract(self, url: str, *, download: bool = False) -> VideoResult:
        """Extract video metadata from ``url`` and optionally download."""
        opts: dict[str, Any] = {
            "format": self.quality,
            "outtmpl": str(self.config.download_path / "%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
        }
        if self.cookie_file:
            opts["cookies"] = str(self.cookie_file)

        try:
            info_raw = yt_dlp.YoutubeDL(opts).extract_info(url, download=download)
        except DownloadError as exc:  # pragma: no cover - network path
            logger.error("yt-dlp failed: %s", exc)
            raise RuntimeError(f"Failed to extract video from {url}") from exc
        except Exception as exc:  # pragma: no cover - unexpected path
            logger.exception("Unexpected error extracting video")
            raise RuntimeError(f"Unexpected error extracting video from {url}") from exc

        if not isinstance(info_raw, dict):
            logger.error("yt-dlp returned no information for %s", url)
            raise RuntimeError(f"Failed to extract video from {url}")

        info = info_raw

        filepath: Path | None = None
        if download:
            downloads = info.get("requested_downloads")
            if downloads and isinstance(downloads, list):
                first = downloads[0]
                path_str = first.get("filepath")
                if isinstance(path_str, str):
                    filepath = Path(path_str)

        return VideoResult(
            video_id=str(info.get("id", "")),
            title=str(info.get("title", "")),
            author=str(info.get("uploader", "")),
            duration=int(info.get("duration", 0)),
            video_url=str(info.get("url", "")),
            thumbnail_url=str(info.get("thumbnail", "")),
            description=str(info.get("description", "")),
            tags=list(info.get("tags", []) or []),
            filepath=filepath,
        )

    # ------------------------------------------------------------------
    def list_formats(self, url: str) -> list[str]:
        """Return available format strings for ``url``."""
        opts: dict[str, Any] = {
            "listformats": True,
            "skip_download": True,
            "quiet": True,
        }
        if self.cookie_file:
            opts["cookies"] = str(self.cookie_file)

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            yt_dlp.YoutubeDL(opts).extract_info(url, download=False)
        lines = [line.strip() for line in buffer.getvalue().splitlines() if line.strip()]
        return lines
