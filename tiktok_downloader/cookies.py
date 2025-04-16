from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any

import browser_cookie3


def load_cookies_from_file(json_path: Path) -> list[dict[str, Any]]:
    """
    Load cookies from a JSON file.

    Args:
        json_path (Path): Path to the JSON file containing cookie data.

    Returns:
        list[dict[str, Any]]: A list of cookies as dictionaries.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
        PermissionError: If the file cannot be read due to permissions.
        ValueError: If the JSON data is not a list of dictionaries.
    """
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))

        # Validate that data is a list
        if not isinstance(data, list):
            logging.error(
                "Expected JSON array, got %s from %s", type(data).__name__, json_path
            )
            raise ValueError("Expected JSON array, got %s", type(data).__name__)

        # Validate that all items are dictionaries
        if not all(isinstance(item, dict) for item in data):
            logging.error(
                "Expected JSON array of objects, but found non-object items in %s",
                json_path,
            )
            raise ValueError(
                "Expected JSON array of objects, but found non-object items"
            )

        logging.info("Loaded %d cookies from %s", len(data), json_path)
        return data

    except json.JSONDecodeError:
        logging.exception("Failed to parse JSON from %s", json_path)
        raise
    except (OSError, FileNotFoundError, PermissionError):
        logging.exception("Failed to read file %s", json_path)
        raise
