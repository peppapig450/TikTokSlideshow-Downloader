"""
Configuration settings for TikTok downloader.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar, Literal, TypedDict, TypeGuard

from .logger import Logger, LogLevel, get_logger

logger = get_logger(__name__)

type ConfigKey = Literal[
    "download_path",
    "browser_timeout",
    "headless",
    "debug",
    "max_retries",
    "chunk_size",
    "log_level",
    "user_agent",
]
type Validator = Callable[[Any], None]


def is_config_key(key: str) -> TypeGuard[ConfigKey]:
    return key in {
        "download_path",
        "browser_timeout",
        "headless",
        "debug",
        "max_retries",
        "chunk_size",
        "log_level",
        "user_agent",
    }


class ConfigDict(TypedDict):
    download_path: Path
    browser_timeout: int
    headless: bool
    debug: bool
    max_retries: int
    chunk_size: int
    log_level: LogLevel
    user_agent: str


class PartialConfigDict(TypedDict, total=False):
    download_path: Path
    browser_timeout: int
    headless: bool
    debug: bool
    max_retries: int
    chunk_size: int
    log_level: LogLevel
    user_agent: str


def validate_download_path(path: Any) -> None:
    if not (isinstance(path, Path | str) and bool(str(path).strip())):
        raise ValueError("'download_path' must be a non-empty path")

    if isinstance(path, Path) and not path.exists():
        logger.debug("'download_path' does not exist and will be created if needed.")


def validate_browser_timeout(timeout: Any) -> None:
    if not (isinstance(timeout, int) and timeout >= 1):
        raise ValueError("'browser_timeout' must be an int greater than 1")


def validate_headless(headless: Any) -> None:
    if not isinstance(headless, bool):
        raise ValueError("'headless' must be boolean")


def validate_debug(debug: Any) -> None:
    if not isinstance(debug, bool):
        raise ValueError("'debug' must be boolean")


def validate_max_retries(retries: Any) -> None:
    if not (isinstance(retries, int) and 0 <= retries <= 10):  # noqa: PLR2004
        raise ValueError("'max_retries' must be an int greater than 0 and less than 10")


def validate_chunk_size(chunk_size: Any) -> None:
    if not (isinstance(chunk_size, int) and chunk_size > 0):
        raise ValueError("'chunk_size' must be an int greater than 0")


def validate_log_level(log_level: Any) -> None:
    if not isinstance(log_level, LogLevel):
        raise ValueError("'log_level' must be a LogLevel")


def validate_user_agent(user_agent: Any) -> None:
    if not (isinstance(user_agent, str) and bool(user_agent.strip())):
        raise ValueError("'user_agent' must be a non-empty string")


class Config:
    """Configuration settings for TikTok downloader."""

    DEFAULT_CONFIG: ClassVar[ConfigDict] = {
        "download_path": Path("downloads"),
        "browser_timeout": 30_000,  # milliseconds
        "headless": True,
        "debug": False,
        "max_retries": 3,
        "chunk_size": 8192,
        "log_level": LogLevel.INFO,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.0.0 Safari/537.36"
        ),
    }

    _instance: ClassVar[Config | None] = None
    _initialized: ClassVar[bool] = False
    _init_lock: ClassVar[Lock] = Lock()

    converts: Mapping[type, Callable[[str], Any]] = {
        bool: lambda v: v.lower() in ("true", "1", "yes"),
        int: int,
        float: float,
        Path: Path,
        LogLevel: LogLevel,
    }

    # per-key validators: Raise ValueError on invalid
    validators: Mapping[ConfigKey, Validator] = {
        "download_path": validate_download_path,
        "browser_timeout": validate_browser_timeout,
        "headless": validate_headless,
        "debug": validate_debug,
        "max_retries": validate_max_retries,
        "chunk_size": validate_chunk_size,
        "log_level": validate_log_level,
        "user_agent": validate_user_agent,
    }

    def __new__(cls, config_dict: PartialConfigDict | None = None) -> Config:
        """Implement singleton pattern."""
        if cls._instance is None:
            instance = super().__new__(cls)
            cls._instance = instance
        return cls._instance

    def __init__(self, config_dict: PartialConfigDict | None) -> None:
        """
        Initialize configuration with default values, overridden by provided config.

        Args:
            config_dict: Dictionary of configuration values to override defaults
        """
        with self._init_lock:
            if self.__class__._initialized:
                return

            # Start with default config
            self._config = self.DEFAULT_CONFIG.copy()

            # Override with environment variables
            self._load_from_env()

            # Override with provided config
            if config_dict:
                self._config.update(config_dict)

            # Validate everything
            self._validate_config()

            # Setup logging based on configuration
            self._setup_logging()

            # Log config
            logger.debug("Configuration initialized: %r", self._config)

            self.__class__._initialized = True

    def _validate_config(self) -> None:
        """Run all key validators, raising ValueError on the first failure."""
        for key, validator in self.validators.items():
            try:
                validator(self._config[key])
            except Exception as e:
                error_msg = f"Configuration validation failed for '{key}'"
                logger.exception(error_msg)
                raise ValueError(f"{error_msg}: {e}") from e

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        env_prefix = "TIKTOK_DOWNLOADER_"
        for raw_key, default in self.DEFAULT_CONFIG.items():
            env_key = f"{env_prefix}{raw_key.upper()}"
            raw = os.getenv(env_key)
            if raw is None:
                continue

            target_type = type(default)
            parser = self.converts.get(target_type)
            if parser is None:
                logger.warning("No converter for %r; skipping %s", target_type, env_key)
                continue

            # Satisfy mypy by letting it know the key is valid *eye_roll*
            if not is_config_key(raw_key):
                continue

            try:
                self._config[raw_key] = parser(raw)
                logger.debug("Loaded %r from %r: %r", raw_key, env_key, self._config[raw_key])
            except Exception as e:
                logger.error("Failed to parse %r=%r for %r: %s", env_key, raw, raw_key, e)

    def _setup_logging(self) -> None:
        """Configure logging based on config settings."""
        log_level = self._config.get("log_level", LogLevel.INFO)

        # Enable debug mode if configured
        if debug_mode := self._config.get("debug", False):
            log_level = LogLevel.DEBUG

        Logger.setup(console_level=log_level)

        # Setup debug mode in logger
        Logger.set_debug_mode(debug=debug_mode)

        if debug_mode:
            logger.debug("Debug mode enabled.")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key is not found

        Returns:
            The configuration value or default
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        old_value = self.get(key)
        if is_config_key(key):
            self.validators[key](value)
            self._config[key] = value
        else:
            logger.warning(
                "Ignoring invalid key: %r or value: %r. Maintaining status quo.",
                key,
                value,
            )

        # If changing debug mode, update logging
        if key == "debug" and old_value != value:
            Logger.set_debug_mode(value)

        logger.debug("Config '%r' set to: %r", key, value)

    def update(self, config_dict: PartialConfigDict) -> None:
        """
        Update multiple configuration values.

        Args:
            config_dict: Dictionary of configuration values
        """
        validated: PartialConfigDict = {}

        for k, v in config_dict.items():
            if is_config_key(k):
                self.validators[k](v)
                # We know this is valid, so it's safe to ignore
                validated[k] = v  # type: ignore

        self._config.update(validated)

        # Update logging if debug mode changes
        if "debug" in validated:
            Logger.set_debug_mode(validated["debug"])

        logger.debug("Config updated with: %r", validated)

    @property
    def all(self) -> ConfigDict:
        """Get all the configuration values."""
        return self._config.copy()

    @property
    def download_path(self) -> Path:
        """Get the download path."""
        return self._config["download_path"]

    @download_path.setter
    def download_path(self, path: str | Path) -> None:
        """Set the download path."""
        self._config["download_path"] = Path(path)
        logger.debug("Downloaded path set to: %r", path)
