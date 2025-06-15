from __future__ import annotations

import re
from pathlib import Path

__all__ = ["build_dest_path", "sanitize_filename", "unique_path"]


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
