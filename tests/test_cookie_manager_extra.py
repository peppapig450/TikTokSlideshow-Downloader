import json
from pathlib import Path
from typing import Any

import pytest

import tiktok_downloader.cookies as cookies_mod
from tiktok_downloader.cookies import (
    CookieManager,
    JSONCookie,
    _write_netscape,
    list_chrome_profiles,
    load_json_file,
    load_netscape_file,
    verify_cookie_profile,
)


def test_write_netscape_exception(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    class BadDict(dict):
        def get(self, *args: Any, **kwargs: Any) -> Any:
            raise ValueError("boom")

    good = {"name": "sid", "value": "1", "domain": ".x", "path": "/"}
    bad = BadDict(name="bad")
    dest = tmp_path / "out.txt"
    caplog.set_level("WARNING")
    with dest.open("w", encoding="utf-8") as fh:
        _write_netscape([good, bad], fh)
    text = dest.read_text()
    assert "Skipping cookie #1" in caplog.text
    assert ".x\tTRUE\t/\tFALSE\t0\tsid\t1" in text


def test_load_json_file_errors(tmp_path: Path) -> None:
    file = tmp_path / "bad.json"
    file.write_text("{}")
    with pytest.raises(ValueError):
        load_json_file(file)


def test_load_json_file_fields(tmp_path: Path) -> None:
    data = [
        {
            "name": "sid",
            "value": "1",
            "domain": "x",
            "secure": True,
            "httpOnly": True,
            "expirationDate": 123.4,
        }
    ]
    file = tmp_path / "c.json"
    file.write_text(json.dumps(data))
    result = load_json_file(file)[0]
    assert result["secure"] is True
    assert result["httpOnly"] is True
    assert result["expirationDate"] == 123  # noqa: PLR2004
    assert result["expires"] == 123  # noqa: PLR2004


def test_load_netscape_http_only_and_skip(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    text = (
        "# Netscape HTTP Cookie File\n"
        "# comment\n"
        "#HttpOnly_example.com\tFALSE\t/\tFALSE\t0\tsid\t1\n"
        "bad\tline\n"
        "example.com\tFALSE\t/\tFALSE\t0\tsid2\t2\n"
    )
    file = tmp_path / "c.txt"
    file.write_text(text)
    caplog.set_level("DEBUG")
    cookies = load_netscape_file(file)
    assert cookies[0]["httpOnly"] is True
    assert cookies[0]["name"] == "sid"
    assert cookies[1]["name"] == "sid2"
    assert "Skipping malformed cookie line" in caplog.text


def test_cookie_manager_save_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    mgr = CookieManager(tmp_path)
    caplog.set_level("ERROR")

    def fail_write(self: Path, *args: Any, **kwargs: Any) -> None:
        raise OSError("fail")

    monkeypatch.setattr(Path, "write_text", fail_write)
    with pytest.raises(OSError):
        mgr.save([], "prof")
    assert "Failed to save cookies" in caplog.text


def test_cookie_manager_load_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = CookieManager(tmp_path)
    json_file = tmp_path / "a.json"
    json_file.write_text("[]")
    netscape_file = tmp_path / "b.txt"
    netscape_file.write_text("# Netscape HTTP Cookie File\n")

    called: dict[str, int] = {"json": 0, "netscape": 0}
    monkeypatch.setattr(
        cookies_mod,
        "load_json_file",
        lambda p: called.__setitem__("json", called["json"] + 1) or [],
    )
    monkeypatch.setattr(
        cookies_mod,
        "load_netscape_file",
        lambda p: called.__setitem__("netscape", called["netscape"] + 1) or [],
    )

    mgr.load_from_file(json_file)
    mgr.load_from_file(netscape_file)
    assert called == {"json": 1, "netscape": 1}
    with pytest.raises(FileNotFoundError):
        mgr.load_from_file(tmp_path / "missing.txt")
    with pytest.raises(ValueError):
        mgr.load_from_file(json_file, fmt="unknown")


def test_list_chrome_profiles(tmp_path: Path) -> None:
    base = tmp_path / "Profiles"
    prof = base / "P1"
    prof.mkdir(parents=True)
    (prof / "Cookies").write_text("")
    (base / "NoCookies").mkdir()
    result = list_chrome_profiles(base)
    assert result == {"P1": prof}


class DummySession:
    def __init__(self) -> None:
        self.cookies = cookies_mod.requests.cookies.RequestsCookieJar()
        self.set_calls: list[tuple[str, str]] = []

    def __enter__(self) -> "DummySession":
        return self

    def __exit__(self, *exc: Any) -> None:
        pass

    def get(self, url: str, timeout: int = 10) -> Any:
        class R:
            ok = True

        return R()


def test_verify_cookie_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    sample: list[JSONCookie] = [{"name": "sid", "value": "1", "domain": "x", "path": "/"}]
    monkeypatch.setattr(cookies_mod.CookieManager, "load", lambda self, p: sample)
    monkeypatch.setattr(cookies_mod.requests, "Session", lambda: DummySession())
    assert verify_cookie_profile("prof") is True
