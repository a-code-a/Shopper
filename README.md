# Aldi Prospekt Scraper

Ein Tool zum automatischen Scrapen und Herunterladen von Prospekten von der Aldi Süd Website.

## Features

- Navigiert automatisch zur Aldi Süd Prospekte-Seite
- Behandelt Cookie-Consent-Banner
- Extrahiert Links zu aktuellen Prospekten
- Lädt die Prospekte als PDFs herunter
- Speichert sie mit aussagekräftigen Dateinamen basierend auf Typ, Kalenderwoche und Datum
- Vermeidet das erneute Herunterladen von bereits vorhandenen Prospekten
- Speichert Metadaten zu den heruntergeladenen Prospekten für eine bessere Verwaltung

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
python aldi_scraper.py [--output_dir OUTPUT_DIR] [--headless] [--force]
```

### Parameter

- `--output_dir`: Verzeichnis zum Speichern der heruntergeladenen Prospekte (Standard: `./prospekte`)
- `--headless`: Browser im Headless-Modus ausführen (Standard: True)
- `--force`: Prospekte erneut herunterladen, auch wenn sie bereits existieren (Standard: False)

## Beispiele

### Standardausführung

```bash
python aldi_scraper.py
```

Dies lädt alle aktuellen Aldi Süd Prospekte in das Verzeichnis `./prospekte` herunter, überspringt aber bereits vorhandene Prospekte.

### Benutzerdefiniertes Ausgabeverzeichnis

```bash
python aldi_scraper.py --output_dir ./aldi_prospekte
```

### Erneutes Herunterladen erzwingen

```bash
python aldi_scraper.py --force
```

Dies lädt alle Prospekte erneut herunter, auch wenn sie bereits existieren.

## Dateinamenformat

Die Prospekte werden mit aussagekräftigen Namen gespeichert, die folgende Informationen enthalten:

- Name des Supermarkts (immer "Aldi_Sued")
- Typ des Prospekts (z.B. "Wochenangebot", "Reisemagazin", "Garten-Broschüre")
- Kalenderwoche (z.B. "KW17")
- Monat oder Datum (z.B. "Januar", "April")
- Jahr (z.B. "2025")

Beispiele für Dateinamen:
- `Aldi_Sued_Wochenangebot_KW17_2025.pdf`
- `Aldi_Sued_Reisemagazin_April_2025.pdf`
- `Aldi_Sued_Garten-Broschüre_2025.pdf`
- `Aldi_Sued_Inlineflyer_KW15_2025.pdf`

## Metadaten

Das Tool speichert Metadaten zu den heruntergeladenen Prospekten in einer JSON-Datei (`prospekte_metadata.json`) im Ausgabeverzeichnis. Diese Metadaten enthalten:

- URL des Prospekts
- Titel
- Dateiname
- Dateipfad
- SHA-256-Hash der Datei
- Zeitpunkt des Downloads
- Informationen zum Prospekt (Typ, Kalenderwoche, Datum, Jahr)

## Hinweise

- Das Tool verwendet Playwright zur Browser-Automatisierung, um JavaScript-geladene Inhalte zu verarbeiten
- Cookie-Consent wird automatisch behandelt
- Wenn ein Prospekt nicht heruntergeladen werden kann, wird ein Screenshot zur Fehlersuche gespeichert

## Duplikaterkennung

Das Tool verwendet mehrere Methoden, um Duplikate zu erkennen und zu vermeiden:

1. **URL-basierte Erkennung**: Wenn ein Prospekt mit derselben URL bereits heruntergeladen wurde, wird es übersprungen.

2. **Inhaltsbasierte Erkennung**: Selbst wenn die URL unterschiedlich ist, erkennt das Tool inhaltlich identische Prospekte anhand ihres Datei-Hashes.

3. **Metadaten-basierte Erkennung**: Das Tool erkennt Prospekte mit gleichen Eigenschaften (Typ, Kalenderwoche, Jahr, Datum) und vermeidet Duplikate.

Beispiele:
- Wenn ein Wochenangebot für KW17 2025 bereits heruntergeladen wurde, wird ein weiteres Wochenangebot für dieselbe Woche nicht erneut heruntergeladen, auch wenn die URL unterschiedlich ist.
- Wenn ein Reisemagazin für April 2025 bereits heruntergeladen wurde, wird ein weiteres Reisemagazin für denselben Monat und Jahr nicht erneut heruntergeladen.

Diese intelligente Duplikaterkennung stellt sicher, dass jedes Prospekt nur einmal heruntergeladen wird, selbst wenn es unter verschiedenen URLs verfügbar ist oder wenn der Scraper mehrfach ausgeführt wird.
