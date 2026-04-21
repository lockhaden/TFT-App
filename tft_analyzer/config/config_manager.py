from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            sample = Path("config/sample_config.json")
            if sample.exists():
                shutil.copyfile(sample, self.path)
            else:
                self.path.write_text(json.dumps(default_config(), indent=2), encoding="utf-8")
        self.data = self.load()
        if self._migrate():
            self.save()

    def load(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            LOGGER.exception("Failed to load config, using in-memory defaults")
            return default_config()

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def get_regions(self) -> dict[str, Any]:
        return self.data.setdefault("regions", {})

    def set_region(self, name: str, bbox: list[int]) -> None:
        self.get_regions()[name] = {"bbox": bbox}
        self.save()

    def _migrate(self) -> bool:
        changed = False
        capture = self.data.setdefault("capture", {})
        if capture.get("window_title_contains") in ("", "Teamfight Tactics", None):
            capture["window_title_contains"] = "League of Legends (TM) Client"
            changed = True
        if capture.get("window_title_contains") == "League of Legends (TM) Client" and capture.get("mode") in ("", "full_screen", None):
            capture["mode"] = "window"
            changed = True
        if int(capture.get("auto_refresh_ms", 0) or 0) in (0, 2500):
            capture["auto_refresh_ms"] = 500
            changed = True
        if int(capture.get("ocr_every_n_frames", 0) or 0) <= 0:
            capture["ocr_every_n_frames"] = 4
            changed = True
        regions = self.data.setdefault("regions", {})
        item_slots = regions.get("item_slots", [])
        first_item = item_slots[0].get("bbox", []) if item_slots and isinstance(item_slots[0], dict) else []
        if self.data.get("base_resolution") == [1920, 1080] and first_item and first_item[0] > 1000:
            preset = default_config()
            self.data["base_resolution"] = preset["base_resolution"]
            self.data["regions"] = preset["regions"]
            self.data["vision"] = preset["vision"]
            capture["region"] = preset["capture"]["region"]
            changed = True
        ocr = self.data.setdefault("ocr", {})
        default_tesseract = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if not ocr.get("tesseract_cmd") and default_tesseract.exists():
            ocr["tesseract_cmd"] = str(default_tesseract)
            changed = True
        return changed


def default_config() -> dict[str, Any]:
    return {
        "base_resolution": [1920, 968],
        "capture": {
            "mode": "window",
            "window_title_contains": "League of Legends (TM) Client",
            "region": [0, 0, 1920, 968],
            "auto_refresh_ms": 500,
            "ocr_every_n_frames": 4,
        },
        "ocr": {"tesseract_cmd": "", "language": "eng"},
        "regions": {
            "stage": {"bbox": [690, 0, 115, 36]},
            "hp": {"bbox": [1715, 150, 95, 55]},
            "gold": {"bbox": [910, 800, 115, 45]},
            "level": {"bbox": [315, 800, 150, 45]},
            "augments": [
                {"bbox": [16, 220, 230, 70]},
                {"bbox": [16, 300, 230, 70]},
                {"bbox": [16, 380, 230, 70]},
            ],
            "board_slots": _grid(640, 340, 78, 58, 7, 4, stagger=True),
            "bench_slots": _grid(360, 640, 104, 74, 9, 1),
            "item_slots": _grid(8, 252, 43, 47, 1, 10),
        },
        "vision": {"occupied_threshold": 0.32, "item_threshold": 0.22},
    }


def _grid(x: int, y: int, w: int, h: int, cols: int, rows: int, stagger: bool = False) -> list[dict[str, list[int]]]:
    slots: list[dict[str, list[int]]] = []
    for row in range(rows):
        for col in range(cols):
            offset = 46 if stagger and row % 2 else 0
            slots.append({"bbox": [x + col * w + offset, y + row * h, w - 8, h - 8]})
    return slots
