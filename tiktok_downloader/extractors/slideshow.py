from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from playwright.async_api import async_playwright

from ..config import Config, PartialConfigDict
from ..cookies import CookieManager, JSONCookie
from ..logger import get_logger
from ..url_parser import extract_video_id
from .base import BaseExtractor

logger = get_logger(__name__)


@dataclass(slots=True)
class SlideshowResult:
    """Result of a slideshow extraction."""

    urls: list[str]
    video_id: str
    count: int
    audio_only: bool


class SlideshowExtractor(BaseExtractor[SlideshowResult]):
    """Extractor for TikTok slideshows."""

    def __init__(
        self,
        config: Config | PartialConfigDict | None = None,
        *,
        cookie_profile: str | None = None,
        cookies: list[JSONCookie] | None = None,
        user_agents: list[str] | None = None,
    ) -> None:
        self.cookie_profile = cookie_profile if cookies is None else None
        self.cookie_data = cookies
        super().__init__(
            config,
            cookie_profile=self.cookie_profile,
            cookies=cookies,
            user_agents=user_agents,
        )

    async def _add_cookies(self, context: Any) -> None:
        cookies: list[JSONCookie] | None
        if self.cookie_data is not None:
            cookies = self.cookie_data
        elif self.cookie_profile:
            try:
                cookies = CookieManager().load(self.cookie_profile)
            except Exception as exc:  # pragma: no cover - error path
                logger.error("Failed to load cookies: %s", exc)
                return
        else:
            return
        formatted = [
            {
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": c.get("domain", ""),
                "path": c.get("path", "/"),
                "expires": int(c.get("expirationDate", c.get("expires", 0))),
            }
            for c in cookies
        ]
        await context.add_cookies(formatted)

    async def _collect_images(self, page: Any) -> list[str]:
        elements = await page.query_selector_all(
            ".css-brxox6-ImgPhotoSlide.e10jea832",
        )
        urls: list[str] = []
        for el in elements:
            src = await el.get_attribute("src")
            if src:
                urls.append(src)
        deduped: list[str] = []
        seen: set[str] = set()
        for url in urls:
            if url not in seen:
                deduped.append(url)
                seen.add(url)
        return deduped

    async def extract(self, url: str) -> SlideshowResult:  # type: ignore[override]
        """Extract slideshow images from ``url``."""
        video_id = extract_video_id(url)
        timeout = self.config.get("browser_timeout")
        headless = self.config.get("headless")
        max_retries = self.config.get("max_retries")
        user_agent = str(self.session.headers["User-Agent"])

        for attempt in range(max_retries + 1):
            try:
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(headless=headless)
                    context = await browser.new_context(user_agent=user_agent)
                    await self._add_cookies(context)
                    page = await context.new_page()
                    await page.goto(url, wait_until="networkidle", timeout=timeout)

                    images = await self._collect_images(page)
                    while True:
                        previous = len(images)
                        await page.mouse.wheel(0, 10_000)
                        await page.wait_for_timeout(500)
                        images = await self._collect_images(page)
                        if len(images) == previous:
                            break

                    await browser.close()

                audio_only = len(images) == 0
                return SlideshowResult(
                    urls=images,
                    video_id=video_id,
                    count=len(images),
                    audio_only=audio_only,
                )
            except Exception as exc:  # pragma: no cover - network path
                logger.warning("Extraction attempt %d failed: %s", attempt + 1, exc)
        return SlideshowResult([], video_id, 0, True)
