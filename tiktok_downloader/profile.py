"""Profile scraping utilities."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urljoin

from .config import Config, PartialConfigDict
from .cookies import JSONCookie
from .extractors.base import BaseExtractor
from .url_parser import parse_tiktok_url


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
