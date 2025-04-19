import logging
import logging.handlers
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from tiktok_downloader.logger import Logger, LogLevel, get_logger


@pytest.fixture(autouse=True)
def reset_logger(monkeypatch: MonkeyPatch) -> Generator[None, None, None]:
    """
    Reset the Logger singleton and root handlers before each test.
    """
    # Reset singleton instance and stored child loggers
    monkeypatch.setattr(Logger, "_instance", None)
    monkeypatch.setattr(Logger, "_loggers", {})

    # Remove all handlers from the root logger
    root = logging.getLogger()
    for handler in root.handlers:
        root.removeHandler(handler)

    yield

    # Clean up any handlers added during the test
    for handler in root.handlers:
        root.removeHandler(handler)


def test_setup_creates_console_and_file_handlers(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    Logger.setup(
        console_level=LogLevel.DEBUG,
        file_level=LogLevel.WARNING,
        log_file=log_file,
        capture_warnings=False,
    )

    root = logging.getLogger()
    handlers = root.handlers
    assert len(handlers) == 2  # noqa: PLR2004

    console = next(h for h in handlers if isinstance(h, logging.StreamHandler))
    file_h = next(
        h for h in handlers if isinstance(h, logging.handlers.RotatingFileHandler)
    )

    assert console.level == logging.DEBUG
    assert file_h.level == logging.WARNING
    # RotatingFileHandler stores the path in .baseFilename
    assert Path(file_h.baseFilename) == log_file
    # File should have been created (empty)
    assert log_file.is_file()


def test_get_logger_returns_same_child_and_propagates(tmp_path: Path) -> None:
    Logger.setup(log_file=tmp_path / "foo.log")
    a = get_logger("mypkg.module")
    b = get_logger("mypkg.module")
    c = get_logger("other")

    assert (
        a is b
    ), "Repeated get_logger calls with the same name should return the same object"
    assert a is not c
    assert a.propagate is True, "Child loggers should propagate to the root handlers"


def test_set_debug_mode_toggles_console_handler_level(tmp_path: Path) -> None:
    Logger.setup(
        console_level=LogLevel.INFO,
        file_level=LogLevel.INFO,
        log_file=tmp_path / "bar.log",
    )

    root = logging.getLogger()
    console = next(
        h
        for h in root.handlers
        if isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
    )

    # Default was INFO
    assert console.level == logging.INFO

    # Turn on debug
    Logger.set_debug_mode(debug=True)
    assert console.level == logging.DEBUG

    # Turn off debug (back to INFO)
    Logger.set_debug_mode(debug=False)
    assert console.level == logging.INFO


def test_singleton_init_only_once(tmp_path: Path) -> None:
    # First setup with one file
    log_1 = tmp_path / "one.log"
    Logger.setup(log_file=log_1, console_level=LogLevel.INFO, file_level=LogLevel.INFO)
    root = logging.getLogger()
    initial_handlers = root.handlers

    # Second setup with a different file
    log_2 = tmp_path / "two.log"
    Logger.setup(
        log_file=log_2, console_level=LogLevel.DEBUG, file_level=LogLevel.DEBUG
    )

    # Handlers should not be duplicated
    assert root.handlers == initial_handlers, "Handlers should not be duplicated."

    # File handler should still point at the first file
    file_handler = next(
        h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
    )
    assert Path(file_handler.baseFilename) == log_1
