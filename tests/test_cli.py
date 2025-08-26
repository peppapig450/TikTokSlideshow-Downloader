import json
from collections.abc import Generator, Sequence
from pathlib import Path
from typing import ClassVar

import pytest
from click.testing import CliRunner

from tiktok_downloader import Config, LogLevel, TikTokURLInfo
from tiktok_downloader.cli import main


@pytest.fixture(autouse=True)
def reset_config_singleton() -> Generator[None, None, None]:
    Config._instance = None
    Config._initialized = False
    yield
    Config._instance = None
    Config._initialized = False


def test_download_error_is_user_friendly(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_value(_url: str) -> None:
        raise ValueError("bad url")

    monkeypatch.setattr("tiktok_downloader.cli.parse_tiktok_url", raise_value)
    runner = CliRunner()
    result = runner.invoke(main, ["download", "http://bad"])
    assert result.exit_code == 1
    assert "Failed to parse http://bad" in result.output
    assert "No valid URLs to download" in result.output
    assert "Traceback" not in result.output


def test_cli_updates_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tiktok_downloader.cli.parse_tiktok_url",
        lambda url: TikTokURLInfo(url, url, "1234567890123456789", "video"),
    )

    async def fake_download_all(self: object, urls: Sequence[str], dest_dir: Path) -> None:
        dest = Path(dest_dir) / "1234567890123456789.bin"
        dest.touch()

    monkeypatch.setattr(
        "tiktok_downloader.cli.DownloadManager.download_all",
        fake_download_all,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "download",
            "https://tiktok.com/@user/video/1234567890123456789",
            "--output",
            str(tmp_path),
            "--browser-timeout",
            "50",
            "--headless",
            "--max-retries",
            "7",
            "--log-level",
            "DEBUG",
        ],
    )
    assert result.exit_code == 0

    cfg = Config(None)
    assert cfg.download_path == tmp_path
    assert cfg.get("browser_timeout") == 50  # noqa: PLR2004
    assert cfg.get("max_retries") == 7  # noqa: PLR2004
    assert cfg.get("headless") is True
    assert cfg.get("log_level") is LogLevel.DEBUG


def test_help_output() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output

    result = runner.invoke(main, ["download", "--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_cookies_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sample = [
        {
            "name": "sid",
            "value": "1",
            "domain": ".tiktok.com",
            "path": "/",
            "secure": False,
            "expirationDate": 0,
        }
    ]
    monkeypatch.setattr(
        "tiktok_downloader.cli.CookieManager.load",
        lambda self, profile: sample,
    )

    runner = CliRunner()
    dest = tmp_path / "cookies.txt"
    result = runner.invoke(main, ["cookies", "export", "test", str(dest)])
    assert result.exit_code == 0
    assert dest.exists()
    assert "# Netscape HTTP Cookie File" in dest.read_text()


def test_cookies_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tiktok_downloader.cli.CookieManager.list_profiles",
        lambda self: ["prof1", "prof2"],
    )

    runner = CliRunner()
    result = runner.invoke(main, ["cookies", "list"])
    assert result.exit_code == 0
    assert "prof1" in result.output
    assert "prof2" in result.output


def test_progress_bar_no_content_length(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tiktok_downloader.cli.parse_tiktok_url",
        lambda url: TikTokURLInfo(url, url, "123", "video"),
    )

    class DummyTqdm:
        instances: ClassVar[list["DummyTqdm"]] = []

        def __init__(self, *args: object, **kwargs: object) -> None:
            self.n = 0
            self.total = kwargs.get("total")
            DummyTqdm.instances.append(self)

        def update(self, n: int) -> None:
            self.n += n

        def close(self) -> None:
            pass

        @staticmethod
        def format_sizeof(_: int) -> str:
            return "size"

    monkeypatch.setattr("tiktok_downloader.cli.tqdm", DummyTqdm)

    class DummyExtractor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def extract(self, url: str, download: bool = False) -> object:
            dest = tmp_path / "123.bin"
            dest.write_bytes(b"abcdef")
            return type("Res", (), {"filepath": dest})()

    monkeypatch.setattr("tiktok_downloader.cli.VideoExtractor", DummyExtractor)
    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", lambda *a, **k: None)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["download", "https://tiktok.com/@user/video/123", "--output", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert (tmp_path / "123.bin").exists()
    assert len(DummyTqdm.instances) >= 1


def test_multiple_urls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    urls = ["https://a", "https://b"]
    mapping = {
        "https://a": TikTokURLInfo("https://a", "https://a", "a", "video"),
        "https://b": TikTokURLInfo("https://b", "https://b", "b", "video"),
    }
    monkeypatch.setattr("tiktok_downloader.cli.parse_tiktok_url", lambda u: mapping[u])

    class DummyExtractor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def extract(self, url: str, download: bool = False) -> object:
            vid = url.split("/")[-1]
            dest = tmp_path / f"{vid}.bin"
            dest.touch()
            return type("Res", (), {"filepath": dest})()

    monkeypatch.setattr("tiktok_downloader.cli.VideoExtractor", DummyExtractor)
    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", lambda *a, **k: None)

    async def fake_download_all(self: object, urls: Sequence[str], dest_dir: Path) -> None:
        for u in urls:
            Path(dest_dir, f"{Path(u).name}.bin").touch()

    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", fake_download_all)

    runner = CliRunner()
    result = runner.invoke(main, ["download", *urls, "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "a.bin").exists()
    assert (tmp_path / "b.bin").exists()


def test_urls_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file = tmp_path / "urls.txt"
    file.write_text("https://x\n#c\n\nhttps://y\n")
    mapping = {
        "https://x": TikTokURLInfo("https://x", "https://x", "x", "video"),
        "https://y": TikTokURLInfo("https://y", "https://y", "y", "video"),
    }
    monkeypatch.setattr("tiktok_downloader.cli.parse_tiktok_url", lambda u: mapping[u])

    class DummyExtractor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def extract(self, url: str, download: bool = False) -> object:
            vid = url.split("/")[-1]
            dest = tmp_path / f"{vid}.bin"
            dest.touch()
            return type("Res", (), {"filepath": dest})()

    monkeypatch.setattr("tiktok_downloader.cli.VideoExtractor", DummyExtractor)
    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", lambda *a, **k: None)

    runner = CliRunner()
    result = runner.invoke(main, ["download", "--url-file", str(file), "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "x.bin").exists()
    assert (tmp_path / "y.bin").exists()


def test_mixed_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    urls = ["https://good", "bad", "https://fail"]

    def fake_parse(url: str) -> TikTokURLInfo:
        if url == "bad":
            raise ValueError("invalid")
        return TikTokURLInfo(url, url, url.split("//")[1], "video")

    monkeypatch.setattr("tiktok_downloader.cli.parse_tiktok_url", fake_parse)

    class DummyExtractor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def extract(self, url: str, download: bool = False) -> object:
            vid = url.split("//")[1]
            if vid.endswith("fail"):
                raise RuntimeError("boom")
            dest = tmp_path / f"{vid}.bin"
            dest.touch()
            return type("Res", (), {"filepath": dest})()

    monkeypatch.setattr("tiktok_downloader.cli.VideoExtractor", DummyExtractor)
    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", lambda *a, **k: None)

    runner = CliRunner()
    result = runner.invoke(main, ["download", *urls, "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "good.bin").exists()
    assert not (tmp_path / "fail.bin").exists()
    assert "Failed to parse bad" in result.output
    assert "Failed to download https://fail" in result.output


def test_quality_option(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = TikTokURLInfo("https://x", "https://x", "123", "video")
    monkeypatch.setattr("tiktok_downloader.cli.parse_tiktok_url", lambda u: info)

    captured: dict[str, str | bool] = {}

    class DummyExtractor:
        def __init__(self, *args: object, quality: str | None = None, **kw: object) -> None:
            captured["quality"] = quality or ""

        def extract(self, url: str, download: bool = False) -> object:
            captured["url"] = url
            captured["download"] = download
            return type("Res", (), {"filepath": tmp_path / "123.mp4"})()

    monkeypatch.setattr("tiktok_downloader.cli.VideoExtractor", DummyExtractor)
    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", lambda *a, **k: None)

    runner = CliRunner()
    result = runner.invoke(main, ["download", "https://x", "--quality", "720p"])
    assert result.exit_code == 0
    assert captured["quality"] == "720p"
    assert captured["url"] == "https://x"
    assert captured["download"] is True


def test_list_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    info = TikTokURLInfo("https://x", "https://x", "123", "video")
    monkeypatch.setattr("tiktok_downloader.cli.parse_tiktok_url", lambda u: info)

    calls: dict[str, int] = {"list": 0, "extract": 0}

    class DummyExtractor:
        def __init__(self, *args: object, **kw: object) -> None: ...

        def list_formats(self, url: str) -> list[str]:
            calls["list"] += 1
            return ["fmt1", "fmt2"]

        def extract(self, url: str, download: bool = False) -> object:
            calls["extract"] += 1
            return type("Res", (), {"filepath": None})()

    monkeypatch.setattr("tiktok_downloader.cli.VideoExtractor", DummyExtractor)
    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", lambda *a, **k: None)

    runner = CliRunner()
    result = runner.invoke(main, ["download", "https://x", "--list-formats"])
    assert result.exit_code == 0
    assert calls["list"] == 1
    assert calls["extract"] == 0
    assert "fmt1" in result.output
    assert "fmt2" in result.output


def test_concurrency_option(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = TikTokURLInfo("https://x", "https://x", "123", "video")
    monkeypatch.setattr("tiktok_downloader.cli.parse_tiktok_url", lambda u: info)

    captured: dict[str, int] = {}

    class DummyManager:
        def __init__(
            self,
            *args: object,
            concurrency: int = 3,
            **kw: object,
        ) -> None:
            captured["concurrency"] = concurrency
            self.concurrency = concurrency

    class DummyExtractor:
        def __init__(self, *args: object, **kw: object) -> None: ...

        def extract(self, url: str, download: bool = False) -> object:
            dest = tmp_path / "123.bin"
            dest.touch()
            return type("Res", (), {"filepath": dest})()

    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager", DummyManager)
    monkeypatch.setattr("tiktok_downloader.cli.VideoExtractor", DummyExtractor)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["download", "https://x", "--output", str(tmp_path), "--concurrency", "5"],
    )
    assert result.exit_code == 0
    assert captured["concurrency"] == 5  # noqa: PLR2004


def test_slideshow_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mapping = {
        "https://slide": TikTokURLInfo("https://slide", "https://slide", "s123", "slideshow"),
        "https://video": TikTokURLInfo("https://video", "https://video", "v123", "video"),
    }
    monkeypatch.setattr("tiktok_downloader.cli.parse_tiktok_url", lambda u: mapping[u])

    captured: dict[str, object] = {}

    class DummySlideExtractor:
        def __init__(self, *args: object, cookie_profile: str | None = None, **kw: object) -> None:
            captured["slide_cookie"] = cookie_profile

        async def extract(self, url: str) -> object:
            captured["slide_url"] = url
            return type("Res", (), {"urls": ["img1", "img2"]})()

    class DummyVideoExtractor:
        def __init__(self, *args: object, cookie_profile: str | None = None, **kw: object) -> None:
            captured["video_cookie"] = cookie_profile

        def extract(self, url: str, download: bool = False) -> object:
            dest = tmp_path / "v123.bin"
            dest.touch()
            return type("Res", (), {"filepath": dest})()

    downloaded: list[tuple[list[str], Path]] = []

    async def fake_download_all(self: object, urls: Sequence[str], dest_dir: Path) -> None:
        downloaded.append((list(urls), dest_dir))

    monkeypatch.setattr("tiktok_downloader.cli.SlideshowExtractor", DummySlideExtractor)
    monkeypatch.setattr("tiktok_downloader.cli.VideoExtractor", DummyVideoExtractor)
    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", fake_download_all)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "download",
            "https://slide",
            "https://video",
            "--output",
            str(tmp_path),
            "--cookie-profile",
            "prof",
        ],
    )
    assert result.exit_code == 0
    assert captured["slide_cookie"] == "prof"
    assert captured["slide_url"] == "https://slide"
    assert downloaded == [(["img1", "img2"], tmp_path / "s123")]
    assert captured["video_cookie"] == "prof"
    assert (tmp_path / "v123.bin").exists()


def test_slideshow_images_renamed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = TikTokURLInfo("https://slide", "https://slide", "s123", "slideshow")
    monkeypatch.setattr("tiktok_downloader.cli.parse_tiktok_url", lambda u: info)

    class DummyExtractor:
        def __init__(self, *args: object, **kw: object) -> None:
            pass

        async def extract(self, url: str) -> object:
            return type("Res", (), {"urls": ["img1", "img2"]})()

    async def fake_download_all(
        self: object, urls: Sequence[str], dest_dir: Path
    ) -> list[tuple[str, Path, str]]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        results: list[tuple[str, Path, str]] = []
        for u in urls:
            dest = dest_dir / f"{Path(u).name}.jpg"
            dest.touch()
            results.append((u, dest, "hash"))
        return results

    monkeypatch.setattr("tiktok_downloader.cli.SlideshowExtractor", DummyExtractor)
    monkeypatch.setattr("tiktok_downloader.cli.VideoExtractor", lambda *a, **k: None)
    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", fake_download_all)

    runner = CliRunner()
    result = runner.invoke(main, ["download", "https://slide", "--output", str(tmp_path)])

    assert result.exit_code == 0
    assert (tmp_path / "s123" / "img1.jpg").exists()
    assert (tmp_path / "s123" / "img2.jpg").exists()


def test_cookie_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = TikTokURLInfo("https://x", "https://x", "123", "video")
    monkeypatch.setattr("tiktok_downloader.cli.parse_tiktok_url", lambda u: info)

    cookie_file = tmp_path / "cookies.json"
    data = [{"name": "sid", "value": "1", "domain": "x", "path": "/"}]
    cookie_file.write_text(json.dumps(data))

    captured: dict[str, object] = {}

    class DummyExtractor:
        def __init__(
            self, *args: object, cookies: list[dict[str, object]] | None = None, **kw: object
        ) -> None:
            captured["cookies"] = cookies

        def extract(self, url: str, download: bool = False) -> object:
            dest = tmp_path / "123.bin"
            dest.touch()
            return type("Res", (), {"filepath": dest})()

    monkeypatch.setattr("tiktok_downloader.cli.VideoExtractor", DummyExtractor)
    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", lambda *a, **k: None)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "download",
            "https://x",
            "--cookie-file",
            str(cookie_file),
            "--cookie-format",
            "json",
            "--output",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert captured["cookies"][0]["name"] == "sid"


def test_profile_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "tiktok_downloader.cli.ProfileScraper.fetch_urls",
        lambda self: ["https://slide", "https://video"],
    )

    mapping = {
        "https://slide": TikTokURLInfo("https://slide", "https://slide", "s123", "slideshow"),
        "https://video": TikTokURLInfo("https://video", "https://video", "v123", "video"),
    }
    monkeypatch.setattr("tiktok_downloader.cli.parse_tiktok_url", lambda u: mapping[u])

    class DummySlideExtractor:
        def __init__(self, *args: object, **kw: object) -> None:
            pass

        async def extract(self, url: str) -> object:
            return type("Res", (), {"urls": ["img1", "img2"]})()

    class DummyVideoExtractor:
        def __init__(self, *args: object, **kw: object) -> None:
            pass

        def extract(self, url: str, download: bool = False) -> object:
            dest = tmp_path / "v123.bin"
            dest.touch()
            return type("Res", (), {"filepath": dest})()

    downloaded: list[tuple[list[str], Path]] = []

    async def fake_download_all(self: object, urls: Sequence[str], dest_dir: Path) -> None:
        downloaded.append((list(urls), dest_dir))

    monkeypatch.setattr("tiktok_downloader.cli.SlideshowExtractor", DummySlideExtractor)
    monkeypatch.setattr("tiktok_downloader.cli.VideoExtractor", DummyVideoExtractor)
    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", fake_download_all)

    runner = CliRunner()
    result = runner.invoke(main, ["profile", "user", "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "v123.bin").exists()
    assert downloaded == [(["img1", "img2"], tmp_path / "s123")]
