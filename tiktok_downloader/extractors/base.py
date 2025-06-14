"""Abstract base class for TikTok extractors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import requests

from ..config import Config, PartialConfigDict
from ..cookies import CookieManager
from ..logger import get_logger

logger = get_logger(__name__)


class BaseExtractor[T](ABC):
    """Base class for extractor implementations."""

    def __init__(
        self,
        config: Config | PartialConfigDict | None = None,
        *,
        cookie_profile: str | None = None,
        user_agents: list[str] | None = None,
    ) -> None:
        """Initialize the extractor.

        Args:
            config: Existing :class:`Config` instance or dictionary of overrides.
            cookie_profile: Name of a saved cookie profile to load.
            user_agents: Sequence of user-agent strings to rotate through. When
                omitted, :data:`config`'s ``user_agent`` value is used.
        """
        self.config = config if isinstance(config, Config) else Config(config)

        self.user_agents = user_agents or [self.config.get("user_agent")]
        self._agent_idx = 0

        self.session = requests.Session()
        self.session.headers["User-Agent"] = self.user_agents[self._agent_idx]

        if cookie_profile:
            self._load_cookies(cookie_profile)

    # ------------------------------------------------------------------
    def _load_cookies(self, profile: str) -> None:
        """Load cookies from ``profile`` into the session."""
        cookies = CookieManager().load(profile)
        for cookie in cookies:
            self.session.cookies.set(
                cookie.get("name", ""),
                cookie.get("value", ""),
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )

    def _rotate_user_agent(self) -> None:
        """Rotate to the next user-agent."""
        if not self.user_agents:
            return
        self._agent_idx = (self._agent_idx + 1) % len(self.user_agents)
        self.session.headers["User-Agent"] = self.user_agents[self._agent_idx]

    # ------------------------------------------------------------------
    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Perform an HTTP request with automatic user-agent rotation."""
        self._rotate_user_agent()
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:  # pragma: no cover - error path
            logger.error("%s %s failed: %s", method, url, exc)
            raise

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """Shortcut for ``GET`` requests."""
        return self.request("GET", url, **kwargs)

    # ------------------------------------------------------------------
    @abstractmethod
    def extract(self, url: str) -> T:
        """Extract information from ``url``."""
        raise NotImplementedError
