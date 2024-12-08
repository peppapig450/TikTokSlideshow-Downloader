import argparse
import itertools
import json
from pathlib import Path

import requests
import yt_dlp
from browser_cookie3 import brave, chrome, edge, firefox, opera
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Map browser names to their browser_cookie3 functions
BROWSER_MAP = {
    "chrome": chrome,
    "firefox": firefox,
    "edge": edge,
    "opera": opera,
    "brave": brave,
}


def load_cookies_from_browser(browser_name: str):
    """
    Load cookies from a browser for the given domain.

    :param domain_name: The domain to fetch cookies for (default: 'tiktok.com').
    :param profile_name: Name of the profile (defaults to "default").
    :return: List of cookies as dictionaries.
    """
    browser_name = browser_name.lower()
    fetch_cookies = BROWSER_MAP.get(browser_name)
    if not fetch_cookies:
        raise ValueError(
            f"Unsupported browser '{browser_name}'. Supported browsers: {', '.join(BROWSER_MAP.keys())}."
        )

    # Fetch cookies for TikTok, with optional profile name
    return fetch_cookies(domain_name="tiktok.com")


def load_cookies_from_file(file_path: str):
    """
    Load cookies from a JSON file.

    :param file_path: Path to the JSON file.
    :return: List of cookies as dictionaries.
    """
    return json.loads(Path(file_path).read_text())


# TODO: auto load cookies from browser files
# Load cookies into the browser
def load_cookies(driver, cookies):
    """
    Load cookies into the Selenium WebDriver.

    :param driver: Selenium WebDriver instance.
    :param cookies: List of cookies to add.
    """
    for cookie in cookies:
        driver.add_cookie(
            {
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie["domain"],
            }
        )


# Fetch the TikTok page
def fetch_page(url: str, cookies):
    options = Options()
    # options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("start-maximized")
    options.add_argument("enable-automation")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Set up WebDriver Manager
    driver = webdriver.Chrome(
        options=options, service=ChromeService(ChromeDriverManager().install())
    )
    driver.get("https://www.tiktok.com/")

    try:
        # Load cookies into the driver
        load_cookies(driver, cookies)
        driver.refresh()

        # Navigate to the target URL
        driver.get(url)
        # Wait for the page to load completely
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".css-brxox6-ImgPhotoSlide.e10jea832")
            )
        )
        return driver.page_source
    except Exception as e:
        print(f"Failed to fetch the page: {e}")
        return None
    finally:
        driver.quit()


# Parse image links from the slideshow
def parse_slideshow_links(html):
    soup = BeautifulSoup(html, "html.parser")
    image_tags = soup.select(".css-brxox6-ImgPhotoSlide.e10jea832")
    image_links = [img["src"] for img in image_tags if "src" in img.attrs]

    # Flatten any nested lists
    flat_image_links = list(
        itertools.chain(
            *[
                sublist if isinstance(sublist, list) else [sublist]
                for sublist in image_links
            ]
        )
    )
    return flat_image_links


# Download images
def download_images(image_links: list[str], output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    for link in image_links:
        try:
            response = requests.get(link, stream=True)
            response.raise_for_status()
            file_name = link.split("/")[-1].split("?")[0]
            file_path = output_dir / file_name
            with file_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            print(f"Downloaded: {file_name}")
        except requests.RequestException as e:
            print(f"Failed to download {link}: {e}")


# Detect content type using regex
def is_slideshow(url: str):
    return "photo" in url


# Download a TikTok video
# TODO: error handling in case it's a priv video? tell user to retry specifying cookies
def download_video(
    url, output_dir, cookies: str | None, browser_name=None, profile_name="default"
):
    """
    Downloads a TikTok video using yt-dlp, with support for cookies.

    :param url: The URL of the TikTok video.
    :param output_dir: Directory to save the downloaded video.
    :param cookies: Cookies to allow saving of private videos.
    :param browser_name: Browser name if cookies are loaded from a browser.
    :param profile_name: Profile name if cookies are loaded from a browser.
    """

    # Choose whether to pass a cookie file or browser-based cookies
    if isinstance(cookies, str):
        cookies_path = Path(cookies)
        if cookies_path.exists() and cookies_path.is_file():
            if "txt" not in cookies_path.suffix:
                raise ValueError(
                    f"{cookies} is not a txt file. When downloading videos a Netscape formatted txt file is required, or use the browser based cookie loading."
                )

        # TODO: use common dictionary then modify it based on the cookies method
        # Pass cookie file for yt-dlp
        ydl_opts = {
            "outtmpl": f"{output_dir}/%(title)s.%(ext)s",  # Save with video title as filename
            "format": "best",  # Specify  format
            "noplaylist": True,  # Single video download
            "quiet": False,  # Verbose output
            "cookiefile": cookies,  # Use cookies from file
        }
    elif browser_name:
        # Pass browser-based cookies via cookiesfrombrowser
        ydl_opts = {
            "outtmpl": f"{output_dir}/%(title)s.%(ext)s",  # Save with video title as filename
            "format": "best",  # Specify format
            "noplaylist": True,  # Single video download
            "quiet": False,  # Verbose output
            "cookiesfrombrowser": (
                browser_name,
                profile_name,
            ),  # Pass browser and profile name
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
            ydl.download([url])
            print("Video downloaded successfully.")
    except Exception as e:
        print(f"Failed to download video: {e}")


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Download TikTok slideshows or videos."
    )
    parser.add_argument("link", help="TikTok video/slideshow link")

    parser.add_argument(
        "--output", required=True, help="Output folder for downloaded images"
    )

    # Create a mutually exclusive group for cookies input
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--browser", choices=BROWSER_MAP.keys(), help="Browser to load cookies from"
    )
    group.add_argument("--cookies", help="Path to the cookies JSON file")

    parser.add_argument(
        "--profile",
        default="default",
        help="Browser profile name to load cookies from (default: 'default')",
    )

    args = parser.parse_args()

    browser_name = None
    cookies = None

    # Load cookies based on input method
    if args.browser:
        print(
            f"Loading cookies from browser: {args.browser} with profile: {args.profile}"
        )
        cookies = load_cookies_from_browser(args.browser)
        browser_name = args.browser
    elif args.cookies:
        print(f"Loading cookies from file: {args.cookies}")
        cookies = load_cookies_from_file(args.cookies)
        browser_name = None

    # Decide based on URl content type
    if is_slideshow(args.link):
        print("Detected slideshow. Downloading images...")
        # Load cookies and fetch
        html = fetch_page(args.link, args.cookies)

        if html:
            # Parse and download images
            if image_links := parse_slideshow_links(html):
                print(f"Found {len(image_links)} images. Downloading...")
                download_images(image_links, args.output)
            else:
                print("No images found.")
    elif not is_slideshow(args.link):
        print("Detected video. Downloading video...")

        download_video(args.link, args.output, cookies, browser_name, args.profile)
    else:
        print("Link neither a video nor slideshow...")


if __name__ == "__main__":
    main()
