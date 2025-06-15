from collections.abc import Generator
from pathlib import Path

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
    assert "Invalid input: bad url" in result.output
    assert "Traceback" not in result.output


def test_cli_updates_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tiktok_downloader.cli.parse_tiktok_url",
        lambda url: TikTokURLInfo(url, url, "1234567890123456789", "video"),
    )

    async def fake_download(self: object, url: str, dest: Path) -> None:
        dest.touch()

    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download", fake_download)

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

    async def fake_download(self: object, url: str, dest: Path) -> None:
        dest.write_bytes(b"abcdef")

    monkeypatch.setattr("tiktok_downloader.cli.DownloadManager.download", fake_download)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["download", "https://tiktok.com/@user/video/123", "--output", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert (tmp_path / "123.bin").exists()
    assert "Saved to" in result.output
