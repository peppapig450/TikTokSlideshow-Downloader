from pathlib import Path

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
