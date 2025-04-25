#!/usr/bin/env python3
"""
Simple Aldi Flyer Downloader

A simple script to download Aldi Süd flyers using requests and BeautifulSoup.
This approach doesn't handle JavaScript, but might work for basic scraping.
"""

import os
import re
import argparse
import logging
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class AldiSimpleDownloader:
    """Class to download Aldi Süd flyers using simple HTTP requests."""
    
    BASE_URL = "https://www.aldi-sued.de/de/angebote/prospekte.html"
    
    def __init__(self, output_dir="./flyers"):
        """
        Initialize the downloader.
        
        Args:
            output_dir (str): Directory to save downloaded flyers
        """
        self.output_dir = output_dir
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
    
    def get_flyer_links(self):
        """
        Extract links to flyers from the Aldi Süd prospekte page.
        
        Returns:
            list: List of dictionaries containing flyer information
        """
        try:
            response = self.session.get(self.BASE_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all flyer links
            flyer_links = []
            
            # Look for links to prospekte
            for link in soup.find_all('a', href=re.compile(r'prospekt\.aldi-sued\.de')):
                # Try to get the title from the link or nearby elements
                title_elem = link.find('div', class_=lambda c: c and ('title' in c.lower() or 'headline' in c.lower()))
                title = title_elem.get_text().strip() if title_elem else link.get_text().strip() or "Aldi Prospekt"
                
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
            
        except Exception as e:
            logger.error(f"Error getting flyer links: {str(e)}")
            return []
    
    def extract_pdf_url(self, flyer_url):
        """
        Extract the PDF URL from a flyer page.
        
        Args:
            flyer_url (str): URL of the flyer page
            
        Returns:
            str: URL of the PDF file or None if not found
        """
        try:
            response = self.session.get(flyer_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Method 1: Look for PDF links
            pdf_links = soup.find_all('a', href=re.compile(r'\.pdf'))
            if pdf_links:
                pdf_url = pdf_links[0].get('href')
                if not pdf_url.startswith('http'):
                    pdf_url = urljoin(flyer_url, pdf_url)
                return pdf_url
            
            # Method 2: Look for embed tags
            embed_tags = soup.find_all('embed', type='application/pdf')
            if embed_tags:
                pdf_url = embed_tags[0].get('src')
                if not pdf_url.startswith('http'):
                    pdf_url = urljoin(flyer_url, pdf_url)
                return pdf_url
            
            # Method 3: Look for iframe tags
            iframe_tags = soup.find_all('iframe', src=re.compile(r'\.pdf|viewer'))
            if iframe_tags:
                iframe_src = iframe_tags[0].get('src')
                if '.pdf' in iframe_src:
                    if not iframe_src.startswith('http'):
                        iframe_src = urljoin(flyer_url, iframe_src)
                    return iframe_src
            
            # Method 4: Check for PDF URLs in the page source
            pdf_matches = re.findall(r'href=[\'"]([^\'"]*\.pdf)[\'"]', response.text)
            if pdf_matches:
                pdf_url = pdf_matches[0]
                if not pdf_url.startswith('http'):
                    pdf_url = urljoin(flyer_url, pdf_url)
                return pdf_url
            
            # Method 5: Check for data-src attributes
            data_src_tags = soup.find_all(attrs={'data-src': re.compile(r'\.pdf')})
            if data_src_tags:
                pdf_url = data_src_tags[0].get('data-src')
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
            # Create a filename based on the title and current date
            date_str = datetime.now().strftime("%Y-%m-%d")
            sanitized_title = re.sub(r'[^\w\-_\. ]', '_', title)
            filename = f"aldi_flyer_{sanitized_title}_{date_str}.pdf"
            filepath = os.path.join(self.output_dir, filename)
            
            # Download the PDF
            response = self.session.get(url, stream=True)
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
    
    def run(self):
        """Run the downloader to download all flyers."""
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

def main():
    """Main function to run the downloader."""
    parser = argparse.ArgumentParser(description='Download Aldi Süd flyers using simple HTTP requests')
    parser.add_argument('--output_dir', type=str, default='./flyers',
                        help='Directory to save downloaded flyers')
    
    args = parser.parse_args()
    
    logger.info(f"Starting Aldi simple flyer downloader with output directory: {args.output_dir}")
    
    downloader = AldiSimpleDownloader(output_dir=args.output_dir)
    downloaded_files = downloader.run()
    
    if downloaded_files:
        logger.info("Successfully downloaded flyers:")
        for file in downloaded_files:
            logger.info(f"  - {file}")
    else:
        logger.warning("No flyers were downloaded")

if __name__ == "__main__":
    main()
