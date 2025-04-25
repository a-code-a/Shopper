# Aldi Flyer Scraper

A collection of tools to automatically scrape and download flyers (Prospekte) from the Aldi Süd website.

## Features

- Automatically navigates to the Aldi Süd prospekte page
- Handles cookie consent banners
- Extracts links to current flyers
- Downloads the flyers as PDFs
- Saves them to a specified directory

## Requirements

- Python 3.6+
- Chrome browser installed
- Required Python packages (install using `pip install -r requirements.txt`):
  - selenium
  - beautifulsoup4
  - requests
  - webdriver-manager
  - PyPDF2
  - pyppeteer (optional, for the Puppeteer-based scraper)

## Available Scripts

This repository contains three different implementations of the Aldi flyer scraper:

1. **aldi_flyer_scraper.py** - Selenium-based scraper with BeautifulSoup
2. **aldi_flyer_downloader.py** - Alternative Selenium-based approach
3. **aldi_puppeteer_scraper.py** - Puppeteer-based scraper (requires pyppeteer)

Each implementation uses a different approach to handle the challenges of scraping a modern JavaScript-heavy website.

## Usage

### Selenium-based Scraper

```bash
python aldi_flyer_scraper.py [--output_dir OUTPUT_DIR] [--headless]
```

### Alternative Selenium-based Downloader

```bash
python aldi_flyer_downloader.py [--output_dir OUTPUT_DIR] [--headless]
```

### Puppeteer-based Scraper

```bash
python aldi_puppeteer_scraper.py [--output_dir OUTPUT_DIR] [--headless]
```

### Test Script

To test all three implementations and see which one works best:

```bash
python test_scrapers.py [--output_dir OUTPUT_DIR] [--scraper {selenium,downloader,puppeteer,all}]
```

### Parameters

- `--output_dir`: Optional directory to save downloaded flyers (default: `./flyers`)
- `--headless`: Run the browser in headless mode (default: True)
- `--scraper`: Which scraper to test (default: all)

## Example

```bash
python aldi_flyer_scraper.py --output_dir ./aldi_flyers --headless
```

This will download all current Aldi Süd flyers to the `./aldi_flyers` directory using the Selenium-based scraper in headless mode.

## Notes

- The tools use browser automation to handle JavaScript and cookie consent
- Cookie consent is automatically handled
- Flyers are saved with descriptive filenames including the date
- If one implementation doesn't work, try another one
- The Puppeteer-based scraper may provide better results for some users
