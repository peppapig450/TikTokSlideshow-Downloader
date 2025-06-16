from collections.abc import Generator
from pathlib import Path
from typing import cast

import pytest
from pytest import LogCaptureFixture, MonkeyPatch

from tiktok_downloader.config import (
    Config,
    PartialConfigDict,
    is_config_key,
)
from tiktok_downloader.logger import LogLevel


@pytest.fixture(autouse=True)
def reset_config_singleton() -> Generator[None, None, None]:
    # Ensure each test sees a fresh singleton
    Config._instance = None
    Config._initialized = False
    yield
    Config._instance = None
    Config._initialized = False


def test_is_config_key() -> None:
    valid = [
        "download_path",
        "browser_timeout",
        "headless",
        "debug",
        "max_retries",
        "chunk_size",
        "log_level",
        "user_agent",
    ]
    for key in valid:
        assert is_config_key(key)
    assert not is_config_key("not_a_key")
    assert not is_config_key("")  # empty string is not valid


def test_default_config_all_keys_and_types() -> None:
    cfg = Config(None)
    all_conf = cfg.all
    # Should match DEFAULT_CONFIG keys
    assert set(all_conf) == set(Config.DEFAULT_CONFIG)
    # And types should match exactly
    for k, v in all_conf.items():
        assert is_config_key(k)
        expected = Config.DEFAULT_CONFIG[k]
        assert isinstance(v, type(expected))
    # log_level should be LogLevel enum
    assert isinstance(all_conf["log_level"], LogLevel)


def test_singleton_behavior() -> None:
    c1 = Config(None)
    c2 = Config(None)
    assert c1 is c2
    # Changing via one reference is visible on the other
    c1.set("max_retries", 9)
    assert c2.get("max_retries") == 9  # noqa: PLR2004


def test_set_and_get_and_update() -> None:
    cfg = Config(None)
    # default
    assert cfg.get("max_retries") == Config.DEFAULT_CONFIG["max_retries"]
    # set valid key
    cfg.set("max_retries", 7)
    assert cfg.get("max_retries") == 7  # noqa: PLR2004
    # set invalid key → ignored
    cfg.set("nope", "value")
    assert cfg.get("nope", None) is None
    # update multiple
    cfg.update({"chunk_size": 1234, "debug": False})
    assert cfg.get("chunk_size") == 1234  # noqa: PLR2004
    assert cfg.get("debug") is False


def test_download_path_property() -> None:
    cfg = Config(None)
    # default is a Path
    assert isinstance(cfg.download_path, Path)
    # setter accepts str
    cfg.download_path = cast(Path, "my_downloads")
    assert isinstance(cfg.download_path, Path)
    assert cfg.download_path == Path("my_downloads")


def test_env_override_valid(monkeypatch: MonkeyPatch) -> None:
    # set a valid override
    monkeypatch.setenv("TIKTOK_DOWNLOADER_BROWSER_TIMEOUT", "5000")
    monkeypatch.setenv("TIKTOK_DOWNLOADER_HEADLESS", "false")
    monkeypatch.setenv("TIKTOK_DOWNLOADER_LOG_LEVEL", "DEBUG")
    cfg = Config(None)
    assert cfg.get("browser_timeout") == 5000  # noqa: PLR2004
    assert cfg.get("headless") is False
    # log_level should be the enum
    assert cfg.get("log_level") is LogLevel.DEBUG


def test_env_override_invalid(monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
    # invalid int for browser_timeout
    monkeypatch.setenv("TIKTOK_DOWNLOADER_BROWSER_TIMEOUT", "not_an_int")
    caplog.set_level("ERROR")
    cfg = Config(None)
    # should fall back to default
    assert cfg.get("browser_timeout") == Config.DEFAULT_CONFIG["browser_timeout"]
    # and log an error
    assert "Failed to parse" in caplog.text


def test_partial_config_init_dict() -> None:
    # Passing a dict at init should override defaults
    init_overrides: PartialConfigDict = {
        "max_retries": 10,
        "user_agent": "my-agent",
    }
    cfg = Config(init_overrides)
    assert cfg.get("max_retries") == 10  # noqa: PLR2004
    assert cfg.get("user_agent") == "my-agent"
    # Others remain defaults
    assert cfg.get("chunk_size") == Config.DEFAULT_CONFIG["chunk_size"]
