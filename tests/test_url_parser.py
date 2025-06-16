import pytest
from pytest import MonkeyPatch

from tiktok_downloader.url_parser import (
    TikTokURLInfo,
    detect_content_type,
    extract_video_id,
    parse_tiktok_url,
    resolve_url,
)


class DummyResponse:
    def __init__(self, url: str) -> None:
        self.url = url


def test_resolve_url_follows_redirects(monkeypatch: MonkeyPatch) -> None:
    timeout_value = 5

    def fake_get(url: str, *, allow_redirects: bool, timeout: int) -> DummyResponse:
        assert allow_redirects is True
        assert timeout == timeout_value
        return DummyResponse("https://resolved.example.com/video/123")

    monkeypatch.setattr("tiktok_downloader.url_parser.requests.get", fake_get)
    resolved = resolve_url("https://short.example.com/abc", timeout=timeout_value)
    assert resolved == "https://resolved.example.com/video/123"


def test_extract_video_id_success() -> None:
    url = "https://www.tiktok.com/@user/video/1234567890123456789"
    assert extract_video_id(url) == "1234567890123456789"


def test_extract_video_id_failure() -> None:
    with pytest.raises(ValueError):
        extract_video_id("https://www.tiktok.com/@user/video/noid")


def test_detect_content_type() -> None:
    assert detect_content_type("https://www.tiktok.com/@user/video/123") == "video"
    assert detect_content_type("https://www.tiktok.com/@user/photo/123") == "slideshow"


def test_parse_tiktok_url_valid(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tiktok_downloader.url_parser.resolve_url",
        lambda url: "https://www.tiktok.com/@user/video/1234567890123456789",
    )
    monkeypatch.setattr(
        "tiktok_downloader.url_parser.extract_video_id", lambda url: "1234567890123456789"
    )
    monkeypatch.setattr("tiktok_downloader.url_parser.detect_content_type", lambda url: "video")

    info = parse_tiktok_url("https://vm.tiktok.com/short")
    assert info == TikTokURLInfo(
        "https://vm.tiktok.com/short",
        "https://www.tiktok.com/@user/video/1234567890123456789",
        "1234567890123456789",
        "video",
    )


def test_parse_tiktok_url_invalid(monkeypatch: MonkeyPatch) -> None:
    called = False

    def fake_resolve(url: str) -> str:
        nonlocal called
        called = True
        return url

    monkeypatch.setattr("tiktok_downloader.url_parser.resolve_url", fake_resolve)

    with pytest.raises(ValueError):
        parse_tiktok_url("ftp://tiktok.com/video/123")
    assert not called

    with pytest.raises(ValueError):
        parse_tiktok_url("https://example.com/123")
    assert not called
