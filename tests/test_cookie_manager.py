import json
from pathlib import Path

import pytest

from tiktok_downloader.cookies import CookieManager


def test_list_profiles(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text("[]")
    (tmp_path / "b.json").write_text("[]")
    (tmp_path / "ignore.txt").write_text("")

    mgr = CookieManager(tmp_path)
    names = mgr.list_profiles()
    assert set(names) == {"a", "b"}


def test_write_netscape_domain_flags(tmp_path: Path) -> None:
    cookies = [
        {"name": "c1", "value": "v1", "domain": ".tiktok.com", "path": "/", "secure": True},
        {"name": "c2", "value": "v2", "domain": "example.com", "path": "/", "secure": False},
    ]
    dest = tmp_path / "cookies.txt"
    with dest.open("w", encoding="utf-8") as fh:
        from tiktok_downloader.cookies import _write_netscape

        _write_netscape(cookies, fh)

    lines = dest.read_text().splitlines()
    assert ".tiktok.com\tTRUE\t/\tTRUE\t0\tc1\tv1" in lines
    assert "example.com\tFALSE\t/\tFALSE\t0\tc2\tv2" in lines


def test_write_netscape_skips_invalid(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    cookies = [
        {"name": "good", "value": "val", "domain": ".domain.com", "path": "/"},
        {"name": "bad_no_domain", "value": "x", "path": "/"},
        {"value": "x", "domain": ".domain.com", "path": "/"},
    ]
    dest = tmp_path / "out.txt"
    with dest.open("w", encoding="utf-8") as fh:
        from tiktok_downloader.cookies import _write_netscape

        caplog.set_level("WARNING")
        _write_netscape(cookies, fh)

    lines = dest.read_text().splitlines()
    cookie_lines = [line for line in lines if line and not line.startswith("#")]
    assert cookie_lines == [".domain.com\tTRUE\t/\tFALSE\t0\tgood\tval"]
    assert "Skipping cookie #1" in caplog.text
    assert "Skipping cookie #2" in caplog.text


def test_write_netscape_none_domain(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    cookies = [{"name": "bad", "value": "x", "domain": None, "path": "/"}]
    dest = tmp_path / "none.txt"
    with dest.open("w", encoding="utf-8") as fh:
        from tiktok_downloader.cookies import _write_netscape

        caplog.set_level("WARNING")
        _write_netscape(cookies, fh)

    lines = dest.read_text().splitlines()
    cookie_lines = [line for line in lines if line and not line.startswith("#")]
    assert cookie_lines == []
    assert "Skipping cookie #0" in caplog.text


def test_load_returns_data(tmp_path: Path) -> None:
    cookies = [
        {
            "name": "sid",
            "value": "1",
            "domain": "example.com",
            "path": "/",
            "secure": False,
            "httpOnly": False,
            "expirationDate": 0,
            "expires": 0,
        }
    ]
    (tmp_path / "prof.json").write_text(json.dumps(cookies))

    mgr = CookieManager(tmp_path)
    loaded = mgr.load("prof")

    assert loaded == cookies


def test_save_writes_file(tmp_path: Path) -> None:
    cookies = [
        {
            "name": "sid",
            "value": "1",
            "domain": "example.com",
            "path": "/",
            "secure": False,
            "httpOnly": False,
            "expirationDate": 0,
            "expires": 0,
        }
    ]

    mgr = CookieManager(tmp_path)
    path = mgr.save(cookies, "prof")

    assert path == tmp_path / "prof.json"
    assert path.is_file()
    assert json.loads(path.read_text()) == cookies


def test_load_nonexistent_file(tmp_path: Path) -> None:
    mgr = CookieManager(tmp_path)
    with pytest.raises(FileNotFoundError):
        mgr.load("missing")


def test_load_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("{not json}")

    mgr = CookieManager(tmp_path)
    with pytest.raises(ValueError):
        mgr.load("bad")


def test_load_json_file(tmp_path: Path) -> None:
    from tiktok_downloader.cookies import load_json_file

    data = [{"name": "sid", "value": "1", "domain": "x", "path": "/"}]
    file = tmp_path / "c.json"
    file.write_text(json.dumps(data))

    cookies = load_json_file(file)
    assert cookies[0]["name"] == "sid"
    assert cookies[0]["domain"] == "x"


def test_load_netscape_file(tmp_path: Path) -> None:
    from tiktok_downloader.cookies import load_netscape_file

    text = "# Netscape HTTP Cookie File\nexample.com\tFALSE\t/\tFALSE\t0\tsid\t1\n"
    file = tmp_path / "c.txt"
    file.write_text(text)

    cookies = load_netscape_file(file)
    assert cookies[0]["name"] == "sid"
    assert cookies[0]["domain"] == "example.com"
