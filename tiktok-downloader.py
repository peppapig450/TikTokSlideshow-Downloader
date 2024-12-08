import argparse
import itertools
import json
import logging
from pathlib import Path
from pprint import pprint

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set logging level to INFO (adjust as needed)
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),  # Log to a file
        logging.StreamHandler(),  # Log to console
    ],
)

# Map browser names to their browser_cookie3 functions
BROWSER_MAP = {
    "chrome": chrome,
    "firefox": firefox,
    "edge": edge,
    "opera": opera,
    "brave": brave,
}


def load_cookies_from_browser(browser_name: str):
    try:
        logging.info(f"Loading cookies from browser: {browser_name}")
        browser_name = browser_name.lower()
        fetch_cookies = BROWSER_MAP.get(browser_name)
        if not fetch_cookies:
            raise ValueError(
                f"Unsupported browser '{browser_name}'. Supported browsers: {', '.join(BROWSER_MAP.keys())}."
            )
        return fetch_cookies(domain_name="tiktok.com")
    except Exception as e:
        logging.error(e, exc_info=True, stack_info=True)
        raise


def load_cookies_from_file(file_path: str):
    try:
        logging.info(f"Loading cookies from file: {file_path}")
        return json.loads(Path(file_path).read_text())
    except Exception as e:
        logging.error(e, exc_info=True, stack_info=True)
        raise


def load_cookies(driver, cookies):
    try:
        logging.info("Loading cookies into Selenium WebDriver.")
        for cookie in cookies:
            pprint(cookies)
            driver.add_cookie(
                {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie["domain"],
                }
            )
    except Exception as e:
        logging.error(e, exc_info=True, stack_info=True)
        raise


def fetch_page(url: str, cookies):
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("start-maximized")
    options.add_argument("enable-automation")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(
        options=options, service=ChromeService(ChromeDriverManager().install())
    )

    try:
        logging.info(f"Fetching page: {url}")
        load_cookies(driver, cookies)
        driver.refresh()
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".css-brxox6-ImgPhotoSlide.e10jea832")
            )
        )
        return driver.page_source
    except Exception as e:
        logging.error(e, exc_info=True, stack_info=True)
        return None
    finally:
        driver.quit()


def parse_slideshow_links(html):
    try:
        logging.info("Parsing slideshow links.")
        soup = BeautifulSoup(html, "html.parser")
        image_tags = soup.select(".css-brxox6-ImgPhotoSlide.e10jea832")
        image_links = [img["src"] for img in image_tags if "src" in img.attrs]
        flat_image_links = list(
            itertools.chain(
                *[
                    sublist if isinstance(sublist, list) else [sublist]
                    for sublist in image_links
                ]
            )
        )
        return flat_image_links
    except Exception as e:
        logging.error(e, exc_info=True, stack_info=True)
        raise


def download_images(image_links: list[str], output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    for link in image_links:
        try:
            logging.info(f"Downloading image: {link}")
            response = requests.get(link, stream=True)
            response.raise_for_status()
            file_name = link.split("/")[-1].split("?")[0]
            file_path = output_dir / file_name
            with file_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            logging.info(f"Downloaded: {file_name}")
        except requests.RequestException as e:
            logging.error(e, exc_info=True, stack_info=True)


def download_video(url, output_dir, cookies, browser_name=None, profile_name="default"):
    try:
        logging.info(f"Downloading video from: {url}")
        ydl_opts = {
            "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
            "format": "best",
            "noplaylist": True,
            "quiet": False,
        }
        if cookies:
            ydl_opts["cookiefile"] = cookies
        elif browser_name:
            ydl_opts["cookiesfrombrowser"] = (browser_name, profile_name)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            logging.info("Video downloaded successfully.")
    except Exception as e:
        logging.error(e, exc_info=True, stack_info=True)


def main():
    parser = argparse.ArgumentParser(
        description="Download TikTok slideshows or videos."
    )
    parser.add_argument("link", help="TikTok video/slideshow link")
    parser.add_argument(
        "--output", required=True, help="Output folder for downloaded images"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--browser", choices=BROWSER_MAP.keys(), help="Browser to load cookies from"
    )
    group.add_argument("--cookies", help="Path to the cookies JSON file")

    parser.add_argument(
        "--profile", default="default", help="Browser profile name (default: 'default')"
    )

    args = parser.parse_args()

    try:
        cookies = None
        browser_name = None
        if args.browser:
            cookies = load_cookies_from_browser(args.browser)
            browser_name = args.browser
        elif args.cookies:
            cookies = load_cookies_from_file(args.cookies)

        if "photo" in args.link:
            html = fetch_page(args.link, cookies)
            if html:
                image_links = parse_slideshow_links(html)
                download_images(image_links, args.output)
        else:
            download_video(args.link, args.output, cookies, browser_name, args.profile)
    except Exception as e:
        logging.error(e, exc_info=True, stack_info=True)


if __name__ == "__main__":
    main()
