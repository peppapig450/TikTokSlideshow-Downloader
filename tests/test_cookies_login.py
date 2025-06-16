from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from tiktok_downloader.cli import main
from tiktok_downloader.cookies import fetch_cookies


def make_async_playwright(state: dict[str, Any]) -> Callable[[], Any]:  # noqa: C901 - helper
    class Page:
        async def goto(self, url: str) -> None:
            state["goto"] = url

    class Context:
        async def new_page(self) -> Page:
            state["new_page"] = True
            return Page()

        async def cookies(self) -> list[dict[str, Any]]:
            return state["return_cookies"]  # type: ignore[no-any-return]

        async def close(self) -> None:
            state["context_closed"] = True

    class Browser:
        async def new_context(self) -> Context:
            state["new_context"] = True
            return Context()

        async def close(self) -> None:
            state["browser_closed"] = True

    class BrowserType:
        def __init__(self, name: str) -> None:
            self.name = name

        async def launch(self, headless: bool = False) -> Browser:
            state["browser"] = self.name
            state["headless"] = headless
            return Browser()

        async def launch_persistent_context(
            self, user_data_dir: str, headless: bool = False
        ) -> Context:
            state["browser"] = self.name
            state["headless"] = headless
            state["user_data_dir"] = user_data_dir
            return Context()

    class PW:
        def __init__(self) -> None:
            self.chromium = BrowserType("chromium")
            self.firefox = BrowserType("firefox")
            self.webkit = BrowserType("webkit")

    class Manager:
        async def __aenter__(self) -> PW:
            return PW()

        async def __aexit__(self, *exc: object) -> None:
            return None

    def wrapper() -> Manager:
        return Manager()

    return wrapper


@pytest.mark.asyncio
async def test_fetch_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    state: dict[str, Any] = {
        "return_cookies": [
            {
                "name": "sid",
                "value": "1",
                "domain": "x",
                "path": "/",
                "secure": False,
                "httpOnly": False,
                "expires": 0,
            }
        ]
    }
    monkeypatch.setattr("playwright.async_api.async_playwright", make_async_playwright(state))
    monkeypatch.setattr("builtins.input", lambda _: "")

    result = await fetch_cookies("prof")

    assert state["browser"] == "chromium"
    assert state["headless"] is False
    assert result[0]["name"] == "sid"


@pytest.mark.asyncio
async def test_fetch_cookies_headless(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state: dict[str, Any] = {"return_cookies": []}
    monkeypatch.setattr("playwright.async_api.async_playwright", make_async_playwright(state))
    monkeypatch.setattr("builtins.input", lambda _: "")

    await fetch_cookies("prof", browser="firefox", headless=True, user_data_dir=tmp_path)

    assert state["browser"] == "firefox"
    assert state["headless"] is True
    assert state["user_data_dir"] == str(tmp_path)


def test_cli_login(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fail(*_: Any, **__: Any) -> None:
        raise AssertionError("should not be called")

    monkeypatch.setattr("tiktok_downloader.cli.fetch_cookies", fail, raising=False)
    monkeypatch.setattr("tiktok_downloader.cli.CookieManager.save", fail, raising=False)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "cookies",
            "login",
            "myprof",
            "--browser",
            "firefox",
            "--headless",
            "--user-data-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert "Cookie login is temporarily disabled" in result.output
