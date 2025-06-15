# TikTokSlideshow-Downloader

## Command line usage

The package installs the ``tiktok-downloader`` script. Use the ``download``
command to fetch a TikTok video or slideshow:

```bash
tiktok-downloader download <url> [OPTIONS]
```

Run ``tiktok-downloader download --help`` to see all configuration options.
The ``--concurrency`` option controls how many downloads run in parallel.

To export cookies saved in a JSON profile:

```bash
tiktok-downloader cookies export <profile> <destination>
```

To create a new cookie profile via a logged-in browser session:

```bash
tiktok-downloader cookies login <profile> [--browser chromium|firefox|webkit] \
    [--headless] [--user-data-dir DIR]
```

Run the command, log into TikTok in the opened browser window and press Enter
when ready. The cookies will be saved under ``<profile>.json`` for reuse.

To fetch cookies directly from an existing Chrome/Chromium profile:

```bash
tiktok-downloader cookies auto <profile> <user-data-dir> [--browser chromium|firefox|webkit] \
    [--headless/--no-headless]
```

To verify that a saved cookie profile is still valid:

```bash
tiktok-downloader cookies verify <profile>
```

## Module entry point

Run the CLI with:

```bash
python -m tiktok_downloader download <url> [OPTIONS]
```

This entry point loads your configuration and handles Ctrl+C gracefully.
