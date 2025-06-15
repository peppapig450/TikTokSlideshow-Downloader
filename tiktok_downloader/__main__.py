"""Module entrypoint for ``python -m tiktok_downloader``."""

from __future__ import annotations

import sys

MIN_VERSION = (3, 12)

if sys.version_info < MIN_VERSION:
    current = ".".join(str(v) for v in sys.version_info[:3])
    raise SystemExit(
        f"Python {MIN_VERSION[0]}.{MIN_VERSION[1]} or higher is required, but {current} is running."
    )

from . import Config, cli, get_logger  # noqa: E402


def main() -> int:
    """Run the command line interface with config and logging initialized."""
    Config(None)
    logger = get_logger(__name__)
    try:
        cli.main()
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        logger.exception("Unhandled error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
