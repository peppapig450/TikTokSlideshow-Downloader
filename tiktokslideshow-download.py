import argparse
import itertools
import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


# Load cookies into the browser
def load_cookies(driver, file_path: str):
    cookies = json.loads(Path(file_path).read_text())
    for cookie in cookies:
        driver.add_cookie(
            {
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie["domain"],
            }
        )


# Fetch the TikTok page
def fetch_page(url: str, file_path: str):
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

    # Load cookies
    load_cookies(driver, file_path)
    driver.refresh()

    # Navigate to the target URL
    driver.get(url)

    try:
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


def main():
    # Parse command-line args
    parser = argparse.ArgumentParser(description="Download TikTok slideshow images.")
    parser.add_argument("link", help="TikTok video link")
    parser.add_argument(
        "--cookies", required=True, help="Path to the cookies file (cookies.json)"
    )
    parser.add_argument(
        "--output", required=True, help="Output folder for downloaded images"
    )
    args = parser.parse_args()

    # Load cookies and fetch
    html = fetch_page(args.link, args.cookies)

    if html:
        # Parse and download images
        if image_links := parse_slideshow_links(html):
            print(f"Found {len(image_links)} images. Downloading...")
            download_images(image_links, args.output)
        else:
            print("No images found.")
    else:
        print("Failed to fetch the video page.")


if __name__ == "__main__":
    main()
