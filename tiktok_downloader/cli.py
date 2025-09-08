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
from .cookies import (
    JSONCookie,
    _write_netscape,
    verify_cookie_profile,
)
from .extractors import SlideshowExtractor
from .profile import ProfileScraper

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


@cookies.command(hidden=True)
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
    help="Browser engine to use",
)
@click.option("--headless/--no-headless", default=False, help="Run the browser without UI")
@click.option(
    "--user-data-dir",
    type=click.Path(path_type=Path),
    help="Location of user data directory",
)
def login(
    profile: str,
    browser: str,
    headless: bool,
    user_data_dir: Path | None,
) -> None:
    """Launch a browser for login and save the resulting cookies."""

    raise click.ClickException("Cookie login is temporarily disabled")


# TODO: only support Chrome for now
@cookies.command(name="auto", hidden=True)
@click.argument("profile", default="Default", required=False)
@click.argument("user_data_dir", default="detect", required=False)
@click.option(
    "--browser",
    type=str,
    default="chromium",
    help="Browser engine to use",
)
@click.option("--headless/--no-headless", default=True, help="Run the browser without UI")
def auto_cookies(
    profile: str,
    user_data_dir: str,
    browser: str,
    headless: bool,
) -> None:
    """Fetch cookies from an existing browser profile."""

    raise click.ClickException("Cookie login is temporarily disabled")


@cookies.command(name="list")
def list_profiles() -> None:
    """Print available cookie profiles."""
    profiles = CookieManager().list_profiles()
    for prof in profiles:
        click.echo(prof)


@cookies.command()
@click.argument("profile")
def verify(profile: str) -> None:
    """Verify that saved cookies work for TikTok."""

    try:
        if verify_cookie_profile(profile):
            click.echo(f"Cookie profile '{profile}' is valid.")
        else:
            raise click.ClickException(f"Cookie profile '{profile}' is invalid.")
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
@click.option("--cookie-file", type=click.Path(path_type=Path), help="Path to cookie file")
@click.option(
    "--cookie-format",
    type=click.Choice(["json", "netscape"]),
    default=None,
    help="Format of cookie file",
)
@click.option("--output", type=click.Path(path_type=Path), help="Output download directory")
@click.option("--browser-timeout", type=int, help="Browser timeout in milliseconds")
@click.option("--headless/--no-headless", default=None, help="Run the browser without UI")
@click.option("--debug/--no-debug", default=None, help="Enable verbose debug logging")
@click.option("--max-retries", type=int, help="Maximum download retries")
@click.option("--chunk-size", type=int, help="Stream chunk size in bytes")
@click.option(
    "--log-level",
    type=click.Choice([lvl.value for lvl in LogLevel]),
    help="Set logging verbosity",
)
@click.option("--user-agent", type=str, help="HTTP user agent string")
@click.option(
    "--quality",
    type=str,
    default=None,
    help="Video format preset such as best, worst, 720p, etc.",
)
@click.option(
    "--concurrency",
    type=int,
    default=3,
    show_default=True,
    help="Maximum concurrent downloads",
)
@click.option("--list-formats", is_flag=True, help="List available formats and exit")
@click.pass_context
def download(  # noqa: PLR0913,C901,PLR0915,PLR0912
    ctx: click.Context,
    urls: tuple[str, ...],
    url_file: Path | None,
    cookie_profile: str | None,
    cookie_file: Path | None,
    cookie_format: str | None,
    output: Path | None,
    browser_timeout: int | None,
    headless: bool | None,
    debug: bool | None,
    max_retries: int | None,
    chunk_size: int | None,
    log_level: str | None,
    user_agent: str | None,
    quality: str | None,
    concurrency: int,
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

    cookie_data: list[JSONCookie] | None = None
    if cookie_file is not None:
        try:
            cookie_data = CookieManager().load_from_file(cookie_file, cookie_format)
            logger.info("Loaded %d cookies from %s", len(cookie_data), cookie_file)
        except Exception as exc:
            logger.error("Failed to load cookies: %s", exc)
    else:
        if cookie_profile is None:
            profiles = CookieManager().list_profiles()
            cookie_profile = profiles[0] if len(profiles) == 1 else "Default"
        if cookie_profile:
            try:
                cookie_data = CookieManager().load(cookie_profile)
                logger.info(
                    "Loaded %d cookies from profile '%s'",
                    len(cookie_data),
                    cookie_profile,
                )
            except Exception as exc:
                logger.error("Failed to load cookies: %s", exc)

    logger.info("Configuration loaded: %r", cfg.all)

    try:
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
            if bar is None:
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

        manager = DownloadManager(
            cfg,
            concurrency=concurrency,
            progress=False,
            progress_callback=callback,
        )

        async def run_all(infos: Iterable[TikTokURLInfo]) -> None:  # noqa: C901
            sem = asyncio.Semaphore(manager.concurrency)

            async def worker(info: TikTokURLInfo) -> None:
                try:
                    async with sem:
                        if info.content_type == "video":
                            kw: dict[str, Any] = {}
                            if cookie_data is not None:
                                kw["cookies"] = cookie_data
                            elif cookie_profile:
                                kw["cookie_profile"] = cookie_profile
                            extractor = VideoExtractor(
                                cfg,
                                quality=quality,
                                **kw,
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
                            click.echo(f"Saved to {dest}")
                        else:
                            slide_kw: dict[str, Any] = {}
                            if cookie_data is not None:
                                slide_kw["cookies"] = cookie_data
                            elif cookie_profile:
                                slide_kw["cookie_profile"] = cookie_profile
                            slide_ext = SlideshowExtractor(
                                cfg,
                                **slide_kw,
                            )
                            slide_res = await slide_ext.extract(info.resolved_url)
                            dest_dir = output_dir / info.video_id
                            await manager.download_all(slide_res.urls, dest_dir)
                            click.echo(f"Saved to {dest_dir}")
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


@main.command()
@click.argument("username")
@click.option("--cookie-profile", "cookie_profile", help="Name of saved cookie profile")
@click.option("--cookie-file", type=click.Path(path_type=Path), help="Path to cookie file")
@click.option(
    "--cookie-format",
    type=click.Choice(["json", "netscape"]),
    default=None,
    help="Format of cookie file",
)
@click.option("--output", type=click.Path(path_type=Path), help="Output download directory")
@click.option("--browser-timeout", type=int, help="Browser timeout in milliseconds")
@click.option("--headless/--no-headless", default=None, help="Run the browser without UI")
@click.option("--debug/--no-debug", default=None, help="Enable verbose debug logging")
@click.option("--max-retries", type=int, help="Maximum download retries")
@click.option("--chunk-size", type=int, help="Stream chunk size in bytes")
@click.option(
    "--log-level",
    type=click.Choice([lvl.value for lvl in LogLevel]),
    help="Set logging verbosity",
)
@click.option("--user-agent", type=str, help="HTTP user agent string")
@click.option(
    "--quality",
    type=str,
    default=None,
    help="Video format preset such as best, worst, 720p, etc.",
)
@click.option(
    "--concurrency",
    type=int,
    default=3,
    show_default=True,
    help="Maximum concurrent downloads",
)
@click.option("--list-formats", is_flag=True, help="List available formats and exit")
@click.pass_context
def profile(  # noqa: PLR0913
    ctx: click.Context,
    username: str,
    cookie_profile: str | None,
    cookie_file: Path | None,
    cookie_format: str | None,
    output: Path | None,
    browser_timeout: int | None,
    headless: bool | None,
    debug: bool | None,
    max_retries: int | None,
    chunk_size: int | None,
    log_level: str | None,
    user_agent: str | None,
    quality: str | None,
    concurrency: int,
    list_formats: bool,
) -> None:
    """Download all posts from ``username``."""
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

    cookie_data: list[JSONCookie] | None = None
    if cookie_file is not None:
        try:
            cookie_data = CookieManager().load_from_file(cookie_file, cookie_format)
            logger.info("Loaded %d cookies from %s", len(cookie_data), cookie_file)
        except Exception as exc:
            logger.error("Failed to load cookies: %s", exc)

    scraper = ProfileScraper(
        username,
        cfg,
        cookies=cookie_data,
        cookie_profile=None if cookie_data is not None else cookie_profile,
    )
    try:
        urls = asyncio.run(scraper.fetch_urls_browser())
    except Exception as exc:
        logger.error("Browser scraping failed: %s", exc)
        urls = []

    if not urls:
        try:
            urls = scraper.fetch_urls()
        except Exception as exc:  # pragma: no cover - network path
            raise click.ClickException(str(exc)) from exc

    if not urls:
        click.echo("No posts found")
        return

    ctx.invoke(
        download,
        urls=tuple(urls),
        url_file=None,
        cookie_profile=cookie_profile,
        cookie_file=cookie_file,
        cookie_format=cookie_format,
        output=output,
        browser_timeout=browser_timeout,
        headless=headless,
        debug=debug,
        max_retries=max_retries,
        chunk_size=chunk_size,
        log_level=log_level,
        user_agent=user_agent,
        quality=quality,
        concurrency=concurrency,
        list_formats=list_formats,
    )
