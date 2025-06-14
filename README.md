# TikTokSlideshow-Downloader

## Command line usage

The package installs the ``tiktok-downloader`` script. Use the ``download``
command to fetch a TikTok video or slideshow:

```bash
tiktok-downloader download <url> [OPTIONS]
```

Alternatively, run the module directly:

```bash
python -m tiktok_downloader download <url> [OPTIONS]
```

Run ``tiktok-downloader download --help`` to see all configuration options.

To export cookies saved in a JSON profile:

```bash
tiktok-downloader cookies export <profile> <destination>
```
