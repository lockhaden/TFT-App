from __future__ import annotations

import cv2
import numpy as np

from tft_analyzer.models.game_state import SlotState
from tft_analyzer.vision.crops import crop, scaled_bbox


class OccupancyDetector:
    def __init__(self, occupied_threshold: float = 0.18, item_threshold: float = 0.14) -> None:
        self.occupied_threshold = occupied_threshold
        self.item_threshold = item_threshold

    def detect_slots(
        self,
        image_bgr: np.ndarray,
        slot_regions: list[dict],
        base_size: list[int],
        kind: str,
    ) -> list[SlotState]:
        threshold = self.item_threshold if kind == "item" else self.occupied_threshold
        states: list[SlotState] = []
        for idx, region in enumerate(slot_regions):
            bbox = scaled_bbox(region["bbox"], base_size, image_bgr.shape)
            slot_image = crop(image_bgr, bbox)
            score = self._occupancy_score(slot_image)
            occupied = score >= threshold
            confidence = min(1.0, abs(score - threshold) / max(threshold, 0.01) + 0.35)
            states.append(SlotState(index=idx, occupied=occupied, confidence=round(confidence, 3), bbox=bbox, kind=kind))
        return states

    @staticmethod
    def _occupancy_score(slot_image: np.ndarray) -> float:
        if slot_image.size == 0:
            return 0.0
        # This hand-built signal is intentionally replaceable. Template matching or a
        # trained detector can later slot in here without changing the GameState model.
        hsv = cv2.cvtColor(slot_image, cv2.COLOR_BGR2HSV)
        saturation = float(np.mean(hsv[:, :, 1])) / 255.0
        gray = cv2.cvtColor(slot_image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 140)
        edge_density = float(np.count_nonzero(edges)) / edges.size
        contrast = float(np.std(gray)) / 128.0
        return 0.45 * saturation + 0.35 * edge_density + 0.20 * min(1.0, contrast)
