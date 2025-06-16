import pytest
from click.testing import CliRunner

from tiktok_downloader.cli import main


def test_cli_verify_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tiktok_downloader.cli.verify_cookie_profile", lambda p: True)
    runner = CliRunner()
    result = runner.invoke(main, ["cookies", "verify", "prof"])
    assert result.exit_code == 0
    assert "prof" in result.output
    assert "valid" in result.output.lower()


def test_cli_verify_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tiktok_downloader.cli.verify_cookie_profile", lambda p: False)
    runner = CliRunner()
    result = runner.invoke(main, ["cookies", "verify", "badprof"])
    assert result.exit_code == 1
    assert "invalid" in result.output.lower()
