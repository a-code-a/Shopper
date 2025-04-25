#!/usr/bin/env python3
"""
Aldi Flyer Scraper using Playwright

This script uses Playwright to scrape and download flyers from the Aldi Süd website.
Playwright is a modern browser automation library that provides better support for
modern web applications.
"""

import os
import re
import asyncio
import argparse
import logging
from datetime import datetime
from urllib.parse import urljoin

import requests
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class AldiPlaywrightScraper:
    """Class to scrape and download Aldi Süd flyers using Playwright."""

    BASE_URL = "https://www.aldi-sued.de/de/angebote/prospekte.html"

    def __init__(self, output_dir="./flyers", headless=True):
        """
        Initialize the scraper.

        Args:
            output_dir (str): Directory to save downloaded flyers
            headless (bool): Whether to run browser in headless mode
        """
        self.output_dir = output_dir
        self.headless = headless

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

    async def handle_cookies(self, page):
        """Handle cookie consent banner."""
        try:
            # Wait for cookie banner to appear
            cookie_button = await page.wait_for_selector("button:text('Alle bestätigen')", timeout=10000)
            if cookie_button:
                await cookie_button.click()
                logger.info("Accepted cookies")
                await asyncio.sleep(2)  # Wait for banner to disappear
        except Exception:
            logger.warning("Cookie banner not found or already accepted")

    async def get_flyer_links(self, page):
        """
        Extract links to flyers from the Aldi Süd prospekte page.

        Args:
            page: Playwright page object

        Returns:
            list: List of dictionaries containing flyer information
        """
        await page.goto(self.BASE_URL)
        logger.info(f"Navigated to {self.BASE_URL}")

        # Handle cookie consent
        await self.handle_cookies(page)

        # Wait for flyers to load
        try:
            await page.wait_for_selector("a[href*='prospekt.aldi-sued.de']", timeout=10000)
        except Exception:
            logger.error("Flyers not found on page")
            return []

        # Find all flyer links
        flyer_links = []

        # Get all links to prospekte
        links = await page.query_selector_all("a[href*='prospekt.aldi-sued.de']")

        for link in links:
            # Get the URL
            url = await link.get_attribute('href')

            # Extract a title from the URL if possible
            url_title = "Aldi Prospekt"  # Default title
            url_parts = url.split('/')
            if len(url_parts) > 0:
                last_part = url_parts[-1]
                if last_part:
                    # Remove any page indicators
                    if last_part.startswith('page'):
                        last_part = url_parts[-2] if len(url_parts) > 1 else ""

                    # Clean up the URL part to make a readable title
                    if last_part:
                        url_title = last_part.replace('-', ' ').replace('_', ' ')
                        url_title = re.sub(r'\d{2,4}$', '', url_title)  # Remove year numbers at the end
                        url_title = url_title.strip()
                        url_title = ' '.join(word.capitalize() for word in url_title.split())

            # Try to get the title from the page
            title = url_title  # Use URL-derived title as fallback

            # Try to get title from child elements
            title_elem = await link.query_selector("div[class*='title'], div[class*='headline']")
            if title_elem:
                page_title = await title_elem.text_content()
                if page_title and page_title.strip():
                    title = page_title.strip()
            else:
                # If no title found, try to get the link text
                link_text = await link.text_content()
                if link_text and link_text.strip():
                    title = link_text.strip()

            # Add to list if not already present
            if url and url not in [f['url'] for f in flyer_links]:
                flyer_links.append({
                    'title': title,
                    'url': url
                })
                logger.info(f"Found flyer: {title} - {url}")

        return flyer_links

    async def extract_pdf_url(self, page, flyer_url):
        """
        Extract the PDF URL from a flyer page.

        Args:
            page: Playwright page object
            flyer_url (str): URL of the flyer page

        Returns:
            str: URL of the PDF file or None if not found
        """
        try:
            await page.goto(flyer_url, wait_until='networkidle')
            logger.info(f"Navigating to flyer page: {flyer_url}")

            # Wait for page to load
            await asyncio.sleep(5)

            # Method 1: Look for PDF embed or object tags
            pdf_elements = await page.query_selector_all("embed[type='application/pdf']")
            if pdf_elements:
                pdf_url = await pdf_elements[0].get_attribute('src')
                if pdf_url:
                    return pdf_url

            # Method 2: Look for PDF viewer iframe
            iframe_elements = await page.query_selector_all("iframe[src*='.pdf'], iframe[src*='viewer']")
            if iframe_elements:
                iframe_src = await iframe_elements[0].get_attribute('src')
                if '.pdf' in iframe_src:
                    return iframe_src

                # If it's a viewer, switch to iframe and look for the PDF
                frame = page.frame(url=iframe_src)
                if frame:
                    pdf_elements = await frame.query_selector_all("embed[type='application/pdf']")
                    if pdf_elements:
                        pdf_url = await pdf_elements[0].get_attribute('src')
                        if pdf_url:
                            return pdf_url

            # Method 3: Look for download links
            download_links = await page.query_selector_all("a[href*='.pdf']")
            if download_links:
                pdf_url = await download_links[0].get_attribute('href')
                if pdf_url:
                    return pdf_url

            # Method 4: Check page source for PDF URLs
            content = await page.content()
            pdf_matches = re.findall(r'href=[\'"]([^\'"]*\.pdf)[\'"]', content)
            if pdf_matches:
                pdf_url = pdf_matches[0]
                if not pdf_url.startswith('http'):
                    pdf_url = urljoin(flyer_url, pdf_url)
                return pdf_url

            # Method 5: Look for download buttons
            download_buttons = await page.query_selector_all("button:text('Download'), button[class*='download']")
            if download_buttons:
                await download_buttons[0].click()
                await asyncio.sleep(2)  # Wait for download link to appear

                # Check for PDF links again
                download_links = await page.query_selector_all("a[href*='.pdf']")
                if download_links:
                    pdf_url = await download_links[0].get_attribute('href')
                    if pdf_url:
                        return pdf_url

            # Method 6: Check network requests for PDF files
            # This is a more advanced method that might catch dynamically loaded PDFs
            async def handle_response(response):
                if '.pdf' in response.url:
                    return response.url

            page.on('response', handle_response)

            # Reload the page to trigger the response handler
            await page.reload(wait_until='networkidle')
            await asyncio.sleep(5)  # Wait for potential PDF responses

            # Take a screenshot for debugging
            screenshot_path = os.path.join(self.output_dir, f"debug_screenshot_{int(datetime.now().timestamp())}.png")
            await page.screenshot(path=screenshot_path)
            logger.info(f"Saved debug screenshot to {screenshot_path}")

            # Method 7: Look for data-src attributes
            elements_with_data_src = await page.query_selector_all("[data-src*='.pdf']")
            if elements_with_data_src:
                pdf_url = await elements_with_data_src[0].get_attribute('data-src')
                if pdf_url and not pdf_url.startswith('http'):
                    pdf_url = urljoin(flyer_url, pdf_url)
                return pdf_url

            # Method 8: Check for PDF URLs in script tags
            script_tags = await page.query_selector_all("script")
            for script_tag in script_tags:
                script_content = await page.evaluate("(element) => element.textContent", script_tag)
                if script_content:
                    pdf_matches = re.findall(r'[\'"]([^\'\"]*\.pdf)[\'"]', script_content)
                    if pdf_matches:
                        pdf_url = pdf_matches[0]
                        if not pdf_url.startswith('http'):
                            pdf_url = urljoin(flyer_url, pdf_url)
                        return pdf_url

            logger.error(f"Could not find PDF URL on page: {flyer_url}")
            return None

        except Exception as e:
            logger.error(f"Error extracting PDF URL: {str(e)}")
            return None

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
            # Extract a better title from the URL or content-disposition header
            better_title = title

            # Try to get a better title from the URL
            url_match = re.search(r'([^/]+)\.pdf', url)
            if url_match:
                better_title = url_match.group(1)

            # Check for content-disposition header
            head_response = requests.head(url)
            if 'content-disposition' in head_response.headers:
                cd_match = re.search(r'filename\*?=(?:UTF-8\'\'|")?([^"]+)', head_response.headers['content-disposition'])
                if cd_match:
                    better_title = cd_match.group(1)
                    better_title = better_title.replace('%20', ' ').replace('%25', '%')
                    better_title = re.sub(r'\.pdf$', '', better_title)

            # Create a unique filename with timestamp
            date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            sanitized_title = re.sub(r'[^\w\-_\. ]', '_', better_title)
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

    async def run(self):
        """Run the scraper to download all flyers."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()

            # Set viewport size
            await page.set_viewport_size({"width": 1920, "height": 1080})

            try:
                flyer_links = await self.get_flyer_links(page)

                if not flyer_links:
                    logger.warning("No flyers found")
                    return []

                downloaded_files = []
                for flyer in flyer_links:
                    pdf_url = await self.extract_pdf_url(page, flyer['url'])
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
                await browser.close()

async def main_async(args):
    """Async main function to run the scraper."""
    logger.info(f"Starting Aldi flyer scraper with output directory: {args.output_dir}")

    scraper = AldiPlaywrightScraper(output_dir=args.output_dir, headless=args.headless)
    downloaded_files = await scraper.run()

    if downloaded_files:
        logger.info("Successfully downloaded flyers:")
        for file in downloaded_files:
            logger.info(f"  - {file}")
    else:
        logger.warning("No flyers were downloaded")

def main():
    """Main function to run the scraper."""
    parser = argparse.ArgumentParser(description='Scrape and download Aldi Süd flyers using Playwright')
    parser.add_argument('--output_dir', type=str, default='./flyers',
                        help='Directory to save downloaded flyers')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run browser in headless mode')

    args = parser.parse_args()

    # Run the async main function
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()
