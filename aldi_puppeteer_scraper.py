#!/usr/bin/env python3
"""
Aldi Flyer Scraper using Puppeteer

This script uses Pyppeteer (Python port of Puppeteer) to scrape and download
flyers from the Aldi Süd website.
"""

import os
import re
import asyncio
import argparse
import logging
from datetime import datetime
from urllib.parse import urljoin

import requests
import pyppeteer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class AldiPuppeteerScraper:
    """Class to scrape and download Aldi Süd flyers using Puppeteer."""
    
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
        self.browser = None
        self.page = None
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
    
    async def setup_browser(self):
        """Set up the browser."""
        self.browser = await pyppeteer.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080']
        )
        self.page = await self.browser.newPage()
        await self.page.setViewport({'width': 1920, 'height': 1080})
        
        # Set user agent to avoid detection
        await self.page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    async def handle_cookies(self):
        """Handle cookie consent banner."""
        try:
            # Wait for cookie banner to appear
            await self.page.waitForSelector("button:text('Alle bestätigen')", {'timeout': 10000})
            await self.page.click("button:text('Alle bestätigen')")
            logger.info("Accepted cookies")
            await asyncio.sleep(2)  # Wait for banner to disappear
        except pyppeteer.errors.TimeoutError:
            logger.warning("Cookie banner not found or already accepted")
    
    async def get_flyer_links(self):
        """
        Extract links to flyers from the Aldi Süd prospekte page.
        
        Returns:
            list: List of dictionaries containing flyer information
        """
        await self.page.goto(self.BASE_URL, {'waitUntil': 'networkidle0'})
        logger.info(f"Navigated to {self.BASE_URL}")
        
        # Handle cookie consent
        await self.handle_cookies()
        
        # Wait for flyers to load
        try:
            await self.page.waitForSelector("a[href*='prospekt.aldi-sued.de']", {'timeout': 10000})
        except pyppeteer.errors.TimeoutError:
            logger.error("Flyers not found on page")
            return []
        
        # Find all flyer links
        flyer_links = []
        
        # Get all links to prospekte
        links = await self.page.querySelectorAll("a[href*='prospekt.aldi-sued.de']")
        
        for link in links:
            # Get the URL
            url = await self.page.evaluate('(element) => element.href', link)
            
            # Try to get the title
            title = "Aldi Prospekt"  # Default title
            try:
                title_elem = await link.querySelector("div[class*='title'], div[class*='headline']")
                if title_elem:
                    title = await self.page.evaluate('(element) => element.textContent', title_elem)
                    title = title.strip()
            except:
                # If no title found, try to get the link text
                try:
                    link_text = await self.page.evaluate('(element) => element.textContent', link)
                    if link_text and link_text.strip():
                        title = link_text.strip()
                except:
                    pass
            
            # Add to list if not already present
            if url and url not in [f['url'] for f in flyer_links]:
                flyer_links.append({
                    'title': title,
                    'url': url
                })
                logger.info(f"Found flyer: {title} - {url}")
        
        return flyer_links
    
    async def extract_pdf_url(self, flyer_url):
        """
        Extract the PDF URL from a flyer page.
        
        Args:
            flyer_url (str): URL of the flyer page
            
        Returns:
            str: URL of the PDF file or None if not found
        """
        try:
            await self.page.goto(flyer_url, {'waitUntil': 'networkidle0'})
            logger.info(f"Navigating to flyer page: {flyer_url}")
            
            # Wait for page to load
            await asyncio.sleep(5)
            
            # Method 1: Look for PDF embed or object tags
            pdf_elements = await self.page.querySelectorAll("embed[type='application/pdf']")
            if pdf_elements:
                pdf_url = await self.page.evaluate('(element) => element.src', pdf_elements[0])
                if pdf_url:
                    return pdf_url
            
            # Method 2: Look for PDF viewer iframe
            iframe_elements = await self.page.querySelectorAll("iframe[src*='.pdf'], iframe[src*='viewer']")
            if iframe_elements:
                iframe_src = await self.page.evaluate('(element) => element.src', iframe_elements[0])
                if '.pdf' in iframe_src:
                    return iframe_src
                
                # If it's a viewer, switch to iframe and look for the PDF
                frames = self.page.frames
                for frame in frames:
                    if iframe_src in frame.url:
                        pdf_elements = await frame.querySelectorAll("embed[type='application/pdf']")
                        if pdf_elements:
                            pdf_url = await frame.evaluate('(element) => element.src', pdf_elements[0])
                            if pdf_url:
                                return pdf_url
            
            # Method 3: Look for download links
            download_links = await self.page.querySelectorAll("a[href*='.pdf']")
            if download_links:
                pdf_url = await self.page.evaluate('(element) => element.href', download_links[0])
                if pdf_url:
                    return pdf_url
            
            # Method 4: Check page source for PDF URLs
            content = await self.page.content()
            pdf_matches = re.findall(r'href=[\'"]([^\'"]*\.pdf)[\'"]', content)
            if pdf_matches:
                pdf_url = pdf_matches[0]
                if not pdf_url.startswith('http'):
                    pdf_url = urljoin(flyer_url, pdf_url)
                return pdf_url
            
            # Method 5: Look for download buttons
            download_buttons = await self.page.querySelectorAll("button:text('Download'), button[class*='download']")
            if download_buttons:
                await download_buttons[0].click()
                await asyncio.sleep(2)  # Wait for download link to appear
                
                # Check for PDF links again
                download_links = await self.page.querySelectorAll("a[href*='.pdf']")
                if download_links:
                    pdf_url = await self.page.evaluate('(element) => element.href', download_links[0])
                    if pdf_url:
                        return pdf_url
            
            # Take a screenshot for debugging
            screenshot_path = os.path.join(self.output_dir, f"debug_screenshot_{int(datetime.now().timestamp())}.png")
            await self.page.screenshot({'path': screenshot_path})
            logger.info(f"Saved debug screenshot to {screenshot_path}")
            
            logger.error("Could not find PDF URL on page")
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
    
    async def run(self):
        """Run the scraper to download all flyers."""
        try:
            await self.setup_browser()
            flyer_links = await self.get_flyer_links()
            
            if not flyer_links:
                logger.warning("No flyers found")
                return []
            
            downloaded_files = []
            for flyer in flyer_links:
                pdf_url = await self.extract_pdf_url(flyer['url'])
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
            if self.browser:
                await self.browser.close()
                logger.info("Browser closed")

async def main_async(args):
    """Async main function to run the scraper."""
    logger.info(f"Starting Aldi flyer scraper with output directory: {args.output_dir}")
    
    scraper = AldiPuppeteerScraper(output_dir=args.output_dir, headless=args.headless)
    downloaded_files = await scraper.run()
    
    if downloaded_files:
        logger.info("Successfully downloaded flyers:")
        for file in downloaded_files:
            logger.info(f"  - {file}")
    else:
        logger.warning("No flyers were downloaded")

def main():
    """Main function to run the scraper."""
    parser = argparse.ArgumentParser(description='Scrape and download Aldi Süd flyers using Puppeteer')
    parser.add_argument('--output_dir', type=str, default='./flyers',
                        help='Directory to save downloaded flyers')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run browser in headless mode')
    
    args = parser.parse_args()
    
    # Run the async main function
    asyncio.get_event_loop().run_until_complete(main_async(args))

if __name__ == "__main__":
    main()
