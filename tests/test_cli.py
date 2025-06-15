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

    async def fake_download_all(self: object, urls: Sequence[str], dest_dir: Path) -> None:
        dest = Path(dest_dir) / "123.bin"
        if self.progress_callback:  # type: ignore[attr-defined]
            self.progress_callback(dest, 6, 6)  # type: ignore[attr-defined]
        dest.write_bytes(b"abcdef")

    monkeypatch.setattr(
        "tiktok_downloader.cli.DownloadManager.download_all",
        fake_download_all,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["download", "https://tiktok.com/@user/video/123", "--output", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert (tmp_path / "123.bin").exists()
    assert len(DummyTqdm.instances) >= 2  # noqa: PLR2004


def test_multiple_urls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    urls = ["https://a", "https://b"]
    mapping = {
        "https://a": TikTokURLInfo("https://a", "https://a", "a", "video"),
        "https://b": TikTokURLInfo("https://b", "https://b", "b", "video"),
    }
    monkeypatch.setattr("tiktok_downloader.cli.parse_tiktok_url", lambda u: mapping[u])

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

    async def fake_download_all(self: object, urls: Sequence[str], dest_dir: Path) -> None:
        for u in urls:
            Path(dest_dir, f"{Path(u).name}.bin").touch()

    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", fake_download_all)

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

    async def fake_download_all(self: object, urls: Sequence[str], dest_dir: Path) -> None:
        u = urls[0]
        if u.endswith("fail"):
            raise RuntimeError("boom")
        Path(dest_dir, f"{Path(u).name}.bin").touch()

    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download_all", fake_download_all)

    runner = CliRunner()
    result = runner.invoke(main, ["download", *urls, "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "good.bin").exists()
    assert not (tmp_path / "fail.bin").exists()
    assert "Failed to parse bad" in result.output
    assert "Failed to download https://fail" in result.output
