from pathlib import Path

from tiktok_downloader.cookies import CookieManager


def test_list_profiles(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text("[]")
    (tmp_path / "b.json").write_text("[]")
    (tmp_path / "ignore.txt").write_text("")

    mgr = CookieManager(tmp_path)
    names = mgr.list_profiles()
    assert set(names) == {"a", "b"}
