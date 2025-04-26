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
import hashlib
import json
from datetime import datetime
from urllib.parse import urljoin, parse_qs, urlparse

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
    METADATA_FILE = "prospekte_metadata.json"

    def __init__(self, output_dir="./prospekte", headless=True, force_download=False):
        """
        Initialisiert den Scraper.

        Args:
            output_dir (str): Verzeichnis zum Speichern der heruntergeladenen Prospekte
            headless (bool): Ob der Browser im Headless-Modus ausgeführt werden soll
            force_download (bool): Ob Prospekte erneut heruntergeladen werden sollen, auch wenn sie bereits existieren
        """
        self.output_dir = output_dir
        self.headless = headless
        self.force_download = force_download
        self.metadata_path = os.path.join(output_dir, self.METADATA_FILE)
        self.metadata = self._load_metadata()

        # Ausgabeverzeichnis erstellen, falls es nicht existiert
        os.makedirs(output_dir, exist_ok=True)

    def _load_metadata(self):
        """Lädt die Metadaten der bereits heruntergeladenen Prospekte."""
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                    # Überprüfen, ob alle in den Metadaten aufgeführten Dateien noch existieren
                    # und entferne Einträge für nicht mehr existierende Dateien
                    to_remove = []
                    for url_hash, info in metadata["prospekte"].items():
                        if "filepath" in info and not os.path.exists(info["filepath"]):
                            to_remove.append(url_hash)

                    for url_hash in to_remove:
                        del metadata["prospekte"][url_hash]

                    # Wenn Dateien entfernt wurden, speichere die aktualisierten Metadaten
                    if to_remove:
                        with open(self.metadata_path, 'w', encoding='utf-8') as f:
                            json.dump(metadata, f, ensure_ascii=False, indent=2)

                    return metadata
            except Exception as e:
                logger.warning(f"Fehler beim Laden der Metadaten: {str(e)}")
        return {"prospekte": {}, "last_update": "", "file_hashes": {}}

    def _save_metadata(self):
        """Speichert die Metadaten der heruntergeladenen Prospekte."""
        self.metadata["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Fehler beim Speichern der Metadaten: {str(e)}")

    def _get_file_hash(self, file_path):
        """Berechnet den SHA-256-Hash einer Datei."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _extract_prospekt_info(self, url, title):
        """
        Extrahiert Informationen über den Prospekt aus der URL und dem Titel.

        Returns:
            dict: Informationen über den Prospekt (Typ, Datum, etc.)
        """
        info = {
            "typ": "Unbekannt",
            "datum": "",
            "kalenderwoche": "",
            "jahr": datetime.now().year,
            "supermarkt": "Aldi_Sued"
        }

        # Versuchen, Informationen aus der URL zu extrahieren
        url_path = urlparse(url).path
        filename = os.path.basename(url_path)

        # Kalenderwoche aus URL oder Titel extrahieren
        kw_match = re.search(r'kw(\d+)', url.lower() + " " + title.lower())
        if kw_match:
            info["kalenderwoche"] = kw_match.group(1)
            info["typ"] = "Wochenangebot"

        # Jahr aus URL oder Titel extrahieren
        jahr_match = re.search(r'20(\d{2})', url + " " + title)
        if jahr_match:
            info["jahr"] = "20" + jahr_match.group(1)

        # Spezielle Prospekttypen erkennen
        if "reisemagazin" in url.lower() or "reisemagazin" in title.lower():
            info["typ"] = "Reisemagazin"
            monat_match = re.search(r'(januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)',
                                   url.lower() + " " + title.lower())
            if monat_match:
                info["datum"] = monat_match.group(1).capitalize()

        elif "garten" in url.lower() or "garten" in title.lower():
            info["typ"] = "Garten-Broschüre"

        elif "themenkatalog" in url.lower() or "themenkatalog" in title.lower():
            info["typ"] = "Themenkatalog"
            monat_match = re.search(r'(januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)',
                                   url.lower() + " " + title.lower())
            if monat_match:
                info["datum"] = monat_match.group(1).capitalize()

        elif "inlineflyer" in url.lower() or "inlineflyer" in title.lower():
            info["typ"] = "Inlineflyer"

        # Versuchen, Datum aus Query-Parametern zu extrahieren
        query_params = parse_qs(urlparse(url).query)
        if "valid_from" in query_params:
            info["datum"] = query_params["valid_from"][0]

        # Extrahiere Kalenderwoche aus dem Inlineflyer-Namen, falls vorhanden
        if info["typ"] == "Inlineflyer" and not info["kalenderwoche"]:
            kw_match = re.search(r'kw[-_]?(\d+)', url.lower())
            if kw_match:
                info["kalenderwoche"] = kw_match.group(1)
            elif "kw" in url.lower():
                # Versuche, die Zahl nach "kw" zu extrahieren
                kw_num_match = re.search(r'kw[^0-9]*(\d+)', url.lower())
                if kw_num_match:
                    info["kalenderwoche"] = kw_num_match.group(1)

        return info

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

    def download_pdf(self, url, title, flyer_url):
        """
        Eine PDF-Datei herunterladen, wenn sie noch nicht existiert.

        Args:
            url (str): URL der PDF-Datei
            title (str): Titel für den Dateinamen
            flyer_url (str): URL der Prospektseite

        Returns:
            str: Pfad zur heruntergeladenen Datei oder None, wenn der Download fehlgeschlagen ist
        """
        try:
            # URL-Hash für die Duplikaterkennung
            url_hash = hashlib.md5(url.encode()).hexdigest()

            # Prüfen, ob die URL bereits in den Metadaten vorhanden ist
            if url_hash in self.metadata["prospekte"] and not self.force_download:
                existing_file = self.metadata["prospekte"][url_hash]["filepath"]
                if os.path.exists(existing_file):
                    logger.info(f"Prospekt bereits vorhanden: {existing_file}")
                    return existing_file

            # Prospektinformationen extrahieren
            prospekt_info = self._extract_prospekt_info(flyer_url, title)

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

            # Eindeutigen Dateinamen erstellen
            sanitized_title = re.sub(r'[^\w\-_\. ]', '_', better_title)

            # Dateiname mit Supermarkt, Typ, Kalenderwoche und Jahr erstellen
            filename_parts = []

            # Supermarkt hinzufügen
            filename_parts.append(prospekt_info["supermarkt"])

            # Typ hinzufügen
            if prospekt_info["typ"] != "Unbekannt":
                filename_parts.append(prospekt_info["typ"])

            # Kalenderwoche hinzufügen, falls vorhanden
            if prospekt_info["kalenderwoche"]:
                filename_parts.append(f"KW{prospekt_info['kalenderwoche']}")

            # Datum oder Monat hinzufügen, falls vorhanden
            if prospekt_info["datum"]:
                filename_parts.append(prospekt_info["datum"])

            # Jahr hinzufügen
            filename_parts.append(str(prospekt_info["jahr"]))

            # Wenn keine spezifischen Informationen gefunden wurden, den bereinigten Titel verwenden
            if len(filename_parts) <= 2:  # Nur Supermarkt und Jahr vorhanden
                filename_parts = [prospekt_info["supermarkt"], sanitized_title]

            # Dateiname zusammensetzen
            base_filename = "_".join(filename_parts)
            filename = f"{base_filename}.pdf"
            filepath = os.path.join(self.output_dir, filename)

            # Prüfen, ob wir das Prospekt bereits haben, basierend auf Typ, KW und Jahr
            if not self.force_download:
                # Suche nach Prospekten mit gleichem Typ, KW und Jahr
                for stored_hash, stored_info in self.metadata["prospekte"].items():
                    stored_info_type = stored_info.get("info", {}).get("typ", "")
                    stored_info_kw = stored_info.get("info", {}).get("kalenderwoche", "")
                    stored_info_year = stored_info.get("info", {}).get("jahr", "")
                    stored_info_date = stored_info.get("info", {}).get("datum", "")

                    # Wenn es sich um ein Wochenangebot handelt, prüfe KW und Jahr
                    if (prospekt_info["typ"] == "Wochenangebot" and
                        stored_info_type == "Wochenangebot" and
                        prospekt_info["kalenderwoche"] == stored_info_kw and
                        str(prospekt_info["jahr"]) == str(stored_info_year)):

                        existing_file = stored_info["filepath"]
                        if os.path.exists(existing_file):
                            # Füge die neue URL zu den Metadaten hinzu
                            self.metadata["prospekte"][url_hash] = stored_info
                            self._save_metadata()
                            logger.info(f"Wochenangebot für KW{prospekt_info['kalenderwoche']} {prospekt_info['jahr']} bereits vorhanden: {existing_file}")
                            return existing_file

                    # Wenn es sich um ein Reisemagazin oder Themenkatalog handelt, prüfe Datum und Jahr
                    elif ((prospekt_info["typ"] == "Reisemagazin" or prospekt_info["typ"] == "Themenkatalog") and
                          stored_info_type == prospekt_info["typ"] and
                          prospekt_info["datum"] == stored_info_date and
                          str(prospekt_info["jahr"]) == str(stored_info_year)):

                        existing_file = stored_info["filepath"]
                        if os.path.exists(existing_file):
                            # Füge die neue URL zu den Metadaten hinzu
                            self.metadata["prospekte"][url_hash] = stored_info
                            self._save_metadata()
                            logger.info(f"{prospekt_info['typ']} für {prospekt_info['datum']} {prospekt_info['jahr']} bereits vorhanden: {existing_file}")
                            return existing_file

                    # Wenn es sich um einen Inlineflyer handelt, prüfe KW und Jahr
                    elif (prospekt_info["typ"] == "Inlineflyer" and
                          stored_info_type == "Inlineflyer" and
                          prospekt_info["kalenderwoche"] == stored_info_kw and
                          str(prospekt_info["jahr"]) == str(stored_info_year)):

                        existing_file = stored_info["filepath"]
                        if os.path.exists(existing_file):
                            # Füge die neue URL zu den Metadaten hinzu
                            self.metadata["prospekte"][url_hash] = stored_info
                            self._save_metadata()
                            logger.info(f"Inlineflyer für KW{prospekt_info['kalenderwoche']} {prospekt_info['jahr']} bereits vorhanden: {existing_file}")
                            return existing_file

            # Prüfen, ob eine Datei mit diesem Namen bereits existiert
            if os.path.exists(filepath) and not self.force_download:
                # Prüfen, ob die Datei bereits in den Metadaten vorhanden ist
                for stored_hash, stored_info in self.metadata["prospekte"].items():
                    if stored_info["filepath"] == filepath:
                        # Wenn die Datei bereits in den Metadaten ist, aber mit einer anderen URL,
                        # fügen wir die neue URL zu den Metadaten hinzu
                        if stored_hash != url_hash:
                            self.metadata["prospekte"][url_hash] = stored_info
                            self._save_metadata()
                        logger.info(f"Prospekt bereits vorhanden: {filepath}")
                        return filepath

                # Wenn die Datei existiert, aber nicht in den Metadaten ist,
                # fügen wir sie zu den Metadaten hinzu
                file_hash = self._get_file_hash(filepath)
                self.metadata["prospekte"][url_hash] = {
                    "url": url,
                    "flyer_url": flyer_url,
                    "title": title,
                    "filename": filename,
                    "filepath": filepath,
                    "hash": file_hash,
                    "downloaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "info": prospekt_info
                }

                # Speichere auch den Datei-Hash für die Duplikaterkennung
                if "file_hashes" not in self.metadata:
                    self.metadata["file_hashes"] = {}
                self.metadata["file_hashes"][file_hash] = url_hash

                self._save_metadata()
                logger.info(f"Prospekt bereits vorhanden (Metadaten aktualisiert): {filepath}")
                return filepath

            # Wenn die Datei bereits existiert, aber force_download aktiviert ist,
            # erstellen wir einen eindeutigen Dateinamen mit Zeitstempel
            if os.path.exists(filepath) and self.force_download:
                date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{base_filename}_{date_str}.pdf"
                filepath = os.path.join(self.output_dir, filename)

            # PDF herunterladen
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                # Zuerst in eine temporäre Datei herunterladen
                temp_filepath = filepath + ".tmp"
                with open(temp_filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Hash der heruntergeladenen Datei berechnen
                file_hash = self._get_file_hash(temp_filepath)

                # Prüfen, ob wir bereits eine Datei mit diesem Hash haben
                if "file_hashes" in self.metadata and file_hash in self.metadata["file_hashes"] and not self.force_download:
                    # Wir haben bereits eine identische Datei
                    existing_url_hash = self.metadata["file_hashes"][file_hash]
                    if existing_url_hash in self.metadata["prospekte"]:
                        existing_file = self.metadata["prospekte"][existing_url_hash]["filepath"]
                        if os.path.exists(existing_file):
                            # Lösche die temporäre Datei
                            os.remove(temp_filepath)

                            # Füge die neue URL zu den Metadaten hinzu
                            self.metadata["prospekte"][url_hash] = self.metadata["prospekte"][existing_url_hash]
                            self._save_metadata()

                            logger.info(f"Inhaltlich identischer Prospekt bereits vorhanden: {existing_file}")
                            return existing_file

                # Umbenennen der temporären Datei zur endgültigen Datei
                if os.path.exists(filepath):
                    os.remove(filepath)
                os.rename(temp_filepath, filepath)

                # Metadaten aktualisieren
                self.metadata["prospekte"][url_hash] = {
                    "url": url,
                    "flyer_url": flyer_url,
                    "title": title,
                    "filename": filename,
                    "filepath": filepath,
                    "hash": file_hash,
                    "downloaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "info": prospekt_info
                }

                # Speichere auch den Datei-Hash für die Duplikaterkennung
                if "file_hashes" not in self.metadata:
                    self.metadata["file_hashes"] = {}
                self.metadata["file_hashes"][file_hash] = url_hash

                self._save_metadata()

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
                        filepath = self.download_pdf(pdf_url, flyer['title'], flyer['url'])
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

    scraper = AldiProspektScraper(
        output_dir=args.output_dir,
        headless=args.headless,
        force_download=args.force
    )
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
    parser.add_argument('--force', action='store_true', default=False,
                        help='Prospekte erneut herunterladen, auch wenn sie bereits existieren')

    args = parser.parse_args()

    # Asynchrone Hauptfunktion ausführen
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()
