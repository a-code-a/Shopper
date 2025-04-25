#!/usr/bin/env python3
"""
Aldi Flyer Scraper

Dieses Skript verwendet Playwright, um Prospekte von der Aldi Süd Website zu scrapen und herunterzuladen.
Playwright ist eine moderne Browser-Automatisierungsbibliothek, die bessere Unterstützung für
moderne JavaScript-basierte Webanwendungen bietet.
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

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class AldiProspektScraper:
    """Klasse zum Scrapen und Herunterladen von Aldi Süd Prospekten mit Playwright."""
    
    BASE_URL = "https://www.aldi-sued.de/de/angebote/prospekte.html"
    
    def __init__(self, output_dir="./flyers", headless=True):
        """
        Initialisiert den Scraper.
        
        Args:
            output_dir (str): Verzeichnis zum Speichern der heruntergeladenen Prospekte
            headless (bool): Ob der Browser im Headless-Modus ausgeführt werden soll
        """
        self.output_dir = output_dir
        self.headless = headless
        
        # Ausgabeverzeichnis erstellen, falls es nicht existiert
        os.makedirs(output_dir, exist_ok=True)
    
    async def handle_cookies(self, page):
        """Cookie-Consent-Banner behandeln."""
        try:
            # Auf Cookie-Banner warten
            cookie_button = await page.wait_for_selector("button:text('Alle bestätigen')", timeout=10000)
            if cookie_button:
                await cookie_button.click()
                logger.info("Cookies akzeptiert")
                await asyncio.sleep(2)  # Warten, bis das Banner verschwindet
        except Exception:
            logger.warning("Cookie-Banner nicht gefunden oder bereits akzeptiert")
    
    async def get_flyer_links(self, page):
        """
        Links zu Prospekten von der Aldi Süd Prospekte-Seite extrahieren.
        
        Args:
            page: Playwright-Seitenobjekt
            
        Returns:
            list: Liste von Dictionaries mit Prospektinformationen
        """
        await page.goto(self.BASE_URL)
        logger.info(f"Zu {self.BASE_URL} navigiert")
        
        # Cookie-Consent behandeln
        await self.handle_cookies(page)
        
        # Warten, bis Prospekte geladen sind
        try:
            await page.wait_for_selector("a[href*='prospekt.aldi-sued.de']", timeout=10000)
        except Exception:
            logger.error("Keine Prospekte auf der Seite gefunden")
            return []
        
        # Alle Prospekt-Links finden
        flyer_links = []
        
        # Alle Links zu Prospekten holen
        links = await page.query_selector_all("a[href*='prospekt.aldi-sued.de']")
        
        for link in links:
            # URL holen
            url = await link.get_attribute('href')
            
            # Titel aus der URL extrahieren, falls möglich
            url_title = "Aldi Prospekt"  # Standard-Titel
            url_parts = url.split('/')
            if len(url_parts) > 0:
                last_part = url_parts[-1]
                if last_part:
                    # Seitenindikatoren entfernen
                    if last_part.startswith('page'):
                        last_part = url_parts[-2] if len(url_parts) > 1 else ""
                    
                    # URL-Teil bereinigen, um einen lesbaren Titel zu erstellen
                    if last_part:
                        url_title = last_part.replace('-', ' ').replace('_', ' ')
                        url_title = re.sub(r'\d{2,4}$', '', url_title)  # Jahreszahlen am Ende entfernen
                        url_title = url_title.strip()
                        url_title = ' '.join(word.capitalize() for word in url_title.split())
            
            # Versuchen, den Titel von der Seite zu holen
            title = url_title  # URL-abgeleiteten Titel als Fallback verwenden
            
            # Versuchen, Titel aus Kind-Elementen zu holen
            title_elem = await link.query_selector("div[class*='title'], div[class*='headline']")
            if title_elem:
                page_title = await title_elem.text_content()
                if page_title and page_title.strip():
                    title = page_title.strip()
            else:
                # Wenn kein Titel gefunden wurde, versuchen, den Link-Text zu holen
                link_text = await link.text_content()
                if link_text and link_text.strip():
                    title = link_text.strip()
            
            # Zur Liste hinzufügen, wenn noch nicht vorhanden
            if url and url not in [f['url'] for f in flyer_links]:
                flyer_links.append({
                    'title': title,
                    'url': url
                })
                logger.info(f"Prospekt gefunden: {title} - {url}")
        
        return flyer_links
    
    async def extract_pdf_url(self, page, flyer_url):
        """
        PDF-URL von einer Prospektseite extrahieren.
        
        Args:
            page: Playwright-Seitenobjekt
            flyer_url (str): URL der Prospektseite
            
        Returns:
            str: URL der PDF-Datei oder None, wenn nicht gefunden
        """
        try:
            await page.goto(flyer_url, wait_until='networkidle')
            logger.info(f"Navigiere zur Prospektseite: {flyer_url}")
            
            # Warten, bis die Seite geladen ist
            await asyncio.sleep(5)
            
            # Methode 1: Nach PDF-Embed- oder Objekt-Tags suchen
            pdf_elements = await page.query_selector_all("embed[type='application/pdf']")
            if pdf_elements:
                pdf_url = await pdf_elements[0].get_attribute('src')
                if pdf_url:
                    return pdf_url
            
            # Methode 2: Nach PDF-Viewer-Iframe suchen
            iframe_elements = await page.query_selector_all("iframe[src*='.pdf'], iframe[src*='viewer']")
            if iframe_elements:
                iframe_src = await iframe_elements[0].get_attribute('src')
                if '.pdf' in iframe_src:
                    return iframe_src
                
                # Wenn es ein Viewer ist, zum Iframe wechseln und nach dem PDF suchen
                frame = page.frame(url=iframe_src)
                if frame:
                    pdf_elements = await frame.query_selector_all("embed[type='application/pdf']")
                    if pdf_elements:
                        pdf_url = await pdf_elements[0].get_attribute('src')
                        if pdf_url:
                            return pdf_url
            
            # Methode 3: Nach Download-Links suchen
            download_links = await page.query_selector_all("a[href*='.pdf']")
            if download_links:
                pdf_url = await download_links[0].get_attribute('href')
                if pdf_url:
                    return pdf_url
            
            # Methode 4: Seitenquelle nach PDF-URLs durchsuchen
            content = await page.content()
            pdf_matches = re.findall(r'href=[\'"]([^\'"]*\.pdf)[\'"]', content)
            if pdf_matches:
                pdf_url = pdf_matches[0]
                if not pdf_url.startswith('http'):
                    pdf_url = urljoin(flyer_url, pdf_url)
                return pdf_url
            
            # Methode 5: Nach Download-Buttons suchen
            download_buttons = await page.query_selector_all("button:text('Download'), button[class*='download']")
            if download_buttons:
                await download_buttons[0].click()
                await asyncio.sleep(2)  # Warten, bis der Download-Link erscheint
                
                # Erneut nach PDF-Links suchen
                download_links = await page.query_selector_all("a[href*='.pdf']")
                if download_links:
                    pdf_url = await download_links[0].get_attribute('href')
                    if pdf_url:
                        return pdf_url
            
            # Methode 6: Netzwerkanfragen nach PDF-Dateien überprüfen
            # Dies ist eine fortgeschrittenere Methode, die dynamisch geladene PDFs erfassen könnte
            async def handle_response(response):
                if '.pdf' in response.url:
                    return response.url
            
            page.on('response', handle_response)
            
            # Seite neu laden, um den Response-Handler auszulösen
            await page.reload(wait_until='networkidle')
            await asyncio.sleep(5)  # Auf potenzielle PDF-Responses warten
            
            # Screenshot für Debugging erstellen
            screenshot_path = os.path.join(self.output_dir, f"debug_screenshot_{int(datetime.now().timestamp())}.png")
            await page.screenshot(path=screenshot_path)
            logger.info(f"Debug-Screenshot gespeichert unter {screenshot_path}")
            
            # Methode 7: Nach data-src-Attributen suchen
            elements_with_data_src = await page.query_selector_all("[data-src*='.pdf']")
            if elements_with_data_src:
                pdf_url = await elements_with_data_src[0].get_attribute('data-src')
                if pdf_url and not pdf_url.startswith('http'):
                    pdf_url = urljoin(flyer_url, pdf_url)
                return pdf_url
            
            # Methode 8: Nach PDF-URLs in Script-Tags suchen
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
            
            logger.error(f"Keine PDF-URL auf der Seite gefunden: {flyer_url}")
            return None
            
        except Exception as e:
            logger.error(f"Fehler beim Extrahieren der PDF-URL: {str(e)}")
            return None
    
    def download_pdf(self, url, title):
        """
        Eine PDF-Datei herunterladen.
        
        Args:
            url (str): URL der PDF-Datei
            title (str): Titel für den Dateinamen
            
        Returns:
            str: Pfad zur heruntergeladenen Datei oder None, wenn der Download fehlgeschlagen ist
        """
        try:
            # Besseren Titel aus der URL oder dem Content-Disposition-Header extrahieren
            better_title = title
            
            # Versuchen, einen besseren Titel aus der URL zu holen
            url_match = re.search(r'([^/]+)\.pdf', url)
            if url_match:
                better_title = url_match.group(1)
            
            # Content-Disposition-Header überprüfen
            head_response = requests.head(url)
            if 'content-disposition' in head_response.headers:
                cd_match = re.search(r'filename\*?=(?:UTF-8\'\'|")?([^"]+)', head_response.headers['content-disposition'])
                if cd_match:
                    better_title = cd_match.group(1)
                    better_title = better_title.replace('%20', ' ').replace('%25', '%')
                    better_title = re.sub(r'\.pdf$', '', better_title)
            
            # Eindeutigen Dateinamen mit Zeitstempel erstellen
            date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            sanitized_title = re.sub(r'[^\w\-_\. ]', '_', better_title)
            filename = f"aldi_prospekt_{sanitized_title}_{date_str}.pdf"
            filepath = os.path.join(self.output_dir, filename)
            
            # PDF herunterladen
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"Prospekt heruntergeladen nach {filepath}")
                return filepath
            else:
                logger.error(f"PDF-Download fehlgeschlagen: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Fehler beim Herunterladen des PDFs: {str(e)}")
        
        return None
    
    async def run(self):
        """Scraper ausführen, um alle Prospekte herunterzuladen."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            
            # Viewport-Größe setzen
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            try:
                flyer_links = await self.get_flyer_links(page)
                
                if not flyer_links:
                    logger.warning("Keine Prospekte gefunden")
                    return []
                
                downloaded_files = []
                for flyer in flyer_links:
                    pdf_url = await self.extract_pdf_url(page, flyer['url'])
                    if pdf_url:
                        logger.info(f"PDF-URL gefunden: {pdf_url}")
                        filepath = self.download_pdf(pdf_url, flyer['title'])
                        if filepath:
                            downloaded_files.append(filepath)
                    else:
                        logger.warning(f"Keine PDF-URL für Prospekt gefunden: {flyer['title']}")
                
                logger.info(f"{len(downloaded_files)} Prospekte heruntergeladen")
                return downloaded_files
                
            finally:
                await browser.close()

async def main_async(args):
    """Asynchrone Hauptfunktion zum Ausführen des Scrapers."""
    logger.info(f"Starte Aldi Prospekt-Scraper mit Ausgabeverzeichnis: {args.output_dir}")
    
    scraper = AldiProspektScraper(output_dir=args.output_dir, headless=args.headless)
    downloaded_files = await scraper.run()
    
    if downloaded_files:
        logger.info("Prospekte erfolgreich heruntergeladen:")
        for file in downloaded_files:
            logger.info(f"  - {file}")
    else:
        logger.warning("Es wurden keine Prospekte heruntergeladen")

def main():
    """Hauptfunktion zum Ausführen des Scrapers."""
    parser = argparse.ArgumentParser(description='Aldi Süd Prospekte mit Playwright scrapen und herunterladen')
    parser.add_argument('--output_dir', type=str, default='./prospekte',
                        help='Verzeichnis zum Speichern der heruntergeladenen Prospekte')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Browser im Headless-Modus ausführen')
    
    args = parser.parse_args()
    
    # Asynchrone Hauptfunktion ausführen
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()
