from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from tft_analyzer.models.game_state import FieldValue, GameState
from tft_analyzer.ocr.ocr_engine import OcrEngine, parse_int, parse_stage
from tft_analyzer.vision.crops import crop, save_crop, scaled_bbox
from tft_analyzer.vision.occupancy import OccupancyDetector

LOGGER = logging.getLogger(__name__)


class StateExtractor:
    def __init__(self, config: dict) -> None:
        self.config = config
        ocr_config = config.get("ocr", {})
        self.ocr = OcrEngine(ocr_config.get("tesseract_cmd", ""), ocr_config.get("language", "eng"))
        vision_config = config.get("vision", {})
        self.occupancy = OccupancyDetector(
            vision_config.get("occupied_threshold", 0.18),
            vision_config.get("item_threshold", 0.14),
        )

    def extract(self, image_bgr: np.ndarray, source: str, debug_dir: Path | None = None) -> GameState:
        state = GameState(source=source, screenshot_size=[int(image_bgr.shape[1]), int(image_bgr.shape[0])])
        regions = self.config.get("regions", {})
        base_size = self.config.get("base_resolution", state.screenshot_size)

        state.stage = self._read_stage(image_bgr, regions.get("stage"), base_size, debug_dir)
        state.hp = self._read_int(image_bgr, regions.get("hp"), base_size, "hp", 0, 100, debug_dir)
        state.gold = self._read_int(image_bgr, regions.get("gold"), base_size, "gold", 0, 999, debug_dir)
        state.level = self._read_int(image_bgr, regions.get("level"), base_size, "level", 1, 10, debug_dir)
        state.augments = self._read_augments(image_bgr, regions.get("augments", []), base_size, debug_dir)

        state.board_slots = self.occupancy.detect_slots(image_bgr, regions.get("board_slots", []), base_size, "board")
        state.bench_slots = self.occupancy.detect_slots(image_bgr, regions.get("bench_slots", []), base_size, "bench")
        state.item_slots = self.occupancy.detect_slots(image_bgr, regions.get("item_slots", []), base_size, "item")

        if not self.ocr.available:
            state.warnings.append("OCR engine unavailable; install Tesseract and configure its path if needed")
        return state

    def save_debug_crops(self, image_bgr: np.ndarray, debug_dir: Path) -> None:
        regions = self.config.get("regions", {})
        base_size = self.config.get("base_resolution", [image_bgr.shape[1], image_bgr.shape[0]])
        for key, region in regions.items():
            if isinstance(region, dict) and "bbox" in region:
                save_crop(debug_dir / f"{key}.png", crop(image_bgr, scaled_bbox(region["bbox"], base_size, image_bgr.shape)))
            elif isinstance(region, list):
                for idx, entry in enumerate(region):
                    if isinstance(entry, dict) and "bbox" in entry:
                        save_crop(debug_dir / f"{key}_{idx:02d}.png", crop(image_bgr, scaled_bbox(entry["bbox"], base_size, image_bgr.shape)))

    def _read_int(
        self,
        image_bgr: np.ndarray,
        region: dict | None,
        base_size: list[int],
        name: str,
        min_value: int,
        max_value: int,
        debug_dir: Path | None,
    ) -> FieldValue:
        if not region:
            return FieldValue(source=name)
        image = crop(image_bgr, scaled_bbox(region["bbox"], base_size, image_bgr.shape))
        if debug_dir:
            save_crop(debug_dir / f"ocr_{name}.png", image)
        result = self.ocr.read_text(image, "0123456789")
        value, confidence = parse_int(result, min_value, max_value)
        return FieldValue(value=value, confidence=round(confidence, 3), source=name, raw_text=result.text)

    def _read_stage(self, image_bgr: np.ndarray, region: dict | None, base_size: list[int], debug_dir: Path | None) -> FieldValue:
        if not region:
            return FieldValue(source="stage")
        image = crop(image_bgr, scaled_bbox(region["bbox"], base_size, image_bgr.shape))
        if debug_dir:
            save_crop(debug_dir / "ocr_stage.png", image)
        result = self.ocr.read_text(image, "0123456789-:")
        value, confidence = parse_stage(result)
        return FieldValue(value=value, confidence=round(confidence, 3), source="stage", raw_text=result.text)

    def _read_augments(self, image_bgr: np.ndarray, regions: list[dict], base_size: list[int], debug_dir: Path | None) -> list[FieldValue]:
        values: list[FieldValue] = []
        for idx, region in enumerate(regions):
            image = crop(image_bgr, scaled_bbox(region["bbox"], base_size, image_bgr.shape))
            if debug_dir:
                save_crop(debug_dir / f"ocr_augment_{idx}.png", image)
            result = self.ocr.read_text(image)
            values.append(FieldValue(value=result.text or None, confidence=round(result.confidence, 3), source=f"augment_{idx}", raw_text=result.text))
        return values
