from __future__ import annotations

import hashlib
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

__all__ = [
    "build_dest_path",
    "checksum",
    "cleanup_temp_files",
    "ensure_directory",
    "guess_extension",
    "is_duplicate",
    "safe_filename",
    "sanitize_filename",
    "unique_path",
]


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safe version of ``name``."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    safe = safe.strip("._")
    return safe or "file"


def unique_path(path: Path) -> Path:
    """Generate a unique file path if ``path`` already exists."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def build_dest_path(directory: Path, name: str, ext: str = "bin") -> Path:
    """Construct a unique destination path inside ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    ext = f".{ext}" if ext and not ext.startswith(".") else ext
    safe_name = sanitize_filename(name)
    path = directory / f"{safe_name}{ext}"
    return unique_path(path)


def safe_filename(name: str) -> str:
    """Alias of :func:`sanitize_filename`. Provided for convenience."""

    return sanitize_filename(name)


def ensure_directory(path: Path) -> None:
    """Create ``path`` if it doesn't already exist."""

    path.mkdir(parents=True, exist_ok=True)


def guess_extension(url: str, content_type: str | None) -> str:
    """Return the best file extension for ``url`` and ``content_type``."""

    ct = content_type.split(";")[0].strip() if content_type else ""
    ext = mimetypes.guess_extension(ct)
    if ext:
        return ext
    suffix = Path(urlparse(url).path).suffix
    return suffix if suffix else ".bin"


def checksum(path: Path) -> str:
    """Compute the SHA256 checksum of ``path``."""

    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def is_duplicate(path: Path, checksum_str: str) -> bool:
    """Return ``True`` if ``path`` exists and matches ``checksum_str``."""

    return path.is_file() and checksum(path) == checksum_str


def cleanup_temp_files(dir: Path) -> None:
    """Remove ``*.part`` and ``*.tmp`` files recursively within ``dir``."""

    for pattern in ("*.part", "*.tmp"):
        for file in dir.rglob(pattern):
            if file.is_file():
                file.unlink()
