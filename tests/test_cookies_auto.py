from collections.abc import Callable
from typing import Any

import pytest
from click.testing import CliRunner

from tiktok_downloader.cli import main
from tiktok_downloader.cookies import auto_fetch_cookies


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

    class BrowserType:
        def __init__(self, name: str) -> None:
            self.name = name

        async def launch_persistent_context(
            self, user_data_dir: str, headless: bool = True
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
async def test_auto_fetch_cookies(monkeypatch: pytest.MonkeyPatch, tmp_path: str) -> None:
    state: dict[str, Any] = {"return_cookies": []}
    # stub out Playwright
    monkeypatch.setattr(
        "playwright.async_api.async_playwright",
        make_async_playwright(state),
    )
    # pretend there's a “prof” profile under tmp_path
    monkeypatch.setattr(
        "tiktok_downloader.cookies.list_chrome_profiles",
        lambda udd: {"prof": tmp_path},
    )
    # avoid “no chrome found” noise
    monkeypatch.setattr(
        "tiktok_downloader.cookies.get_chrome_executable_path",
        lambda: None,
    )

    await auto_fetch_cookies("prof", tmp_path, browser="chromium", headless=False)

    assert state["browser"] == "chromium"
    assert state["headless"] is False
    assert state["user_data_dir"] == str(tmp_path)
    assert state["goto"] == "https://www.tiktok.com/"


def test_cli_auto(monkeypatch: pytest.MonkeyPatch, tmp_path: str) -> None:
    captured: dict[str, Any] = {}

    async def fake_auto(
        profile: str, user_data_dir: str, browser: str, headless: bool
    ) -> list[dict[str, Any]]:
        captured["args"] = (profile, user_data_dir, browser, headless)
        return [
            {
                "name": "sid",
                "value": "1",
                "domain": "x",
                "path": "/",
                "secure": False,
                "httpOnly": False,
                "expirationDate": 0,
                "expires": 0,
            }
        ]

    saved: dict[str, Any] = {}

    def fake_save(self: object, cookies: list[dict[str, Any]], profile: str) -> None:
        saved["cookies"] = cookies
        saved["profile"] = profile

    monkeypatch.setattr("tiktok_downloader.cli.auto_fetch_cookies", fake_auto)
    monkeypatch.setattr("tiktok_downloader.cli.CookieManager.save", fake_save)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "cookies",
            "auto",
            "myprof",
            str(tmp_path),
            "--browser",
            # "webkit", #XXX: chromium is the only one supported
            "chromium",
            "--no-headless",
        ],
    )

    assert result.exit_code == 0
    assert captured["args"] == ("myprof", str(tmp_path), "chromium", False)
    assert saved["profile"] == "myprof"
    assert saved["cookies"][0]["name"] == "sid"
