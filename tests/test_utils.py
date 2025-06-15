from __future__ import annotations

import hashlib
from pathlib import Path

from tiktok_downloader.utils import (
    checksum,
    cleanup_temp_files,
    ensure_directory,
    is_duplicate,
    safe_filename,
)


def test_safe_filename() -> None:
    assert safe_filename("abc/def") == "abc_def"
    assert safe_filename("???") == "file"


def test_ensure_directory(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b"
    ensure_directory(target)
    assert target.exists() and target.is_dir()


def test_checksum_and_duplicate(tmp_path: Path) -> None:
    file = tmp_path / "data.bin"
    data = b"hello"
    file.write_bytes(data)

    expected = hashlib.sha256(data).hexdigest()
    assert checksum(file) == expected
    assert is_duplicate(file, expected)
    assert not is_duplicate(file, "0" * 64)


def test_cleanup_temp_files(tmp_path: Path) -> None:
    part = tmp_path / "file.part"
    tmp = tmp_path / "file.tmp"
    keep = tmp_path / "keep.bin"
    sub = tmp_path / "sub"
    sub.mkdir()
    nested = sub / "nested.part"

    part.write_text("1")
    tmp.write_text("2")
    keep.write_text("3")
    nested.write_text("4")

    cleanup_temp_files(tmp_path)

    assert not part.exists()
    assert not tmp.exists()
    assert not nested.exists()
    assert keep.exists()
