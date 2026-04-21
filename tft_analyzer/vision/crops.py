from __future__ import annotations

from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


def scaled_bbox(bbox: Iterable[int], base_size: list[int], image_shape: tuple[int, ...]) -> list[int]:
    x, y, w, h = [int(v) for v in bbox]
    base_w, base_h = base_size
    img_h, img_w = image_shape[:2]
    sx = img_w / max(base_w, 1)
    sy = img_h / max(base_h, 1)
    return [round(x * sx), round(y * sy), round(w * sx), round(h * sy)]


def crop(image_bgr: np.ndarray, bbox: Iterable[int]) -> np.ndarray:
    x, y, w, h = [int(v) for v in bbox]
    img_h, img_w = image_bgr.shape[:2]
    x1 = max(0, min(img_w, x))
    y1 = max(0, min(img_h, y))
    x2 = max(0, min(img_w, x + w))
    y2 = max(0, min(img_h, y + h))
    return image_bgr[y1:y2, x1:x2].copy()


def save_crop(path: Path, image_bgr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image_bgr)
