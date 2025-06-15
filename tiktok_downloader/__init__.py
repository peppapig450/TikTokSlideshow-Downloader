"""TikTok Downloader package."""

from .config import Config, ConfigDict, PartialConfigDict, is_config_key
from .cookies import CookieManager
from .downloader import DownloadManager, run_download
from .extractors.base import BaseExtractor
from .logger import Logger, LogLevel, get_logger
from .url_parser import TikTokURLInfo, parse_tiktok_url
from .utils import build_dest_path, sanitize_filename, unique_path

__all__ = [
    "BaseExtractor",
    "Config",
    "ConfigDict",
    "CookieManager",
    "DownloadManager",
    "LogLevel",
    "Logger",
    "PartialConfigDict",
    "TikTokURLInfo",
    "build_dest_path",
    "get_logger",
    "is_config_key",
    "parse_tiktok_url",
    "run_download",
    "sanitize_filename",
    "unique_path",
]
