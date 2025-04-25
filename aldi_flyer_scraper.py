#!/usr/bin/env python3
"""
Aldi Flyer Scraper

This script scrapes and downloads flyers (Prospekte) from the Aldi Süd website.
"""

import os
import re
import time
import argparse
import logging
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class AldiProspektScraper:
    """Class to scrape and download Aldi Süd flyers."""
    
    BASE_URL = "https://www.aldi-sued.de/de/angebote/prospekte.html"
    
    def __init__(self, output_dir="./flyers", headless=True):
        """
        Initialize the scraper.
        
        Args:
            output_dir (str): Directory to save downloaded flyers
            headless (bool): Whether to run Chrome in headless mode
        """
        self.output_dir = output_dir
        self.headless = headless
        self.driver = None
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
    def setup_driver(self):
        """Set up the Chrome WebDriver."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Set up Chrome WebDriver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
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
        
        # Get page source and parse with BeautifulSoup
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        
        # Find all flyer links
        flyer_links = []
        
        # Look for links to prospekte
        for link in soup.find_all('a', href=re.compile(r'prospekt\.aldi-sued\.de')):
            # Try to get the title from the link or nearby elements
            title_elem = link.find('div', class_=lambda c: c and 'title' in c.lower())
            title = title_elem.get_text().strip() if title_elem else "Unknown Title"
            
            # Get the URL
            url = link.get('href')
            
            # Add to list if not already present
            if url and url not in [f['url'] for f in flyer_links]:
                flyer_links.append({
                    'title': title,
                    'url': url
                })
                logger.info(f"Found flyer: {title} - {url}")
        
        return flyer_links
    
    def download_flyer(self, flyer_info):
        """
        Download a flyer PDF.
        
        Args:
            flyer_info (dict): Dictionary containing flyer information
            
        Returns:
            str: Path to downloaded file or None if download failed
        """
        url = flyer_info['url']
        title = flyer_info['title']
        
        # Navigate to the flyer page
        self.driver.get(url)
        logger.info(f"Navigating to flyer page: {url}")
        
        # Wait for page to load
        time.sleep(5)
        
        # Try to find PDF download link
        try:
            # Look for PDF download button or link
            pdf_link = None
            
            # Method 1: Try to find a direct PDF link
            try:
                pdf_elem = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '.pdf')]"))
                )
                pdf_link = pdf_elem.get_attribute('href')
            except TimeoutException:
                logger.warning("No direct PDF link found, trying alternative methods")
            
            # Method 2: Try to find download button
            if not pdf_link:
                try:
                    download_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Download') or contains(@class, 'download')]"))
                    )
                    download_button.click()
                    time.sleep(2)  # Wait for download link to appear
                    
                    # Try to get the PDF link after clicking download button
                    pdf_elem = self.driver.find_element(By.XPATH, "//a[contains(@href, '.pdf')]")
                    pdf_link = pdf_elem.get_attribute('href')
                except (TimeoutException, NoSuchElementException):
                    logger.warning("Download button not found")
            
            # Method 3: Extract PDF URL from page source
            if not pdf_link:
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                pdf_tags = soup.find_all('a', href=re.compile(r'\.pdf'))
                
                if pdf_tags:
                    pdf_link = pdf_tags[0].get('href')
                    if not pdf_link.startswith('http'):
                        pdf_link = urljoin(url, pdf_link)
            
            # If we found a PDF link, download it
            if pdf_link:
                logger.info(f"Found PDF link: {pdf_link}")
                
                # Create a filename based on the title and current date
                date_str = datetime.now().strftime("%Y-%m-%d")
                sanitized_title = re.sub(r'[^\w\-_\. ]', '_', title)
                filename = f"aldi_flyer_{sanitized_title}_{date_str}.pdf"
                filepath = os.path.join(self.output_dir, filename)
                
                # Download the PDF
                response = requests.get(pdf_link, stream=True)
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    logger.info(f"Downloaded flyer to {filepath}")
                    return filepath
                else:
                    logger.error(f"Failed to download PDF: HTTP {response.status_code}")
            else:
                logger.error("Could not find PDF download link")
                
                # Take a screenshot for debugging
                screenshot_path = os.path.join(self.output_dir, f"debug_screenshot_{int(time.time())}.png")
                self.driver.save_screenshot(screenshot_path)
                logger.info(f"Saved debug screenshot to {screenshot_path}")
                
        except Exception as e:
            logger.error(f"Error downloading flyer: {str(e)}")
        
        return None
    
    def run(self):
        """Run the scraper to download all flyers."""
        try:
            self.setup_driver()
            flyer_links = self.get_flyer_links()
            
            if not flyer_links:
                logger.warning("No flyers found")
                return []
            
            downloaded_files = []
            for flyer in flyer_links:
                filepath = self.download_flyer(flyer)
                if filepath:
                    downloaded_files.append(filepath)
            
            logger.info(f"Downloaded {len(downloaded_files)} flyers")
            return downloaded_files
            
        finally:
            # Clean up
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver closed")

def main():
    """Main function to run the scraper."""
    parser = argparse.ArgumentParser(description='Scrape and download Aldi Süd flyers')
    parser.add_argument('--output_dir', type=str, default='./flyers',
                        help='Directory to save downloaded flyers')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run Chrome in headless mode')
    
    args = parser.parse_args()
    
    logger.info(f"Starting Aldi flyer scraper with output directory: {args.output_dir}")
    
    scraper = AldiProspektScraper(output_dir=args.output_dir, headless=args.headless)
    downloaded_files = scraper.run()
    
    if downloaded_files:
        logger.info("Successfully downloaded flyers:")
        for file in downloaded_files:
            logger.info(f"  - {file}")
    else:
        logger.warning("No flyers were downloaded")

if __name__ == "__main__":
    main()
