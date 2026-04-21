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
            score = self._occupancy_score(slot_image, kind)
            occupied = score >= threshold
            confidence = min(1.0, abs(score - threshold) / max(threshold, 0.01) + 0.35)
            states.append(SlotState(index=idx, occupied=occupied, confidence=round(confidence, 3), bbox=bbox, kind=kind))
        return states

    @staticmethod
    def _occupancy_score(slot_image: np.ndarray, kind: str) -> float:
        if slot_image.size == 0:
            return 0.0
        # This hand-built signal is intentionally replaceable. Template matching or a
        # trained detector can later slot in here without changing the GameState model.
        hsv = cv2.cvtColor(slot_image, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(slot_image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 140)
        edge_density = float(np.count_nonzero(edges)) / edges.size
        contrast = float(np.std(gray)) / 128.0
        h, w = gray.shape[:2]
        center = hsv[h // 5 : max(h // 5 + 1, 4 * h // 5), w // 5 : max(w // 5 + 1, 4 * w // 5)]
        center_sat = float(np.mean(center[:, :, 1])) / 255.0 if center.size else 0.0

        if kind == "item":
            bright = float(np.count_nonzero(center[:, :, 2] > 55)) / max(center.shape[0] * center.shape[1], 1)
            return 0.55 * center_sat + 0.25 * edge_density + 0.20 * bright

        green_bar = cv2.inRange(hsv, (35, 80, 80), (95, 255, 255))
        red_bar_a = cv2.inRange(hsv, (0, 80, 80), (12, 255, 255))
        red_bar_b = cv2.inRange(hsv, (170, 80, 80), (179, 255, 255))
        blue_bar = cv2.inRange(hsv, (85, 70, 80), (110, 255, 255))
        health_bar_pixels = cv2.countNonZero(green_bar | red_bar_a | red_bar_b | blue_bar)
        health_bar_density = health_bar_pixels / max(h * w, 1)

        return max(
            min(1.0, health_bar_density * 8.0),
            0.55 * min(1.0, health_bar_density * 6.0)
            + 0.20 * center_sat
            + 0.15 * edge_density
            + 0.10 * min(1.0, contrast),
        )
