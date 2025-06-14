"""Module entrypoint for ``python -m tiktok_downloader``."""

from __future__ import annotations

from . import Config, cli, get_logger


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
