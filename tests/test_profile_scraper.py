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
    assert captured == [
        "https://www.tiktok.com/@user/video/111",
        "https://www.tiktok.com/@other/photo/222",
        "https://www.tiktok.com/@user/video/111",
    ]
