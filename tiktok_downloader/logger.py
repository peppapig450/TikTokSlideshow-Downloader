"""
Logging configuration for TikTok downloader.
"""

from __future__ import annotations

import logging
import logging.config
import logging.handlers
import sys
from enum import StrEnum
from os import PathLike
from pathlib import Path
from threading import Lock
from typing import ClassVar, Final, Self

from platformdirs import user_log_dir


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Logger:
    """
    Centralized logging configuration for TikTok downloader.

    This class provides a singleton logger instance with configurable log levels,
    formatters, and rotating file handlers for both console and file output.
    """

    APP_NAME: Final[str] = "tiktok-downloader"
    APP_AUTHOR: Final[str] = "tiktok-downloader"

    DEFAULT_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    CONSOLE_FORMAT: Final[str] = "%(levelname)s: %(message)s"

    # Singleton instance and related bookkeeping
    _instance: ClassVar[Self | None] = None
    _loggers: ClassVar[dict[str, logging.Logger]] = {}
    _init_lock: ClassVar[Lock] = Lock()

    # Instance attributes (for type checking)
    _initialized: bool
    console_level: int
    file_level: int
    capture_warnings: bool
    log_file: Path

    def __new__(  # noqa: PLR0913
        cls,
        console_level: LogLevel = LogLevel.INFO,
        file_level: LogLevel = LogLevel.DEBUG,
        log_file: PathLike[str] | None = None,
        capture_warnings: bool = True,
        *,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> Self:
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instance = instance
        return cls._instance

    def __init__(  # noqa: PLR0913
        self,
        console_level: LogLevel = LogLevel.INFO,
        file_level: LogLevel = LogLevel.DEBUG,
        log_file: PathLike | None = None,
        capture_warnings: bool = True,
        *,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> None:
        """
        Initialize the logger (only on first call).

        Args:
            console_level: minimum level for console output
            file_level: minimum level for file output
            log_file: path to log file (defaults to platform user log dir)
            capture_warnings: whether to capture Python warnings
            max_bytes: rotate file when it reaches this size (in bytes)
            backup_count: number of rotated files to keep
        """
        with self._init_lock:
            if self._initialized:
                return

            # Convert level names to ints
            self.console_level = getattr(logging, console_level)
            self.file_level = getattr(logging, file_level)
            self.capture_warnings = capture_warnings

            # Determine log file path
            if log_file:
                self.log_file = Path(log_file)
            else:
                log_dir = Path(
                    user_log_dir(
                        appname=self.APP_NAME,
                        appauthor=self.APP_AUTHOR,
                        version=None,
                        ensure_exists=True,
                    )
                )
                self.log_file = log_dir / f"{self.APP_NAME}.log"
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

            # Configure handlers once
            self._configure_handlers(max_bytes, backup_count)

            # Optionally capture warnings
            if self.capture_warnings:
                logging.captureWarnings(True)

            self._initialized = True

    def _configure_handlers(self, max_bytes: int, backup_count: int) -> None:
        """
        Set up and install console and rotating file handlers on the root logger.
        """
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.console_level)
        console_handler.setFormatter(logging.Formatter(self.CONSOLE_FORMAT, style="%"))

        file_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(self.file_level)
        file_handler.setFormatter(logging.Formatter(self.DEFAULT_FORMAT, style="%"))

        # Override any existing handlers
        logging.basicConfig(
            level=logging.DEBUG,
            handlers=[console_handler, file_handler],
            force=True,
        )

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get (or create) a child logger with the given name.
        Child loggers inherit handlers from the root.
        """
        if name not in self._loggers:
            logger = logging.getLogger(name)
            # prevent double-handling if someone adds handlers to child
            logger.propagate = True
            self._loggers[name] = logger
        return self._loggers[name]

    @classmethod
    def setup(  # noqa: PLR0913
        cls,
        console_level: LogLevel = LogLevel.INFO,
        file_level: LogLevel = LogLevel.DEBUG,
        log_file: PathLike | None = None,
        capture_warnings: bool = True,
        *,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> None:
        """
        Convenience method to configure logging once at application start.
        """
        cls(
            console_level=console_level,
            file_level=file_level,
            log_file=log_file,
            capture_warnings=capture_warnings,
            max_bytes=max_bytes,
            backup_count=backup_count,
        )

    @classmethod
    def set_debug_mode(cls, debug: bool = True) -> None:
        """
        Swap console output between INFO and DEBUG on the fly.
        """
        root = logging.getLogger()
        for handler in root.handlers:
            if (
                isinstance(handler, logging.StreamHandler)
                and handler.stream is sys.stdout
            ):
                handler.setLevel(logging.DEBUG if debug else logging.INFO)
                break


def get_logger(name: str) -> logging.Logger:
    """
    Initialize the Logger singleton (if needed) and return a child logger.
    """
    return Logger().get_logger(name)
