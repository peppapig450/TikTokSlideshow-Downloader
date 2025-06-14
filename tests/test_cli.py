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
    monkeypatch.setattr("tiktok_downloader.cli._stream_download", lambda u, d, c: None)

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
