"""Profile scraping utilities."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import async_playwright

from .config import Config, PartialConfigDict
from .cookies import CookieManager, JSONCookie
from .extractors.base import BaseExtractor
from .logger import get_logger
from .url_parser import parse_tiktok_url

logger = get_logger(__name__)


class ProfileScraper(BaseExtractor[list[str]]):
    """Scrape all post URLs from a TikTok profile."""

    def __init__(
        self,
        username: str,
        config: Config | PartialConfigDict | None = None,
        *,
        cookie_profile: str | None = None,
        cookies: list[JSONCookie] | None = None,
        user_agents: list[str] | None = None,
    ) -> None:
        self.username = username.lstrip("@")
        self.cookie_profile = cookie_profile if cookies is None else None
        self.cookie_data = cookies
        super().__init__(
            config,
            cookie_profile=cookie_profile,
            cookies=cookies,
            user_agents=user_agents,
        )

    def extract(self, url: str) -> list[str]:  # pragma: no cover - unused
        raise NotImplementedError

    # ------------------------------------------------------------------
    def _find_links(self, html: str) -> Iterable[str]:
        pattern = re.compile(r'href=["\'](.*?)["\']')
        for href in pattern.findall(html):
            link = "https:" + href if href.startswith("//") else href
            yield link

    def fetch_urls(self) -> list[str]:
        """Return a list of resolved post URLs from the profile."""
        url = f"https://www.tiktok.com/@{self.username}"
        response = self.get(url)
        html = response.text
        found: list[str] = []
        for raw in self._find_links(html):
            link = urljoin(url, raw) if raw.startswith("/") else raw
            try:
                info = parse_tiktok_url(link)
            except Exception:
                continue
            found.append(info.resolved_url)

        unique: list[str] = []
        seen: set[str] = set()
        for u in found:
            if u not in seen:
                unique.append(u)
                seen.add(u)
        return unique

    # ------------------------------------------------------------------
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

    async def _collect_links(self, page: Any, base_url: str) -> list[str]:
        elements = await page.query_selector_all("a")
        links: list[str] = []
        for el in elements:
            href = await el.get_attribute("href")
            if href:
                link = urljoin(base_url, href) if href.startswith("/") else href
                try:
                    info = parse_tiktok_url(link)
                except Exception:
                    continue
                links.append(info.resolved_url)
        return links

    async def fetch_urls_browser(self) -> list[str]:
        """Use a headless browser to gather post URLs."""
        url = f"https://www.tiktok.com/@{self.username}"
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

                    links = await self._collect_links(page, url)
                    while True:
                        previous = len(links)
                        await page.mouse.wheel(0, 10_000)
                        await page.wait_for_timeout(500)
                        links = await self._collect_links(page, url)
                        if len(links) == previous:
                            break

                    await browser.close()

                unique: list[str] = []
                seen: set[str] = set()
                for link in links:
                    if link not in seen:
                        unique.append(link)
                        seen.add(link)
                return unique
            except Exception as exc:  # pragma: no cover - network path
                logger.warning("Browser scrape attempt %d failed: %s", attempt + 1, exc)

        return []
