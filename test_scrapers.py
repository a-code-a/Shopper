#!/usr/bin/env python3
"""
Test script for Aldi flyer scrapers.

This script tests the different scraper implementations to see which one works best.
"""

import os
import argparse
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def test_selenium_scraper(output_dir):
    """Test the Selenium-based scraper."""
    logger.info("Testing Selenium-based scraper...")
    
    try:
        from aldi_flyer_scraper import AldiProspektScraper
        
        scraper = AldiProspektScraper(output_dir=output_dir, headless=False)
        downloaded_files = scraper.run()
        
        if downloaded_files:
            logger.info(f"Selenium scraper successfully downloaded {len(downloaded_files)} flyers")
            return True
        else:
            logger.warning("Selenium scraper did not download any flyers")
            return False
    except Exception as e:
        logger.error(f"Error testing Selenium scraper: {str(e)}")
        return False

def test_selenium_downloader(output_dir):
    """Test the alternative Selenium-based downloader."""
    logger.info("Testing alternative Selenium-based downloader...")
    
    try:
        from aldi_flyer_downloader import AldiProspektDownloader
        
        downloader = AldiProspektDownloader(output_dir=output_dir, headless=False)
        downloaded_files = downloader.run()
        
        if downloaded_files:
            logger.info(f"Selenium downloader successfully downloaded {len(downloaded_files)} flyers")
            return True
        else:
            logger.warning("Selenium downloader did not download any flyers")
            return False
    except Exception as e:
        logger.error(f"Error testing Selenium downloader: {str(e)}")
        return False

def test_puppeteer_scraper(output_dir):
    """Test the Puppeteer-based scraper."""
    logger.info("Testing Puppeteer-based scraper...")
    
    try:
        import asyncio
        from aldi_puppeteer_scraper import AldiPuppeteerScraper, main_async
        
        # Create args object
        class Args:
            def __init__(self, output_dir, headless):
                self.output_dir = output_dir
                self.headless = headless
        
        args = Args(output_dir, False)
        
        # Run the async main function
        asyncio.get_event_loop().run_until_complete(main_async(args))
        
        # Check if any files were downloaded
        files = [f for f in os.listdir(output_dir) if f.endswith('.pdf')]
        if files:
            logger.info(f"Puppeteer scraper successfully downloaded {len(files)} flyers")
            return True
        else:
            logger.warning("Puppeteer scraper did not download any flyers")
            return False
    except Exception as e:
        logger.error(f"Error testing Puppeteer scraper: {str(e)}")
        return False

def main():
    """Main function to test the scrapers."""
    parser = argparse.ArgumentParser(description='Test Aldi flyer scrapers')
    parser.add_argument('--output_dir', type=str, default='./test_flyers',
                        help='Directory to save downloaded flyers')
    parser.add_argument('--scraper', type=str, choices=['selenium', 'downloader', 'puppeteer', 'all'],
                        default='all', help='Which scraper to test')
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Test the specified scraper(s)
    if args.scraper == 'selenium' or args.scraper == 'all':
        test_selenium_scraper(args.output_dir)
    
    if args.scraper == 'downloader' or args.scraper == 'all':
        test_selenium_downloader(args.output_dir)
    
    if args.scraper == 'puppeteer' or args.scraper == 'all':
        test_puppeteer_scraper(args.output_dir)

if __name__ == "__main__":
    main()
