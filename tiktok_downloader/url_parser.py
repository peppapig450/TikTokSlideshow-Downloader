"""Utilities for parsing TikTok URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests


@dataclass(slots=True)
class TikTokURLInfo:
    """Information extracted from a TikTok URL."""

    raw_url: str
    resolved_url: str
    video_id: str
    content_type: str  # "video" or "slideshow"


def resolve_url(url: str, *, timeout: int = 10) -> str:
    """Follow redirects and return the final URL.

    Args:
        url: The URL to resolve.
        timeout: Request timeout in seconds.

    Returns:
        The resolved URL.
    """
    response = requests.get(url, allow_redirects=True, timeout=timeout)
    return response.url


def extract_video_id(url: str) -> str:
    """Extract the 19-digit video identifier from a TikTok URL.

    Args:
        url: TikTok URL.

    Returns:
        The 19-digit video ID.

    Raises:
        ValueError: If the ID cannot be found.
    """
    match = re.search(r"(\d{19})", url)
    if not match:
        raise ValueError("Could not extract video id from URL")
    return match.group(1)


def detect_content_type(url: str) -> str:
    """Determine whether the URL refers to a slideshow or regular video.

    Args:
        url: TikTok URL.

    Returns:
        "slideshow" if the path contains ``/photo/`` otherwise ``"video"``.
    """
    path = urlparse(url).path
    return "slideshow" if "/photo/" in path else "video"


def parse_tiktok_url(url: str) -> TikTokURLInfo:
    """Parse and validate a TikTok URL.

    Args:
        url: The (possibly shortened) TikTok URL to parse.

    Returns:
        A :class:`TikTokURLInfo` with the extracted information.

    Raises:
        ValueError: If the URL is invalid or cannot be parsed.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc.endswith("tiktok.com"):
        raise ValueError("Invalid TikTok URL")

    resolved = resolve_url(url)
    video_id = extract_video_id(resolved)
    content_type = detect_content_type(resolved)

    return TikTokURLInfo(url, resolved, video_id, content_type)
