from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tiktok_downloader.extractors import SlideshowExtractor
from tiktok_downloader.extractors import slideshow as slideshow_mod


class DummyState(dict):
    pass


def make_async_playwright(batches: list[list[str]], state: DummyState) -> Callable[[], Any]:  # noqa: C901 - helper
    class Element:
        def __init__(self, src: str) -> None:
            self.src = src

        async def get_attribute(self, name: str) -> str | None:
            return self.src if name == "src" else None

    class Page:
        def __init__(self) -> None:
            self.loaded: list[str] = []
            self.idx = -1
            self.mouse = self.Mouse(self)

        class Mouse:
            def __init__(self, page: Page) -> None:
                self.page = page

            async def wheel(self, _x: int, _y: int) -> None:
                self.page._scroll()

        async def goto(self, _url: str, **_kw: object) -> None:
            self._scroll()

        def _scroll(self) -> None:
            self.idx += 1
            if self.idx < len(batches):
                self.loaded.extend(batches[self.idx])

        async def query_selector_all(self, selector: str) -> list[Element]:
            state.setdefault("selectors", []).append(selector)
            return [Element(src) for src in self.loaded]

        async def wait_for_timeout(self, _ms: int) -> None:
            return None

    class Context:
        async def add_cookies(self, cookies: list[dict[str, object]]) -> None:
            state["cookies"] = cookies

        async def new_page(self) -> Page:
            page = Page()
            state["page"] = page
            return page

    class Browser:
        async def new_context(self, **kwargs: object) -> Context:
            state["context_kwargs"] = kwargs
            return Context()

        async def close(self) -> None:
            state["closed"] = True

    class PW:
        def __init__(self) -> None:
            self.chromium = self

        async def launch(self, **kwargs: object) -> Browser:
            state["launch_kwargs"] = kwargs
            return Browser()

    class Manager:
        async def __aenter__(self) -> PW:
            return PW()

        async def __aexit__(self, *exc: object) -> None:
            return None

    def wrapper() -> Manager:
        return Manager()

    return wrapper


@pytest.mark.asyncio
async def test_cookie_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    state: DummyState = DummyState()
    monkeypatch.setattr(slideshow_mod, "async_playwright", make_async_playwright([[]], state))

    loaded: list[str] = []

    def fake_load(self: object, profile: str) -> list[dict[str, str]]:
        loaded.append(profile)
        return [{"name": "sid", "value": "1", "domain": "x", "path": "/"}]

    monkeypatch.setattr(slideshow_mod.CookieManager, "load", fake_load)

    ext = SlideshowExtractor(cookie_profile="test")
    await ext.extract("https://tiktok.com/@u/video/1234567890123456789")

    assert loaded == ["test", "test"]
    assert state["cookies"] == [
        {"name": "sid", "value": "1", "domain": "x", "path": "/", "expires": 0}
    ]


@pytest.mark.asyncio
async def test_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    state: DummyState = DummyState()
    monkeypatch.setattr(slideshow_mod, "async_playwright", make_async_playwright([[]], state))
    ext = SlideshowExtractor(user_agents=["UA"])
    await ext.extract("https://tiktok.com/@u/video/1234567890123456789")
    assert state["context_kwargs"]["user_agent"] == "UA"


@pytest.mark.asyncio
async def test_deduplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    state: DummyState = DummyState()
    batches = [["a", "b", "a"], ["b", "c"]]
    monkeypatch.setattr(slideshow_mod, "async_playwright", make_async_playwright(batches, state))
    ext = SlideshowExtractor()
    result = await ext.extract("https://tiktok.com/@u/video/1234567890123456789")
    assert result.urls == ["a", "b", "c"]
    assert result.count == 3  # noqa: PLR2004
    assert state["selectors"][0] == ".css-brxox6-ImgPhotoSlide.e10jea832"


@pytest.mark.asyncio
async def test_audio_only(monkeypatch: pytest.MonkeyPatch) -> None:
    state: DummyState = DummyState()
    monkeypatch.setattr(slideshow_mod, "async_playwright", make_async_playwright([], state))
    ext = SlideshowExtractor()
    result = await ext.extract("https://tiktok.com/@u/video/1234567890123456789")
    assert result.audio_only is True
    assert result.urls == []
