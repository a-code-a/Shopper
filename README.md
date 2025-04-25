# Aldi Flyer Scraper

Ein Tool zum automatischen Scrapen und Herunterladen von Prospekten von der Aldi Süd Website.

## Features

- Navigiert automatisch zur Aldi Süd Prospekte-Seite
- Behandelt Cookie-Consent-Banner
- Extrahiert Links zu aktuellen Prospekten
- Lädt die Prospekte als PDFs herunter
- Speichert sie mit eindeutigen, beschreibenden Dateinamen

## Anforderungen

- Python 3.6+
- Chromium (wird automatisch von Playwright installiert)
- Benötigte Python-Pakete (Installation mit `pip install -r requirements.txt`):
  - playwright
  - requests

## Installation

1. Klone dieses Repository oder lade die Dateien herunter
2. Installiere die benötigten Abhängigkeiten:

```bash
pip install -r requirements.txt
```

3. Installiere die Playwright-Browser:

```bash
python -m playwright install
```

## Verwendung

```bash
python aldi_scraper.py [--output_dir OUTPUT_DIR] [--headless]
```

### Parameter

- `--output_dir`: Optionales Verzeichnis zum Speichern der heruntergeladenen Prospekte (Standard: `./prospekte`)
- `--headless`: Browser im Headless-Modus ausführen (Standard: True)

## Beispiel

```bash
python aldi_scraper.py --output_dir ./aldi_prospekte
```

Dies lädt alle aktuellen Aldi Süd Prospekte in das Verzeichnis `./aldi_prospekte` herunter.

## Hinweise

- Das Tool verwendet Playwright zur Browser-Automatisierung, um JavaScript-geladene Inhalte zu verarbeiten
- Cookie-Consent wird automatisch behandelt
- Prospekte werden mit eindeutigen, beschreibenden Dateinamen gespeichert, die das Datum und die Uhrzeit enthalten
- Wenn ein Prospekt nicht heruntergeladen werden kann, wird ein Screenshot zur Fehlersuche gespeichert
