# TFT Screen State Analyzer

Windows-only local desktop MVP for reading the visible Teamfight Tactics screen and showing a neutral state summary. It uses PySide6 for the UI, Pillow/pywin32 for capture, OpenCV for crop and occupancy heuristics, and local Tesseract OCR through `pytesseract`.

The app also includes a private-prototype TFT Academy source adapter. It scrapes public comp-related pages once on startup or when manually refreshed, stores normalized results in a local SQLite cache, and the analyzer reads from that cache rather than making live website requests during screen analysis.

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

- Captures the visible client area of the `League of Legends (TM) Client` window by default, with full-screen and region modes available for fallback.
- Stores crop regions in JSON under `config/default_config.json`.
- OCRs stage, HP, gold, level, and augment text on a best-effort basis.
- Detects occupied board, bench, and item bench slots using local OpenCV heuristics.
- Builds a normalized `GameState` model with confidence values.
- Provides a modern dark desktop UI with Dashboard, Comps, Comp Details, Items, Augments, Units, Tier List, Team Builder, Match History, and Settings pages.
- Uses reusable PySide UI components for cards, stat tiles, chips, badges, search/filter bars, item/unit tiles, toggles, empty states, and calibration preview.
- Shows calibration screenshot preview, parsed state summaries, cached comp details, and neutral analyzer output.
- Provides an optional passive always-on-top desktop overlay with compact visible-state and cached-comp-fit summaries.
- Manually refreshes cached TFT Academy comp data using configurable seed URLs and selectors in `config/tft_academy_scraper.json`.
- Stores normalized comps in SQLite at `cache/tft_comps.sqlite3`.
- Scores cached comps against the detected state using non-prescriptive fit signals: unit overlap, item fit, augment fit, level/econ fit, parse confidence, and unknown-field penalties.
- Exports JSON state snapshots to `exports/`.
- Exports the cached comp database to JSON from the desktop UI.
- Saves debug crops to `debug/`.
- Calibration mode lets you draw a new crop for stage, HP, gold, or level on the current preview.

## Calibration

Capture a screen, enable `Calibration Mode`, choose a target field, and drag a rectangle on the preview. The app saves that crop and updates `base_resolution` to the current screenshot size. For `board_slots`, `bench_slots`, and `item_slots`, draw the full area and the app will generate the slot grid automatically.

## Overlay Mode

Enable **Overlay** in the main app to show a compact always-on-top companion panel. It is a normal transparent desktop window, not a game-injected overlay. It does not hook DirectX, read game memory, or control mouse/keyboard input.

The overlay can be dragged while click-through is off. Enable **Click-through** when you want mouse clicks to pass to the game or other windows underneath it. Use the opacity slider to make it less intrusive.

For live tracking, enable **Auto-refresh**. The default refresh interval is `500 ms`; lower values are available down to `250 ms`, but OCR and screenshot capture may take longer on some PCs. The app skips overlapping captures so it stays responsive instead of building a backlog. **Live fast mode** reduces lag by OCRing every few frames, avoiding preview scaling during auto-refresh unless enabled, and updating the heavy text panels at most once per second.

## TFT Academy Cache

The TFT Academy integration is a fragile unofficial adapter for public pages. Website markup can change without notice, so parsing is selector-driven and isolated in `tft_analyzer/sources/tft_academy.py`.

The app refreshes TFT Academy comp data once on startup and stores it in `cache/tft_comps.sqlite3`. You can also refresh manually with **Refresh TFT Academy Data**. Live analysis only reads from the local cache; it does not call TFT Academy on every capture or frame.

The **TFT Academy Comps** panel lists cached comps. Selecting a comp shows its parsed champs, items, augments, tags, confidence, and source URL.

If parsing fails, raw HTML snapshots are written to `debug/html_snapshots/` for inspection. Adjust seed URLs and selectors in:

```text
config/tft_academy_scraper.json
```

Future source adapters can output the same `NormalizedComp` model and write through `CompRepository`.

## Known Limitations

- OCR quality depends on local Tesseract installation, TFT resolution, UI scale, and crop calibration.
- Occupancy detection is heuristic and can confuse bright empty slots, shadows, effects, or busy backgrounds.
- Window capture uses the visible League client area; minimized or covered windows may not capture correctly.
- Augment and archetype detection are best-effort text summaries, not strategy recommendations.
- The app does not identify champion names, item names, traits, shops, combat outcomes, or hidden state.
- TFT Academy scraping is unofficial and brittle. Selectors may need updating when the site changes.
- Candidate comp scores are descriptive fit estimates from visible/cached data, not recommendations or coaching instructions.
- If no cache exists or scraping fails, the screen analyzer continues to work without comp scoring.
- Overlay mode is a desktop companion window and may not appear over exclusive fullscreen games. Borderless/windowed fullscreen is more reliable.

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
