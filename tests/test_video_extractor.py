from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from tiktok_downloader.config import Config
from tiktok_downloader.extractors import video as video_mod
from tiktok_downloader.extractors.video import VideoExtractor, VideoResult


@pytest.fixture(autouse=True)
def reset_config() -> Generator[None, None, None]:
    Config._instance = None
    Config._initialized = False
    yield
    Config._instance = None
    Config._initialized = False


def make_dummy_ytdl(return_info: dict[str, Any], opts_holder: dict[str, Any]) -> type:
    class DummyYDL:
        def __init__(self, opts: dict[str, Any]) -> None:
            opts_holder.update(opts)

        def extract_info(self, url: str, download: bool = False) -> dict[str, Any]:
            opts_holder["url"] = url
            opts_holder["download"] = download
            return return_info

    return DummyYDL


def test_cookie_file_creation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sample_cookies = [{"name": "sid", "value": "1", "domain": "example.com", "path": "/"}]

    def fake_load(self: object, profile: str) -> list[dict[str, Any]]:
        assert profile == "test"
        return sample_cookies

    written: list[list[dict[str, Any]]] = []

    def fake_write(cookies: list[dict[str, Any]], file: Any) -> None:
        written.append(cookies)
        file.write("# cookie\n")

    monkeypatch.setattr(video_mod.CookieManager, "load", fake_load)
    monkeypatch.setattr(video_mod, "_write_netscape", fake_write)

    captured: dict[str, Any] = {}
    monkeypatch.setattr(video_mod.yt_dlp, "YoutubeDL", make_dummy_ytdl({}, captured))

    ext = VideoExtractor(cookie_profile="test")
    result = ext.extract("https://tiktok.com/@u/video/123")

    assert ext.cookie_file and ext.cookie_file.exists()
    assert written == [sample_cookies]
    assert captured["cookiefile"] == str(ext.cookie_file)
    assert isinstance(result, VideoResult)


def test_quality_and_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = {
        "id": "123",
        "title": "A title",
        "uploader": "user",
        "duration": 5,
        "url": "http://video/file.mp4",
        "thumbnail": "thumb.jpg",
        "description": "desc",
        "tags": ["t1", "t2"],
        "requested_downloads": [{"filepath": str(tmp_path / "123.mp4")}],
    }
    captured: dict[str, Any] = {}
    monkeypatch.setattr(video_mod.yt_dlp, "YoutubeDL", make_dummy_ytdl(info, captured))

    cfg = Config(None)
    cfg.download_path = tmp_path

    ext = VideoExtractor(config=cfg, quality="720p")
    result = ext.extract("https://tiktok.com/@u/video/123", download=True)

    assert captured["format"] == "720p"
    assert captured["outtmpl"] == str(tmp_path / "%(id)s.%(ext)s")
    assert captured["download"] is True
    assert result.filepath == Path(tmp_path / "123.mp4")
    assert result.video_id == "123"
    assert result.title == "A title"
    assert result.author == "user"
    assert result.duration == 5  # noqa: PLR2004
    assert result.video_url == "http://video/file.mp4"
    assert result.thumbnail_url == "thumb.jpg"
    assert result.description == "desc"
    assert result.tags == ["t1", "t2"]


def test_extract_bad_info(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class DummyYDL:
        def __init__(self, opts: dict[str, Any]) -> None:
            captured.update(opts)

        def extract_info(self, url: str, download: bool = False) -> object:
            return "not-a-dict"

    monkeypatch.setattr(video_mod.yt_dlp, "YoutubeDL", DummyYDL)
    ext = VideoExtractor()
    with pytest.raises(RuntimeError):
        ext.extract("https://tiktok.com/vid")


def test_list_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    output_lines = ["fmt line 1", "fmt line 2"]

    class DummyYDL:
        def __init__(self, opts: dict[str, Any]) -> None:
            pass

        def extract_info(self, url: str, download: bool = False) -> None:
            print("\n".join(output_lines))

    monkeypatch.setattr(video_mod.yt_dlp, "YoutubeDL", DummyYDL)
    ext = VideoExtractor()
    result = ext.list_formats("https://x")
    assert result == output_lines
