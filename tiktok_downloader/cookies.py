"""
Cookie management functionality for TikTok content extraction.

This module provides an instance-based CookieManager that can load,
save, convert, and simplify cookies in JSON and Netscape formats. It
supports both JSONCookie dictionaries and Playwright Cookie objects.
"""

from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from platformdirs import user_data_dir
from playwright.sync_api import Cookie
from typing import TypedDict, Protocol, Iterable, TextIO

from .logger import get_logger

logger = get_logger(__name__)


class JSONCookie(TypedDict, total=False):
    """
    TypedDict for JSON-serializable cookies.

    Attributes:
        name: The name of the cookie.
        value: The value of the cookie.
        domain: The domain for which the cookie is valid.
        path: The URL path for which the cookie is valid.
        secure: Whether the cookie is only sent over HTTPS.
        httpOnly: Whether the cookie is inaccessible to JavaScript.
        expirationDate: The UNIX timestamp when the cookie expires.
        expires: Alias for expirationDate.
    """

    name: str
    value: str
    domain: str
    path: str
    secure: bool
    httpOnly: bool
    expirationDate: float
    expires: float


class CookieLike(Protocol):
    """
    Protocol for objects that have cookie-like attributes.

    Attributes:
        name: The name of the cookie.
        value: The value of the cookie.
        domain: The domain for which the cookie is valid.
        path: The URL path for which the cookie is valid.
        secure: Whether the cookie is only sent over HTTPS.
        expires: The UNIX timestamp when the cookie expires.
    """

    name: str
    value: str
    domain: str
    path: str
    secure: bool
    expires: float
