"""Command line interface for tiktok-downloader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from . import Config, CookieManager, LogLevel, PartialConfigDict, get_logger, parse_tiktok_url
from .config import ConfigKey, is_config_key

logger = get_logger(__name__)


@click.group()
@click.pass_context
def main(ctx: click.Context) -> None:
    """TikTok downloader command line interface."""
    ctx.obj = {"config": Config(None)}


def _collect_config_updates(**options: Any) -> PartialConfigDict:
    updates: PartialConfigDict = {}
    for key, value in options.items():
        if value is None:
            continue

        if key == "output":
            updates["download_path"] = Path(value)
        elif key == "log_level":
            updates["log_level"] = LogLevel(value)
        elif is_config_key(key):
            cfg_key: ConfigKey = key
            updates[cfg_key] = value
    return updates


@main.command()
@click.argument("url")
@click.option("--cookie-profile", "cookie_profile", help="Name of saved cookie profile")
@click.option("--output", type=click.Path(path_type=Path), help="Output download directory")
@click.option("--browser-timeout", type=int)
@click.option("--headless/--no-headless", default=None)
@click.option("--debug/--no-debug", default=None)
@click.option("--max-retries", type=int)
@click.option("--chunk-size", type=int)
@click.option("--log-level", type=click.Choice([lvl.value for lvl in LogLevel]))
@click.option("--user-agent", type=str)
@click.pass_context
def download(  # noqa: PLR0913
    ctx: click.Context,
    url: str,
    cookie_profile: str | None,
    output: Path | None,
    browser_timeout: int | None,
    headless: bool | None,
    debug: bool | None,
    max_retries: int | None,
    chunk_size: int | None,
    log_level: str | None,
    user_agent: str | None,
) -> None:
    """Download a TikTok video or slideshow."""
    cfg: Config = ctx.obj["config"]

    updates = _collect_config_updates(
        output=output,
        browser_timeout=browser_timeout,
        headless=headless,
        debug=debug,
        max_retries=max_retries,
        chunk_size=chunk_size,
        log_level=log_level,
        user_agent=user_agent,
    )
    if updates:
        cfg.update(updates)

    logger.info("Configuration loaded: %r", cfg.all)

    if cookie_profile:
        try:
            cookies = CookieManager().load(cookie_profile)
            logger.info("Loaded %d cookies from profile '%s'", len(cookies), cookie_profile)
        except Exception as exc:
            logger.error("Failed to load cookies: %s", exc)

    info = parse_tiktok_url(url)
    logger.info("Parsed URL info: %s", info)
