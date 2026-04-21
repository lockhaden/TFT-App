# TFT Screen State Analyzer v0.1.0

Windows-only private local MVP for passive TFT screen-state analysis.

## Included

- Screen/window/region capture
- Configurable OCR crop regions
- Local Tesseract OCR integration
- Board, bench, and item-bench occupancy detection
- Neutral state analysis summary
- Local SQLite TFT Academy comp cache
- Manual TFT Academy refresh
- Cache-backed candidate comp fit scoring
- JSON export for detected state and cached comps

## Notes

- No gameplay automation
- No mouse or keyboard control
- No memory reading or hidden-state access
- TFT Academy adapter is unofficial and may need selector updates if the site changes
- Tesseract OCR should be installed on the target PC at `C:\Program Files\Tesseract-OCR\tesseract.exe`
