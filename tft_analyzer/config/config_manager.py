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


def default_config() -> dict[str, Any]:
    return {
        "base_resolution": [1920, 1080],
        "capture": {
            "mode": "full_screen",
            "window_title_contains": "Teamfight Tactics",
            "region": [0, 0, 1920, 1080],
            "auto_refresh_ms": 2500,
        },
        "ocr": {"tesseract_cmd": "", "language": "eng"},
        "regions": {
            "stage": {"bbox": [845, 24, 230, 52]},
            "hp": {"bbox": [382, 986, 80, 40]},
            "gold": {"bbox": [865, 990, 110, 44]},
            "level": {"bbox": [780, 988, 70, 44]},
            "augments": [
                {"bbox": [16, 220, 230, 70]},
                {"bbox": [16, 300, 230, 70]},
                {"bbox": [16, 380, 230, 70]},
            ],
            "board_slots": _grid(555, 360, 92, 78, 7, 4, stagger=True),
            "bench_slots": _grid(520, 882, 98, 82, 9, 1),
            "item_slots": _grid(1228, 838, 54, 54, 10, 1),
        },
        "vision": {"occupied_threshold": 0.18, "item_threshold": 0.14},
    }


def _grid(x: int, y: int, w: int, h: int, cols: int, rows: int, stagger: bool = False) -> list[dict[str, list[int]]]:
    slots: list[dict[str, list[int]]] = []
    for row in range(rows):
        for col in range(cols):
            offset = 46 if stagger and row % 2 else 0
            slots.append({"bbox": [x + col * w + offset, y + row * h, w - 8, h - 8]})
    return slots
