"""Command line interface for tiktok-downloader."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import click
from tqdm import tqdm

from . import (
    Config,
    CookieManager,
    DownloadManager,
    LogLevel,
    PartialConfigDict,
    TikTokURLInfo,
    VideoExtractor,
    get_logger,
    parse_tiktok_url,
)
from .config import ConfigKey, is_config_key
from .cookies import _write_netscape, fetch_cookies

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


@main.group()
def cookies() -> None:
    """Cookie management commands."""


@cookies.command()
@click.argument("profile")
@click.argument("dest", type=click.Path(path_type=Path))
def export(profile: str, dest: Path) -> None:
    """Export cookies in Netscape format."""
    try:
        cookies = CookieManager().load(profile)
        with Path(dest).open("w", encoding="utf-8") as file:
            _write_netscape(cookies, file)
        logger.info("Exported %d cookies to %s", len(cookies), dest)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@cookies.command()
@click.argument("profile")
@click.option(
    "--browser",
    type=click.Choice(["chromium", "firefox", "webkit"]),
    default="chromium",
)
@click.option("--headless/--no-headless", default=False)
@click.option("--user-data-dir", type=click.Path(path_type=Path))
def login(
    profile: str,
    browser: str,
    headless: bool,
    user_data_dir: Path | None,
) -> None:
    """Launch a browser for login and save the resulting cookies."""

    try:
        cookies = asyncio.run(fetch_cookies(profile, browser, headless, user_data_dir))
        CookieManager().save(cookies, profile)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@main.command()
@click.argument("urls", nargs=-1)
@click.option(
    "--url-file",
    "url_file",
    type=click.Path(path_type=Path),
    help="File with newline separated URLs",
)
@click.option("--cookie-profile", "cookie_profile", help="Name of saved cookie profile")
@click.option("--output", type=click.Path(path_type=Path), help="Output download directory")
@click.option("--browser-timeout", type=int)
@click.option("--headless/--no-headless", default=None)
@click.option("--debug/--no-debug", default=None)
@click.option("--max-retries", type=int)
@click.option("--chunk-size", type=int)
@click.option("--log-level", type=click.Choice([lvl.value for lvl in LogLevel]))
@click.option("--user-agent", type=str)
@click.option(
    "--quality",
    type=str,
    default=None,
    help="Video format preset such as best, worst, 720p, etc.",
)
@click.option("--list-formats", is_flag=True, help="List available formats and exit")
@click.pass_context
def download(  # noqa: PLR0913,C901,PLR0915,PLR0912
    ctx: click.Context,
    urls: tuple[str, ...],
    url_file: Path | None,
    cookie_profile: str | None,
    output: Path | None,
    browser_timeout: int | None,
    headless: bool | None,
    debug: bool | None,
    max_retries: int | None,
    chunk_size: int | None,
    log_level: str | None,
    user_agent: str | None,
    quality: str | None,
    list_formats: bool,
) -> None:
    """Download a TikTok video or slideshow.

    Use ``--quality`` to specify formats like ``best``, ``worst``, ``720p`` and
    ``--list-formats`` to show available options without downloading.
    """
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

    try:
        if cookie_profile:
            try:
                cookies = CookieManager().load(cookie_profile)
                logger.info("Loaded %d cookies from profile '%s'", len(cookies), cookie_profile)
            except Exception as exc:
                logger.error("Failed to load cookies: %s", exc)

        url_list: list[str] = list(urls)
        if url_file:
            for line in Path(url_file).read_text().splitlines():
                clean = line.strip()
                if clean and not clean.startswith("#"):
                    url_list.append(clean)
        if not url_list:
            raise click.UsageError("No URLs provided")

        infos: list[TikTokURLInfo] = []
        for u in url_list:
            try:
                info = parse_tiktok_url(u)
                infos.append(info)
                logger.info("Parsed URL info: %s", info)
            except Exception as exc:  # pragma: no cover - parse failure path
                click.echo(f"Failed to parse {u}: {exc}")

        if not infos:
            raise click.ClickException("No valid URLs to download")

        output_dir = cfg.download_path
        output_dir.mkdir(parents=True, exist_ok=True)

        bars: dict[Path, tqdm] = {}
        overall = tqdm(total=len(infos), desc="Overall", unit="url")

        def callback(dest: Path, downloaded: int, total: int) -> None:
            bar = bars.get(dest)
            if not bar:
                size_desc = tqdm.format_sizeof(total) if total else "unknown"
                bar = tqdm(
                    total=total or None,
                    unit="B",
                    unit_scale=True,
                    desc=f"{dest.name} ({size_desc})",
                    leave=False,
                )
                bars[dest] = bar
            bar.update(downloaded - bar.n)

        manager = DownloadManager(cfg, progress=False, progress_callback=callback)

        async def run_all(infos: Iterable[TikTokURLInfo]) -> None:
            sem = asyncio.Semaphore(manager.concurrency)

            async def worker(info: TikTokURLInfo) -> None:
                try:
                    async with sem:
                        if info.content_type == "video":
                            extractor = VideoExtractor(
                                cfg,
                                cookie_profile=cookie_profile,
                                quality=quality,
                            )
                            if list_formats:
                                lines = await asyncio.to_thread(
                                    extractor.list_formats, info.resolved_url
                                )
                                for line in lines:
                                    click.echo(line)
                                return
                            result = await asyncio.to_thread(
                                extractor.extract, info.resolved_url, download=True
                            )
                            dest = result.filepath or output_dir / (info.video_id + ".bin")
                        else:
                            await manager.download_all([info.resolved_url], output_dir)
                            dest = output_dir / (info.video_id + ".bin")
                        click.echo(f"Saved to {dest}")
                except Exception as exc:  # pragma: no cover - network error path
                    click.echo(f"Failed to download {info.raw_url}: {exc}")
                finally:
                    overall.update(1)

            async with asyncio.TaskGroup() as group:
                for info in infos:
                    group.create_task(worker(info))

        asyncio.run(run_all(infos))
        for bar in bars.values():
            bar.close()
        overall.close()
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise click.ClickException(f"Invalid input: {exc}") from exc
        raise click.ClickException(str(exc)) from exc
