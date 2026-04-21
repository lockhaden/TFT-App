# TFT Screen State Analyzer

Windows-only local desktop MVP for reading the visible Teamfight Tactics screen and showing a neutral state summary. It uses PySide6 for the UI, Pillow/pywin32 for capture, OpenCV for crop and occupancy heuristics, and local Tesseract OCR through `pytesseract`.

The app also includes a private-prototype TFT Academy source adapter. It scrapes public comp-related pages only when manually refreshed, stores normalized results in a local SQLite cache, and the analyzer reads from that cache rather than making live website requests during screen analysis.

## Policy / Compliance Note

This app is intentionally non-prescriptive. It summarizes visible state only and does not implement gameplay automation or live coaching instructions such as when to buy, roll, level, slam items, or force a composition.

## Setup

1. Install Python 3.11+ on Windows.
2. Install Tesseract OCR locally. If it is not on `PATH`, set `ocr.tesseract_cmd` in `config/default_config.json` after the first run.
3. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

4. Run:

```powershell
python main.py
```

## Packaged EXE

A one-file Windows executable can be built with PyInstaller:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm TFTScreenStateAnalyzer.spec
```

The built app is:

```text
dist/TFTScreenStateAnalyzer.exe
```

Copy that `.exe` to another Windows PC. For OCR, the other PC must also have Tesseract OCR installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`, or you must update `config/default_config.json` after first launch to point at that PC's Tesseract executable. The app can still open without OCR, but OCR fields will be unknown.

## Features

- Captures full screen, a configured region, or a visible window title containing `Teamfight Tactics`.
- Stores crop regions in JSON under `config/default_config.json`.
- OCRs stage, HP, gold, level, and augment text on a best-effort basis.
- Detects occupied board, bench, and item bench slots using local OpenCV heuristics.
- Builds a normalized `GameState` model with confidence values.
- Shows screenshot preview, parsed JSON state, and a neutral analyzer summary.
- Manually refreshes cached TFT Academy comp data using configurable seed URLs and selectors in `config/tft_academy_scraper.json`.
- Stores normalized comps in SQLite at `cache/tft_comps.sqlite3`.
- Scores cached comps against the detected state using non-prescriptive fit signals: unit overlap, item fit, augment fit, level/econ fit, parse confidence, and unknown-field penalties.
- Exports JSON state snapshots to `exports/`.
- Exports the cached comp database to JSON from the desktop UI.
- Saves debug crops to `debug/`.
- Calibration mode lets you draw a new crop for stage, HP, gold, or level on the current preview.

## Calibration

Capture a screen, enable `Calibration Mode`, choose a target field, and drag a rectangle on the preview. The app saves that crop and updates `base_resolution` to the current screenshot size. For board, bench, and item slots, edit the JSON lists directly for now.

## TFT Academy Cache

The TFT Academy integration is a fragile unofficial adapter for public pages. Website markup can change without notice, so parsing is selector-driven and isolated in `tft_analyzer/sources/tft_academy.py`.

To refresh cached comp data, use **Refresh TFT Academy Data** in the UI. The analyzer only reads from `cache/tft_comps.sqlite3`; it does not call TFT Academy on every capture or frame.

If parsing fails, raw HTML snapshots are written to `debug/html_snapshots/` for inspection. Adjust seed URLs and selectors in:

```text
config/tft_academy_scraper.json
```

Future source adapters can output the same `NormalizedComp` model and write through `CompRepository`.

## Known Limitations

- OCR quality depends on local Tesseract installation, TFT resolution, UI scale, and crop calibration.
- Occupancy detection is heuristic and can confuse bright empty slots, shadows, effects, or busy backgrounds.
- Window capture uses the visible window rectangle; minimized or covered windows may not capture correctly.
- Augment and archetype detection are best-effort text summaries, not strategy recommendations.
- The app does not identify champion names, item names, traits, shops, combat outcomes, or hidden state.
- TFT Academy scraping is unofficial and brittle. Selectors may need updating when the site changes.
- Candidate comp scores are descriptive fit estimates from visible/cached data, not recommendations or coaching instructions.
- If no cache exists or scraping fails, the screen analyzer continues to work without comp scoring.

## Repository Structure

- `tft_analyzer/capture`: screen and window capture
- `tft_analyzer/ocr`: local OCR wrapper and parsers
- `tft_analyzer/vision`: crops, slot occupancy, and state extraction
- `tft_analyzer/analysis`: neutral summary generation
- `tft_analyzer/models`: normalized state dataclasses
- `tft_analyzer/sources`: isolated website source adapters
- `tft_analyzer/storage`: SQLite repositories
- `tft_analyzer/ui`: PySide6 desktop UI
- `config`: JSON configuration
- `assets/templates`: placeholder local template assets
- `cache`: local SQLite cache files
- `debug`: logs, screenshots, and crop exports
- `exports`: exported state JSON
