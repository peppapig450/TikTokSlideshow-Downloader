import pytest

from tiktok_downloader import TikTokURLInfo
from tiktok_downloader.profile import ProfileScraper


class DummyResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:  # pragma: no cover - unused
        pass


def test_fetch_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    html = (
        '<a href="/@user/video/111"></a>'
        '<a href="https://www.tiktok.com/@other/photo/222"></a>'
        '<a href="/@user/video/111"></a>'
    )

    def fake_request(self: object, method: str, url: str, **_: object) -> DummyResponse:
        assert method == "GET"
        return DummyResponse(html)

    monkeypatch.setattr(
        "tiktok_downloader.profile.BaseExtractor.request",
        fake_request,
    )

    captured: list[str] = []
    mapping = {
        "https://www.tiktok.com/@user/video/111": TikTokURLInfo(
            "a", "https://www.tiktok.com/@user/video/111", "111", "video"
        ),
        "https://www.tiktok.com/@other/photo/222": TikTokURLInfo(
            "b", "https://www.tiktok.com/@other/photo/222", "222", "slideshow"
        ),
    }

    def fake_parse(url: str) -> TikTokURLInfo:
        captured.append(url)
        return mapping[url]

    monkeypatch.setattr("tiktok_downloader.profile.parse_tiktok_url", fake_parse)

    scraper = ProfileScraper("user")
    urls = scraper.fetch_urls()

    assert urls == [
        "https://www.tiktok.com/@user/video/111",
        "https://www.tiktok.com/@other/photo/222",
    ]
    assert captured.count("https://www.tiktok.com/@user/video/111") >= 1
    assert captured.count("https://www.tiktok.com/@other/photo/222") >= 1


class DummyState(dict):
    pass


def make_async_playwright(batches: list[list[str]], state: DummyState):  # noqa: C901 - helper
    class Element:
        def __init__(self, href: str) -> None:
            self.href = href

        async def get_attribute(self, name: str) -> str | None:
            return self.href if name == "href" else None

    class Page:
        def __init__(self) -> None:
            self.loaded: list[str] = []
            self.idx = -1
            self.mouse = self.Mouse(self)

        class Mouse:
            def __init__(self, page: "Page") -> None:
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
            return [Element(h) for h in self.loaded]

        async def wait_for_timeout(self, _ms: int) -> None:
            return None

    class Context:
        async def add_cookies(self, _cookies: list[dict[str, object]]) -> None:
            pass

        async def new_page(self) -> Page:
            page = Page()
            return page

    class Browser:
        async def new_context(self, **_kw: object) -> Context:
            return Context()

        async def close(self) -> None:
            state["closed"] = True

    class PW:
        def __init__(self) -> None:
            self.chromium = self

        async def launch(self, **_kw: object) -> Browser:
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
async def test_fetch_urls_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    state: DummyState = DummyState()
    monkeypatch.setattr(
        "tiktok_downloader.profile.async_playwright",
        make_async_playwright(
            [["/@user/video/111", "https://www.tiktok.com/@other/photo/222", "/@user/video/111"]],
            state,
        ),
    )

    captured: list[str] = []
    mapping = {
        "https://www.tiktok.com/@user/video/111": TikTokURLInfo(
            "a",
            "https://www.tiktok.com/@user/video/111",
            "111",
            "video",
        ),
        "https://www.tiktok.com/@other/photo/222": TikTokURLInfo(
            "b",
            "https://www.tiktok.com/@other/photo/222",
            "222",
            "slideshow",
        ),
    }

    def fake_parse(url: str) -> TikTokURLInfo:
        captured.append(url)
        return mapping[url]

    monkeypatch.setattr("tiktok_downloader.profile.parse_tiktok_url", fake_parse)

    scraper = ProfileScraper("user")
    urls = await scraper.fetch_urls_browser()

    assert urls == [
        "https://www.tiktok.com/@user/video/111",
        "https://www.tiktok.com/@other/photo/222",
    ]
    assert captured.count("https://www.tiktok.com/@user/video/111") >= 1
    assert captured.count("https://www.tiktok.com/@other/photo/222") >= 1
