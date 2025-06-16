from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from tiktok_downloader.cookies import (
    get_chrome_executable_path,
    get_chrome_user_data_dir,
)


def test_user_data_dir_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32", raising=False)
    monkeypatch.setattr(Path, "home", lambda: Path("C:/Users/test"), raising=False)
    expected = Path("C:/Users/test") / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    assert get_chrome_user_data_dir() == expected


def test_user_data_dir_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin", raising=False)
    monkeypatch.setattr(Path, "home", lambda: Path("/Users/test"), raising=False)
    expected = Path("/Users/test") / "Library" / "Application Support" / "Google" / "Chrome"
    assert get_chrome_user_data_dir() == expected


def test_user_data_dir_linux_existing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "linux", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path, raising=False)
    chromium = tmp_path / ".config" / "chromium"
    chromium.mkdir(parents=True)
    assert get_chrome_user_data_dir() == chromium


def test_user_data_dir_linux_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "linux", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path, raising=False)
    assert get_chrome_user_data_dir() is None


def test_executable_path_which(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_path = "/usr/bin/fake-chrome"
    monkeypatch.setattr(shutil, "which", lambda name: fake_path)
    assert get_chrome_executable_path() == Path(fake_path)


def test_executable_path_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(sys, "platform", "linux", raising=False)

    def fake_is_file(self: Path) -> bool:
        return str(self) == "/usr/bin/chromium"

    monkeypatch.setattr(Path, "is_file", fake_is_file)
    assert get_chrome_executable_path() == Path("/usr/bin/chromium")


def test_executable_path_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    paths = []

    def fake_is_file(self: Path) -> bool:
        paths.append(str(self))
        return str(self) == "C:/Program Files/Google/Chrome/Application/chrome.exe"

    monkeypatch.setattr(Path, "is_file", fake_is_file)
    assert get_chrome_executable_path() == Path(
        "C:/Program Files/Google/Chrome/Application/chrome.exe"
    )
    assert any(p.startswith("C:/Program Files") for p in paths)
