from collections.abc import Generator
from typing import Any

import pytest
import requests

from tiktok_downloader import BaseExtractor, Config


class DummyExtractor(BaseExtractor):
    def extract(self, url: str) -> Any:
        return url


@pytest.fixture(autouse=True)
def reset_config() -> Generator[None, None, None]:
    Config._instance = None
    Config._initialized = False
    yield
    Config._instance = None
    Config._initialized = False


def test_session_initialized() -> None:
    ext = DummyExtractor()
    assert isinstance(ext.session, requests.Session)
    assert ext.session.headers["User-Agent"]


def test_user_agent_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    ext = DummyExtractor(user_agents=["A", "B"])

    calls: list[str | bytes] = []

    def fake_request(method: str, url: str, **_: Any) -> Any:
        calls.append(ext.session.headers["User-Agent"])

        class R:
            def raise_for_status(self) -> None:
                pass

        return R()

    monkeypatch.setattr(ext.session, "request", fake_request)
    ext.get("http://example.com")
    ext.get("http://example.com")

    assert calls == ["B", "A"]


def test_cookie_profile_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded: list[str] = []

    def fake_load(self: Any, profile: str) -> list[dict[str, str]]:
        loaded.append(profile)
        return [{"name": "sid", "value": "1", "domain": "example.com", "path": "/"}]

    monkeypatch.setattr(
        "tiktok_downloader.extractors.base.CookieManager.load",
        fake_load,
    )

    ext = DummyExtractor(cookie_profile="test")

    assert loaded == ["test"]
    assert ext.session.cookies.get("sid", domain="example.com") == "1"
