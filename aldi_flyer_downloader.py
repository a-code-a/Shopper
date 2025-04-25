#!/usr/bin/env python3
"""
Aldi Flyer Downloader

A simpler, more direct approach to download Aldi Süd flyers using Selenium
to handle JavaScript and extract PDF URLs.
"""

import os
import re
import time
import argparse
import logging
from datetime import datetime
from urllib.parse import urljoin

import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class AldiProspektDownloader:
    """Class to download Aldi Süd flyers."""

    BASE_URL = "https://www.aldi-sued.de/de/angebote/prospekte.html"

    def __init__(self, output_dir="./flyers", headless=True):
        """
        Initialize the downloader.

        Args:
            output_dir (str): Directory to save downloaded flyers
            headless (bool): Whether to run Chrome in headless mode
        """
        self.output_dir = output_dir
        self.headless = headless

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Set up Chrome options
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        try:
            # Try to set up Chrome WebDriver with ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            logger.warning(f"Error using ChromeDriverManager: {str(e)}")
            # Try alternative approach
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
            except Exception as e2:
                logger.error(f"Failed to initialize Chrome WebDriver: {str(e2)}")
                raise

    def handle_cookies(self):
        """Handle cookie consent banner."""
        try:
            # Wait for cookie banner to appear
            cookie_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Alle bestätigen')]"))
            )
            cookie_button.click()
            logger.info("Accepted cookies")
            time.sleep(2)  # Wait for banner to disappear
        except TimeoutException:
            logger.warning("Cookie banner not found or already accepted")

    def get_flyer_links(self):
        """
        Extract links to flyers from the Aldi Süd prospekte page.

        Returns:
            list: List of dictionaries containing flyer information
        """
        self.driver.get(self.BASE_URL)
        logger.info(f"Navigated to {self.BASE_URL}")

        # Handle cookie consent
        self.handle_cookies()

        # Wait for flyers to load
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'prospekt.aldi-sued.de')]"))
            )
        except TimeoutException:
            logger.error("Flyers not found on page")
            return []

        # Find all flyer links
        flyer_links = []

        # Get all links to prospekte
        links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'prospekt.aldi-sued.de')]")

        for link in links:
            try:
                # Try to get the title
                title_elem = link.find_element(By.XPATH, ".//div[contains(@class, 'title') or contains(@class, 'headline')]")
                title = title_elem.text.strip()
            except:
                # If no title found, use the link text or a default
                title = link.text.strip() or "Aldi Prospekt"

            # Get the URL
            url = link.get_attribute('href')

            # Add to list if not already present
            if url and url not in [f['url'] for f in flyer_links]:
                flyer_links.append({
                    'title': title,
                    'url': url
                })
                logger.info(f"Found flyer: {title} - {url}")

        return flyer_links

    def download_pdf(self, url, title):
        """
        Download a PDF file.

        Args:
            url (str): URL of the PDF file
            title (str): Title to use for the filename

        Returns:
            str: Path to downloaded file or None if download failed
        """
        try:
            # Create a filename based on the title and current date
            date_str = datetime.now().strftime("%Y-%m-%d")
            sanitized_title = re.sub(r'[^\w\-_\. ]', '_', title)
            filename = f"aldi_flyer_{sanitized_title}_{date_str}.pdf"
            filepath = os.path.join(self.output_dir, filename)

            # Download the PDF
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"Downloaded flyer to {filepath}")
                return filepath
            else:
                logger.error(f"Failed to download PDF: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Error downloading PDF: {str(e)}")

        return None

    def extract_pdf_url(self, flyer_url):
        """
        Extract the PDF URL from a flyer page.

        Args:
            flyer_url (str): URL of the flyer page

        Returns:
            str: URL of the PDF file or None if not found
        """
        try:
            self.driver.get(flyer_url)
            logger.info(f"Navigating to flyer page: {flyer_url}")

            # Wait for page to load
            time.sleep(5)

            # Method 1: Look for PDF embed or object tags
            pdf_elements = self.driver.find_elements(By.XPATH, "//embed[@type='application/pdf']")
            if pdf_elements:
                pdf_url = pdf_elements[0].get_attribute('src')
                if pdf_url:
                    return pdf_url

            # Method 2: Look for PDF viewer iframe
            iframe_elements = self.driver.find_elements(By.XPATH, "//iframe[contains(@src, '.pdf') or contains(@src, 'viewer')]")
            if iframe_elements:
                iframe_src = iframe_elements[0].get_attribute('src')
                if '.pdf' in iframe_src:
                    return iframe_src

                # If it's a viewer, switch to iframe and look for the PDF
                self.driver.switch_to.frame(iframe_elements[0])
                pdf_elements = self.driver.find_elements(By.XPATH, "//embed[@type='application/pdf']")
                if pdf_elements:
                    pdf_url = pdf_elements[0].get_attribute('src')
                    self.driver.switch_to.default_content()
                    if pdf_url:
                        return pdf_url
                self.driver.switch_to.default_content()

            # Method 3: Look for download links
            download_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf')]")
            if download_links:
                pdf_url = download_links[0].get_attribute('href')
                if pdf_url:
                    return pdf_url

            # Method 4: Check page source for PDF URLs
            page_source = self.driver.page_source
            pdf_matches = re.findall(r'href=[\'"]([^\'"]*\.pdf)[\'"]', page_source)
            if pdf_matches:
                pdf_url = pdf_matches[0]
                if not pdf_url.startswith('http'):
                    pdf_url = urljoin(flyer_url, pdf_url)
                return pdf_url

            # Method 5: Look for download buttons
            download_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Download') or contains(@class, 'download')]")
            if download_buttons:
                download_buttons[0].click()
                time.sleep(2)  # Wait for download link to appear

                # Check for PDF links again
                download_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf')]")
                if download_links:
                    pdf_url = download_links[0].get_attribute('href')
                    if pdf_url:
                        return pdf_url

            # Take a screenshot for debugging
            screenshot_path = os.path.join(self.output_dir, f"debug_screenshot_{int(time.time())}.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Saved debug screenshot to {screenshot_path}")

            logger.error("Could not find PDF URL on page")
            return None

        except Exception as e:
            logger.error(f"Error extracting PDF URL: {str(e)}")
            return None

    def run(self):
        """Run the downloader to download all flyers."""
        try:
            flyer_links = self.get_flyer_links()

            if not flyer_links:
                logger.warning("No flyers found")
                return []

            downloaded_files = []
            for flyer in flyer_links:
                pdf_url = self.extract_pdf_url(flyer['url'])
                if pdf_url:
                    logger.info(f"Found PDF URL: {pdf_url}")
                    filepath = self.download_pdf(pdf_url, flyer['title'])
                    if filepath:
                        downloaded_files.append(filepath)
                else:
                    logger.warning(f"Could not find PDF URL for flyer: {flyer['title']}")

            logger.info(f"Downloaded {len(downloaded_files)} flyers")
            return downloaded_files

        finally:
            # Clean up
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver closed")

def main():
    """Main function to run the downloader."""
    parser = argparse.ArgumentParser(description='Download Aldi Süd flyers')
    parser.add_argument('--output_dir', type=str, default='./flyers',
                        help='Directory to save downloaded flyers')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run Chrome in headless mode')

    args = parser.parse_args()

    logger.info(f"Starting Aldi flyer downloader with output directory: {args.output_dir}")

    downloader = AldiProspektDownloader(output_dir=args.output_dir, headless=args.headless)
    downloaded_files = downloader.run()

    if downloaded_files:
        logger.info("Successfully downloaded flyers:")
        for file in downloaded_files:
            logger.info(f"  - {file}")
    else:
        logger.warning("No flyers were downloaded")

if __name__ == "__main__":
    main()
