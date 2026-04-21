from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)


@dataclass
class OcrResult:
    text: str
    confidence: float


class OcrEngine:
    def __init__(self, tesseract_cmd: str = "", language: str = "eng") -> None:
        self.language = language
        self.available = False
        try:
            import pytesseract

            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            pytesseract.get_tesseract_version()
            self._pytesseract = pytesseract
            self.available = True
        except Exception:
            LOGGER.warning("Tesseract OCR is unavailable; OCR fields will be unknown")
            self._pytesseract = None

    def read_text(self, image_bgr: np.ndarray, whitelist: str | None = None) -> OcrResult:
        if not self.available or self._pytesseract is None:
            return OcrResult("", 0.0)
        prepared = self._prepare(image_bgr)
        config = "--psm 7"
        if whitelist:
            config += f" -c tessedit_char_whitelist={whitelist}"
        try:
            data = self._pytesseract.image_to_data(
                prepared,
                lang=self.language,
                config=config,
                output_type=self._pytesseract.Output.DICT,
            )
        except Exception:
            LOGGER.exception("OCR failed")
            return OcrResult("", 0.0)

        words: list[str] = []
        confidences: list[float] = []
        for text, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
            clean = str(text).strip()
            try:
                score = float(conf)
            except ValueError:
                score = -1.0
            if clean:
                words.append(clean)
            if score >= 0:
                confidences.append(score / 100.0)
        return OcrResult(" ".join(words), sum(confidences) / len(confidences) if confidences else 0.0)

    @staticmethod
    def _prepare(image_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]


def parse_int(result: OcrResult, min_value: int = 0, max_value: int = 999) -> tuple[int | None, float]:
    match = re.search(r"\d+", result.text.replace("O", "0"))
    if not match:
        return None, 0.0
    value = int(match.group(0))
    if min_value <= value <= max_value:
        return value, result.confidence
    return None, result.confidence * 0.4


def parse_stage(result: OcrResult) -> tuple[str | None, float]:
    match = re.search(r"(\d+)\s*[-:]\s*(\d+)", result.text)
    if match:
        return f"{match.group(1)}-{match.group(2)}", result.confidence
    return None, result.confidence * 0.5
